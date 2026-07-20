import pytest

from ngh2 import (
    Configuration,
    Connection,
    ConnectionClosingError,
    DataReceived,
    ErrorCode,
    GoAwayReceived,
    Role,
    StreamClosed,
    StreamReset,
    WindowUpdated,
)

REQUEST_HEADERS = [
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/"),
]


def handshake(client: Connection, server: Connection) -> None:
    """Exchange the initial SETTINGS frames and acknowledgements."""
    client.initiate_connection()
    server.initiate_connection()
    for source, destination in (
        (client, server),
        (server, client),
        (client, server),
        (server, client),
    ):
        if data := source.data_to_send():
            destination.receive_data(data)
    client.events()
    server.events()


def test_end_stream_emits_an_empty_terminal_data_event() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)

    client.end_stream(stream_id)
    server.receive_data(client.data_to_send())

    data = next(event for event in server.events() if isinstance(event, DataReceived))
    assert data.data == b""
    assert data.end_stream


def test_normal_completion_closes_the_stream_on_both_peers() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS, end_stream=True)
    server.receive_data(client.data_to_send())
    server.events()

    server.send_response(stream_id, [(b":status", b"204")], end_stream=True)
    client.receive_data(server.data_to_send())

    client_closed = next(
        event for event in client.events() if isinstance(event, StreamClosed)
    )
    server_closed = next(
        event for event in server.events() if isinstance(event, StreamClosed)
    )
    assert client_closed.error_code == ErrorCode.NO_ERROR
    assert server_closed.error_code == ErrorCode.NO_ERROR


def test_remote_reset_releases_unsent_body_data() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    client.send_data(stream_id, b"x" * 100_000, end_stream=True)
    server.receive_data(client.data_to_send())
    server.events()
    assert client.pending_data(stream_id) > 0

    server.reset_stream(stream_id, ErrorCode.CANCEL)
    client.receive_data(server.data_to_send())

    events = client.events()
    assert any(isinstance(event, StreamReset) for event in events)
    assert any(isinstance(event, StreamClosed) for event in events)
    assert client.pending_data(stream_id) == 0
    assert client.pending_data() == 0


def test_manual_consumption_emits_connection_and_stream_window_updates() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(
        Role.SERVER,
        Configuration(auto_window_update=False),
    )
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    client.send_data(stream_id, b"x" * 40_000, end_stream=True)
    server.receive_data(client.data_to_send())
    consumed = sum(
        len(event.data) for event in server.events() if isinstance(event, DataReceived)
    )

    server.acknowledge_received_data(consumed, stream_id)
    client.receive_data(server.data_to_send())

    updates = [event for event in client.events() if isinstance(event, WindowUpdated)]
    assert {(event.stream_id, event.increment) for event in updates} == {
        (0, consumed),
        (stream_id, consumed),
    }


def test_manual_consumption_excludes_padding_already_consumed_by_engine() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(
        Role.SERVER,
        Configuration(auto_window_update=False),
    )
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    padded_data = (
        b"\x00\x00\x0c\x00\x08"
        + stream_id.to_bytes(4, "big")
        + b"\x0a"
        + b"x"
        + bytes(10)
    )

    server.receive_data(padded_data)
    event = next(event for event in server.events() if isinstance(event, DataReceived))

    assert event.data == b"x"
    server.acknowledge_received_data(len(event.data), stream_id)
    with pytest.raises(ValueError, match="exceeds unacknowledged"):
        server.acknowledge_received_data(1, stream_id)


def test_shutdown_notice_stops_new_requests() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)

    server.send_shutdown_notice()
    client.receive_data(server.data_to_send())

    goaway = next(
        event for event in client.events() if isinstance(event, GoAwayReceived)
    )
    assert goaway.last_stream_id == (1 << 31) - 1
    assert not client.can_send_request
    with pytest.raises(ConnectionClosingError):
        client.send_request(REQUEST_HEADERS, end_stream=True)


def test_terminate_connection_stops_both_session_directions() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)

    server.terminate_connection()
    client.receive_data(server.data_to_send())

    assert any(isinstance(event, GoAwayReceived) for event in client.events())
    assert not server.want_read
    assert not server.want_write
    assert not client.want_read
    assert not client.want_write
