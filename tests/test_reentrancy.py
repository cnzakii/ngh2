import subprocess
import sys
from collections.abc import Callable, Iterator
from typing import cast

import pytest

from ngh2 import (
    Configuration,
    Connection,
    ConnectionProtocolError,
    ConnectionStateError,
    DenialOfServiceError,
    NeverIndexedHeader,
    Priority,
    Role,
)

REQUEST_HEADERS = [
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/"),
]


def fail_connection(connection: Connection) -> None:
    """Invalidate a server whose client preface has not arrived yet."""
    with pytest.raises(ConnectionProtocolError):
        connection.receive_data(b"x" * 24)


@pytest.fixture
def server() -> Connection:
    connection = Connection(Role.SERVER, Configuration(auto_window_update=False))
    connection.initiate_connection()
    return connection


@pytest.mark.parametrize(
    "invoke",
    [
        lambda connection, value: connection.data_to_send(value),
        lambda connection, value: connection.send_data(value, b"body"),
        lambda connection, value: connection.reset_stream(value),
        lambda connection, value: connection.reset_stream(1, value),
        lambda connection, value: connection.send_goaway(value),
        lambda connection, value: connection.send_goaway(last_stream_id=value),
        lambda connection, value: connection.terminate_connection(value),
        lambda connection, value: connection.terminate_connection(last_stream_id=value),
        lambda connection, value: connection.set_local_window_size(value),
        lambda connection, value: connection.set_local_window_size(
            65_535, stream_id=value
        ),
        lambda connection, value: connection.set_stream_priority(value, Priority()),
        lambda connection, value: connection.set_stream_priority(
            1, Priority(urgency=value)
        ),
        lambda connection, value: connection.get_stream_priority(value),
        lambda connection, value: connection.send_alt_svc(
            b'h3=":443"', stream_id=value
        ),
        lambda connection, value: connection.stream_remote_window_size(value),
        lambda connection, value: connection.stream_local_window_size(value),
        lambda connection, value: connection.acknowledge_received_data(value, 1),
        lambda connection, value: connection.acknowledge_received_data(0, value),
    ],
    ids=[
        "output-budget",
        "body-stream",
        "reset-stream",
        "reset-code",
        "goaway-code",
        "goaway-stream",
        "terminate-code",
        "terminate-stream",
        "window-size",
        "window-stream",
        "priority-stream",
        "priority-urgency",
        "get-priority",
        "altsvc-stream",
        "remote-window",
        "local-window",
        "acknowledge-amount",
        "acknowledge-stream",
    ],
)
def test_integer_conversion_cannot_leave_a_stale_native_session(
    server: Connection,
    invoke: Callable[[Connection, int], object],
) -> None:
    class StreamID:
        def __index__(self) -> int:
            fail_connection(server)
            return 1

    with pytest.raises(ConnectionStateError, match="no longer usable"):
        invoke(server, cast(int, StreamID()))


def test_origin_iterator_cannot_leave_a_stale_native_session(
    server: Connection,
) -> None:
    def origins() -> Iterator[bytes]:
        fail_connection(server)
        yield b"https://example.test"

    with pytest.raises(ConnectionStateError, match="no longer usable"):
        server.send_origins(origins())


def test_settings_mapping_cannot_leave_a_stale_native_session(
    server: Connection,
) -> None:
    class Settings(dict[int, int]):
        def items(self):
            fail_connection(server)
            return super().items()

    with pytest.raises(ConnectionStateError, match="no longer usable"):
        server.update_settings(Settings())


def test_priority_flag_conversion_cannot_leave_a_stale_native_session() -> None:
    server = Connection(Role.SERVER)
    server.initiate_upgrade(b"", local_settings={9: 1})

    class IgnoreSignal:
        def __bool__(self) -> bool:
            fail_connection(server)
            return True

        def __int__(self) -> int:
            return int(bool(self))

    with pytest.raises(ConnectionStateError, match="no longer usable"):
        server.set_stream_priority(
            1, Priority(), ignore_client_signal=cast(bool, IgnoreSignal())
        )


def test_body_conversion_cannot_leave_a_stale_native_session() -> None:
    server = Connection(Role.SERVER)
    server.initiate_upgrade(b"")
    server.send_response(1, [(b":status", b"200")])

    class Body(bytearray):
        def __bytes__(self) -> bytes:
            fail_connection(server)
            return b"body"

    with pytest.raises(ConnectionStateError, match="no longer usable"):
        server.send_data(1, Body(b"body"))


@pytest.mark.parametrize(
    "method",
    [
        "send_request",
        "send_response",
        "send_informational_response",
        "send_push_promise",
        "send_trailers",
    ],
)
@pytest.mark.parametrize("custom_pair", [False, True])
def test_header_producers_cannot_submit_after_failing_the_connection(
    method: str,
    custom_pair: bool,
    handshake: Callable[[Connection, Connection], None],
) -> None:
    config = Configuration(max_outbound_ack=1)
    client, server = Connection(Role.CLIENT, config), Connection(Role.SERVER, config)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    if method == "send_trailers":
        server.send_response(stream_id, [(b":status", b"200")])
    target, peer = (client, server) if method == "send_request" else (server, client)
    peer.ping(b"first---")
    peer.ping(b"second--")
    flood = peer.data_to_send()

    def fail_target():
        with pytest.raises(DenialOfServiceError):
            target.receive_data(flood)

    def headers():
        fail_target()
        yield b"x-test", b"value"

    class Pair:
        def __iter__(self):
            fail_target()
            yield b"x-test"
            yield b"value"

    fields = [Pair()] if custom_pair else headers()
    arguments = (fields,) if method == "send_request" else (stream_id, fields)
    with pytest.raises(ConnectionStateError, match="no longer usable"):
        getattr(target, method)(*arguments)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="Python buffer protocol")
def test_buffer_acquisition_cannot_enter_a_failed_native_session() -> None:
    server = Connection(Role.SERVER)
    server.initiate_connection()

    class Buffer:
        def __buffer__(self, flags):
            with pytest.raises(ConnectionProtocolError):
                server.receive_data(b"x" * 24)
            return memoryview(b"")

    with pytest.raises(ConnectionStateError, match="no longer usable"):
        server.receive_data(cast(memoryview, Buffer()))


def check_trailer_finalizer_reentrancy(position: str, never_indexed: bool) -> None:
    config = Configuration(max_outbound_ack=1)
    client, server = Connection(Role.CLIENT, config), Connection(Role.SERVER, config)
    client.initiate_connection()
    server.initiate_connection()
    for _ in range(2):
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
    client.events()
    server.events()
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    server.ping(b"first---")
    server.ping(b"second--")
    flood = server.data_to_send()
    invalidated = []

    class Field(bytes):
        def __del__(self):
            try:
                client.receive_data(flood)
            except DenialOfServiceError:
                invalidated.append(True)

    def headers():
        name = Field(b"x-test") if position == "name" else b"x-test"
        value = Field(b"done") if position == "value" else b"done"
        return [NeverIndexedHeader(name, value) if never_indexed else (name, value)]

    # Drop producer references before output so only queued fields can retain it.
    with pytest.raises(ConnectionStateError, match="no longer usable"):
        client.send_trailers(stream_id, headers())
        client.data_to_send()
    assert invalidated == [True]


@pytest.mark.parametrize("position", ["name", "value"])
@pytest.mark.parametrize("never_indexed", [False, True])
def test_trailer_finalizers_cannot_reenter_native_output(
    position: str, never_indexed: bool
) -> None:
    # A native crash must fail this test without taking down the test runner.
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "faulthandler",
            __file__,
            position,
            str(int(never_indexed)),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    check_trailer_finalizer_reentrancy(sys.argv[1], bool(int(sys.argv[2])))
