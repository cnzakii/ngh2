from collections.abc import Sequence
from typing import cast

import pytest

from ngh2 import (
    Connection,
    DataReceived,
    Header,
    InformationalResponseReceived,
    NeverIndexedHeader,
    PushedStreamReceived,
    RequestReceived,
    ResponseReceived,
    Role,
    SettingsReceived,
    StreamProtocolError,
    TrailersReceived,
)


def exchange(source: Connection, destination: Connection) -> bytes:
    data = source.data_to_send()
    destination.receive_data(data)
    return data


class TestConnection:
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
        assert client.pending_data(stream_id) == 4
        assert client.pending_data() == 4

        exchange(client, server)
        assert client.pending_data(stream_id) == 0
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
        assert any(
            isinstance(item, InformationalResponseReceived) for item in client_events
        )
        pushed = next(
            item for item in client_events if isinstance(item, PushedStreamReceived)
        )
        assert pushed.promised_stream_id == promised_id

    def test_pending_data_tracks_native_flow_control(self):
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
        assert client.pending_data(stream_id) > 0
        server.receive_data(first_output)
        client.receive_data(server.data_to_send())
        second_output = client.data_to_send()

        assert second_output
        assert client.pending_data(stream_id) == 0

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

    def test_outbound_message_validation_remains_the_callers_responsibility(self):
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

        server.send_informational_response(stream_id, [(b"x-example", b"value")])
        client.send_trailers(stream_id, [(b":path", b"/not-a-valid-trailer")])
