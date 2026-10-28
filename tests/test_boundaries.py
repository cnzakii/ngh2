from collections.abc import Callable
from enum import Enum
from typing import cast

import pytest

import ngh2
from ngh2 import (
    Connection,
    DataReceived,
    OriginReceived,
    RequestReceived,
    Role,
)

REQUEST_HEADERS = [
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/upload"),
]


class PretendBytes:
    @property
    def __class__(self):
        return bytes


class BytesSubclass(bytes):
    def __len__(self):
        raise AssertionError("length must use the underlying bytes")

    def __bool__(self):
        raise AssertionError("emptiness must use the underlying bytes")

    def __bytes__(self):
        raise AssertionError("conversion must use the underlying bytes")


class BytesEnum(bytes, Enum):
    VALUE = b"12345678"
    EMPTY = b""


EVENT_BYTES = [
    pytest.param(lambda value: ngh2.DataReceived(1, value, False), "data", id="data"),
    pytest.param(ngh2.PingReceived, "opaque_data", id="ping"),
    pytest.param(ngh2.PingAcknowledged, "opaque_data", id="ping-ack"),
    pytest.param(
        lambda value: ngh2.GoAwayReceived(1, 0, value), "debug_data", id="goaway"
    ),
    pytest.param(
        lambda value: ngh2.ConnectionClosed(0, value), "debug_data", id="closed"
    ),
    pytest.param(
        lambda value: ngh2.AltSvcReceived(0, value, b""), "origin", id="altsvc-origin"
    ),
    pytest.param(
        lambda value: ngh2.AltSvcReceived(0, b"", value),
        "field_value",
        id="altsvc-field",
    ),
    pytest.param(
        lambda value: ngh2.PriorityUpdateReceived(1, value),
        "field_value",
        id="priority",
    ),
]


@pytest.mark.parametrize(("make_event", "field"), EVENT_BYTES)
@pytest.mark.parametrize("byte_type", [bytes, BytesSubclass, BytesEnum])
def test_event_bytes_accept_subclasses(
    make_event: Callable[[bytes], ngh2.Event],
    field: str,
    byte_type: Callable[[bytes], bytes],
) -> None:
    value = byte_type(b"12345678")
    event = make_event(value)
    assert getattr(event, field) is value
    with pytest.raises(AttributeError):
        setattr(event, field, b"changed")


@pytest.mark.parametrize(("make_event", "field"), EVENT_BYTES)
@pytest.mark.parametrize(
    "invalid",
    [None, "text", 1, bytearray(b"bytes"), memoryview(b"bytes"), PretendBytes()],
    ids=["none", "str", "int", "bytearray", "memoryview", "spoofed-bytes"],
)
def test_event_bytes_reject_non_bytes(
    make_event: Callable[[bytes], ngh2.Event], field: str, invalid: object
) -> None:
    with pytest.raises(TypeError, match=f"{field} must be bytes"):
        make_event(cast(bytes, invalid))


def test_event_header_and_origin_containers_accept_bytes_subclasses() -> None:
    value = BytesEnum.VALUE
    headers = (ngh2.NeverIndexedHeader(value, value),)
    events = (
        ngh2.RequestReceived(1, headers, True),
        ngh2.ResponseReceived(1, headers, True),
        ngh2.InformationalResponseReceived(1, headers),
        ngh2.TrailersReceived(1, headers),
        ngh2.PushedStreamReceived(1, 2, headers),
    )
    assert all(event.headers == headers for event in events)
    assert ngh2.OriginReceived((value,)).origins == (value,)


@pytest.mark.parametrize(
    "convert",
    [bytes, bytearray, memoryview, BytesSubclass],
    ids=["bytes", "bytearray", "memoryview", "bytes-subclass"],
)
def test_receive_data_accepts_contiguous_buffers(
    convert: Callable[[bytes], bytes | bytearray | memoryview],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()

    server.receive_data(convert(client.data_to_send()))

    assert server.events()


def test_send_data_takes_ownership_of_mutable_input(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    body = bytearray(b"original")

    client.send_data(stream_id, body, end_stream=True)
    body[:] = b"modified"
    server.receive_data(client.data_to_send())

    received = next(
        event for event in server.events() if isinstance(event, DataReceived)
    )
    assert received.data == b"original"


@pytest.mark.parametrize("byte_type", [BytesSubclass, BytesEnum])
@pytest.mark.parametrize("payload", [b"12345678", b""])
@pytest.mark.parametrize("amount", [None, 1], ids=["unlimited", "one-byte"])
def test_send_data_accepts_bytes_subclasses(
    byte_type: Callable[[bytes], bytes],
    payload: bytes,
    amount: int | None,
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()

    client.send_data(stream_id, byte_type(payload), end_stream=True)
    assert client.queued_body_size(stream_id) == len(payload)
    while data := client.data_to_send(amount):
        server.receive_data(data)

    received = [e for e in server.events() if isinstance(e, DataReceived)]
    assert b"".join(e.data for e in received) == payload
    assert received[-1].end_stream
    assert client.queued_body_size(stream_id) == 0


@pytest.mark.parametrize("byte_type", [BytesSubclass, BytesEnum])
@pytest.mark.parametrize("role", [Role.CLIENT, Role.SERVER])
def test_upgrade_and_goaway_accept_empty_bytes_subclasses(
    byte_type: Callable[[bytes], bytes], role: Role
) -> None:
    connection = Connection(role)
    connection.initiate_upgrade(byte_type(b""))
    connection.send_goaway(debug_data=byte_type(b""))
    assert connection.data_to_send()


def test_origin_uses_the_actual_bytes_buffer_length(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    class Origin(bytes):
        def __len__(self):
            return super().__len__() + 32

    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    handshake(client, server)
    server.send_origins([Origin(b"https://example.test")])
    client.receive_data(server.data_to_send())

    origins = next(e for e in client.events() if isinstance(e, OriginReceived))
    assert origins.origins == (b"https://example.test",)


@pytest.mark.parametrize(
    "invalid",
    [None, "text", 1, bytearray(b"bytes"), memoryview(b"bytes"), PretendBytes()],
    ids=["none", "str", "int", "bytearray", "memoryview", "spoofed-bytes"],
)
@pytest.mark.parametrize(
    "operation",
    [
        "origins",
        "alt-svc-field",
        "alt-svc-origin",
        "priority-update",
        "ping",
        "goaway",
        "upgrade",
    ],
)
def test_byte_parameters_reject_non_bytes(operation: str, invalid: object) -> None:
    role = Role.CLIENT if operation == "priority-update" else Role.SERVER
    connection = Connection(role)
    if operation != "upgrade":
        connection.initiate_connection()
    value = cast(bytes, invalid)

    with pytest.raises(TypeError, match="must be bytes"):
        if operation == "origins":
            connection.send_origins([value])
        elif operation == "alt-svc-field":
            connection.send_alt_svc(value, origin=b"https://example.test")
        elif operation == "alt-svc-origin":
            connection.send_alt_svc(b'h3=":443"', origin=value)
        elif operation == "ping":
            connection.send_ping(value)
        elif operation == "goaway":
            connection.send_goaway(debug_data=value)
        elif operation == "upgrade":
            connection.initiate_upgrade(value)
        else:
            connection.send_priority_update(1, value)


@pytest.mark.parametrize(
    "fragment_size",
    [7, 1],
    ids=["small-chunks", "one-byte-chunks"],
)
def test_fragmented_headers_and_data_preserve_events(fragment_size: int) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    server.receive_data(client.data_to_send())
    client.events()
    server.events()

    large_headers = REQUEST_HEADERS + [
        (f"x-field-{index}".encode(), bytes([65 + index % 26]) * 1_000)
        for index in range(32)
    ]
    stream_id = client.send_request(large_headers)
    client.send_data(stream_id, b"payload", end_stream=True)
    wire_data = client.data_to_send()

    frame_types = []
    offset = 0
    while offset < len(wire_data):
        frame_length = int.from_bytes(
            wire_data[offset : offset + 3],
            byteorder="big",
        )
        frame_types.append(wire_data[offset + 3])
        offset += 9 + frame_length

    assert 0x09 in frame_types
    for offset in range(0, len(wire_data), fragment_size):
        server.receive_data(wire_data[offset : offset + fragment_size])

    events = server.events()
    request = next(event for event in events if isinstance(event, RequestReceived))
    data = next(event for event in events if isinstance(event, DataReceived))
    assert request.headers == tuple(large_headers)
    assert data.data == b"payload"
    assert data.end_stream


@pytest.mark.parametrize("sign", [1, -1], ids=["positive", "negative"])
@pytest.mark.parametrize(
    ("invoke", "message"),
    [
        (lambda c, v: c.send_data(v, b""), "stream_id is out of range"),
        (lambda c, v: c.reset_stream(1, v), "error_code is out of range"),
        (lambda c, v: c.send_goaway(last_stream_id=v), "last_stream_id is out of"),
        (lambda c, v: c.local_window_size(v), "stream_id is out of range"),
    ],
    ids=["stream-id", "uint32", "uint31", "window-stream"],
)
def test_integers_beyond_64_bits_are_out_of_range(
    invoke: Callable[[Connection, int], object],
    message: str,
    sign: int,
) -> None:
    connection = Connection(Role.CLIENT)
    connection.initiate_connection()

    with pytest.raises(ValueError, match=message):
        invoke(connection, sign << 70)


@pytest.mark.parametrize(
    ("amount", "message"),
    [(1 << 70, "too large"), (-(1 << 70), "non-negative"), (-1, "non-negative")],
)
def test_size_arguments_beyond_64_bits_are_rejected(amount: int, message: str) -> None:
    connection = Connection(Role.CLIENT)
    connection.initiate_connection()

    with pytest.raises(ValueError, match=message):
        connection.data_to_send(amount)
