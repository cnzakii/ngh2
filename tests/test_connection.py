from collections.abc import Sequence
from typing import cast

import pytest

from ngh2 import (
    Connection,
    ConnectionClosingError,
    DataReceived,
    ErrorCode,
    Header,
    InformationalResponseReceived,
    NeverIndexedHeader,
    PushedStreamReceived,
    RequestReceived,
    ResponseReceived,
    Role,
    SettingsReceived,
    StreamClosed,
    StreamProtocolError,
    StreamReset,
    TrailersReceived,
)


def exchange(source: Connection, destination: Connection) -> bytes:
    data = source.data_to_send()
    destination.receive_data(data)
    return data


class TestConnection:
    def test_boolean_stream_flags_require_bool(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)

        with pytest.raises(TypeError, match="end_stream must be a bool"):
            client.send_request(
                [
                    (b":method", b"POST"),
                    (b":scheme", b"https"),
                    (b":authority", b"example.test"),
                    (b":path", b"/"),
                ],
                end_stream=cast(bool, 1),
            )

        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        exchange(client, server)
        server.events()
        with pytest.raises(TypeError, match="end_stream must be a bool"):
            client.send_data(stream_id, b"body", end_stream=cast(bool, 1))
        with pytest.raises(TypeError, match="end_stream must be a bool"):
            server.send_response(
                stream_id,
                [(b":status", b"204")],
                end_stream=cast(bool, 1),
            )

    def test_outbound_headers_require_a_sequence(self):
        client = Connection(Role.CLIENT)
        client.initiate_connection()
        headers = (
            (b":method", b"GET"),
            (b":scheme", b"https"),
            (b":authority", b"example.test"),
            (b":path", b"/"),
        )

        assert client.send_request(headers, end_stream=True) == 1
        generator = cast(Sequence[Header], (header for header in headers))
        with pytest.raises(TypeError):
            client.send_request(generator, end_stream=True)

    def test_connection_stays_quiet_until_initiated(self):
        connection = Connection(Role.CLIENT)

        assert connection.data_to_send() == b""

    def test_client_and_server_exchange_a_request_and_response(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()

        client_preface = exchange(client, server)
        server_preface = exchange(server, client)
        exchange(client, server)
        exchange(server, client)

        assert client_preface.startswith(b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n")
        assert not server_preface.startswith(b"PRI * HTTP/2.0")
        assert any(isinstance(event, SettingsReceived) for event in client.events())
        assert any(isinstance(event, SettingsReceived) for event in server.events())

        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/upload"),
                NeverIndexedHeader(b"authorization", b"secret"),
            ],
        )
        client.send_data(stream_id, b"body", end_stream=True)
        assert client.queued_body_size(stream_id) == 4
        assert client.queued_body_size() == 4

        exchange(client, server)
        assert client.queued_body_size(stream_id) == 0
        request_events = server.events()
        request = next(
            event for event in request_events if isinstance(event, RequestReceived)
        )
        body = next(
            event for event in request_events if isinstance(event, DataReceived)
        )
        assert request.stream_id == stream_id
        assert request.headers[0] == (b":method", b"POST")
        assert type(request.headers[0]) is tuple
        sensitive = request.headers[-1]
        assert isinstance(sensitive, NeverIndexedHeader)
        assert tuple(sensitive) == (b"authorization", b"secret")
        assert not request.end_stream
        assert body.data == b"body"
        assert body.end_stream

        server.send_response(
            stream_id,
            [(b":status", b"200"), (b"content-length", b"2")],
        )
        server.send_data(stream_id, b"OK", end_stream=True)
        exchange(server, client)

        response_events = client.events()
        response = next(
            event for event in response_events if isinstance(event, ResponseReceived)
        )
        response_body = next(
            event for event in response_events if isinstance(event, DataReceived)
        )
        assert response.headers[0] == (b":status", b"200")
        assert response_body.data == b"OK"
        assert response_body.end_stream

    def test_informational_response_trailers_and_server_push(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)
        client.events()
        server.events()

        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        client.send_data(stream_id, b"body")
        client.send_trailers(stream_id, [(b"digest", b"sha-256=:abc:")])
        exchange(client, server)
        server_events = server.events()
        assert any(isinstance(item, TrailersReceived) for item in server_events)

        server.send_informational_response(stream_id, [(b":status", b"102")])
        server.send_informational_response(stream_id, [(b":status", b"103")])
        promised_id = server.send_push_promise(
            stream_id,
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/style.css"),
            ],
        )
        server.send_response(stream_id, [(b":status", b"204")], end_stream=True)

        with pytest.raises(StreamProtocolError, match="precede the final"):
            server.send_informational_response(stream_id, [(b":status", b"103")])

        exchange(server, client)

        client_events = client.events()
        informational = [
            item
            for item in client_events
            if isinstance(item, InformationalResponseReceived)
        ]
        assert [event.headers[0] for event in informational] == [
            (b":status", b"102"),
            (b":status", b"103"),
        ]
        pushed = next(
            item for item in client_events if isinstance(item, PushedStreamReceived)
        )
        assert pushed.promised_stream_id == promised_id

    def test_empty_body_can_end_with_trailers_after_data_defers(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)
        client.events()
        server.events()

        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        exchange(client, server)
        server.events()

        client.send_trailers(stream_id, [(b"digest", b"sha-256=:abc:")])
        exchange(client, server)

        trailers = next(
            event for event in server.events() if isinstance(event, TrailersReceived)
        )
        assert trailers.headers == ((b"digest", b"sha-256=:abc:"),)

    def test_stream_body_rejects_invalid_lifecycle_operations(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)

        with pytest.raises(StreamProtocolError, match="no open body"):
            client.send_data(1, b"body")
        with pytest.raises(StreamProtocolError, match="no open body"):
            client.send_trailers(1, [])

        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        with pytest.raises(TypeError, match="bytes-like"):
            client.send_data(stream_id, cast(bytes, "body"))
        with pytest.raises(TypeError, match="each header must be a pair"):
            client.send_trailers(
                stream_id,
                cast(Sequence[Header], [b"not-a-pair"]),
            )
        client.send_trailers(stream_id, [])
        with pytest.raises(StreamProtocolError, match="already ended"):
            client.send_data(stream_id, b"body")
        with pytest.raises(StreamProtocolError, match="already ended"):
            client.send_trailers(stream_id, [])

    def test_response_rejects_a_second_final_response(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )
        exchange(client, server)
        server.events()

        server.send_response(stream_id, [(b":status", b"204")], end_stream=True)
        with pytest.raises(StreamProtocolError, match="already pending"):
            server.send_response(stream_id, [(b":status", b"204")], end_stream=True)

    def test_stream_identifiers_and_headers_are_validated(self):
        client = Connection(Role.CLIENT)
        client.initiate_connection()

        with pytest.raises(TypeError, match="stream_id must be an integer"):
            client.reset_stream(cast(int, 1.5))
        with pytest.raises(ValueError, match="stream_id is out of range"):
            client.reset_stream(0)
        with pytest.raises(TypeError, match="each header must be a pair"):
            client.send_request(cast(Sequence[Header], [b"not-a-pair"]))
        with pytest.raises(TypeError):
            client.send_request(cast(Sequence[Header], [(b"name", 1)]))

    def test_peer_goaway_stops_new_request_submission(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        exchange(client, server)
        server.events()
        server.send_goaway(last_stream_id=stream_id)
        exchange(server, client)
        client.events()

        with pytest.raises(ConnectionClosingError):
            client.send_request([], end_stream=True)

    def test_queued_body_size_tracks_flow_control_blocked_body(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)
        client.events()
        server.events()
        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/upload"),
            ],
        )
        body = b"x" * 100_000
        client.send_data(stream_id, body, end_stream=True)

        first_output = client.data_to_send()
        assert client.queued_body_size(stream_id) > 0
        server.receive_data(first_output)
        client.receive_data(server.data_to_send())
        second_output = client.data_to_send()

        assert second_output
        assert client.queued_body_size(stream_id) == 0

    def test_fragmented_input_emits_one_event_per_data_frame(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)
        client.events()
        server.events()

        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/upload"),
            ],
        )
        payload = b"x" * 20_000
        client.send_data(stream_id, payload, end_stream=True)
        wire_data = client.data_to_send()

        frame_count = 0
        offset = 0
        while offset < len(wire_data):
            frame_length = int.from_bytes(
                wire_data[offset : offset + 3],
                byteorder="big",
            )
            if wire_data[offset + 3] == 0:
                frame_count += 1
            offset += 9 + frame_length

        for offset in range(0, len(wire_data), 1_024):
            server.receive_data(wire_data[offset : offset + 1_024])

        data_events = [
            event for event in server.events() if isinstance(event, DataReceived)
        ]
        assert frame_count > 1
        assert len(data_events) == frame_count
        assert b"".join(event.data for event in data_events) == payload
        assert data_events[-1].end_stream

    def test_peer_rejects_an_invalid_outbound_message_block(self):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()
        exchange(client, server)
        exchange(server, client)
        exchange(client, server)
        exchange(server, client)

        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        exchange(client, server)
        server.events()

        server.send_informational_response(stream_id, [(b"x-example", b"value")])
        exchange(server, client)

        assert not any(
            isinstance(event, InformationalResponseReceived)
            for event in client.events()
        )

        server.receive_data(client.data_to_send())
        client_closed = next(
            event for event in client.events() if isinstance(event, StreamClosed)
        )
        server_events = server.events()
        reset = next(event for event in server_events if isinstance(event, StreamReset))
        server_closed = next(
            event for event in server_events if isinstance(event, StreamClosed)
        )
        assert client_closed.error_code == ErrorCode.PROTOCOL_ERROR
        assert reset.error_code == ErrorCode.PROTOCOL_ERROR
        assert server_closed.error_code == ErrorCode.PROTOCOL_ERROR
