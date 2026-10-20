"""Python callback failures must reach callers and invalidate the connection."""

from collections.abc import Callable
from typing import NoReturn

import pytest

from ngh2 import Configuration, Connection, ConnectionStateError, Role

REQUEST_HEADERS = [
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/"),
]


def fail_allocation(*args: object) -> NoReturn:
    raise MemoryError("cannot allocate a protocol result")


def assert_connection_failed(connection: Connection) -> None:
    assert connection.queued_body_size() == 0
    with pytest.raises(ConnectionStateError, match="no longer usable"):
        connection.receive_data(b"")
    with pytest.raises(ConnectionStateError, match="no longer usable"):
        connection.data_to_send()
    with pytest.raises(ConnectionStateError, match="no longer usable"):
        connection.ping()


@pytest.fixture
def pending_upload(
    handshake: Callable[[Connection, Connection], None],
) -> tuple[Connection, Connection, int]:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    client.send_data(stream_id, b"still queued")
    return client, server, stream_id


def test_received_event_allocation_failure_invalidates_connection(
    pending_upload: tuple[Connection, Connection, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, server, _ = pending_upload
    server.ping()
    incoming = server.data_to_send()
    monkeypatch.setattr("ngh2._core.PingReceived", fail_allocation)

    with pytest.raises(MemoryError, match="cannot allocate a protocol result"):
        client.receive_data(incoming)

    assert_connection_failed(client)


@pytest.mark.parametrize("local", [False, True], ids=["peer-reset", "local-reset"])
def test_stream_close_allocation_failure_invalidates_connection(
    pending_upload: tuple[Connection, Connection, int],
    monkeypatch: pytest.MonkeyPatch,
    local: bool,
) -> None:
    client, server, stream_id = pending_upload
    if local:
        client.reset_stream(stream_id)
    else:
        server.reset_stream(stream_id)
        incoming = server.data_to_send()
    monkeypatch.setattr("ngh2._core.StreamClosed", fail_allocation)

    with pytest.raises(MemoryError, match="cannot allocate a protocol result"):
        if local:
            client.data_to_send()
        else:
            client.receive_data(incoming)

    assert_connection_failed(client)


def test_delayed_send_error_allocation_failure_invalidates_connection(
    handshake: Callable[[Connection, Connection], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Connection(Role.CLIENT, Configuration(max_send_header_block_length=64))
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request([*REQUEST_HEADERS, (b"x-large", b"x" * 200)])
    client.send_data(stream_id, b"still queued")
    monkeypatch.setattr("ngh2._core.StreamProtocolError", fail_allocation)

    with pytest.raises(MemoryError, match="cannot allocate a protocol result"):
        client.data_to_send()

    assert_connection_failed(client)
