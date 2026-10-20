from collections.abc import Callable
from typing import cast

import pytest

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


@pytest.mark.parametrize(
    "convert",
    [bytes, bytearray, memoryview],
    ids=["bytes", "bytearray", "memoryview"],
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


def test_origin_rejects_an_object_spoofing_the_bytes_class() -> None:
    class PretendBytes:
        @property
        def __class__(self):
            return bytes

    server = Connection(Role.SERVER)
    server.initiate_connection()
    with pytest.raises(TypeError, match="each origin must be bytes"):
        server.send_origins([cast(bytes, PretendBytes())])


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
