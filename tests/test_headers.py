from collections.abc import Iterable, Iterator, Sequence
from typing import cast, overload

import pytest

from ngh2 import (
    Connection,
    Header,
    InformationalResponseReceived,
    NeverIndexedHeader,
    PushedStreamReceived,
    RequestReceived,
    ResponseReceived,
    Role,
    TrailersReceived,
)

REQUEST = (
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/"),
)
FIELDS = (
    (b"x-first", b"A" * 128),
    (b"x-repeat", b"first"),
    (b"x-repeat", b"second"),
    NeverIndexedHeader(b"x-secret", b"B" * 128),
)


class EncodedHeaders(Sequence[Header]):
    """Create fresh field bytes on every access instead of storing them."""

    def __init__(self, fields: Sequence[Header]) -> None:
        self.fields = fields

    def __len__(self) -> int:
        return len(self.fields)

    @overload
    def __getitem__(self, index: int) -> Header: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[Header]: ...

    def __getitem__(self, index: int | slice) -> Header | Sequence[Header]:
        if isinstance(index, slice):
            return [self[position] for position in range(*index.indices(len(self)))]
        field = self.fields[index]
        name, value = field
        name, value = name.decode().encode(), value.decode().encode()
        if isinstance(field, NeverIndexedHeader):
            return NeverIndexedHeader(name, value)
        return name, value


class RegeneratedHeader(tuple[bytes, bytes]):
    def __iter__(self) -> Iterator[bytes]:
        for value in tuple.__iter__(self):
            yield value.decode().encode()


class RegeneratedNeverIndexedHeader(NeverIndexedHeader):
    def __iter__(self) -> Iterator[bytes]:
        for value in tuple.__iter__(self):
            yield value.decode().encode()


class HeaderView(tuple[bytes, bytes]):
    current: Header = (b"", b"")

    def __iter__(self) -> Iterator[bytes]:
        yield from self.current


def reusing_headers(fields: Sequence[Header]) -> Iterator[Header]:
    view = HeaderView((b"", b""))
    for field in fields:
        if isinstance(field, NeverIndexedHeader):
            yield field
        else:
            view.current = field
            yield view


@pytest.mark.parametrize(
    "source_kind", ["sequence", "generator", "custom-pairs", "reused-view"]
)
@pytest.mark.parametrize(
    "operation", ["request", "response", "informational", "push", "trailers"]
)
def test_header_bytes_survive_submission(operation: str, source_kind: str) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()
    for _ in range(2):
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
    client.events()
    server.events()

    if operation in ("request", "push"):
        expected = REQUEST + FIELDS
    elif operation == "response":
        expected = ((b":status", b"200"), *FIELDS)
    elif operation == "informational":
        expected = ((b":status", b"103"), *FIELDS)
    else:
        expected = FIELDS

    if source_kind == "sequence":
        headers = EncodedHeaders(expected)
    elif source_kind == "generator":
        headers = iter(EncodedHeaders(expected))
    elif source_kind == "reused-view":
        headers = reusing_headers(expected)
    else:
        headers = [
            RegeneratedNeverIndexedHeader(*field)
            if isinstance(field, NeverIndexedHeader)
            else RegeneratedHeader(field)
            for field in expected
        ]

    if operation == "request":
        client.send_request(headers, end_stream=True)
        source, destination = client, server
        event_type = RequestReceived
    elif operation == "trailers":
        stream_id = client.send_request(REQUEST)
        client.send_data(stream_id, b"body")
        client.send_trailers(stream_id, headers)
        source, destination = client, server
        event_type = TrailersReceived
    else:
        stream_id = client.send_request(REQUEST, end_stream=True)
        server.receive_data(client.data_to_send())
        server.events()
        if operation == "response":
            server.send_response(stream_id, headers, end_stream=True)
            event_type = ResponseReceived
        elif operation == "informational":
            server.send_informational_response(stream_id, headers)
            server.send_response(stream_id, [(b":status", b"204")], end_stream=True)
            event_type = InformationalResponseReceived
        else:
            server.send_push_promise(stream_id, headers)
            event_type = PushedStreamReceived
        source, destination = server, client

    destination.receive_data(source.data_to_send())
    event = next(e for e in destination.events() if isinstance(e, event_type))
    assert event.headers == expected
    assert isinstance(event.headers[-1], NeverIndexedHeader)


def test_trailers_snapshot_mutable_fields_before_deferred_submission() -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    server.receive_data(client.data_to_send())
    client.events()
    server.events()
    stream_id = client.send_request(REQUEST)
    server.receive_data(client.data_to_send())
    server.events()

    field = [b"x-result", b"original"]
    client.send_trailers(stream_id, cast(Iterable[Header], iter([field])))
    field[1] = b"modified"
    server.receive_data(client.data_to_send())

    event = next(e for e in server.events() if isinstance(e, TrailersReceived))
    assert event.headers == ((b"x-result", b"original"),)


@pytest.mark.parametrize("field", [(None, b"value"), (b"x-name", None)])
@pytest.mark.parametrize("operation", ["request", "trailers"])
def test_none_header_fields_fail_before_submission(
    field: tuple[bytes | None, bytes | None],
    operation: str,
) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    client.initiate_connection()
    server.initiate_connection()
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    server.receive_data(client.data_to_send())
    server.events()
    headers = [cast(Header, field)]

    if operation == "request":
        with pytest.raises(TypeError, match="pair of bytes"):
            client.send_request(headers)
        assert client.next_stream_id == 1
        stream_id = client.send_request(REQUEST)
    else:
        stream_id = client.send_request(REQUEST)
        with pytest.raises(TypeError, match="pair of bytes"):
            client.send_trailers(stream_id, headers)
    client.send_data(stream_id, b"still usable", end_stream=True)
    server.receive_data(client.data_to_send())
    assert any(isinstance(e, RequestReceived) for e in server.events())
