from enum import IntEnum


class Setting(IntEnum):
    """Parameters exchanged in an HTTP/2 SETTINGS frame.

    See RFC 9113, section 6.5.2:
    https://www.rfc-editor.org/rfc/rfc9113.html#section-6.5.2

    Attributes:
        HEADER_TABLE_SIZE: Maximum HPACK decoder table size the sender
            permits.
        ENABLE_PUSH: Whether the recipient permits server push.
        MAX_CONCURRENT_STREAMS: Advisory maximum number of concurrent
            peer-initiated streams.
        INITIAL_WINDOW_SIZE: Initial flow-control window for newly
            created streams.
        MAX_FRAME_SIZE: Largest frame payload the sender accepts.
        MAX_HEADER_LIST_SIZE: Advisory maximum size of a decoded header
            list.
        ENABLE_CONNECT_PROTOCOL: Whether the recipient permits the
            extended CONNECT protocol.
        NO_RFC7540_PRIORITIES: Whether RFC 7540 priority signaling
            should be disabled.
    """

    HEADER_TABLE_SIZE = 0x01
    ENABLE_PUSH = 0x02
    MAX_CONCURRENT_STREAMS = 0x03
    INITIAL_WINDOW_SIZE = 0x04
    MAX_FRAME_SIZE = 0x05
    MAX_HEADER_LIST_SIZE = 0x06
    ENABLE_CONNECT_PROTOCOL = 0x08
    NO_RFC7540_PRIORITIES = 0x09


class ErrorCode(IntEnum):
    """Reasons carried by RST_STREAM and GOAWAY frames.

    See RFC 9113, section 7:
    https://www.rfc-editor.org/rfc/rfc9113.html#section-7

    Attributes:
        NO_ERROR: Graceful shutdown or ordinary stream completion.
        PROTOCOL_ERROR: A protocol rule was violated.
        INTERNAL_ERROR: The endpoint encountered an unexpected internal
            failure.
        FLOW_CONTROL_ERROR: A flow-control rule was violated.
        SETTINGS_TIMEOUT: A SETTINGS acknowledgement was not received
            in time.
        STREAM_CLOSED: A frame was received for a closed stream.
        FRAME_SIZE_ERROR: A frame had an invalid payload size.
        REFUSED_STREAM: The stream was refused before application
            processing.
        CANCEL: The stream is no longer needed.
        COMPRESSION_ERROR: HPACK state could not be maintained or
            decoded.
        CONNECT_ERROR: An extended CONNECT tunnel could not be
            established.
        ENHANCE_YOUR_CALM: The peer's behavior exceeded an endpoint-
            defined limit.
        INADEQUATE_SECURITY: The negotiated transport security is
            insufficient.
        HTTP_1_1_REQUIRED: HTTP/1.1 is required for this request.
    """

    NO_ERROR = 0x00
    PROTOCOL_ERROR = 0x01
    INTERNAL_ERROR = 0x02
    FLOW_CONTROL_ERROR = 0x03
    SETTINGS_TIMEOUT = 0x04
    STREAM_CLOSED = 0x05
    FRAME_SIZE_ERROR = 0x06
    REFUSED_STREAM = 0x07
    CANCEL = 0x08
    COMPRESSION_ERROR = 0x09
    CONNECT_ERROR = 0x0A
    ENHANCE_YOUR_CALM = 0x0B
    INADEQUATE_SECURITY = 0x0C
    HTTP_1_1_REQUIRED = 0x0D
