# cython: embedsignature=True, freethreading_compatible=True, language_level=3

from libc.stdint cimport uint32_t


cdef class Event:
    """Base type for events produced during HTTP/2 protocol processing."""

    __match_args__ = ()

    def __repr__(self):
        """Return a representation containing the public event fields."""
        names = type(self).__match_args__
        fields = ", ".join(
            f"{name}={getattr(self, name)!r}"
            for name in names
        )
        return f"{type(self).__name__}({fields})"


cdef class RequestReceived(Event):
    """A complete request header block was received.

    Attributes:
        stream_id: Stream carrying the request.
        headers: Decoded request fields in wire order.
        end_stream: Whether the peer ended its sending direction.
    """

    __match_args__ = ("stream_id", "headers", "end_stream")

    cdef readonly int stream_id
    cdef readonly tuple headers
    cdef readonly bint end_stream

    def __init__(self, int stream_id, tuple headers, bint end_stream):
        self.stream_id = stream_id
        self.headers = headers
        self.end_stream = end_stream


cdef class ResponseReceived(Event):
    """A complete final response header block was received.

    Attributes:
        stream_id: Stream carrying the response.
        headers: Decoded response fields in wire order.
        end_stream: Whether the peer ended its sending direction.
    """

    __match_args__ = ("stream_id", "headers", "end_stream")

    cdef readonly int stream_id
    cdef readonly tuple headers
    cdef readonly bint end_stream

    def __init__(self, int stream_id, tuple headers, bint end_stream):
        self.stream_id = stream_id
        self.headers = headers
        self.end_stream = end_stream


cdef class InformationalResponseReceived(Event):
    """A 1xx response other than the forbidden 101 response was received.

    Attributes:
        stream_id: Stream carrying the response.
        headers: Decoded informational response fields.
    """

    __match_args__ = ("stream_id", "headers")

    cdef readonly int stream_id
    cdef readonly tuple headers

    def __init__(self, int stream_id, tuple headers):
        self.stream_id = stream_id
        self.headers = headers


cdef class TrailersReceived(Event):
    """A trailing header block was received for a stream.

    Attributes:
        stream_id: Stream carrying the trailers.
        headers: Decoded trailer fields.
    """

    __match_args__ = ("stream_id", "headers")

    cdef readonly int stream_id
    cdef readonly tuple headers

    def __init__(self, int stream_id, tuple headers):
        self.stream_id = stream_id
        self.headers = headers


cdef class PushedStreamReceived(Event):
    """A server reserved a stream with a PUSH_PROMISE frame.

    Attributes:
        stream_id: Existing stream associated with the promise.
        promised_stream_id: Newly reserved stream.
        headers: Decoded promised request fields.
    """

    __match_args__ = ("stream_id", "promised_stream_id", "headers")

    cdef readonly int stream_id
    cdef readonly int promised_stream_id
    cdef readonly tuple headers

    def __init__(self, int stream_id, int promised_stream_id, tuple headers):
        self.stream_id = stream_id
        self.promised_stream_id = promised_stream_id
        self.headers = headers


cdef class DataReceived(Event):
    """One complete DATA frame payload was received.

    Attributes:
        stream_id: Stream carrying the payload.
        data: Application data, excluding frame padding.
        end_stream: Whether the peer ended its sending direction.
    """

    __match_args__ = (
        "stream_id",
        "data",
        "end_stream",
    )

    cdef readonly int stream_id
    cdef readonly bytes data
    cdef readonly bint end_stream

    def __init__(
        self,
        int stream_id,
        bytes data,
        bint end_stream,
    ):
        self.stream_id = stream_id
        self.data = data
        self.end_stream = end_stream


cdef class StreamReset(Event):
    """The peer sent RST_STREAM for a stream.

    Attributes:
        stream_id: Reset stream.
        error_code: Wire error code supplied by the peer.
    """

    __match_args__ = ("stream_id", "error_code")

    cdef readonly int stream_id
    cdef readonly uint32_t error_code

    def __init__(self, int stream_id, uint32_t error_code):
        self.stream_id = stream_id
        self.error_code = error_code


cdef class StreamClosed(Event):
    """The HTTP/2 state machine closed a stream.

    Attributes:
        stream_id: Closed stream.
        error_code: Wire reason, including zero for ordinary completion.
    """

    __match_args__ = ("stream_id", "error_code")

    cdef readonly int stream_id
    cdef readonly uint32_t error_code

    def __init__(self, int stream_id, uint32_t error_code):
        self.stream_id = stream_id
        self.error_code = error_code


cdef class SettingsReceived(Event):
    """A non-acknowledgement SETTINGS frame was received.

    Attributes:
        settings: Received identifiers and values, including unknown IDs.
    """

    __match_args__ = ("settings",)

    cdef readonly dict settings

    def __init__(self, dict settings):
        self.settings = settings


cdef class SettingsAcknowledged(Event):
    """The peer acknowledged the oldest outstanding local SETTINGS frame."""


cdef class PingReceived(Event):
    """A PING request was received; its acknowledgement is automatic.

    Attributes:
        opaque_data: Eight bytes supplied by the peer.
    """

    __match_args__ = ("opaque_data",)

    cdef readonly bytes opaque_data

    def __init__(self, bytes opaque_data):
        self.opaque_data = opaque_data


cdef class PingAcknowledged(Event):
    """The peer acknowledged a PING payload.

    Attributes:
        opaque_data: Eight bytes echoed by the peer.
    """

    __match_args__ = ("opaque_data",)

    cdef readonly bytes opaque_data

    def __init__(self, bytes opaque_data):
        self.opaque_data = opaque_data


cdef class WindowUpdated(Event):
    """The peer increased a stream or connection send window.

    Attributes:
        stream_id: Updated stream, or zero for connection scope.
        increment: Positive window increment from the frame.
    """

    __match_args__ = ("stream_id", "increment")

    cdef readonly int stream_id
    cdef readonly int increment

    def __init__(self, int stream_id, int increment):
        self.stream_id = stream_id
        self.increment = increment


cdef class GoAwayReceived(Event):
    """The peer began or completed connection shutdown with GOAWAY.

    Attributes:
        last_stream_id: Last local stream the peer may have processed.
        error_code: Wire shutdown reason.
        debug_data: Opaque diagnostics supplied by the peer.
    """

    __match_args__ = ("last_stream_id", "error_code", "debug_data")

    cdef readonly int last_stream_id
    cdef readonly uint32_t error_code
    cdef readonly bytes debug_data

    def __init__(self, int last_stream_id, uint32_t error_code, bytes debug_data):
        self.last_stream_id = last_stream_id
        self.error_code = error_code
        self.debug_data = debug_data


cdef class AltSvcReceived(Event):
    """An RFC 7838 alternative service advertisement was received.

    Attributes:
        stream_id: Associated stream, or zero for origin scope.
        origin: Advertised origin for connection-level advertisements.
        field_value: Raw Alt-Svc field value.
    """

    __match_args__ = ("stream_id", "origin", "field_value")

    cdef readonly int stream_id
    cdef readonly bytes origin
    cdef readonly bytes field_value

    def __init__(self, int stream_id, bytes origin, bytes field_value):
        self.stream_id = stream_id
        self.origin = origin
        self.field_value = field_value


cdef class OriginReceived(Event):
    """An RFC 8336 authoritative-origin advertisement was received.

    Attributes:
        origins: Origins for which the connection claims authority.
    """

    __match_args__ = ("origins",)

    cdef readonly tuple origins

    def __init__(self, tuple origins):
        self.origins = origins


cdef class PriorityUpdateReceived(Event):
    """An RFC 9218 priority field value was received for a stream.

    Attributes:
        prioritized_stream_id: Stream targeted by the update.
        field_value: Raw Priority field value.
    """

    __match_args__ = ("prioritized_stream_id", "field_value")

    cdef readonly int prioritized_stream_id
    cdef readonly bytes field_value

    def __init__(self, int prioritized_stream_id, bytes field_value):
        self.prioritized_stream_id = prioritized_stream_id
        self.field_value = field_value


cdef class FrameNotSent(Event):
    """A queued non-DATA frame failed during preparation.

    Attributes:
        stream_id: Associated stream, or zero for connection frames.
        frame_type: Type of frame that could not be sent.
        error: Exception describing why the frame could not be prepared.
    """

    __match_args__ = ("stream_id", "frame_type", "error")

    cdef readonly int stream_id
    cdef readonly object frame_type
    cdef readonly object error

    def __init__(self, int stream_id, object frame_type, object error):
        self.stream_id = stream_id
        self.frame_type = frame_type
        self.error = error
