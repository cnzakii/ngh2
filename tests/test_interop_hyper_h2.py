from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import DataReceived as H2DataReceived
from h2.events import RequestReceived as H2RequestReceived
from h2.events import StreamEnded as H2StreamEnded

from ngh2 import Connection, RequestReceived, ResponseReceived, Role

REQUEST_HEADERS = [
    (b":method", b"POST"),
    (b":scheme", b"https"),
    (b":authority", b"example.test"),
    (b":path", b"/interop"),
]


class TestHyperH2Interop:
    def test_ngh2_client_talks_to_hyper_h2_server(self):
        client = Connection(Role.CLIENT)
        server = H2Connection(H2Configuration(client_side=False))
        client.initiate_connection()
        server.initiate_connection()

        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
        server.receive_data(client.data_to_send())
        client.events()

        stream_id = client.send_request(REQUEST_HEADERS)
        client.send_data(stream_id, b"body", end_stream=True)
        events = server.receive_data(client.data_to_send())

        assert any(isinstance(item, H2RequestReceived) for item in events)
        body = next(item for item in events if isinstance(item, H2DataReceived))
        assert body.data == b"body"
        server.send_headers(stream_id, [(b":status", b"204")], end_stream=True)
        client.receive_data(server.data_to_send())
        assert any(isinstance(item, ResponseReceived) for item in client.events())

    def test_hyper_h2_client_talks_to_ngh2_server(self):
        client = H2Connection(H2Configuration(client_side=True))
        server = Connection(Role.SERVER)
        client.initiate_connection()
        server.initiate_connection()

        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
        server.receive_data(client.data_to_send())
        server.events()

        stream_id = client.get_next_available_stream_id()
        client.send_headers(stream_id, REQUEST_HEADERS, end_stream=True)
        server.receive_data(client.data_to_send())
        request = next(
            item for item in server.events() if isinstance(item, RequestReceived)
        )

        assert request.stream_id == stream_id
        server.send_response(stream_id, [(b":status", b"204")], end_stream=True)
        response_events = client.receive_data(server.data_to_send())
        assert response_events

    def test_hyper_h2_window_updates_drain_queued_ngh2_body(self):
        client = Connection(Role.CLIENT)
        server = H2Connection(H2Configuration(client_side=False))
        client.initiate_connection()
        server.initiate_connection()
        server.receive_data(client.data_to_send())
        client.receive_data(server.data_to_send())
        server.receive_data(client.data_to_send())
        client.events()

        stream_id = client.send_request(REQUEST_HEADERS)
        body = b"x" * 100_000
        client.send_data(stream_id, body, end_stream=True)
        received = bytearray()
        ended = False

        for _ in range(10):
            if not client.pending_data(stream_id):
                break
            events = server.receive_data(client.data_to_send())
            for event in events:
                if isinstance(event, H2DataReceived):
                    received.extend(event.data)
                    server.acknowledge_received_data(
                        event.flow_controlled_length,
                        event.stream_id,
                    )
                elif isinstance(event, H2StreamEnded):
                    ended = True
            if window_updates := server.data_to_send():
                client.receive_data(window_updates)
        else:
            raise AssertionError("queued body did not drain after window updates")

        assert received == body
        assert ended
        assert client.pending_data() == 0
