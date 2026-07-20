# cython: embedsignature=True, freethreading_compatible=True, language_level=3

from cpython.bytearray cimport (
    PyByteArray_AS_STRING,
    PyByteArray_GET_SIZE,
    PyByteArray_Resize,
)
from cpython.buffer cimport (
    PyBUF_CONTIG_RO,
    Py_buffer,
    PyBuffer_Release,
    PyObject_GetBuffer,
)
from cpython.bytes cimport PyBytes_AS_STRING, PyBytes_FromStringAndSize
from collections import deque
from libc.stdint cimport int32_t, uint8_t, uint32_t, uint64_t
from libc.stdlib cimport free, malloc
from libc.string cimport memcpy

from . cimport _nghttp2

from .config import Configuration, Role
from .enums import FrameType
from .events import (
    AltSvcReceived,
    DataReceived,
    FrameNotSent,
    GoAwayReceived,
    InformationalResponseReceived,
    OriginReceived,
    PingAcknowledged,
    PingReceived,
    PriorityUpdateReceived,
    PushedStreamReceived,
    RequestReceived,
    ResponseReceived,
    SettingsAcknowledged,
    SettingsReceived,
    StreamClosed,
    StreamReset,
    TrailersReceived,
    WindowUpdated,
)
from .exceptions import (
    ConnectionClosingError,
    ConnectionProtocolError,
    ConnectionStateError,
    DenialOfServiceError,
    InternalError,
    NGH2Error,
    NoAvailableStreamIDError,
    PushDisabledError,
    StreamProtocolError,
    StreamUnavailableError,
)
from .types import NeverIndexedHeader, Priority


_DEFAULT_PING_OPAQUE_DATA = bytes(8)


def pack_settings_payload(settings):
    """Serialize settings for the h2c ``HTTP2-Settings`` header.

    Each setting is encoded as a two-byte identifier followed by a four-byte
    value. The returned payload is not base64url encoded; the HTTP/1.1 layer
    is responsible for that encoding before placing it in the header.

    Args:
        settings: Mapping of HTTP/2 setting identifiers to values.

    Returns:
        The binary HTTP2-Settings payload.

    Raises:
        TypeError: If the input is not an integer mapping.
        ValueError: If an identifier or value is invalid.
    """
    cdef list entries = _normalize_settings(settings)
    cdef size_t count = len(entries)
    cdef _nghttp2.nghttp2_settings_entry *native_entries = NULL
    cdef bytearray output = bytearray(count * 6)
    cdef _nghttp2.nghttp2_ssize result

    if not count:
        return b""

    native_entries = _make_settings(entries)
    try:
        result = _nghttp2.nghttp2_pack_settings_payload2(
            <uint8_t *>PyByteArray_AS_STRING(output),
            len(output), native_entries, count,
        )
    finally:
        free(native_entries)

    if result < 0:
        _raise_nghttp2_error(result)

    return bytes(output[:result])


cdef class _BodySource:
    cdef object chunks
    cdef Py_ssize_t offset
    cdef size_t pending
    cdef bint ended
    cdef bint deferred
    cdef object trailers

    def __cinit__(self):
        self.chunks = deque()
        self.offset = 0
        self.pending = 0
        self.ended = False
        self.deferred = False
        self.trailers = None


cdef class Connection:
    """One client or server endpoint's HTTP/2 protocol state.

    Drive an individual connection from one thread or task at a time. Separate
    connections may be driven concurrently.

    Args:
        role: The local endpoint's role.
        config: Connection behavior and resource limits.

    Attributes:
        role: The immutable local endpoint role.
        config: The immutable connection configuration.

    Raises:
        TypeError: If ``role`` or ``config`` has the wrong type.
        ValueError: If a resource limit is negative.
        OverflowError: If a configuration value exceeds its supported range.
        MemoryError: If the HTTP/2 connection state cannot be allocated.
    """

    cdef readonly object role
    cdef readonly object config
    cdef _nghttp2.nghttp2_session *_session
    cdef bytearray _output
    cdef Py_ssize_t _output_remaining
    cdef object _callback_error
    cdef bint _initialized
    cdef bint _active
    cdef bint _failed
    cdef bint _local_extensible_priority
    cdef list _events
    cdef dict _bodies
    cdef size_t _pending_data
    cdef list _current_headers
    cdef size_t _current_header_size
    cdef dict _data_chunks
    cdef set _responses
    cdef dict _unacknowledged

    def __cinit__(self):
        self._session = NULL
        self._output = bytearray()
        self._output_remaining = 0
        self._callback_error = None
        self._initialized = False
        self._active = False
        self._failed = False
        self._local_extensible_priority = False
        self._events = []
        self._bodies = {}
        self._pending_data = 0
        self._current_headers = []
        self._current_header_size = 0
        self._data_chunks = {}
        self._responses = set()
        self._unacknowledged = {}

    def __init__(self, role, config=None):
        cdef _nghttp2.nghttp2_session_callbacks *callbacks = NULL
        cdef _nghttp2.nghttp2_option *option = NULL
        cdef _nghttp2.nghttp2_session *session = NULL
        cdef int result

        if self._initialized:
            raise ConnectionStateError("Connection is already initialized")
        if not isinstance(role, Role):
            raise TypeError("role must be a Role")
        if config is None:
            config = Configuration()
        elif not isinstance(config, Configuration):
            raise TypeError("config must be a Configuration")

        result = _nghttp2.nghttp2_session_callbacks_new(&callbacks)
        if result < 0:
            _raise_nghttp2_error(result)

        try:
            _configure_callbacks(callbacks)
            result = _nghttp2.nghttp2_option_new(&option)
            if result < 0:
                _raise_nghttp2_error(result)
            _apply_configuration(option, config)

            if role is Role.CLIENT:
                result = _nghttp2.nghttp2_session_client_new2(
                    &session, callbacks, <void *>self, option,
                )
            else:
                result = _nghttp2.nghttp2_session_server_new2(
                    &session, callbacks, <void *>self, option,
                )
            if result < 0:
                _raise_nghttp2_error(result)
        finally:
            _nghttp2.nghttp2_option_del(option)
            _nghttp2.nghttp2_session_callbacks_del(callbacks)

        self.role = role
        self.config = config
        self._session = session
        self._initialized = True

    def __dealloc__(self):
        if self._session != NULL:
            _nghttp2.nghttp2_session_del(self._session)

    def initiate_connection(self, settings=None):
        """Submit the initial SETTINGS frame.

        Args:
            settings: Optional mapping of setting identifiers to values.

        Raises:
            ConnectionStateError: If the connection is already initiated or failed.
            TypeError: If settings are not an integer mapping.
            ValueError: If settings are invalid or exceed the configured limit.
        """
        cdef list entries
        cdef _nghttp2.nghttp2_settings_entry *native_entries = NULL
        cdef size_t count
        cdef int result

        self._require_created()
        entries = _normalize_settings(settings)
        if len(entries) > self.config.max_settings:
            raise ValueError("settings exceed the configured entry limit")
        count = len(entries)
        if count:
            native_entries = _make_settings(entries)
        try:
            result = _nghttp2.nghttp2_submit_settings(
                self._session, _nghttp2.NGHTTP2_FLAG_NONE,
                native_entries, count,
            )
        finally:
            free(native_entries)
        if result < 0:
            self._raise_native_error(result)

        self._local_extensible_priority = (9, 1) in entries
        self._active = True

    def initiate_upgrade(
        self,
        settings_payload,
        *,
        local_settings=None,
        head_request=False,
    ):
        """Initialize a connection after an HTTP/1.1 h2c upgrade.

        Args:
            settings_payload: Decoded HTTP2-Settings binary payload.
            local_settings: Server settings to send after accepting the upgrade.
            head_request: Whether the upgraded request used the HEAD method.

        Raises:
            ConnectionStateError: If the connection was already initiated or failed.
            TypeError: If an argument has the wrong type.
            ValueError: If the settings payload is malformed.
        """
        cdef bytes payload
        cdef list entries = []
        cdef _nghttp2.nghttp2_settings_entry *native_entries = NULL
        cdef size_t count = 0
        cdef const uint8_t *pointer = NULL
        cdef int result

        self._require_created()
        if self.role is Role.CLIENT and local_settings is not None:
            raise ValueError("client upgrade does not accept local_settings")

        if self.role is Role.SERVER:
            entries = _normalize_settings(local_settings)
            if len(entries) > self.config.max_settings:
                raise ValueError("settings exceed the configured entry limit")
            count = len(entries)
            if count:
                native_entries = _make_settings(entries)

        payload = settings_payload
        if payload:
            pointer = <const uint8_t *>PyBytes_AS_STRING(payload)

        result = _nghttp2.nghttp2_session_upgrade2(
            self._session, pointer, len(payload), head_request, NULL,
        )
        if result < 0:
            free(native_entries)
            self._raise_native_error(result)

        if self.role is Role.SERVER:
            try:
                result = _nghttp2.nghttp2_submit_settings(
                    self._session,
                    _nghttp2.NGHTTP2_FLAG_NONE,
                    native_entries,
                    count,
                )
            finally:
                free(native_entries)
            if result < 0:
                self._fail()
                raise _nghttp2_error(result)
            self._local_extensible_priority = (9, 1) in entries

        self._active = True

    def receive_data(self, data):
        """Process bytes received from the peer.

        Args:
            data: A contiguous bytes-like object.

        Raises:
            ConnectionStateError: If the connection is not active or has failed.
            TypeError: If ``data`` is not bytes-like.
            BufferError: If ``data`` is not contiguous.
            ConnectionProtocolError: If peer input fatally violates HTTP/2.
            DenialOfServiceError: If peer input exceeds a resource limit.
        """
        cdef Py_buffer view
        cdef size_t length
        cdef _nghttp2.nghttp2_ssize result

        self._require_active()
        PyObject_GetBuffer(data, &view, PyBUF_CONTIG_RO)

        try:
            length = view.len
            self._callback_error = None
            result = _nghttp2.nghttp2_session_mem_recv2(
                self._session, <const uint8_t *>view.buf, length,
            )
        finally:
            PyBuffer_Release(&view)

        self._raise_callback_or_native(result)
        if result != <_nghttp2.nghttp2_ssize>length:
            self._fail()
            raise InternalError("HTTP/2 engine did not consume all input")

    def events(self):
        """Return and clear events produced while processing protocol actions.

        Events can be produced by ``initiate_upgrade()``, ``receive_data()``,
        and ``data_to_send()``.

        Returns:
            Events in protocol order.
        """
        result = self._events
        self._events = []
        return result

    def data_to_send(self, amount=None):
        """Return bytes currently ready for a network transport.

        Args:
            amount: Maximum bytes to return, or ``None`` for no limit.

        Returns:
            Serialized bytes ready for a transport. Before initialization or
            when no output is schedulable, returns ``b""``.

        Raises:
            TypeError: If ``amount`` is not an integer or ``None``.
            ValueError: If ``amount`` is negative.
            ConnectionStateError: If the connection has failed.
            MemoryError: If output staging cannot be allocated.
        """
        cdef Py_ssize_t limit
        cdef int result

        if self._failed:
            raise ConnectionStateError("Connection is no longer usable")

        if amount is None:
            limit = -1
        else:
            limit = _nonnegative_size(amount, "amount")
            if limit == 0:
                return b""

        if not self._active:
            return b""

        self._output = bytearray()
        self._output_remaining = limit
        self._callback_error = None
        result = _nghttp2.nghttp2_session_send(self._session)
        self._output_remaining = 0
        self._raise_callback_or_native(result)
        return bytes(self._output)

    def send_request(self, headers, *, end_stream=False):
        """Queue request headers and create a client stream.

        Args:
            headers: Sequence of request fields in transmission order. The
                caller supplies the required pseudo-header fields and RFC
                9113-compliant values.
            end_stream: Whether the request has no body or trailers.

        Returns:
            The stream identifier allocated by the HTTP/2 state machine.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a server.
            ConnectionClosingError: If a new request cannot be created.
            NoAvailableStreamIDError: If stream identifiers are exhausted.
            TypeError: If headers or ``end_stream`` have invalid types.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef size_t count
        cdef _nghttp2.nghttp2_data_provider2 provider
        cdef _nghttp2.nghttp2_data_provider2 *provider_pointer = NULL
        cdef int32_t stream_id

        self._require_active()
        if self.role is not Role.CLIENT:
            raise ConnectionProtocolError("a server cannot send requests")
        if not _nghttp2.nghttp2_session_check_request_allowed(self._session):
            raise ConnectionClosingError(
                "the connection cannot create another request stream",
            )
        count = len(headers)
        native_headers = _make_headers(headers, count)
        if not end_stream:
            provider.read_callback = _read_body
            provider.source.ptr = NULL
            provider_pointer = &provider
        try:
            stream_id = _nghttp2.nghttp2_submit_request2(
                self._session, NULL, native_headers, count,
                provider_pointer, NULL,
            )
        finally:
            free(native_headers)
        if stream_id < 0:
            self._raise_native_error(stream_id)
        if not end_stream:
            self._bodies[stream_id] = _BodySource()
        return stream_id

    def send_response(self, stream_id, headers, *, end_stream=False):
        """Queue final response headers for a server stream.

        Args:
            stream_id: Stream receiving the response.
            headers: Sequence of final response fields in transmission order.
                The caller supplies ``:status`` and RFC 9113-compliant field
                values.
            end_stream: Whether the response has no body or trailers.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a client.
            StreamProtocolError: If a final response is already pending.
            StreamUnavailableError: If the stream cannot accept a response.
            TypeError: If headers, ``stream_id``, or ``end_stream`` are invalid.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef size_t count
        cdef _nghttp2.nghttp2_data_provider2 provider
        cdef _nghttp2.nghttp2_data_provider2 *provider_pointer = NULL
        cdef int result

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError("a client cannot send responses")
        stream_id = _stream_id(stream_id)
        if stream_id in self._responses:
            raise StreamProtocolError("a response is already pending")
        count = len(headers)
        native_headers = _make_headers(headers, count)
        if not end_stream:
            provider.read_callback = _read_body
            provider.source.ptr = NULL
            provider_pointer = &provider
        try:
            result = _nghttp2.nghttp2_submit_response2(
                self._session, stream_id, native_headers, count,
                provider_pointer,
            )
        finally:
            free(native_headers)
        if result < 0:
            self._raise_native_error(result)
        self._responses.add(stream_id)
        if not end_stream:
            self._bodies[stream_id] = _BodySource()

    def send_informational_response(self, stream_id, headers):
        """Queue an informational response on an existing stream.

        Args:
            stream_id: Stream receiving the response.
            headers: Sequence of informational response fields in transmission
                order. The caller supplies a valid 1xx ``:status`` and
                otherwise RFC 9113-compliant fields.

        Raises:
            ConnectionProtocolError: If called on a client.
            ConnectionStateError: If the connection is not active.
            StreamProtocolError: If a final response is already pending.
            TypeError: If headers or ``stream_id`` are invalid.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef size_t count
        cdef int32_t result

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError(
                "a client cannot send informational responses",
            )
        stream_id = _stream_id(stream_id)
        if stream_id in self._responses:
            raise StreamProtocolError(
                "informational responses must precede the final response",
            )

        count = len(headers)
        native_headers = _make_headers(headers, count)
        try:
            result = _nghttp2.nghttp2_submit_headers(
                self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
                NULL, native_headers, count, NULL,
            )
        finally:
            free(native_headers)
        if result < 0:
            self._raise_native_error(result)

    def send_trailers(self, stream_id, headers):
        """Queue trailers after all pending stream body bytes.

        Args:
            stream_id: Stream whose local direction will be ended.
            headers: Sequence of trailer fields in transmission order. The
                caller is responsible for omitting pseudo-headers and otherwise
                meeting RFC 9113 field requirements.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamProtocolError: If the stream has no open body or was ended.
            TypeError: If headers or ``stream_id`` are invalid.
        """
        cdef _BodySource body
        cdef list normalized
        cdef int result

        self._require_active()
        stream_id = _stream_id(stream_id)
        body = self._bodies.get(stream_id)
        if body is None:
            raise StreamProtocolError("stream has no open body")
        if body.ended:
            raise StreamProtocolError("stream body is already ended")
        normalized = _normalize_headers(headers)
        body.trailers = normalized
        body.ended = True
        if body.deferred:
            result = _nghttp2.nghttp2_session_resume_data(self._session, stream_id)
            if result < 0:
                self._raise_native_error(result)
            body.deferred = False

    def send_push_promise(self, stream_id, headers):
        """Queue a server push promise and reserve a stream.

        Args:
            stream_id: Existing request stream associated with the push.
            headers: Sequence of promised request fields. The caller supplies
                the required pseudo-header fields and RFC 9113-compliant values.

        Returns:
            The reserved promised stream identifier.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a client.
            StreamUnavailableError: If the associated stream is unavailable.
            TypeError: If headers or ``stream_id`` are invalid.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef size_t count
        cdef int32_t promised_stream_id

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError("a client cannot send push promises")
        stream_id = _stream_id(stream_id)
        count = len(headers)
        native_headers = _make_headers(headers, count)
        try:
            promised_stream_id = _nghttp2.nghttp2_submit_push_promise(
                self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
                native_headers, count, NULL,
            )
        finally:
            free(native_headers)
        if promised_stream_id < 0:
            self._raise_native_error(promised_stream_id)
        return promised_stream_id

    def send_data(self, stream_id, data, *, end_stream=False):
        """Queue body bytes for a stream.

        Args:
            stream_id: Stream whose body receives the bytes.
            data: Body bytes retained until they are serialized into DATA frames.
            end_stream: Whether these are the final body bytes.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamProtocolError: If the stream has no open body or already ended.
            TypeError: If ``data`` is not bytes-like.
        """
        cdef _BodySource body
        cdef bytes chunk
        cdef int result

        self._require_active()
        stream_id = _stream_id(stream_id)
        try:
            body = self._bodies[stream_id]
        except KeyError:
            raise StreamProtocolError("stream has no open body") from None
        if body.ended:
            raise StreamProtocolError("stream body is already ended")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be a bytes-like object")
        chunk = data if isinstance(data, bytes) else bytes(data)
        if chunk:
            body.chunks.append(chunk)
            body.pending += len(chunk)
            self._pending_data += len(chunk)
        body.ended = end_stream
        if body.deferred and (chunk or end_stream):
            result = _nghttp2.nghttp2_session_resume_data(self._session, stream_id)
            if result < 0:
                self._raise_native_error(result)
            body.deferred = False

    def end_stream(self, stream_id):
        """End a stream after all queued body bytes are consumed.

        Args:
            stream_id: Stream whose local sending direction should end.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamProtocolError: If the stream has no open body.
        """
        self.send_data(stream_id, b"", end_stream=True)

    def reset_stream(self, stream_id, error_code=0x08):
        """Queue an RST_STREAM frame.

        Args:
            stream_id: Stream to terminate.
            error_code: HTTP/2 wire error code.

        Raises:
            ConnectionStateError: If the connection is not active.
            TypeError: If an argument is not an integer.
            ValueError: If an argument is outside its wire range.
        """
        cdef int result

        self._require_active()
        stream_id = _stream_id(stream_id)
        error_code = _uint32(error_code, "error_code")
        result = _nghttp2.nghttp2_submit_rst_stream(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE,
            stream_id, error_code,
        )
        if result < 0:
            self._raise_native_error(result)

    def update_settings(self, settings):
        """Queue a SETTINGS update.

        Args:
            settings: Mapping of setting identifiers to unsigned values.

        Raises:
            ConnectionStateError: If the connection is not active.
            TypeError: If settings are not an integer mapping.
            ValueError: If values are invalid or the mapping is too large.
        """
        cdef list entries
        cdef _nghttp2.nghttp2_settings_entry *native_entries = NULL
        cdef size_t count
        cdef int result

        self._require_active()
        entries = _normalize_settings(settings)
        if len(entries) > self.config.max_settings:
            raise ValueError("settings exceed the configured entry limit")
        count = len(entries)
        if count:
            native_entries = _make_settings(entries)
        try:
            result = _nghttp2.nghttp2_submit_settings(
                self._session, _nghttp2.NGHTTP2_FLAG_NONE,
                native_entries, count,
            )
        finally:
            free(native_entries)
        if result < 0:
            self._raise_native_error(result)

    def ping(self, opaque_data=_DEFAULT_PING_OPAQUE_DATA):
        """Queue a PING frame with an eight-byte payload.

        Args:
            opaque_data: Exactly eight opaque bytes echoed by the peer.

        Raises:
            ConnectionStateError: If the connection is not active.
            TypeError: If ``opaque_data`` is not bytes.
            ValueError: If it is not exactly eight bytes long.
        """
        cdef bytes payload
        cdef int result

        self._require_active()
        payload = opaque_data
        if len(payload) != 8:
            raise ValueError("opaque_data must contain exactly 8 bytes")
        result = _nghttp2.nghttp2_submit_ping(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE,
            <const uint8_t *>PyBytes_AS_STRING(payload),
        )
        if result < 0:
            self._raise_native_error(result)

    def send_goaway(self, error_code=0, *, last_stream_id=None, debug_data=b""):
        """Queue a GOAWAY frame without closing the transport.

        Args:
            error_code: HTTP/2 wire error code.
            last_stream_id: Last peer stream that may have been processed.
            debug_data: Opaque diagnostic bytes copied into the frame.

        Raises:
            ConnectionStateError: If the connection is not active.
            TypeError: If an argument has the wrong type.
            ValueError: If an integer is outside its wire range.
        """
        cdef bytes payload
        cdef const uint8_t *pointer = NULL
        cdef int result

        self._require_active()
        error_code = _uint32(error_code, "error_code")
        if last_stream_id is None:
            last_stream_id = _nghttp2.nghttp2_session_get_last_proc_stream_id(
                self._session,
            )
        elif not 0 <= last_stream_id <= 0x7FFFFFFF:
            raise ValueError("last_stream_id is out of range")
        payload = debug_data
        if payload:
            pointer = <const uint8_t *>PyBytes_AS_STRING(payload)
        result = _nghttp2.nghttp2_submit_goaway(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE,
            last_stream_id, error_code, pointer, len(payload),
        )
        if result < 0:
            self._raise_native_error(result)

    def send_shutdown_notice(self):
        """Queue the first GOAWAY in a server graceful-shutdown sequence.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a client.
        """
        cdef int result

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError(
                "a client cannot send shutdown notices",
            )
        result = _nghttp2.nghttp2_submit_shutdown_notice(self._session)
        if result < 0:
            self._raise_native_error(result)

    def terminate_connection(self, error_code=0, *, last_stream_id=None):
        """Queue a final GOAWAY and terminate session processing.

        Args:
            error_code: HTTP/2 wire error code.
            last_stream_id: Optional final peer stream identifier.

        Raises:
            ConnectionStateError: If the connection is not active.
            TypeError: If an argument is not an integer.
            ValueError: If an argument is outside its wire range.
        """
        cdef int result

        self._require_active()
        error_code = _uint32(error_code, "error_code")
        if last_stream_id is None:
            result = _nghttp2.nghttp2_session_terminate_session(
                self._session, error_code,
            )
        else:
            if not 0 <= last_stream_id <= 0x7FFFFFFF:
                raise ValueError("last_stream_id is out of range")
            result = _nghttp2.nghttp2_session_terminate_session2(
                self._session, last_stream_id, error_code,
            )
        if result < 0:
            self._raise_native_error(result)

    def acknowledge_received_data(self, amount, stream_id):
        """Release manually consumed application data bytes.

        Args:
            amount: Application data bytes consumed, normally
                ``len(event.data)`` for a ``DataReceived`` event. Frame padding
                is consumed internally.
            stream_id: Stream that delivered those bytes.

        Raises:
            ConnectionStateError: If the connection is not active or automatic
                receive-window updates are enabled.
            TypeError: If ``amount`` or ``stream_id`` is not an integer.
            ValueError: If ``amount`` exceeds outstanding received data.
            StreamUnavailableError: If the stream cannot be acknowledged.
        """
        cdef int result

        self._require_active()
        if self.config.auto_window_update:
            raise ConnectionStateError(
                "manual acknowledgement requires auto_window_update=False",
            )
        stream_id = _stream_id(stream_id)
        amount = _nonnegative_size(amount, "amount")
        if amount == 0:
            return
        if amount > self._unacknowledged.get(stream_id, 0):
            raise ValueError("amount exceeds unacknowledged data")
        result = _nghttp2.nghttp2_session_consume(
            self._session, stream_id, amount,
        )
        if result < 0:
            self._raise_native_error(result)
        self._unacknowledged[stream_id] -= amount
        if self._unacknowledged[stream_id] == 0:
            del self._unacknowledged[stream_id]

    def send_priority_update(self, stream_id, field_value):
        """Queue an RFC 9218 PRIORITY_UPDATE frame from a client.

        Args:
            stream_id: Stream whose priority is updated.
            field_value: Raw RFC 9218 Priority field value.

        Returns:
            ``True`` when queued, or ``False`` after the peer has explicitly
            disabled extensible priority.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a server.
            TypeError: If ``field_value`` is not bytes.
        """
        cdef bytes value
        cdef int result

        self._require_active()
        if self.role is not Role.CLIENT:
            raise ConnectionProtocolError(
                "a server cannot send PRIORITY_UPDATE frames",
            )
        stream_id = _stream_id(stream_id)
        if _nghttp2.nghttp2_session_get_remote_settings(self._session, 9) == 0:
            return False
        value = field_value
        result = _nghttp2.nghttp2_submit_priority_update(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
            <const uint8_t *>PyBytes_AS_STRING(value), len(value),
        )
        if result < 0:
            self._raise_native_error(result)
        return True

    def set_stream_priority(self, stream_id, priority, *, ignore_client_signal=False):
        """Apply RFC 9218 scheduling parameters to a server stream.

        Args:
            stream_id: Existing stream to reschedule.
            priority: New urgency and incremental parameters.
            ignore_client_signal: Whether future client updates are ignored.

        Returns:
            ``True`` when applied, or ``False`` when local extensible priority
            has not been enabled.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a client.
            StreamUnavailableError: If the stream does not exist.
        """
        cdef _nghttp2.nghttp2_extpri native_priority
        cdef int result

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError(
                "a client cannot set server scheduling priority",
            )
        stream_id = _stream_id(stream_id)
        if not isinstance(priority, Priority):
            raise TypeError("priority must be a Priority")
        if not self._local_extensible_priority:
            return False

        self._require_stream(stream_id)
        native_priority.urgency = priority.urgency
        native_priority.inc = priority.incremental
        result = _nghttp2.nghttp2_session_change_extpri_stream_priority(
            self._session, stream_id, &native_priority, ignore_client_signal,
        )
        if result < 0:
            self._raise_native_error(result)
        return True

    def get_stream_priority(self, stream_id):
        """Return RFC 9218 priority for a server stream.

        Args:
            stream_id: Existing stream to query.

        Returns:
            Current priority, or ``None`` when extensible priority is disabled.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a client.
            StreamUnavailableError: If the stream does not exist.
        """
        cdef _nghttp2.nghttp2_extpri native_priority
        cdef int result

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError(
                "a client cannot query server scheduling priority",
            )
        stream_id = _stream_id(stream_id)
        if not self._local_extensible_priority:
            return None

        self._require_stream(stream_id)
        result = _nghttp2.nghttp2_session_get_extpri_stream_priority(
            self._session, &native_priority, stream_id,
        )
        if result < 0:
            self._raise_native_error(result)
        return Priority(native_priority.urgency, bool(native_priority.inc))

    def send_alt_svc(self, field_value, *, stream_id=0, origin=b""):
        """Queue an RFC 7838 ALTSVC frame from a server.

        Args:
            field_value: Raw Alt-Svc field value.
            stream_id: Associated stream, or zero for an origin advertisement.
            origin: Required origin for connection-level advertisements.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a client.
            TypeError: If byte fields or ``stream_id`` have wrong types.
            ValueError: If origin and stream scope are inconsistent.
        """
        cdef bytes value, origin_value
        cdef const uint8_t *origin_pointer = NULL
        cdef int result

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError("a client cannot send ALTSVC frames")
        if not 0 <= stream_id <= 0x7FFFFFFF:
            raise ValueError("stream_id is out of range")
        value = field_value
        origin_value = origin
        if origin_value:
            origin_pointer = <const uint8_t *>PyBytes_AS_STRING(origin_value)
        result = _nghttp2.nghttp2_submit_altsvc(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
            origin_pointer, len(origin_value),
            <const uint8_t *>PyBytes_AS_STRING(value), len(value),
        )
        if result < 0:
            self._raise_native_error(result)

    def send_origins(self, origins):
        """Queue an RFC 8336 ORIGIN frame from a server.

        Args:
            origins: Byte origins advertised by this connection.

        Raises:
            ConnectionStateError: If the connection is not active.
            ConnectionProtocolError: If called on a client.
            TypeError: If an origin is not bytes.
            ValueError: If the payload cannot fit in an HTTP/2 frame.
        """
        cdef list values
        cdef _nghttp2.nghttp2_origin_entry *native = NULL
        cdef size_t index, count
        cdef int result

        self._require_active()
        if self.role is not Role.SERVER:
            raise ConnectionProtocolError("a client cannot send ORIGIN frames")
        values = [bytes(value) for value in origins]
        count = len(values)
        if count:
            native = <_nghttp2.nghttp2_origin_entry *>malloc(
                count * sizeof(_nghttp2.nghttp2_origin_entry)
            )
            if native == NULL:
                raise MemoryError()
        try:
            for index in range(count):
                native[index].origin = <uint8_t *>PyBytes_AS_STRING(values[index])
                native[index].origin_len = len(values[index])
            result = _nghttp2.nghttp2_submit_origin(
                self._session, _nghttp2.NGHTTP2_FLAG_NONE, native, count,
            )
        finally:
            free(native)
        if result < 0:
            self._raise_native_error(result)

    @property
    def want_read(self):
        """Whether the session expects more peer input.

        Returns:
            ``True`` while reading may advance the connection.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return bool(_nghttp2.nghttp2_session_want_read(self._session))

    @property
    def want_write(self):
        """Whether the session has schedulable output.

        Returns:
            ``True`` while ``data_to_send()`` may advance output.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return bool(_nghttp2.nghttp2_session_want_write(self._session))

    @property
    def next_stream_id(self):
        """Return the next locally initiated stream ID.

        Returns:
            The next client or server stream identifier for this role.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return _nghttp2.nghttp2_session_get_next_stream_id(self._session)

    @property
    def can_send_request(self):
        """Whether a client request can currently be submitted.

        Returns:
            ``False`` after peer GOAWAY, shutdown, or ID exhaustion.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return bool(_nghttp2.nghttp2_session_check_request_allowed(self._session))

    def pending_data(self, stream_id=None):
        """Return queued body bytes not yet serialized into DATA frames.

        Args:
            stream_id: Stream to query, or ``None`` for the connection total.

        Returns:
            The exact number of queued application body bytes.

        Raises:
            TypeError: If ``stream_id`` is not an integer or ``None``.
            ValueError: If ``stream_id`` is outside its wire range.
        """
        cdef _BodySource body

        if stream_id is None:
            return self._pending_data

        stream_id = _stream_id(stream_id)
        body = self._bodies.get(stream_id)
        return 0 if body is None else body.pending

    @property
    def remote_window_size(self):
        """Return the connection-level outbound flow-control window.

        Returns:
            Bytes the peer currently permits at connection scope.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return _nghttp2.nghttp2_session_get_remote_window_size(self._session)

    def stream_remote_window_size(self, stream_id):
        """Return a stream's outbound flow-control window.

        Args:
            stream_id: Stream to query.

        Returns:
            Bytes the peer currently permits for the stream.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamUnavailableError: If the stream does not exist.
        """
        cdef int normalized_stream_id

        self._require_active()
        normalized_stream_id = _stream_id(stream_id)
        self._require_stream(normalized_stream_id)

        return _nghttp2.nghttp2_session_get_stream_remote_window_size(
            self._session, normalized_stream_id,
        )

    @property
    def local_window_size(self):
        """Return the connection-level inbound flow-control window.

        Returns:
            Bytes this endpoint currently permits at connection scope.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return _nghttp2.nghttp2_session_get_local_window_size(self._session)

    def stream_local_window_size(self, stream_id):
        """Return a stream's inbound flow-control window.

        Args:
            stream_id: Stream to query.

        Returns:
            Bytes this endpoint currently permits for the stream.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamUnavailableError: If the stream does not exist.
        """
        cdef int normalized_stream_id

        self._require_active()
        normalized_stream_id = _stream_id(stream_id)
        self._require_stream(normalized_stream_id)

        return _nghttp2.nghttp2_session_get_stream_local_window_size(
            self._session, normalized_stream_id,
        )

    @property
    def local_settings(self):
        """Return local SETTINGS values acknowledged by the peer.

        Before acknowledgement, ``NO_RFC7540_PRIORITIES`` is ``0xFFFFFFFF``
        to represent an unknown value.

        Returns:
            A new mapping containing known setting identifiers and values.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return _settings_snapshot(self._session, True)

    @property
    def remote_settings(self):
        """Return effective peer SETTINGS values.

        Before the peer's first SETTINGS, ``NO_RFC7540_PRIORITIES`` is
        ``0xFFFFFFFF`` to represent an unknown value.

        Returns:
            A new mapping containing known setting identifiers and values.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_active()
        return _settings_snapshot(self._session, False)

    cdef void _require_created(self) except *:
        """Require a usable connection that has not been initiated."""
        if self._failed:
            raise ConnectionStateError("Connection is no longer usable")
        if self._active:
            raise ConnectionStateError("Connection is already initiated")

    cdef void _require_active(self) except *:
        """Require an initiated, usable connection."""
        if self._failed:
            raise ConnectionStateError("Connection is no longer usable")
        if not self._active:
            raise ConnectionStateError("Connection is not initiated")

    cdef void _require_stream(self, int32_t stream_id) except *:
        """Require a stream that is still tracked by the HTTP/2 state machine."""
        if _nghttp2.nghttp2_session_get_stream_local_close(
            self._session,
            stream_id,
        ) < 0:
            raise StreamUnavailableError("stream does not exist")

    cdef void _raise_native_error(self, int error_code) except *:
        """Raise a translated error and invalidate the connection when fatal."""
        cdef object error = _nghttp2_error(error_code)

        if _nghttp2.nghttp2_is_fatal(error_code):
            self._fail()
        raise error

    cdef void _raise_callback_or_native(self, _nghttp2.nghttp2_ssize result) except *:
        """Raise a deferred callback error or translated engine error."""
        cdef object error

        if result >= 0:
            return

        error = self._callback_error
        if error is not None:
            self._fail()
            raise error
        error = _nghttp2_error(<int>result)
        if _nghttp2.nghttp2_is_fatal(<int>result):
            self._fail()
        raise error

    cdef void _fail(self):
        """Release all connection-owned state and permanently invalidate it."""
        if self._session != NULL:
            _nghttp2.nghttp2_session_del(self._session)
            self._session = NULL
        self._output.clear()
        self._output_remaining = 0
        self._callback_error = None
        self._bodies.clear()
        self._pending_data = 0
        self._current_headers.clear()
        self._current_header_size = 0
        self._data_chunks.clear()
        self._responses.clear()
        self._unacknowledged.clear()
        self._failed = True
        self._active = False


cdef void _configure_callbacks(
    _nghttp2.nghttp2_session_callbacks *callbacks,
):
    """Register the fixed callbacks used by every connection."""
    _nghttp2.nghttp2_session_callbacks_set_send_callback2(callbacks, _collect_output)
    _nghttp2.nghttp2_session_callbacks_set_on_begin_headers_callback(
        callbacks, _begin_headers,
    )
    _nghttp2.nghttp2_session_callbacks_set_on_header_callback(callbacks, _header)
    _nghttp2.nghttp2_session_callbacks_set_on_data_chunk_recv_callback(
        callbacks, _data_chunk,
    )
    _nghttp2.nghttp2_session_callbacks_set_on_frame_recv_callback(
        callbacks, _frame_received,
    )
    _nghttp2.nghttp2_session_callbacks_set_on_stream_close_callback(
        callbacks, _stream_closed,
    )
    _nghttp2.nghttp2_session_callbacks_set_on_frame_not_send_callback(
        callbacks, _frame_not_sent,
    )


cdef void _apply_configuration(_nghttp2.nghttp2_option *option, object config):
    """Validate binding limits and apply native session options."""
    cdef uint64_t reset_burst, reset_rate, glitch_burst, glitch_rate

    if config.max_inbound_header_list_size < 0:
        raise ValueError("max_inbound_header_list_size must be non-negative")
    if config.max_inbound_header_count < 0:
        raise ValueError("max_inbound_header_count must be non-negative")

    reset_burst, reset_rate = config.stream_reset_rate_limit
    glitch_burst, glitch_rate = config.glitch_rate_limit
    _nghttp2.nghttp2_option_set_no_auto_window_update(
        option, not config.auto_window_update,
    )
    _nghttp2.nghttp2_option_set_peer_max_concurrent_streams(
        option, config.peer_max_concurrent_streams,
    )
    _nghttp2.nghttp2_option_set_max_reserved_remote_streams(
        option, config.max_reserved_remote_streams,
    )
    _nghttp2.nghttp2_option_set_max_send_header_block_length(
        option, config.max_send_header_block_length,
    )
    _nghttp2.nghttp2_option_set_max_deflate_dynamic_table_size(
        option, config.max_deflate_dynamic_table_size,
    )
    _nghttp2.nghttp2_option_set_max_outbound_ack(option, config.max_outbound_ack)
    _nghttp2.nghttp2_option_set_max_settings(option, config.max_settings)
    _nghttp2.nghttp2_option_set_stream_reset_rate_limit(option, reset_burst, reset_rate)
    _nghttp2.nghttp2_option_set_max_continuations(option, config.max_continuations)
    _nghttp2.nghttp2_option_set_glitch_rate_limit(option, glitch_burst, glitch_rate)
    _nghttp2.nghttp2_option_set_builtin_recv_extension_type(
        option, _nghttp2.NGHTTP2_ALTSVC,
    )
    _nghttp2.nghttp2_option_set_builtin_recv_extension_type(
        option, _nghttp2.NGHTTP2_ORIGIN,
    )
    _nghttp2.nghttp2_option_set_builtin_recv_extension_type(
        option, _nghttp2.NGHTTP2_PRIORITY_UPDATE,
    )


cdef list _normalize_headers(object headers):
    """Copy a header sequence retained for deferred trailer submission."""
    cdef list result = []
    cdef object item
    cdef bytes name, value
    cdef Py_ssize_t index

    for index in range(len(headers)):
        item = headers[index]
        try:
            name, value = item
        except (TypeError, ValueError):
            raise TypeError("each header must be a pair of bytes") from None
        result.append(item if isinstance(item, tuple) else (name, value))
    return result


cdef _nghttp2.nghttp2_nv *_make_headers(
    object headers,
    size_t count,
) except NULL:
    """Build a temporary header array that borrows Python byte storage."""
    cdef _nghttp2.nghttp2_nv *native = NULL
    cdef size_t index
    cdef object header
    cdef bytes name, value

    # Cython uses NULL as this function's exception sentinel, so allocate one
    # unused entry for an empty sequence rather than returning an ambiguous NULL.
    native = <_nghttp2.nghttp2_nv *>malloc(
        (count if count else 1) * sizeof(_nghttp2.nghttp2_nv)
    )
    if native == NULL:
        raise MemoryError()
    try:
        for index in range(count):
            header = headers[index]
            try:
                name, value = header
            except (TypeError, ValueError):
                raise TypeError("each header must be a pair of bytes") from None
            native[index].name = <uint8_t *>PyBytes_AS_STRING(name)
            native[index].value = <uint8_t *>PyBytes_AS_STRING(value)
            native[index].namelen = len(name)
            native[index].valuelen = len(value)
            native[index].flags = (
                _nghttp2.NGHTTP2_NV_FLAG_NO_INDEX
                if isinstance(header, NeverIndexedHeader)
                else 0
            )
    except BaseException:
        free(native)
        raise
    return native


cdef list _normalize_settings(object settings):
    """Copy and validate a mapping of HTTP/2 setting identifiers and values."""
    cdef list result = []
    cdef object items
    cdef object key, value

    if settings is None:
        return result
    try:
        items = settings.items()
    except AttributeError:
        raise TypeError("settings must be a mapping") from None
    for key, value in items:
        if not 0 <= key <= 0xFFFF or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("setting identifiers or values are out of range")
        result.append((key, value))
    return result


cdef _nghttp2.nghttp2_settings_entry *_make_settings(list entries) except NULL:
    """Build a temporary settings array from validated integer pairs."""
    cdef size_t count = len(entries)
    cdef _nghttp2.nghttp2_settings_entry *native = NULL
    cdef size_t index

    if count:
        native = <_nghttp2.nghttp2_settings_entry *>malloc(
            count * sizeof(_nghttp2.nghttp2_settings_entry)
        )
        if native == NULL:
            raise MemoryError()
    for index in range(count):
        native[index].settings_id = entries[index][0]
        native[index].value = entries[index][1]
    return native


cdef int _stream_id(object value) except -1:
    """Validate and return a nonzero HTTP/2 stream identifier."""
    if value <= 0 or value > 0x7FFFFFFF:
        raise ValueError("stream_id is out of range")
    return value


cdef uint32_t _uint32(object value, str name) except *:
    """Validate and return an unsigned 32-bit integer."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"{name} is out of range")
    return value


cdef Py_ssize_t _nonnegative_size(object value, str name) except -1:
    """Validate and return a non-negative platform-sized integer."""
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    if value > ((<size_t>-1) >> 1):
        raise ValueError(f"{name} is too large for this platform")
    return value


cdef dict _settings_snapshot(_nghttp2.nghttp2_session *session, bint local):
    """Copy native local or peer SETTINGS values into a Python mapping."""
    cdef dict result = {}
    cdef int identifier

    for identifier in (1, 2, 3, 4, 5, 6, 8, 9):
        if local:
            result[identifier] = _nghttp2.nghttp2_session_get_local_settings(
                session, identifier,
            )
        else:
            result[identifier] = _nghttp2.nghttp2_session_get_remote_settings(
                session, identifier,
            )
    return result


cdef void _raise_nghttp2_error(int error_code) except *:
    """Raise the public exception corresponding to an engine error code."""
    raise _nghttp2_error(error_code)


cdef object _nghttp2_error(int error_code):
    """Translate a private library error code into a public exception."""
    cdef str message = _error_message(error_code)
    if error_code == _nghttp2.NGHTTP2_ERR_NOMEM:
        return MemoryError("HTTP/2 engine ran out of memory")
    if error_code == _nghttp2.NGHTTP2_ERR_STREAM_ID_NOT_AVAILABLE:
        return NoAvailableStreamIDError(message)
    if error_code in (
        _nghttp2.NGHTTP2_ERR_INVALID_STREAM_ID,
        _nghttp2.NGHTTP2_ERR_STREAM_CLOSED,
        _nghttp2.NGHTTP2_ERR_STREAM_CLOSING,
        _nghttp2.NGHTTP2_ERR_STREAM_SHUT_WR,
    ):
        return StreamUnavailableError(message)
    if error_code == _nghttp2.NGHTTP2_ERR_PUSH_DISABLED:
        return PushDisabledError(message)
    if error_code in (
        _nghttp2.NGHTTP2_ERR_START_STREAM_NOT_ALLOWED,
        _nghttp2.NGHTTP2_ERR_SESSION_CLOSING,
    ):
        return ConnectionClosingError(message)
    if error_code in (
        _nghttp2.NGHTTP2_ERR_DATA_EXIST,
        _nghttp2.NGHTTP2_ERR_DEFERRED_DATA_EXIST,
    ):
        return StreamProtocolError(message)
    if error_code == _nghttp2.NGHTTP2_ERR_BAD_CLIENT_MAGIC:
        return ConnectionProtocolError(message)
    if error_code in (
        _nghttp2.NGHTTP2_ERR_FLOODED,
        _nghttp2.NGHTTP2_ERR_TOO_MANY_CONTINUATIONS,
    ):
        return DenialOfServiceError(message)
    if error_code == _nghttp2.NGHTTP2_ERR_INVALID_ARGUMENT:
        return ValueError(message)
    return InternalError(message)


cdef object _frame_not_sent_error(int error_code):
    """Translate a delayed frame failure into the event error hierarchy."""
    error = _nghttp2_error(error_code)
    if isinstance(error, NGH2Error):
        return error
    return InternalError(str(error))


cdef str _error_message(int error_code):
    """Return the native diagnostic without exposing its numeric code."""
    description = _nghttp2.nghttp2_strerror(error_code).decode("ascii")
    return f"HTTP/2 engine error: {description}"


cdef int _callback_failed(Connection connection, object error) noexcept:
    """Defer a Python exception until control returns across the C ABI."""
    connection._callback_error = error
    return _nghttp2.NGHTTP2_ERR_CALLBACK_FAILURE


cdef _nghttp2.nghttp2_ssize _collect_output(
    _nghttp2.nghttp2_session *session,
    const uint8_t *data,
    size_t length,
    int flags,
    void *user_data,
) noexcept:
    """Append serialized bytes while honoring the current public byte limit."""
    cdef Connection connection = <Connection>user_data
    cdef size_t accepted = length
    cdef Py_ssize_t current_size

    if connection._output_remaining >= 0:
        if connection._output_remaining == 0:
            return _nghttp2.NGHTTP2_ERR_WOULDBLOCK
        accepted = min(accepted, <size_t>connection._output_remaining)
    try:
        current_size = PyByteArray_GET_SIZE(connection._output)
        if accepted > ((<size_t>-1) >> 1) - <size_t>current_size:
            raise MemoryError("outbound data is too large")
        PyByteArray_Resize(connection._output, current_size + accepted)
        memcpy(
            PyByteArray_AS_STRING(connection._output) + current_size,
            data,
            accepted,
        )
    except BaseException as error:
        return _callback_failed(connection, error)
    if connection._output_remaining >= 0:
        connection._output_remaining -= accepted
    return accepted


cdef _nghttp2.nghttp2_ssize _read_body(
    _nghttp2.nghttp2_session *session,
    int32_t stream_id,
    uint8_t *buffer,
    size_t length,
    uint32_t *data_flags,
    _nghttp2.nghttp2_data_source *source,
    void *user_data,
) noexcept:
    """Copy queued body bytes and emit the stream's terminal marker.

    Pending-byte counters are reduced only after bytes enter the serialized
    output. Empty, unfinished queues defer DATA generation until the
    application queues more bytes.
    """
    cdef Connection connection = <Connection>user_data
    cdef _BodySource body
    cdef bytes chunk
    cdef size_t available, copied = 0, take
    cdef list trailers
    cdef _nghttp2.nghttp2_nv *native_headers = NULL
    cdef int result

    try:
        body = connection._bodies[stream_id]
        while body.chunks and copied < length:
            chunk = body.chunks[0]
            available = len(chunk) - body.offset
            take = min(available, length - copied)
            memcpy(buffer + copied, PyBytes_AS_STRING(chunk) + body.offset, take)
            copied += take
            body.offset += take
            body.pending -= take
            connection._pending_data -= take
            if body.offset == len(chunk):
                body.chunks.popleft()
                body.offset = 0
        if copied:
            if body.ended and not body.chunks:
                if body.trailers is None:
                    data_flags[0] |= _nghttp2.NGHTTP2_DATA_FLAG_EOF
                else:
                    trailers = body.trailers
                    native_headers = _make_headers(trailers, len(trailers))
                    try:
                        result = _nghttp2.nghttp2_submit_trailer(
                            session, stream_id, native_headers, len(trailers),
                        )
                    finally:
                        free(native_headers)
                    if result < 0:
                        _raise_nghttp2_error(result)
                    body.trailers = None
                    data_flags[0] |= (
                        _nghttp2.NGHTTP2_DATA_FLAG_EOF
                        | _nghttp2.NGHTTP2_DATA_FLAG_NO_END_STREAM
                    )
            return copied
        if body.ended:
            if body.trailers is None:
                data_flags[0] |= _nghttp2.NGHTTP2_DATA_FLAG_EOF
            else:
                trailers = body.trailers
                native_headers = _make_headers(trailers, len(trailers))
                try:
                    result = _nghttp2.nghttp2_submit_trailer(
                        session, stream_id, native_headers, len(trailers),
                    )
                finally:
                    free(native_headers)
                if result < 0:
                    _raise_nghttp2_error(result)
                body.trailers = None
                data_flags[0] |= (
                    _nghttp2.NGHTTP2_DATA_FLAG_EOF
                    | _nghttp2.NGHTTP2_DATA_FLAG_NO_END_STREAM
                )
            return 0
        body.deferred = True
        return _nghttp2.NGHTTP2_ERR_DEFERRED
    except BaseException as error:
        return _callback_failed(connection, error)


cdef int _begin_headers(
    _nghttp2.nghttp2_session *session,
    const _nghttp2.nghttp2_frame *frame,
    void *user_data,
) noexcept:
    """Start collecting one decoded header block."""
    cdef Connection connection = <Connection>user_data

    try:
        connection._current_headers = []
        connection._current_header_size = 0
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef int _header(
    _nghttp2.nghttp2_session *session,
    const _nghttp2.nghttp2_frame *frame,
    const uint8_t *name,
    size_t name_length,
    const uint8_t *value,
    size_t value_length,
    uint8_t flags,
    void *user_data,
) noexcept:
    """Copy one decoded header field after enforcing resource limits."""
    cdef Connection connection = <Connection>user_data
    cdef bytes header_name, header_value
    cdef object header

    try:
        connection._current_header_size += name_length + value_length + 32
        if (
            connection._current_header_size
            > connection.config.max_inbound_header_list_size
        ):
            raise DenialOfServiceError("received header list exceeds configured size")
        if (
            len(connection._current_headers)
            >= connection.config.max_inbound_header_count
        ):
            raise DenialOfServiceError("received header list exceeds configured count")
        header_name = PyBytes_FromStringAndSize(<const char *>name, name_length)
        header_value = PyBytes_FromStringAndSize(<const char *>value, value_length)
        if flags & _nghttp2.NGHTTP2_NV_FLAG_NO_INDEX:
            header = NeverIndexedHeader(header_name, header_value)
        else:
            header = (header_name, header_value)
        connection._current_headers.append(header)
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef int _data_chunk(
    _nghttp2.nghttp2_session *session,
    uint8_t flags,
    int32_t stream_id,
    const uint8_t *data,
    size_t length,
    void *user_data,
) noexcept:
    """Collect DATA fragments until the complete frame callback arrives."""
    cdef Connection connection = <Connection>user_data
    cdef object accumulator
    cdef bytearray chunks
    cdef Py_ssize_t current_size

    try:
        accumulator = connection._data_chunks.get(stream_id)
        if accumulator is None:
            connection._data_chunks[stream_id] = PyBytes_FromStringAndSize(
                <const char *>data,
                length,
            )
            return 0

        if isinstance(accumulator, bytes):
            chunks = bytearray(accumulator)
            connection._data_chunks[stream_id] = chunks
        else:
            chunks = accumulator

        current_size = PyByteArray_GET_SIZE(chunks)
        PyByteArray_Resize(chunks, current_size + length)
        memcpy(
            PyByteArray_AS_STRING(chunks) + current_size,
            data,
            length,
        )
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef inline void _headers_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish the event represented by one complete header block."""
    cdef tuple headers
    cdef bytes status
    cdef int category

    headers = tuple(connection._current_headers)
    category = frame.headers.cat
    if category == _nghttp2.NGHTTP2_HCAT_REQUEST:
        connection._events.append(RequestReceived(
            frame.hd.stream_id,
            headers,
            bool(frame.hd.flags & _nghttp2.NGHTTP2_FLAG_END_STREAM),
        ))
    elif category in (
        _nghttp2.NGHTTP2_HCAT_RESPONSE,
        _nghttp2.NGHTTP2_HCAT_PUSH_RESPONSE,
    ):
        status = next((h[1] for h in headers if h[0] == b":status"), b"")
        if status.startswith(b"1"):
            connection._events.append(InformationalResponseReceived(
                frame.hd.stream_id,
                headers,
            ))
        else:
            connection._events.append(ResponseReceived(
                frame.hd.stream_id,
                headers,
                bool(frame.hd.flags & _nghttp2.NGHTTP2_FLAG_END_STREAM),
            ))
    else:
        status = next((h[1] for h in headers if h[0] == b":status"), b"")
        if status.startswith(b"1"):
            connection._events.append(InformationalResponseReceived(
                frame.hd.stream_id,
                headers,
            ))
        elif status:
            connection._events.append(ResponseReceived(
                frame.hd.stream_id,
                headers,
                bool(frame.hd.flags & _nghttp2.NGHTTP2_FLAG_END_STREAM),
            ))
        else:
            connection._events.append(TrailersReceived(
                frame.hd.stream_id,
                headers,
            ))
    connection._current_headers = []


cdef inline void _push_promise_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one complete promised request header block."""
    connection._events.append(PushedStreamReceived(
        frame.hd.stream_id,
        frame.push_promise.promised_stream_id,
        tuple(connection._current_headers),
    ))
    connection._current_headers = []


cdef inline void _data_frame_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one complete DATA frame and update receive accounting."""
    cdef bytes payload
    cdef object accumulator

    accumulator = connection._data_chunks.pop(frame.hd.stream_id, None)
    if accumulator is None:
        payload = b""
    elif isinstance(accumulator, bytes):
        payload = accumulator
    else:
        payload = bytes(accumulator)
    if payload and not connection.config.auto_window_update:
        connection._unacknowledged[frame.hd.stream_id] = (
            connection._unacknowledged.get(frame.hd.stream_id, 0)
            + len(payload)
        )
    connection._events.append(DataReceived(
        frame.hd.stream_id,
        payload,
        bool(frame.hd.flags & _nghttp2.NGHTTP2_FLAG_END_STREAM),
    ))


cdef inline void _settings_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one SETTINGS frame or its acknowledgement."""
    cdef dict settings
    cdef size_t index

    if frame.hd.flags & _nghttp2.NGHTTP2_FLAG_ACK:
        connection._events.append(SettingsAcknowledged())
        return

    settings = {}
    for index in range(frame.settings.niv):
        settings[frame.settings.iv[index].settings_id] = (
            frame.settings.iv[index].value
        )
    connection._events.append(SettingsReceived(settings))


cdef inline void _reset_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish the peer's stream reset."""
    connection._events.append(StreamReset(
        frame.hd.stream_id,
        frame.rst_stream.error_code,
    ))


cdef inline void _ping_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one PING request or acknowledgement."""
    cdef bytes opaque_data = PyBytes_FromStringAndSize(
        <const char *>frame.ping.opaque_data,
        8,
    )

    if frame.hd.flags & _nghttp2.NGHTTP2_FLAG_ACK:
        connection._events.append(PingAcknowledged(opaque_data))
    else:
        connection._events.append(PingReceived(opaque_data))


cdef inline void _window_update_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one stream- or connection-level window update."""
    connection._events.append(WindowUpdated(
        frame.hd.stream_id,
        frame.window_update.window_size_increment,
    ))


cdef inline void _goaway_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish the peer's connection shutdown notice."""
    connection._events.append(GoAwayReceived(
        frame.goaway.last_stream_id,
        frame.goaway.error_code,
        PyBytes_FromStringAndSize(
            <const char *>frame.goaway.opaque_data,
            frame.goaway.opaque_data_len,
        ),
    ))


cdef inline void _altsvc_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one parsed ALTSVC extension frame."""
    cdef _nghttp2.nghttp2_ext_altsvc *altsvc = (
        <_nghttp2.nghttp2_ext_altsvc *>frame.ext.payload
    )

    connection._events.append(AltSvcReceived(
        frame.hd.stream_id,
        PyBytes_FromStringAndSize(
            <const char *>altsvc.origin,
            altsvc.origin_len,
        ),
        PyBytes_FromStringAndSize(
            <const char *>altsvc.field_value,
            altsvc.field_value_len,
        ),
    ))


cdef inline void _origin_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one parsed ORIGIN extension frame."""
    cdef _nghttp2.nghttp2_ext_origin *origin = (
        <_nghttp2.nghttp2_ext_origin *>frame.ext.payload
    )
    cdef list origins = []
    cdef size_t index

    for index in range(origin.nov):
        origins.append(PyBytes_FromStringAndSize(
            <const char *>origin.ov[index].origin,
            origin.ov[index].origin_len,
        ))
    connection._events.append(OriginReceived(tuple(origins)))


cdef inline void _priority_update_received(
    Connection connection,
    const _nghttp2.nghttp2_frame *frame,
):
    """Publish one parsed PRIORITY_UPDATE extension frame."""
    cdef _nghttp2.nghttp2_ext_priority_update *priority_update = (
        <_nghttp2.nghttp2_ext_priority_update *>frame.ext.payload
    )

    connection._events.append(PriorityUpdateReceived(
        priority_update.stream_id,
        PyBytes_FromStringAndSize(
            <const char *>priority_update.field_value,
            priority_update.field_value_len,
        ),
    ))


cdef int _frame_received(
    _nghttp2.nghttp2_session *session,
    const _nghttp2.nghttp2_frame *frame,
    void *user_data,
) noexcept:
    """Dispatch one fully processed frame to its event handler."""
    cdef Connection connection = <Connection>user_data

    try:
        if frame.hd.type == _nghttp2.NGHTTP2_HEADERS:
            _headers_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_PUSH_PROMISE:
            _push_promise_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_DATA:
            _data_frame_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_SETTINGS:
            _settings_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_RST_STREAM:
            _reset_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_PING:
            _ping_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_WINDOW_UPDATE:
            _window_update_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_GOAWAY:
            _goaway_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_ALTSVC:
            _altsvc_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_ORIGIN:
            _origin_received(connection, frame)
        elif frame.hd.type == _nghttp2.NGHTTP2_PRIORITY_UPDATE:
            _priority_update_received(connection, frame)
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef int _stream_closed(
    _nghttp2.nghttp2_session *session,
    int32_t stream_id,
    uint32_t error_code,
    void *user_data,
) noexcept:
    """Release per-stream Python state and publish stream closure."""
    cdef Connection connection = <Connection>user_data
    cdef _BodySource body

    try:
        body = connection._bodies.pop(stream_id, None)
        if body is not None:
            connection._pending_data -= body.pending
        connection._data_chunks.pop(stream_id, None)
        connection._responses.discard(stream_id)
        connection._events.append(StreamClosed(stream_id, error_code))
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef int _frame_not_sent(
    _nghttp2.nghttp2_session *session,
    const _nghttp2.nghttp2_frame *frame,
    int error_code,
    void *user_data,
) noexcept:
    """Expose delayed frame-preparation failures as events."""
    cdef Connection connection = <Connection>user_data
    cdef _BodySource body

    try:
        if frame.hd.type == _nghttp2.NGHTTP2_HEADERS:
            body = connection._bodies.pop(frame.hd.stream_id, None)
            if body is not None:
                connection._pending_data -= body.pending
        connection._events.append(FrameNotSent(
            frame.hd.stream_id,
            FrameType(frame.hd.type),
            _frame_not_sent_error(error_code),
        ))
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)
