from dataclasses import dataclass
from enum import Enum


class Role(Enum):
    """The local endpoint's HTTP/2 role.

    Attributes:
        CLIENT: Initiates requests and receives responses.
        SERVER: Receives requests and sends responses.
    """

    CLIENT = "client"
    SERVER = "server"


@dataclass(frozen=True, kw_only=True, slots=True)
class Configuration:
    """Connection options for automatic flow control and resource limits.

    Values are validated when the configuration is used to create a
    ``Connection``.

    Attributes:
        auto_window_update: Whether to generate receive-side WINDOW_UPDATE
            frames automatically. Disable this when consumption is tracked by
            the application.
        peer_max_concurrent_streams: Maximum concurrent streams assumed until
            the peer's first SETTINGS frame arrives. Must fit an unsigned
            32-bit integer.
        max_reserved_remote_streams: Maximum remotely reserved streams retained
            by a client connection. Must fit an unsigned 32-bit integer.
        max_send_header_block_length: Maximum outbound header block length as
            estimated before HPACK encoding. Must be non-negative.
        max_deflate_dynamic_table_size: Maximum HPACK dynamic table size used
            to encode outbound headers. Must be non-negative.
        max_outbound_ack: Maximum queued SETTINGS and PING acknowledgements
            before the connection is closed. Must be non-negative.
        max_settings: Maximum entries accepted in one SETTINGS frame. Must be
            non-negative.
        stream_reset_rate_limit: Token-bucket ``(burst, rate)`` for incoming
            RST_STREAM frames on server connections. Each value must fit an
            unsigned 64-bit integer.
        max_continuations: Maximum CONTINUATION frames accepted after one
            header frame. Must be non-negative.
        glitch_rate_limit: Token-bucket ``(burst, rate)`` for suspicious peer
            activity. Each value must fit an unsigned 64-bit integer.
        max_inbound_header_list_size: Maximum decoded header-list size retained
            for one received block, including the RFC 9113 per-field overhead.
            Must be non-negative.
        max_inbound_header_count: Maximum fields retained for one received
            header block. Must be non-negative.
    """

    auto_window_update: bool = True
    peer_max_concurrent_streams: int = 100
    max_reserved_remote_streams: int = 200
    max_send_header_block_length: int = 65_536
    max_deflate_dynamic_table_size: int = 4_096
    max_outbound_ack: int = 1_000
    max_settings: int = 32
    stream_reset_rate_limit: tuple[int, int] = (1_000, 33)
    max_continuations: int = 8
    glitch_rate_limit: tuple[int, int] = (10_000, 330)
    max_inbound_header_list_size: int = 65_536
    max_inbound_header_count: int = 1_024
