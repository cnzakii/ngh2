import tracemalloc
from collections.abc import Callable
from itertools import cycle

import pytest

from ngh2 import (
    Configuration,
    Connection,
    DataReceived,
    ErrorCode,
    RequestReceived,
    Role,
    StreamClosed,
    StreamReset,
    TrailersReceived,
)

REQUEST = (
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/"),
)


def test_returned_output_does_not_leave_a_staging_copy_in_the_connection(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST)
    server.receive_data(client.data_to_send())
    server.events()
    server.set_local_window_size(2 * 1024 * 1024)
    server.set_local_window_size(2 * 1024 * 1024, stream_id=stream_id)
    client.receive_data(server.data_to_send())
    payload = b"x" * (1024 * 1024)
    client.send_data(stream_id, payload, end_stream=True)

    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    try:
        before, _ = tracemalloc.get_traced_memory()
        output = client.data_to_send()
        retained, _ = tracemalloc.get_traced_memory()
        retained -= before
    finally:
        if not already_tracing:
            tracemalloc.stop()

    # Allow small bookkeeping allocations, but not another copy of the body.
    assert retained < len(output) + 64 * 1024
    server.receive_data(output)
    received = b"".join(
        event.data for event in server.events() if isinstance(event, DataReceived)
    )
    assert received == payload


@pytest.mark.parametrize("amount", [None, 1], ids=["unlimited", "one-byte"])
def test_body_output_resumes_each_time_more_data_is_queued(
    handshake: Callable[[Connection, Connection], None],
    amount: int | None,
) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST)
    server.receive_data(client.data_to_send())
    server.events()

    for chunk, end_stream in ((b"first", False), (b"second", True)):
        assert client.data_to_send(amount) == b""
        client.send_data(stream_id, chunk, end_stream=end_stream)
        while output := client.data_to_send(amount):
            server.receive_data(output)

        received = [
            (event.data, event.end_stream)
            for event in server.events()
            if isinstance(event, DataReceived)
        ]
        assert received == [(chunk, end_stream)]
        assert client.queued_body_size(stream_id) == 0

    assert client.data_to_send(amount) == b""


@pytest.mark.parametrize(
    "limits",
    [(None,), (1,), (4096,), (1, None, 7, 4096)],
    ids=["unlimited", "one-byte", "bounded", "mixed"],
)
@pytest.mark.parametrize("trailers", [False, True], ids=["end-stream", "trailers"])
@pytest.mark.parametrize("manual", [False, True], ids=["auto-window", "manual-window"])
def test_body_output_survives_limits_and_window_resumption(
    handshake: Callable[[Connection, Connection], None],
    limits: tuple[int | None, ...],
    trailers: bool,
    manual: bool,
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER, Configuration(auto_window_update=not manual))
    handshake(client, server)
    stream_id = client.send_request(REQUEST)
    server.receive_data(client.data_to_send())
    assert any(isinstance(e, RequestReceived) for e in server.events())

    payload = bytes(range(251)) * 399
    for offset in range(0, len(payload), 997):
        end = offset + 997 >= len(payload)
        client.send_data(
            stream_id,
            payload[offset : offset + 997],
            end_stream=end and not trailers,
        )
    if trailers:
        client.send_trailers(stream_id, iter([(b"x-result", b"complete")]))

    received = bytearray()
    ended = False
    budgets = cycle(limits)
    for _ in range(len(payload) + 4096):
        amount = next(budgets)
        output = client.data_to_send(amount)
        assert output
        if amount is not None:
            assert len(output) <= amount
        server.receive_data(output)
        for event in server.events():
            if isinstance(event, DataReceived):
                received.extend(event.data)
                if manual:
                    server.acknowledge_received_data(len(event.data), stream_id)
                if event.end_stream:
                    assert not trailers
                    ended = True
            elif isinstance(event, TrailersReceived):
                assert trailers
                assert event.headers == ((b"x-result", b"complete"),)
                ended = True
        if updates := server.data_to_send():
            client.receive_data(updates)
        if ended:
            break
    assert ended
    assert received == payload
    assert client.queued_body_size() == 0
    assert client.data_to_send() == b""

    server.send_response(stream_id, [(b":status", b"204")], end_stream=True)
    client.receive_data(server.data_to_send())
    for connection in (client, server):
        closed = [e for e in connection.events() if isinstance(e, StreamClosed)]
        assert len(closed) == 1
        assert closed[0].error_code == ErrorCode.NO_ERROR
        assert closed[0].local_error is None


def test_reset_after_partial_data_output_preserves_the_prepared_frame(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST)
    server.receive_data(client.data_to_send())
    server.events()
    client.send_data(stream_id, b"abc", end_stream=True)

    first_byte = client.data_to_send(1)
    assert len(first_byte) == 1
    assert client.queued_body_size(stream_id) == 0
    client.reset_stream(stream_id)
    server.receive_data(first_byte + client.data_to_send())

    events = server.events()
    data = next(e for e in events if isinstance(e, DataReceived))
    reset = next(e for e in events if isinstance(e, StreamReset))
    assert data.data == b"abc"
    assert reset.error_code == ErrorCode.CANCEL


def test_multiplexed_bodies_resume_without_mixing_stream_buffers(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    handshake(client, server)
    payloads = {}
    for value in (b"a", b"b", b"c"):
        stream_id = client.send_request(REQUEST)
        payloads[stream_id] = value * 70000
        client.send_data(stream_id, payloads[stream_id], end_stream=True)
    received = {stream_id: bytearray() for stream_id in payloads}
    ended = set()
    for _ in range(20):
        output = client.data_to_send()
        assert output
        server.receive_data(output)
        for event in server.events():
            if isinstance(event, DataReceived):
                received[event.stream_id].extend(event.data)
                if event.end_stream:
                    ended.add(event.stream_id)
        client.receive_data(server.data_to_send())
        if ended == payloads.keys():
            break
    assert ended == payloads.keys()
    assert received == payloads
    assert client.queued_body_size() == 0
