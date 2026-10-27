from collections.abc import Callable

import pytest

from ngh2 import (
    Configuration,
    Connection,
    ConnectionClosed,
    ConnectionClosingError,
    ConnectionProtocolError,
    ConnectionStateError,
    DataReceived,
    ErrorCode,
    GoAwayReceived,
    PingReceived,
    RequestReceived,
    ResponseReceived,
    Role,
    Setting,
    StreamClosed,
    StreamProtocolError,
    StreamReset,
    StreamUnavailableError,
    TrailersReceived,
    WindowUpdated,
)

REQUEST_HEADERS = [
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/"),
]


@pytest.mark.parametrize("upgrade", [False, True])
@pytest.mark.parametrize("subclass", [False, True])
def test_uninitialized_connections_cannot_enter_native_code(
    upgrade: bool, subclass: bool
) -> None:
    class MissingSuper(Connection):
        def __init__(self):
            pass

    connection = MissingSuper() if subclass else Connection.__new__(Connection)
    with pytest.raises(ConnectionStateError, match="not initialized"):
        if upgrade:
            connection.initiate_upgrade(b"")
        else:
            connection.initiate_connection()


def test_end_stream_emits_an_empty_terminal_data_event(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)

    client.end_stream(stream_id)
    server.receive_data(client.data_to_send())

    data = next(event for event in server.events() if isinstance(event, DataReceived))
    assert data.data == b""
    assert data.end_stream


def test_normal_completion_closes_the_stream_on_both_peers(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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


def test_remote_reset_releases_unsent_body_data(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    client.send_data(stream_id, b"x" * 100_000, end_stream=True)
    server.receive_data(client.data_to_send())
    server.events()
    assert client.queued_body_size(stream_id) > 0

    server.reset_stream(stream_id, ErrorCode.CANCEL)
    client.receive_data(server.data_to_send())

    events = client.events()
    assert any(isinstance(event, StreamReset) for event in events)
    closed = next(event for event in events if isinstance(event, StreamClosed))
    assert closed.local_error is None
    assert client.queued_body_size(stream_id) == 0
    assert client.queued_body_size() == 0


@pytest.mark.parametrize("amount", [None, 1024])
@pytest.mark.parametrize("sent_first", [False, True])
def test_reset_after_end_stream_follows_the_queued_response(
    handshake: Callable[[Connection, Connection], None],
    amount: int | None,
    sent_first: bool,
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    server.send_response(stream_id, [(b":status", b"200")])
    server.send_data(stream_id, b"x" * 10_000)
    server.send_trailers(stream_id, [(b"grpc-status", b"0")])

    events = []
    if sent_first:
        client.receive_data(server.data_to_send())
        events += client.events()
    server.reset_stream(stream_id, ErrorCode.NO_ERROR, after_end_stream=True)
    while output := server.data_to_send(amount):
        client.receive_data(output)
    events += client.events()

    assert sum(len(e.data) for e in events if isinstance(e, DataReceived)) == 10_000
    assert any(isinstance(event, TrailersReceived) for event in events)
    reset = next(event for event in events if isinstance(event, StreamReset))
    assert reset.error_code == ErrorCode.NO_ERROR
    assert isinstance(events[-1], StreamClosed)


def test_reset_after_end_stream_waits_for_flow_control(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    client.update_settings({Setting.INITIAL_WINDOW_SIZE: 0})
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    client.events()
    server.events()
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    server.send_response(stream_id, [(b":status", b"200")])
    server.send_data(stream_id, b"answer", end_stream=True)

    server.reset_stream(stream_id, ErrorCode.NO_ERROR, after_end_stream=True)
    client.receive_data(server.data_to_send())

    events = client.events()
    assert any(isinstance(event, ResponseReceived) for event in events)
    assert not any(isinstance(event, (DataReceived, StreamReset)) for event in events)
    assert server.queued_body_size(stream_id) == len(b"answer")

    client.update_settings({Setting.INITIAL_WINDOW_SIZE: 65_535})
    server.receive_data(client.data_to_send())
    server.events()
    client.receive_data(server.data_to_send())

    events = [
        event
        for event in client.events()
        if isinstance(event, (DataReceived, StreamReset, StreamClosed))
    ]
    data, reset, closed = events
    assert isinstance(data, DataReceived)
    assert data.data == b"answer"
    assert data.end_stream
    assert isinstance(reset, StreamReset)
    assert reset.error_code == ErrorCode.NO_ERROR
    assert isinstance(closed, StreamClosed)


def test_reset_after_end_stream_is_skipped_when_the_peer_ended_first(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS, end_stream=True)
    server.receive_data(client.data_to_send())
    server.events()
    server.send_response(stream_id, [(b":status", b"204")], end_stream=True)

    server.reset_stream(stream_id, ErrorCode.CANCEL, after_end_stream=True)
    client.receive_data(server.data_to_send())

    events = client.events()
    assert not any(isinstance(event, StreamReset) for event in events)
    closed = next(event for event in events if isinstance(event, StreamClosed))
    assert closed.error_code == ErrorCode.NO_ERROR


def test_reset_after_end_stream_requires_an_ended_local_direction(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()

    with pytest.raises(StreamProtocolError):
        server.reset_stream(stream_id, after_end_stream=True)
    server.send_response(stream_id, [(b":status", b"200")])
    with pytest.raises(StreamProtocolError):
        server.reset_stream(stream_id, after_end_stream=True)
    with pytest.raises(StreamUnavailableError):
        server.reset_stream(stream_id + 2, after_end_stream=True)


def test_invalid_regular_header_closes_only_its_stream(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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


def test_ignorable_invalid_regular_header_is_rejected(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(
        [*REQUEST_HEADERS, (b"host", b"bad\x00host")],
        end_stream=True,
    )

    server.receive_data(client.data_to_send())
    assert not any(isinstance(event, RequestReceived) for event in server.events())

    client.receive_data(server.data_to_send())
    reset = next(event for event in client.events() if isinstance(event, StreamReset))
    assert reset.stream_id == stream_id
    assert reset.error_code == ErrorCode.PROTOCOL_ERROR


def test_manual_consumption_emits_connection_and_stream_window_updates(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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


def test_manual_consumption_after_stream_close_updates_connection_window(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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

    server.send_response(stream_id, [(b":status", b"204")], end_stream=True)
    client.receive_data(server.data_to_send())
    assert any(
        isinstance(event, StreamClosed) and event.stream_id == stream_id
        for event in server.events()
    )

    server.acknowledge_received_data(consumed, stream_id)
    client.receive_data(server.data_to_send())

    updates = [event for event in client.events() if isinstance(event, WindowUpdated)]
    assert [(event.stream_id, event.increment) for event in updates] == [(0, consumed)]


def test_manual_consumption_requires_manual_window_updates() -> None:
    server = Connection(Role.SERVER)
    server.initiate_connection()

    with pytest.raises(ConnectionStateError, match="auto_window_update=False"):
        server.acknowledge_received_data(0, 1)


def test_manual_consumption_excludes_padding_already_consumed_by_engine(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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


def test_shutdown_notice_stops_new_requests(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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


def test_goaway_defaults_to_the_last_processed_peer_stream(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS, end_stream=True)
    server.receive_data(client.data_to_send())
    server.events()

    server.send_goaway()
    client.receive_data(server.data_to_send())

    goaway = next(
        event for event in client.events() if isinstance(event, GoAwayReceived)
    )
    assert goaway.last_stream_id == stream_id


def test_goaway_closes_a_queued_request_with_the_local_reason(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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


def test_terminate_connection_stops_both_session_directions(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)

    stream_id = client.send_request(REQUEST_HEADERS)
    server.receive_data(client.data_to_send())
    server.events()
    server.send_response(stream_id, [(b":status", b"200")])
    server.send_data(stream_id, b"queued")

    server.terminate_connection(
        ErrorCode.INTERNAL_ERROR,
        last_stream_id=stream_id,
    )
    assert server.queued_body_size() == 0
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

    goaway = next(
        event for event in client.events() if isinstance(event, GoAwayReceived)
    )
    assert goaway.last_stream_id == stream_id
    assert not server.want_read
    assert not server.want_write
    assert not client.can_send_request


def test_peer_connection_error_finishes_with_goaway_and_closed_event(
    handshake: Callable[[Connection, Connection], None],
) -> None:
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


def test_bad_client_preface_fails_the_connection() -> None:
    server = Connection(Role.SERVER)
    server.initiate_connection()

    with pytest.raises(ConnectionProtocolError, match="client magic"):
        server.receive_data(b"not an HTTP/2 client preface")
    with pytest.raises(ConnectionStateError, match="no longer usable"):
        server.initiate_connection()


def test_queued_response_is_discarded_after_peer_reset(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client = Connection(Role.CLIENT)
    server = Connection(Role.SERVER)
    handshake(client, server)
    stream_id = client.send_request(REQUEST_HEADERS, end_stream=True)
    server.receive_data(client.data_to_send())
    server.events()
    server.send_response(stream_id, [(b":status", b"204")], end_stream=True)

    client.reset_stream(stream_id)
    server.receive_data(client.data_to_send())
    server.events()

    assert server.data_to_send() == b""
    assert server.events() == []


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


def test_terminal_protocol_error_discards_a_queued_ping(
    handshake: Callable[[Connection, Connection], None],
) -> None:
    client, server = Connection(Role.CLIENT), Connection(Role.SERVER)
    handshake(client, server)
    server.ping(b"pending!")
    settings_on_stream_one = b"\x00\x00\x00\x04\x00\x00\x00\x00\x01"

    server.receive_data(settings_on_stream_one)
    client.receive_data(server.data_to_send())

    local_events = server.events()
    assert len(local_events) == 1
    assert isinstance(local_events[0], ConnectionClosed)
    assert local_events[0].error_code == ErrorCode.PROTOCOL_ERROR
    peer_events = client.events()
    assert not any(isinstance(event, PingReceived) for event in peer_events)
    goaway = next(event for event in peer_events if isinstance(event, GoAwayReceived))
    assert goaway.error_code == ErrorCode.PROTOCOL_ERROR
    assert not server.want_read
    assert not server.want_write
    assert server.data_to_send() == b""
    assert server.events() == []
