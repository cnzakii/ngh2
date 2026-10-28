class NGH2Error(Exception):
    """Base class for ngh2-specific operational and protocol errors."""


class ConnectionStateError(NGH2Error):
    """Raised when a call is invalid for the connection's role or state."""


class ConnectionClosingError(ConnectionStateError):
    """Raised when connection shutdown prevents a new operation."""


class NoAvailableStreamIDError(ConnectionStateError):
    """Raised when no local stream identifier remains available."""


class StreamStateError(NGH2Error):
    """Raised when a call is invalid for one stream's current state."""


class StreamUnavailableError(StreamStateError):
    """Raised when an operation cannot use the requested stream."""


class PushDisabledError(StreamStateError):
    """Raised when the peer does not permit server push."""


class ProtocolError(NGH2Error):
    """Base class for violations of HTTP/2 protocol rules."""


class ConnectionProtocolError(ProtocolError):
    """Raised when a protocol violation affects the entire connection."""


class StreamProtocolError(ProtocolError):
    """Raised when a protocol violation affects one stream."""


class DenialOfServiceError(ConnectionProtocolError):
    """Raised when peer input exceeds a configured resource limit."""


class InternalError(NGH2Error):
    """Raised when the HTTP/2 engine encounters an internal failure."""
