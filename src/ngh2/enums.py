from enum import IntEnum


class Setting(IntEnum):
    """Parameters exchanged in an HTTP/2 SETTINGS frame.

    See RFC 9113, section 6.5.2:
    https://www.rfc-editor.org/rfc/rfc9113.html#section-6.5.2
    """

    # Maximum HPACK decoder table size the sender permits.
    HEADER_TABLE_SIZE = 0x01
    # Whether the recipient permits server push.
    ENABLE_PUSH = 0x02
    # Advisory maximum number of concurrent peer-initiated streams.
    MAX_CONCURRENT_STREAMS = 0x03
    # Initial flow-control window for newly created streams.
    INITIAL_WINDOW_SIZE = 0x04
    # Largest frame payload the sender accepts.
    MAX_FRAME_SIZE = 0x05
    # Advisory maximum size of a decoded header list.
    MAX_HEADER_LIST_SIZE = 0x06
    # Whether the recipient permits the extended CONNECT protocol.
    ENABLE_CONNECT_PROTOCOL = 0x08
    # Whether RFC 7540 priority signaling should be disabled.
    NO_RFC7540_PRIORITIES = 0x09


class ErrorCode(IntEnum):
    """Reasons carried by RST_STREAM and GOAWAY frames.

    See RFC 9113, section 7:
    https://www.rfc-editor.org/rfc/rfc9113.html#section-7
    """

    # Graceful shutdown or ordinary stream completion.
    NO_ERROR = 0x00
    # A protocol rule was violated.
    PROTOCOL_ERROR = 0x01
    # The endpoint encountered an unexpected internal failure.
    INTERNAL_ERROR = 0x02
    # A flow-control rule was violated.
    FLOW_CONTROL_ERROR = 0x03
    # A SETTINGS acknowledgement was not received in time.
    SETTINGS_TIMEOUT = 0x04
    # A frame was received for a closed stream.
    STREAM_CLOSED = 0x05
    # A frame had an invalid payload size.
    FRAME_SIZE_ERROR = 0x06
    # The stream was refused before application processing.
    REFUSED_STREAM = 0x07
    # The stream is no longer needed.
    CANCEL = 0x08
    # HPACK state could not be maintained or decoded.
    COMPRESSION_ERROR = 0x09
    # An extended CONNECT tunnel could not be established.
    CONNECT_ERROR = 0x0A
    # The peer's behavior exceeded an endpoint-defined limit.
    ENHANCE_YOUR_CALM = 0x0B
    # The negotiated transport security is insufficient.
    INADEQUATE_SECURITY = 0x0C
    # HTTP/1.1 is required for this request.
    HTTP_1_1_REQUIRED = 0x0D


class FrameType(IntEnum):
    """Values in the frame header's type field.

    Core frame types are defined by RFC 9113, section 11.2. Extension
    frame types are maintained in the IANA HTTP/2 Frame Type registry:
    https://www.iana.org/assignments/http2-parameters/http2-parameters.xhtml
    """

    # Carries stream body octets.
    DATA = 0x00
    # Opens a stream or carries a header block.
    HEADERS = 0x01
    # Carries the deprecated RFC 7540 priority signal.
    PRIORITY = 0x02
    # Terminates one stream with an error code.
    RST_STREAM = 0x03
    # Exchanges connection parameters or acknowledges them.
    SETTINGS = 0x04
    # Reserves a server-push stream.
    PUSH_PROMISE = 0x05
    # Measures liveness or acknowledges a probe.
    PING = 0x06
    # Begins graceful or error-driven connection shutdown.
    GOAWAY = 0x07
    # Increases a connection or stream flow-control window.
    WINDOW_UPDATE = 0x08
    # Continues a header block fragmented across frames.
    CONTINUATION = 0x09
    # Advertises an alternative service (RFC 7838).
    ALTSVC = 0x0A
    # Advertises authoritative origins (RFC 8336).
    ORIGIN = 0x0C
    # Updates extensible priority parameters (RFC 9218).
    PRIORITY_UPDATE = 0x10
