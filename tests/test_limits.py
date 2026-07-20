import pytest

from ngh2 import (
    Configuration,
    Connection,
    ConnectionStateError,
    DenialOfServiceError,
    FrameNotSent,
    Role,
)


def begin(client: Connection, server: Connection) -> None:
    client.initiate_connection()
    server.initiate_connection()
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    server.receive_data(client.data_to_send())
    client.receive_data(server.data_to_send())
    client.events()
    server.events()


class TestResourceLimits:
    def test_header_count_limit_fails_the_connection(self):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(max_inbound_header_count=3),
        )
        begin(client, server)
        client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )

        with pytest.raises(DenialOfServiceError):
            server.receive_data(client.data_to_send())
        with pytest.raises(ConnectionStateError):
            server.receive_data(b"")
        with pytest.raises(ConnectionStateError):
            server.data_to_send(0)

    def test_failed_connection_releases_pending_body_data(self):
        client = Connection(
            Role.CLIENT,
            Configuration(max_inbound_header_count=1),
        )
        server = Connection(Role.SERVER)
        begin(client, server)
        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        server.receive_data(client.data_to_send())
        server.events()
        client.send_data(stream_id, b"body")
        server.send_response(
            stream_id,
            [(b":status", b"200"), (b"content-type", b"text/plain")],
            end_stream=True,
        )

        with pytest.raises(DenialOfServiceError):
            client.receive_data(server.data_to_send())

        assert client.pending_data() == 0
        assert client.pending_data(stream_id) == 0

    def test_unsent_response_headers_release_pending_body_data(self):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(max_send_header_block_length=64),
        )
        begin(client, server)
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )
        server.receive_data(client.data_to_send())
        server.events()
        server.send_response(
            stream_id,
            [(b":status", b"200"), (b"x-large", b"x" * 200)],
        )
        server.send_data(stream_id, b"body", end_stream=True)

        assert server.pending_data(stream_id) == 4
        assert server.data_to_send() == b""
        assert any(isinstance(event, FrameNotSent) for event in server.events())
        assert server.pending_data(stream_id) == 0
        assert server.pending_data() == 0

    def test_manual_window_update_rejects_double_acknowledgement(self):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(auto_window_update=False),
        )
        begin(client, server)
        server.acknowledge_received_data(0, 1)
        stream_id = client.send_request(
            [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
        )
        client.send_data(stream_id, b"body")
        server.receive_data(client.data_to_send())

        server.acknowledge_received_data(4, stream_id)
        with pytest.raises(ValueError, match="exceeds unacknowledged"):
            server.acknowledge_received_data(1, stream_id)
