import pytest

from ngh2 import (
    Configuration,
    Connection,
    ConnectionClosed,
    ConnectionClosingError,
    ConnectionStateError,
    DataReceived,
    ErrorCode,
    GoAwayReceived,
    RequestReceived,
    ResponseReceived,
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
    assert client_closed.local_error is None
    assert server_closed.error_code == ErrorCode.NO_ERROR
    assert server_closed.local_error is None


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
    closed = next(event for event in events if isinstance(event, StreamClosed))
    assert closed.local_error is None
    assert client.pending_data(stream_id) == 0
    assert client.pending_data() == 0


def test_invalid_regular_header_closes_only_its_stream() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(
        [*REQUEST_HEADERS, (b"connection", b"close")],
        end_stream=True,
    )
    sibling_id = client.send_request(REQUEST_HEADERS, end_stream=True)

    server.receive_data(client.data_to_send())
    request = next(
        event for event in server.events() if isinstance(event, RequestReceived)
    )
    assert request.stream_id == sibling_id

    client.receive_data(server.data_to_send())
    reset = next(event for event in client.events() if isinstance(event, StreamReset))
    assert reset.stream_id == stream_id

    closed = next(event for event in server.events() if isinstance(event, StreamClosed))
    assert closed.stream_id == stream_id
    assert closed.error_code == ErrorCode.PROTOCOL_ERROR
    assert closed.local_error is None

    server.send_response(sibling_id, [(b":status", b"204")], end_stream=True)
    client.receive_data(server.data_to_send())
    response = next(
        event for event in client.events() if isinstance(event, ResponseReceived)
    )
    assert response.stream_id == sibling_id


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
    with pytest.raises(ConnectionStateError):
        client.send_request(REQUEST_HEADERS, end_stream=True)


def test_goaway_closes_a_queued_request_with_the_local_reason() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS, end_stream=True)

    server.send_goaway(last_stream_id=0)
    client.receive_data(server.data_to_send())
    client.events()
    assert client.data_to_send() == b""

    closed = next(event for event in client.events() if isinstance(event, StreamClosed))
    assert closed.stream_id == stream_id
    assert closed.error_code == ErrorCode.REFUSED_STREAM
    assert isinstance(closed.local_error, ConnectionClosingError)


def test_terminate_connection_stops_both_session_directions() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)

    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    server.send_response(stream_id, [(b":status", b"200")])
    server.send_data(stream_id, b"queued")

    server.terminate_connection(ErrorCode.INTERNAL_ERROR)
    assert server.pending_data() == 0
    with pytest.raises(ConnectionStateError):
        server.ping()

    final_output = server.data_to_send()
    closed = next(
        event for event in server.events() if isinstance(event, ConnectionClosed)
    )
    assert closed.error_code == ErrorCode.INTERNAL_ERROR
    assert closed.debug_data == b""
    assert server.data_to_send() == b""
    assert server.events() == []
    client.receive_data(final_output)

    assert any(isinstance(event, GoAwayReceived) for event in client.events())
    assert not server.want_read
    assert not server.want_write
    assert not client.can_send_request


def test_peer_connection_error_finishes_with_goaway_and_closed_event() -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    settings_on_stream_one = b"\x00\x00\x00\x04\x00\x00\x00\x00\x01"

    server.receive_data(settings_on_stream_one)
    final_output = server.data_to_send()

    assert final_output
    closed = next(
        event for event in server.events() if isinstance(event, ConnectionClosed)
    )
    assert closed.error_code == ErrorCode.PROTOCOL_ERROR
    assert not server.want_read
    assert not server.want_write
    with pytest.raises(ConnectionStateError):
        server.receive_data(b"")


def test_connection_closes_only_with_the_last_limited_output_chunk() -> None:
    server = Connection(Role.SERVER)
    server.initiate_connection()
    server.data_to_send()
    server.events()
    server.terminate_connection()

    while server.want_write:
        output = server.data_to_send(1)
        events = server.events()
        if any(isinstance(event, ConnectionClosed) for event in events):
            assert output
            break
        assert server.want_write
    else:
        pytest.fail("terminal output did not produce ConnectionClosed")

    assert not server.want_write
