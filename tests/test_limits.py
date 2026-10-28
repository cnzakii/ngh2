from collections.abc import Callable
from typing import cast

import pytest

from ngh2 import (
    Configuration,
    Connection,
    ConnectionStateError,
    DenialOfServiceError,
    ErrorCode,
    RequestReceived,
    Role,
    StreamClosed,
    StreamProtocolError,
)


class IndexInteger:
    def __init__(self, value: int):
        self.value = value

    def __index__(self) -> int:
        return self.value


class TestResourceLimits:
    @pytest.mark.parametrize(
        "configure",
        [
            lambda limit: Configuration(max_settings=limit),
            lambda limit: Configuration(max_inbound_header_count=limit),
            lambda limit: Configuration(max_inbound_header_list_size=limit),
        ],
        ids=["settings", "header-count", "header-size"],
    )
    @pytest.mark.parametrize("integer", [int, IndexInteger], ids=["int", "index"])
    def test_integer_configuration_accepts_values_within_limits(
        self,
        handshake: Callable[[Connection, Connection], None],
        configure: Callable[[int], Configuration],
        integer: Callable[[int], object],
    ):
        client = Connection(Role.CLIENT)
        server = Connection(Role.SERVER, configure(cast(int, integer(1_000))))
        handshake(client, server)
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

        assert any(
            isinstance(event, RequestReceived) and event.stream_id == stream_id
            for event in server.events()
        )

    @pytest.mark.parametrize("limit", [1, IndexInteger(1)], ids=["int", "index"])
    def test_settings_limit_rejects_excess_entries(self, limit: int):
        server = Connection(Role.SERVER, Configuration(max_settings=limit))
        server.initiate_connection({3: 10})

        with pytest.raises(ValueError, match="configured entry limit"):
            server.update_settings({3: 10, 4: 65_535})

        server.update_settings({3: 20})
        assert server.data_to_send()

    def test_continuation_limit_fails_the_connection(
        self, handshake: Callable[[Connection, Connection], None]
    ):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(max_continuations=0),
        )
        handshake(client, server)
        client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
                *[
                    (
                        f"x-field-{index}".encode(),
                        bytes([65 + index % 26]) * 1_000,
                    )
                    for index in range(32)
                ],
            ],
            end_stream=True,
        )

        with pytest.raises(
            DenialOfServiceError,
            match="Too many CONTINUATION frames",
        ):
            server.receive_data(client.data_to_send())
        with pytest.raises(ConnectionStateError):
            server.receive_data(b"")

    def test_outbound_ack_limit_fails_the_connection(
        self, handshake: Callable[[Connection, Connection], None]
    ):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(max_outbound_ack=1),
        )
        handshake(client, server)
        client.send_ping(b"first---")
        client.send_ping(b"second--")

        with pytest.raises(DenialOfServiceError, match="Flooding was detected"):
            server.receive_data(client.data_to_send())
        with pytest.raises(ConnectionStateError):
            server.receive_data(b"")

    @pytest.mark.parametrize("limit", [3, IndexInteger(3)], ids=["int", "index"])
    def test_header_count_limit_fails_the_connection(
        self, handshake: Callable[[Connection, Connection], None], limit: int
    ):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(max_inbound_header_count=limit),
        )
        handshake(client, server)
        client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )

        with pytest.raises(
            DenialOfServiceError, match="header list exceeds configured count"
        ):
            server.receive_data(client.data_to_send())
        with pytest.raises(ConnectionStateError):
            server.receive_data(b"")
        with pytest.raises(ConnectionStateError):
            server.data_to_send(0)

    @pytest.mark.parametrize("limit", [160, IndexInteger(160)], ids=["int", "index"])
    def test_header_size_limit_fails_the_connection(
        self, handshake: Callable[[Connection, Connection], None], limit: int
    ):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(max_inbound_header_list_size=limit),
        )
        handshake(client, server)
        client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
            ],
            end_stream=True,
        )

        with pytest.raises(
            DenialOfServiceError,
            match="header list exceeds configured size",
        ):
            server.receive_data(client.data_to_send())

    def test_failed_connection_releases_queued_body_data(
        self, handshake: Callable[[Connection, Connection], None]
    ):
        client = Connection(
            Role.CLIENT,
            Configuration(max_inbound_header_count=1),
        )
        server = Connection(Role.SERVER)
        handshake(client, server)
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

        assert client.queued_body_size() == 0
        assert client.queued_body_size(stream_id) == 0

    def test_unsent_response_headers_release_queued_body_data(
        self, handshake: Callable[[Connection, Connection], None]
    ):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(max_send_header_block_length=64),
        )
        handshake(client, server)
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

        assert server.queued_body_size(stream_id) == 4
        assert server.data_to_send()
        closed = next(
            event for event in server.events() if isinstance(event, StreamClosed)
        )
        assert closed.stream_id == stream_id
        assert closed.error_code == ErrorCode.INTERNAL_ERROR
        assert isinstance(closed.local_error, StreamProtocolError)
        assert server.queued_body_size(stream_id) == 0
        assert server.queued_body_size() == 0

    def test_unsent_request_headers_close_the_reserved_stream(
        self, handshake: Callable[[Connection, Connection], None]
    ):
        client = Connection(
            Role.CLIENT,
            Configuration(max_send_header_block_length=64),
        )
        server = Connection(Role.SERVER)
        handshake(client, server)
        stream_id = client.send_request(
            [
                (b":method", b"GET"),
                (b":scheme", b"https"),
                (b":authority", b"example.test"),
                (b":path", b"/"),
                (b"x-large", b"x" * 200),
            ],
            end_stream=True,
        )

        assert client.data_to_send() == b""
        closed = next(
            event for event in client.events() if isinstance(event, StreamClosed)
        )
        assert closed.stream_id == stream_id
        assert closed.error_code == ErrorCode.REFUSED_STREAM
        assert isinstance(closed.local_error, StreamProtocolError)

    def test_manual_window_update_rejects_double_acknowledgement(
        self, handshake: Callable[[Connection, Connection], None]
    ):
        client = Connection(Role.CLIENT)
        server = Connection(
            Role.SERVER,
            Configuration(auto_window_update=False),
        )
        handshake(client, server)
        server.consume_received_data(1, 0)
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

        server.consume_received_data(stream_id, 4)
        with pytest.raises(ValueError, match="exceeds unconsumed"):
            server.consume_received_data(stream_id, 1)
