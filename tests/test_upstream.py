"""HTTP/2 rules the pinned libnghttp2 v1.71.0 does not follow.

ngh2 leaves these to libnghttp2 rather than working around them. Each test
asserts the RFC behavior and is a strict expected failure, so a dependency
update that fixes one fails here until its marker is removed.
"""

from collections.abc import Callable

import pytest

from ngh2 import (
    Connection,
    ConnectionClosed,
    ErrorCode,
    OriginReceived,
    Priority,
    PriorityUpdateReceived,
    Role,
    Setting,
)

REQUEST = [
    (b":method", b"GET"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/"),
]
PRIORITIES = {Setting.NO_RFC7540_PRIORITIES: 1}


def upstream(reason: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)


def handshake(
    settings: dict[Setting, int] | None = None,
) -> tuple[Connection, Connection]:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    client.initiate_connection(settings)
    server.initiate_connection(settings)
    for _ in range(2):
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
    client.events()
    server.events()
    return client, server


def frame(frame_type: int, flags: int, payload: bytes) -> bytes:
    """Serialize one frame on stream 0."""
    return (
        len(payload).to_bytes(3, "big")
        + bytes([frame_type, flags, 0, 0, 0, 0])
        + payload
    )


def closed_with(connection: Connection) -> ErrorCode | int | None:
    connection.data_to_send()
    closed = [
        item for item in connection.events() if isinstance(item, ConnectionClosed)
    ]
    return closed[0].error_code if closed else None


def goaway_stream_ids(data: bytes) -> list[int]:
    stream_ids = []
    while data:
        length = int.from_bytes(data[:3], "big")
        if data[3] == 0x7:
            stream_ids.append(int.from_bytes(data[9:13], "big"))
        data = data[9 + length :]
    return stream_ids


def rejects(call: Callable[[], object]) -> bool:
    try:
        call()
    except ValueError:
        return True
    return False


@upstream("PRIORITY on stream 0 is ignored; RFC 9113 section 6.3")
def test_priority_frame_on_stream_zero_is_a_connection_error() -> None:
    _, server = handshake()

    server.receive_data(frame(0x2, 0, bytes(5)))

    assert closed_with(server) == ErrorCode.PROTOCOL_ERROR


@upstream("PRIORITY_UPDATE for stream 0 is accepted; RFC 9218 section 7.1")
def test_priority_update_for_stream_zero_is_a_connection_error() -> None:
    _, server = handshake(PRIORITIES)

    server.receive_data(frame(0x10, 0, bytes(4) + b"u=1"))

    assert not any(isinstance(item, PriorityUpdateReceived) for item in server.events())
    assert closed_with(server) == ErrorCode.PROTOCOL_ERROR


@upstream("queued GOAWAY frames can raise last_stream_id; RFC 9113 section 6.8")
def test_goaway_never_raises_the_last_stream_id() -> None:
    client, server = handshake()
    for _ in range(2):
        client.send_request(REQUEST, end_stream=True)
    server.receive_data(client.data_to_send())
    server.events()

    server.send_goaway(last_stream_id=1)
    server.send_goaway(last_stream_id=3)

    assert goaway_stream_ids(server.data_to_send()) == [1, 1]


@upstream("a server may queue ENABLE_PUSH=1; RFC 9113 section 6.5.2")
def test_server_cannot_enable_push() -> None:
    _, server = handshake()

    assert rejects(lambda: server.update_settings({Setting.ENABLE_PUSH: 1}))


@upstream("extended CONNECT can be withdrawn; RFC 8441 section 3")
def test_extended_connect_cannot_be_withdrawn() -> None:
    _, server = handshake({Setting.ENABLE_CONNECT_PROTOCOL: 1})

    assert rejects(
        lambda: server.update_settings({Setting.ENABLE_CONNECT_PROTOCOL: 0}),
    )


@upstream("ORIGIN flag handling is inverted; RFC 8336 section 2.2")
@pytest.mark.parametrize(("flags", "processed"), [(0x01, False), (0x10, True)])
def test_origin_flags(flags: int, processed: bool) -> None:
    client, _ = handshake()
    origin = b"https://example.test"

    client.receive_data(frame(0xC, flags, len(origin).to_bytes(2, "big") + origin))

    received = any(isinstance(item, OriginReceived) for item in client.events())
    assert received is processed


@upstream("one invalid priority parameter discards the field; RFC 9218 section 4")
@pytest.mark.parametrize(
    ("field_value", "priority"),
    [(b"u=1, i=42", Priority(1)), (b"u=99, i", Priority(3, True))],
)
def test_invalid_priority_parameters_are_ignored_individually(
    field_value: bytes,
    priority: Priority,
) -> None:
    client, server = handshake(PRIORITIES)
    stream_id = client.send_request(
        [*REQUEST, (b"priority", field_value)], end_stream=True
    )
    server.receive_data(client.data_to_send())
    server.events()

    assert server.get_stream_priority(stream_id) == priority
