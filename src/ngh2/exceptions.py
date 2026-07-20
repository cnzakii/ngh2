class NGH2Error(Exception):
    """Base class for ngh2-specific operational and protocol errors."""


class ConnectionStateError(NGH2Error):
    """Raised when an operation is invalid in the connection's current state."""


class ProtocolError(NGH2Error):
    """Base class for HTTP/2 protocol errors."""


class ConnectionProtocolError(ProtocolError):
    """Raised when an error affects the entire connection."""


class StreamProtocolError(ProtocolError):
    """Raised when an error affects one stream."""


class DenialOfServiceError(ConnectionProtocolError):
    """Raised when peer input exceeds a configured resource limit."""


class StreamUnavailableError(StreamProtocolError):
    """Raised when an operation cannot use the requested stream."""


class PushDisabledError(StreamProtocolError):
    """Raised when the peer does not permit server push."""


class ConnectionClosingError(NGH2Error):
    """Raised when connection shutdown prevents a new operation."""


class NoAvailableStreamIDError(NGH2Error):
    """Raised when no local stream identifier remains available."""


class InternalError(NGH2Error):
    """Raised when the HTTP/2 engine encounters an internal failure."""
