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
from cpython.bytes cimport (
    PyBytes_AS_STRING,
    PyBytes_Check,
    PyBytes_FromStringAndSize,
    PyBytes_GET_SIZE,
)
from cpython.long cimport PyLong_AsLongLongAndOverflow
from cpython.number cimport PyNumber_Index as integer_index
from libc.stdint cimport int32_t, uint8_t, uint32_t, uint64_t
from libc.stdlib cimport free, malloc
from libc.string cimport memcpy, memset
from os import urandom

from . cimport _nghttp2

from .config import Configuration, Role
from .enums import ErrorCode, Setting
from .events import (
    AltSvcReceived,
    ConnectionClosed,
    DataReceived,
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
    StreamStateError,
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
    cdef list chunks
    cdef Py_ssize_t head
    cdef Py_ssize_t offset
    cdef size_t queued_size
    cdef bint ended
    cdef bint deferred
    cdef object trailers

    def __cinit__(self):
        self.chunks = []
        self.head = 0
        self.offset = 0
        self.queued_size = 0
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
        ValueError: If a resource limit is outside its supported range.
        MemoryError: If the HTTP/2 connection state cannot be allocated.
    """

    cdef readonly object role
    cdef readonly object config
    cdef bint _server
    cdef _nghttp2.nghttp2_session *_session
    cdef bytearray _output
    cdef Py_ssize_t _output_size
    cdef Py_ssize_t _output_remaining
    cdef object _callback_error
    cdef bint _initialized
    cdef bint _active
    cdef bint _failed
    cdef bint _terminating
    cdef bint _closing
    cdef bint _closed
    cdef uint32_t _close_error_code
    cdef bytes _close_debug_data
    cdef bint _local_extensible_priority
    cdef bint _auto_window_update
    cdef size_t _max_settings
    cdef Py_ssize_t _max_inbound_header_list_size
    cdef Py_ssize_t _max_inbound_header_count
    cdef list _events
    cdef dict _bodies
    cdef size_t _queued_body_size
    cdef list _current_headers
    cdef size_t _current_header_size
    cdef dict _data_chunks
    cdef set _responses
    cdef dict _unconsumed
    cdef dict _local_stream_errors
    cdef dict _deferred_resets

    def __cinit__(self):
        self._session = NULL
        self._output = None
        self._output_remaining = 0
        self._callback_error = None
        self._initialized = False
        self._active = False
        self._failed = False
        self._terminating = False
        self._closing = False
        self._closed = False
        self._close_error_code = 0
        self._close_debug_data = b""
        self._local_extensible_priority = False
        self._events = []
        self._bodies = {}
        self._queued_body_size = 0
        self._current_headers = []
        self._current_header_size = 0
        self._data_chunks = {}
        self._responses = set()
        self._unconsumed = {}
        self._local_stream_errors = {}
        self._deferred_resets = {}

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
            _apply_configuration(self, option, config)

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
        self._server = role is Role.SERVER
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

        entries = _normalize_settings(settings)
        self._require_created()
        if <size_t>len(entries) > self._max_settings:
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
        bint head_request=False,
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
        cdef list entries = []
        cdef _nghttp2.nghttp2_settings_entry *native_entries = NULL
        cdef size_t count = 0
        cdef const uint8_t *pointer = NULL
        cdef int result

        if not self._server and local_settings is not None:
            raise ValueError("client upgrade does not accept local_settings")
        if not PyBytes_Check(settings_payload):
            raise TypeError("settings_payload must be bytes")
        if PyBytes_GET_SIZE(settings_payload):
            pointer = <const uint8_t *>PyBytes_AS_STRING(settings_payload)

        if self._server:
            entries = _normalize_settings(local_settings)
        self._require_created()
        if self._server:
            if <size_t>len(entries) > self._max_settings:
                raise ValueError("settings exceed the configured entry limit")
            count = len(entries)
            if count:
                native_entries = _make_settings(entries)

        self._callback_error = None
        try:
            result = _nghttp2.nghttp2_session_upgrade2(
                self._session, pointer, PyBytes_GET_SIZE(settings_payload),
                head_request, NULL,
            )
            self._raise_callback_or_native(result)
        except BaseException:
            free(native_entries)
            raise

        if self._server:
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

        Peer violations that the HTTP/2 state machine handles with GOAWAY do
        not raise here; drive ``data_to_send()`` and handle
        ``ConnectionClosed``. Fatal processing failures raise and invalidate
        the connection.

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

        PyObject_GetBuffer(data, &view, PyBUF_CONTIG_RO)

        try:
            self._require_active()
            length = view.len
            self._callback_error = None
            result = _nghttp2.nghttp2_session_mem_recv2(
                self._session, <const uint8_t *>view.buf, length,
            )
            self._raise_callback_or_native(result)
            if result != <_nghttp2.nghttp2_ssize>length:
                self._fail()
                raise InternalError("HTTP/2 engine did not consume all input")
            if self._closing:
                self._update_terminal_state()
        finally:
            PyBuffer_Release(&view)

    def events(self):
        """Return and clear events produced while processing protocol actions.

        Events can be produced by ``initiate_upgrade()``, ``receive_data()``,
        and ``data_to_send()``. When ``data_to_send()`` also produces
        ``ConnectionClosed``, write its returned bytes before closing the
        transport.

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
        cdef bytes output

        if amount is None:
            limit = -1
        else:
            limit = _nonnegative_size(amount, "amount")
        if self._failed:
            raise ConnectionStateError("Connection is no longer usable")
        if limit == 0 or not self._active:
            return b""

        self._output = bytearray()
        self._output_size = 0
        self._output_remaining = limit
        self._callback_error = None
        try:
            result = _nghttp2.nghttp2_session_send(self._session)
            self._raise_callback_or_native(result)
            if self._closing:
                self._update_terminal_state()
            output = PyBytes_FromStringAndSize(
                PyByteArray_AS_STRING(self._output), self._output_size,
            )
        except BaseException:
            # Native output has advanced; lost bytes cannot be regenerated.
            self._fail()
            raise
        self._output = None
        self._output_remaining = 0
        return output

    def send_request(self, headers, *, bint end_stream=False):
        """Queue request headers and create a client stream.

        Args:
            headers: Iterable of request fields in transmission order. The
                caller supplies the required pseudo-header fields and RFC
                9113-compliant values.
            end_stream: Whether the request has no body or trailers.

        Returns:
            The stream identifier allocated by the HTTP/2 state machine.

        Raises:
            ConnectionStateError: If the connection is not active or is a server.
            ConnectionClosingError: If a new request cannot be created.
            NoAvailableStreamIDError: If stream identifiers are exhausted.
            TypeError: If headers or ``end_stream`` have invalid types.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef list fields
        cdef size_t count
        cdef _nghttp2.nghttp2_data_provider2 provider
        cdef _nghttp2.nghttp2_data_provider2 *provider_pointer = NULL
        cdef int32_t stream_id

        fields = _normalize_headers(headers)
        count = len(fields)
        native_headers = _make_headers(fields, count)
        if not end_stream:
            provider.read_callback = _read_body
            provider.source.ptr = NULL
            provider_pointer = &provider
        try:
            self._require_active()
            if self._server:
                raise ConnectionStateError("a server cannot send requests")
            if not _nghttp2.nghttp2_session_check_request_allowed(self._session):
                raise ConnectionClosingError(
                    "the connection cannot create another request stream",
                )
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

    def send_response(self, stream_id, headers, *, bint end_stream=False):
        """Queue final response headers for a server stream.

        Args:
            stream_id: Stream receiving the response.
            headers: Iterable of final response fields in transmission order.
                The caller supplies ``:status`` and RFC 9113-compliant field
                values.
            end_stream: Whether the response has no body or trailers.

        Raises:
            ConnectionStateError: If the connection is not active or is a client.
            StreamStateError: If a final response is already pending.
            StreamUnavailableError: If the stream cannot accept a response.
            TypeError: If headers, ``stream_id``, or ``end_stream`` are invalid.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef list fields
        cdef size_t count
        cdef _nghttp2.nghttp2_data_provider2 provider
        cdef _nghttp2.nghttp2_data_provider2 *provider_pointer = NULL
        cdef int result

        stream_id = _stream_id(stream_id)
        fields = _normalize_headers(headers)
        count = len(fields)
        native_headers = _make_headers(fields, count)
        if not end_stream:
            provider.read_callback = _read_body
            provider.source.ptr = NULL
            provider_pointer = &provider
        try:
            self._require_active()
            if not self._server:
                raise ConnectionStateError("a client cannot send responses")
            self._require_stream(stream_id)
            if stream_id in self._responses:
                raise StreamStateError("a response is already pending")
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
            headers: Iterable of informational response fields in transmission
                order. The caller supplies a valid 1xx ``:status`` and
                otherwise RFC 9113-compliant fields.

        Raises:
            ConnectionStateError: If the connection is not active or is a client.
            StreamStateError: If a final response is already pending.
            StreamUnavailableError: If the stream no longer exists.
            TypeError: If headers or ``stream_id`` are invalid.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef list fields
        cdef size_t count
        cdef int32_t result

        stream_id = _stream_id(stream_id)
        fields = _normalize_headers(headers)
        count = len(fields)
        native_headers = _make_headers(fields, count)
        try:
            self._require_active()
            if not self._server:
                raise ConnectionStateError(
                    "a client cannot send informational responses",
                )
            self._require_stream(stream_id)
            if stream_id in self._responses:
                raise StreamStateError(
                    "informational responses must precede the final response",
                )
            result = _nghttp2.nghttp2_submit_headers(
                self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
                NULL, native_headers, count, NULL,
            )
        finally:
            free(native_headers)
        if result < 0:
            self._raise_native_error(result)

    def send_trailers(self, stream_id, headers):
        """Queue trailers after all queued stream body bytes.

        Args:
            stream_id: Stream whose local direction will be ended.
            headers: Iterable of trailer fields in transmission order. The
                caller is responsible for omitting pseudo-headers and otherwise
                meeting RFC 9113 field requirements.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamStateError: If the stream has no open body or was ended.
            TypeError: If headers or ``stream_id`` are invalid.
        """
        cdef _BodySource body
        cdef list normalized
        cdef int result

        stream_id = _stream_id(stream_id)
        normalized = _normalize_headers(headers, deferred=True)
        self._require_active()
        body = self._bodies.get(stream_id)
        if body is None:
            raise StreamStateError("stream has no open body")
        if body.ended:
            raise StreamStateError("stream body is already ended")
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
            headers: Iterable of promised request fields. The caller supplies
                the required pseudo-header fields and RFC 9113-compliant values.

        Returns:
            The reserved promised stream identifier.

        Raises:
            ConnectionStateError: If the connection is not active or is a client.
            StreamUnavailableError: If the associated stream is unavailable.
            TypeError: If headers or ``stream_id`` are invalid.
        """
        cdef _nghttp2.nghttp2_nv *native_headers = NULL
        cdef list fields
        cdef size_t count
        cdef int32_t promised_stream_id

        stream_id = _stream_id(stream_id)
        fields = _normalize_headers(headers)
        count = len(fields)
        native_headers = _make_headers(fields, count)
        try:
            self._require_active()
            if not self._server:
                raise ConnectionStateError("a client cannot send push promises")
            self._require_stream(stream_id)
            promised_stream_id = _nghttp2.nghttp2_submit_push_promise(
                self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
                native_headers, count, NULL,
            )
        finally:
            free(native_headers)
        if promised_stream_id < 0:
            self._raise_native_error(promised_stream_id)
        return promised_stream_id

    def send_data(self, stream_id, data, *, bint end_stream=False):
        """Queue body bytes for a stream.

        Args:
            stream_id: Stream whose body receives the bytes.
            data: Body bytes retained in the outbound queue until the HTTP/2
                engine takes them for DATA framing.
            end_stream: Whether these are the final body bytes.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamStateError: If the stream has no open body or already ended.
            TypeError: If ``data`` is not bytes-like.
        """
        cdef _BodySource body
        cdef bytes chunk
        cdef int result

        stream_id = _stream_id(stream_id)
        if type(data) is bytes:
            chunk = data
        elif PyBytes_Check(data):
            # Keep native DATA callbacks free of subclass hooks and finalizers.
            chunk = PyBytes_FromStringAndSize(
                PyBytes_AS_STRING(data), PyBytes_GET_SIZE(data),
            )
        elif isinstance(data, (bytearray, memoryview)):
            chunk = bytes(data)
        else:
            raise TypeError("data must be a bytes-like object")
        self._require_active()
        try:
            body = self._bodies[stream_id]
        except KeyError:
            raise StreamStateError("stream has no open body") from None
        if body.ended:
            raise StreamStateError("stream body is already ended")
        if chunk:
            body.chunks.append(chunk)
            body.queued_size += len(chunk)
            self._queued_body_size += len(chunk)
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
            StreamStateError: If the stream has no open body.
        """
        self.send_data(stream_id, b"", end_stream=True)

    def reset_stream(
        self, stream_id, error_code=ErrorCode.CANCEL, *, bint after_end_stream=False,
    ):
        """Queue an RST_STREAM frame.

        By default the stream stops at once, and headers, body bytes, and
        trailers still queued for it are discarded. With
        ``after_end_stream=True``, those frames are sent first and
        RST_STREAM follows the frame that ends the local direction. If the
        peer has ended its direction by then, the stream closes normally and
        no RST_STREAM is sent. A server can use this with ``NO_ERROR`` to stop
        a request body it no longer needs after a complete response.

        Args:
            stream_id: Stream to terminate.
            error_code: HTTP/2 wire error code.
            after_end_stream: Whether to send the stream's queued frames
                first. The local direction must already be ended.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamStateError: If ``after_end_stream`` is set before the
                local direction is ended.
            StreamUnavailableError: If ``after_end_stream`` is set for a
                stream that is not open.
            TypeError: If an argument is not an integer.
            ValueError: If an argument is outside its wire range.
        """
        cdef int result
        cdef _BodySource body
        cdef bint ended

        stream_id = _stream_id(stream_id)
        error_code = _uint32(error_code, "error_code")
        self._require_active()
        if after_end_stream:
            self._require_stream(stream_id)
            if not _nghttp2.nghttp2_session_get_stream_local_close(
                self._session, stream_id,
            ):
                body = self._bodies.get(stream_id)
                if body is not None:
                    ended = body.ended
                else:
                    # A server stream without a body ended with its response.
                    ended = (
                        not self._server
                        or stream_id in self._responses
                    )
                if not ended:
                    raise StreamStateError(
                        "stream local direction is not ended",
                    )
                # Submitting now would mark the stream closing and drop its
                # queued frames, so _frame_sent submits after END_STREAM.
                self._deferred_resets[stream_id] = error_code
                return
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

        entries = _normalize_settings(settings)
        self._require_active()
        if <size_t>len(entries) > self._max_settings:
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

    def send_ping(self, opaque_data=_DEFAULT_PING_OPAQUE_DATA):
        """Queue a PING frame with an eight-byte payload.

        Args:
            opaque_data: Exactly eight opaque bytes echoed by the peer.

        Raises:
            ConnectionStateError: If the connection is not active.
            TypeError: If ``opaque_data`` is not bytes.
            ValueError: If it is not exactly eight bytes long.
        """
        cdef int result

        self._require_active()
        if not PyBytes_Check(opaque_data):
            raise TypeError("opaque_data must be bytes")
        if PyBytes_GET_SIZE(opaque_data) != 8:
            raise ValueError("opaque_data must contain exactly 8 bytes")
        result = _nghttp2.nghttp2_submit_ping(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE,
            <const uint8_t *>PyBytes_AS_STRING(opaque_data),
        )
        if result < 0:
            self._raise_native_error(result)

    def send_goaway(
        self, error_code=ErrorCode.NO_ERROR, *, last_stream_id=None, debug_data=b"",
    ):
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
        cdef const uint8_t *pointer = NULL
        cdef int result

        error_code = _uint32(error_code, "error_code")
        if last_stream_id is not None:
            last_stream_id = _uint31(
                last_stream_id,
                "last_stream_id",
            )
        if not PyBytes_Check(debug_data):
            raise TypeError("debug_data must be bytes")
        if PyBytes_GET_SIZE(debug_data):
            pointer = <const uint8_t *>PyBytes_AS_STRING(debug_data)
        self._require_active()
        if last_stream_id is None:
            last_stream_id = _nghttp2.nghttp2_session_get_last_proc_stream_id(
                self._session,
            )
        result = _nghttp2.nghttp2_submit_goaway(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE,
            last_stream_id, error_code, pointer, PyBytes_GET_SIZE(debug_data),
        )
        if result < 0:
            self._raise_native_error(result)

    def send_shutdown_notice(self):
        """Queue the first GOAWAY in a server graceful-shutdown sequence.

        Raises:
            ConnectionStateError: If the connection is not active or is a client.
        """
        cdef int result

        self._require_active()
        if not self._server:
            raise ConnectionStateError(
                "a client cannot send shutdown notices",
            )
        result = _nghttp2.nghttp2_submit_shutdown_notice(self._session)
        if result < 0:
            self._raise_native_error(result)

    def terminate_connection(
        self, error_code=ErrorCode.NO_ERROR, *, last_stream_id=None,
    ):
        """Queue a final GOAWAY and terminate session processing.

        Frames still queued for any stream, including body bytes and
        trailers, are discarded. Use ``send_goaway()`` instead to let accepted
        streams finish first.

        After this call, use ``data_to_send()`` to obtain the final output.
        Writing that output and handling ``ConnectionClosed`` completes the
        caller-owned transport lifecycle.

        Args:
            error_code: HTTP/2 wire error code.
            last_stream_id: Optional final peer stream identifier.

        Raises:
            ConnectionStateError: If the connection is not active.
            TypeError: If an argument is not an integer.
            ValueError: If an argument is outside its wire range.
        """
        cdef int result

        error_code = _uint32(error_code, "error_code")
        if last_stream_id is not None:
            last_stream_id = _uint31(last_stream_id, "last_stream_id")
        self._require_active()
        if last_stream_id is None:
            result = _nghttp2.nghttp2_session_terminate_session(
                self._session, error_code,
            )
        else:
            result = _nghttp2.nghttp2_session_terminate_session2(
                self._session, last_stream_id, error_code,
            )
        if result < 0:
            self._raise_native_error(result)
        self._terminating = True
        self._closing = True
        self._discard_pending_state()

    def consume_received_data(self, stream_id, amount):
        """Release manually consumed application data bytes.

        Args:
            stream_id: Stream that delivered those bytes.
            amount: Application data bytes consumed, normally
                ``len(event.data)`` for a ``DataReceived`` event. Frame padding
                is consumed internally.

        Raises:
            ConnectionStateError: If the connection is not active or automatic
                receive-window updates are enabled.
            TypeError: If ``amount`` or ``stream_id`` is not an integer.
            ValueError: If ``amount`` exceeds outstanding received data.
            StreamUnavailableError: If the stream cannot be acknowledged.
        """
        cdef int result

        stream_id = _stream_id(stream_id)
        amount = _nonnegative_size(amount, "amount")
        self._require_active()
        if self._auto_window_update:
            raise ConnectionStateError(
                "manual consumption requires auto_window_update=False",
            )
        if amount == 0:
            return
        remaining = self._unconsumed.get(stream_id, 0) - amount
        if remaining < 0:
            raise ValueError("amount exceeds unconsumed received data")
        result = _nghttp2.nghttp2_session_consume(
            self._session, stream_id, amount,
        )
        if result < 0:
            self._raise_native_error(result)
        if remaining:
            self._unconsumed[stream_id] = remaining
        else:
            del self._unconsumed[stream_id]

    def set_local_window_size(self, window_size, *, stream_id=0):
        """Set an absolute receive-window target.

        Args:
            window_size: Bytes this endpoint is prepared to receive at the
                selected scope.
            stream_id: Stream to update, or zero for the connection window.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamUnavailableError: If a nonzero stream does not exist.
            TypeError: If an argument is not an integer.
            ValueError: If an argument is outside its protocol range.

        This changes advertised capacity without marking received application
        data as consumed. Use ``consume_received_data()`` for consumption
        accounting when automatic window updates are disabled.
        """
        cdef int result

        window_size = _uint31(window_size, "window_size")
        stream_id = _uint31(stream_id, "stream_id")
        self._require_active()
        if stream_id:
            self._require_stream(stream_id)
        result = _nghttp2.nghttp2_session_set_local_window_size(
            self._session,
            _nghttp2.NGHTTP2_FLAG_NONE,
            stream_id,
            window_size,
        )
        if result < 0:
            self._raise_native_error(result)

    def send_priority_update(self, stream_id, field_value):
        """Queue an RFC 9218 PRIORITY_UPDATE frame from a client.

        Args:
            stream_id: Stream whose priority is updated.
            field_value: Raw RFC 9218 Priority field value as bytes, including
                bytes subclasses.

        Returns:
            ``True`` when queued, or ``False`` after the peer has explicitly
            disabled extensible priority.

        Raises:
            ConnectionStateError: If the connection is not active or is a server.
            TypeError: If ``field_value`` is not bytes.
            ValueError: If the payload cannot fit in an HTTP/2 frame.
        """
        cdef int result

        stream_id = _stream_id(stream_id)
        self._require_active()
        if self._server:
            raise ConnectionStateError(
                "a server cannot send PRIORITY_UPDATE frames",
            )
        if _nghttp2.nghttp2_session_get_remote_settings(self._session, 9) == 0:
            return False
        if not PyBytes_Check(field_value):
            raise TypeError("field_value must be bytes")
        result = _nghttp2.nghttp2_submit_priority_update(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
            <const uint8_t *>PyBytes_AS_STRING(field_value),
            PyBytes_GET_SIZE(field_value),
        )
        if result < 0:
            self._raise_native_error(result)
        return True

    def set_stream_priority(
        self, stream_id, priority, *, bint ignore_client_signal=False,
    ):
        """Apply RFC 9218 scheduling parameters to a server stream.

        Args:
            stream_id: Existing stream to reschedule.
            priority: New urgency and incremental parameters.
            ignore_client_signal: Whether future client updates are ignored.

        Returns:
            ``True`` when applied, or ``False`` when local extensible priority
            has not been enabled.

        Raises:
            ConnectionStateError: If the connection is not active or is a client.
            StreamUnavailableError: If the stream does not exist.
            TypeError: If ``priority`` is not a ``Priority``.
            ValueError: If urgency is negative or does not fit 32 bits.
        """
        cdef _nghttp2.nghttp2_extpri native_priority
        cdef int result

        stream_id = _stream_id(stream_id)
        if not isinstance(priority, Priority):
            raise TypeError("priority must be a Priority")
        native_priority.urgency = _uint32(priority.urgency, "priority.urgency")
        native_priority.inc = priority.incremental
        self._require_active()
        if not self._server:
            raise ConnectionStateError(
                "a client cannot set server scheduling priority",
            )
        if not self._local_extensible_priority:
            return False

        self._require_stream(stream_id)
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
            ConnectionStateError: If the connection is not active or is a client.
            StreamUnavailableError: If the stream does not exist.
        """
        cdef _nghttp2.nghttp2_extpri native_priority

        stream_id = _stream_id(stream_id)
        self._require_active()
        if not self._server:
            raise ConnectionStateError(
                "a client cannot query server scheduling priority",
            )
        if not self._local_extensible_priority:
            return None

        self._require_stream(stream_id)
        _nghttp2.nghttp2_session_get_extpri_stream_priority(
            self._session, &native_priority, stream_id,
        )
        return Priority(native_priority.urgency, bool(native_priority.inc))

    def send_alt_svc(self, field_value, *, stream_id=0, origin=b""):
        """Queue an RFC 7838 ALTSVC frame from a server.

        Args:
            field_value: Raw Alt-Svc field value as bytes, including bytes
                subclasses.
            stream_id: Associated stream, or zero for an origin advertisement.
            origin: Required origin for connection-level advertisements, as
                bytes including bytes subclasses.

        Raises:
            ConnectionStateError: If the connection is not active or is a client.
            TypeError: If byte fields or ``stream_id`` have wrong types.
            ValueError: If origin and stream scope are inconsistent.
        """
        cdef const uint8_t *origin_pointer = NULL
        cdef int result

        stream_id = _uint31(stream_id, "stream_id")
        if not PyBytes_Check(field_value):
            raise TypeError("field_value must be bytes")
        if not PyBytes_Check(origin):
            raise TypeError("origin must be bytes")
        if PyBytes_GET_SIZE(origin):
            origin_pointer = <const uint8_t *>PyBytes_AS_STRING(origin)
        self._require_active()
        if not self._server:
            raise ConnectionStateError("a client cannot send ALTSVC frames")
        result = _nghttp2.nghttp2_submit_altsvc(
            self._session, _nghttp2.NGHTTP2_FLAG_NONE, stream_id,
            origin_pointer, PyBytes_GET_SIZE(origin),
            <const uint8_t *>PyBytes_AS_STRING(field_value),
            PyBytes_GET_SIZE(field_value),
        )
        if result < 0:
            self._raise_native_error(result)

    def send_origins(self, origins):
        """Queue an RFC 8336 ORIGIN frame from a server.

        Args:
            origins: Byte origins advertised by this connection.

        Raises:
            ConnectionStateError: If the connection is not active or is a client.
            TypeError: If an origin is not bytes.
            ValueError: If the payload cannot fit in an HTTP/2 frame.
        """
        cdef list values
        cdef _nghttp2.nghttp2_origin_entry *native = NULL
        cdef size_t index, count
        cdef int result

        values = []
        for value in origins:
            if not PyBytes_Check(value):
                raise TypeError("each origin must be bytes")
            values.append(value)
        self._require_active()
        if not self._server:
            raise ConnectionStateError("a client cannot send ORIGIN frames")
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
                native[index].origin_len = PyBytes_GET_SIZE(values[index])
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
        self._require_drivable()
        return bool(_nghttp2.nghttp2_session_want_read(self._session))

    @property
    def want_write(self):
        """Whether the session has schedulable output.

        Returns:
            ``True`` while ``data_to_send()`` may advance output.

        Raises:
            ConnectionStateError: If the connection is not active.
        """
        self._require_drivable()
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
        self._require_drivable()
        if self._terminating:
            return False
        return bool(_nghttp2.nghttp2_session_check_request_allowed(self._session))

    def queued_body_size(self, stream_id=None):
        """Return body bytes still waiting in ngh2's outbound queue.

        Args:
            stream_id: Stream to query, or ``None`` for the connection total.

        Returns:
            Body bytes accepted by ``send_data()`` that the HTTP/2 engine has
            not yet taken. This excludes framed output and transport buffers.

        Raises:
            TypeError: If ``stream_id`` is not an integer or ``None``.
            ValueError: If ``stream_id`` is outside its wire range.
        """
        cdef _BodySource body

        if stream_id is None:
            return self._queued_body_size

        stream_id = _stream_id(stream_id)
        body = self._bodies.get(stream_id)
        return 0 if body is None else body.queued_size

    def remote_window_size(self, stream_id=0):
        """Return an outbound flow-control window.

        Args:
            stream_id: Stream to query, or ``0`` for the connection.

        Returns:
            Bytes the peer currently permits at the selected scope.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamUnavailableError: If a nonzero stream does not exist.
            TypeError: If ``stream_id`` is not an integer.
            ValueError: If ``stream_id`` is outside its wire range.
        """
        stream_id = _uint31(stream_id, "stream_id")
        self._require_active()
        if not stream_id:
            return _nghttp2.nghttp2_session_get_remote_window_size(self._session)
        self._require_stream(stream_id)
        return _nghttp2.nghttp2_session_get_stream_remote_window_size(
            self._session, stream_id,
        )

    def local_window_size(self, stream_id=0):
        """Return an inbound flow-control window.

        Args:
            stream_id: Stream to query, or ``0`` for the connection.

        Returns:
            Bytes this endpoint currently permits at the selected scope.

        Raises:
            ConnectionStateError: If the connection is not active.
            StreamUnavailableError: If a nonzero stream does not exist.
            TypeError: If ``stream_id`` is not an integer.
            ValueError: If ``stream_id`` is outside its wire range.
        """
        stream_id = _uint31(stream_id, "stream_id")
        self._require_active()
        if not stream_id:
            return _nghttp2.nghttp2_session_get_local_window_size(self._session)
        self._require_stream(stream_id)
        return _nghttp2.nghttp2_session_get_stream_local_window_size(
            self._session, stream_id,
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
        if not self._initialized:
            raise ConnectionStateError("Connection is not initialized")
        if self._failed:
            raise ConnectionStateError("Connection is no longer usable")
        if self._active:
            raise ConnectionStateError("Connection is already initiated")

    cdef void _require_active(self) except *:
        """Check state after input conversion, which can execute user code."""
        self._require_drivable()
        if self._terminating:
            raise ConnectionStateError("Connection is terminating")

    cdef void _require_drivable(self) except *:
        """Require an initiated session that may still expose final output."""
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
        self._output = None
        self._output_remaining = 0
        self._callback_error = None
        self._discard_pending_state()
        self._failed = True
        self._active = False
        self._terminating = False
        self._closing = False
        self._closed = True

    cdef void _discard_pending_state(self):
        """Release Python-owned protocol state that can no longer progress."""
        self._bodies.clear()
        self._queued_body_size = 0
        self._current_headers.clear()
        self._current_header_size = 0
        self._data_chunks.clear()
        self._responses.clear()
        self._unconsumed.clear()
        self._local_stream_errors.clear()
        self._deferred_resets.clear()

    cdef void _update_terminal_state(self):
        """Stop accepting work once native state no longer wants any I/O."""
        if (
            self._active
            and not self._closed
            and not _nghttp2.nghttp2_session_want_read(self._session)
            and not _nghttp2.nghttp2_session_want_write(self._session)
        ):
            self._terminating = True
            self._discard_pending_state()
            self._closed = True
            self._events.append(ConnectionClosed(
                self._close_error_code,
                self._close_debug_data,
            ))


cdef void _configure_callbacks(
    _nghttp2.nghttp2_session_callbacks *callbacks,
):
    """Register the fixed callbacks used by every connection."""
    _nghttp2.nghttp2_session_callbacks_set_send_callback2(callbacks, _collect_output)
    _nghttp2.nghttp2_session_callbacks_set_send_data_callback(callbacks, _send_body)
    _nghttp2.nghttp2_session_callbacks_set_on_begin_headers_callback(
        callbacks, _begin_headers,
    )
    _nghttp2.nghttp2_session_callbacks_set_on_header_callback(callbacks, _header)
    _nghttp2.nghttp2_session_callbacks_set_on_invalid_header_callback(
        callbacks, _invalid_header,
    )
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
    _nghttp2.nghttp2_session_callbacks_set_on_frame_send_callback(
        callbacks, _frame_sent,
    )
    _nghttp2.nghttp2_session_callbacks_set_rand_callback(
        callbacks, _random_bytes,
    )


cdef void _apply_configuration(
    Connection connection,
    _nghttp2.nghttp2_option *option,
    object config,
):
    """Validate binding limits and apply native session options."""
    cdef object reset_burst_value
    cdef object reset_rate_value
    cdef object glitch_burst_value
    cdef object glitch_rate_value
    cdef object auto_window_update = config.auto_window_update
    cdef uint32_t peer_max_concurrent_streams = _uint32(
        config.initial_peer_max_concurrent_streams,
        "initial_peer_max_concurrent_streams",
    )
    cdef uint32_t max_reserved_remote_streams = _uint32(
        config.max_reserved_remote_streams,
        "max_reserved_remote_streams",
    )
    cdef size_t max_send_header_block_length = _size(
        config.max_send_header_block_length,
        "max_send_header_block_length",
    )
    cdef size_t max_deflate_dynamic_table_size = _size(
        config.max_deflate_dynamic_table_size,
        "max_deflate_dynamic_table_size",
    )
    cdef size_t max_outbound_ack = _size(
        config.max_outbound_ack,
        "max_outbound_ack",
    )
    cdef size_t max_settings = _positive_size(
        config.max_settings,
        "max_settings",
    )
    cdef size_t max_continuations = _size(
        config.max_continuations,
        "max_continuations",
    )
    cdef uint64_t reset_burst
    cdef uint64_t reset_rate
    cdef uint64_t glitch_burst
    cdef uint64_t glitch_rate

    if type(auto_window_update) is not bool:
        raise TypeError("auto_window_update must be a bool")
    try:
        reset_burst_value, reset_rate_value = config.stream_reset_rate_limit
    except (TypeError, ValueError):
        raise TypeError("stream_reset_rate_limit must contain two integers") from None
    try:
        glitch_burst_value, glitch_rate_value = config.glitch_rate_limit
    except (TypeError, ValueError):
        raise TypeError("glitch_rate_limit must contain two integers") from None
    reset_burst = _uint64(
        reset_burst_value,
        "stream_reset_rate_limit burst",
    )
    reset_rate = _uint64(
        reset_rate_value,
        "stream_reset_rate_limit rate",
    )
    glitch_burst = _uint64(
        glitch_burst_value,
        "glitch_rate_limit burst",
    )
    glitch_rate = _uint64(
        glitch_rate_value,
        "glitch_rate_limit rate",
    )
    # Keep validated values so native callbacks never invoke configuration code.
    connection._auto_window_update = auto_window_update
    connection._max_settings = max_settings
    connection._max_inbound_header_list_size = _nonnegative_size(
        config.max_inbound_header_list_size,
        "max_inbound_header_list_size",
    )
    connection._max_inbound_header_count = _nonnegative_size(
        config.max_inbound_header_count,
        "max_inbound_header_count",
    )
    _nghttp2.nghttp2_option_set_no_auto_window_update(
        option, not connection._auto_window_update,
    )
    _nghttp2.nghttp2_option_set_peer_max_concurrent_streams(
        option, peer_max_concurrent_streams,
    )
    _nghttp2.nghttp2_option_set_max_reserved_remote_streams(
        option, max_reserved_remote_streams,
    )
    _nghttp2.nghttp2_option_set_max_send_header_block_length(
        option, max_send_header_block_length,
    )
    _nghttp2.nghttp2_option_set_max_deflate_dynamic_table_size(
        option, max_deflate_dynamic_table_size,
    )
    _nghttp2.nghttp2_option_set_max_outbound_ack(option, max_outbound_ack)
    _nghttp2.nghttp2_option_set_max_settings(option, max_settings)
    _nghttp2.nghttp2_option_set_stream_reset_rate_limit(option, reset_burst, reset_rate)
    _nghttp2.nghttp2_option_set_max_continuations(option, max_continuations)
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


cdef list _normalize_headers(object headers, bint deferred=False):
    """Freeze producer-owned fields before advancing to the next item."""
    cdef list result
    cdef object item, name, value
    cdef bint copy_pair

    # Built-in collections need no producer calls; _make_headers freezes pairs.
    if not deferred and (type(headers) is list or type(headers) is tuple):
        return list(headers)
    result = []
    for item in headers:
        try:
            name, value = item
        except (TypeError, ValueError):
            raise TypeError("each header must be a pair of bytes") from None
        if not PyBytes_Check(name) or not PyBytes_Check(value):
            raise TypeError("each header must be a pair of bytes")
        copy_pair = type(item) is not tuple and type(item) is not NeverIndexedHeader
        if deferred:
            # Queued fields must not finalize subclasses inside native callbacks.
            if type(name) is not bytes:
                name = PyBytes_FromStringAndSize(
                    PyBytes_AS_STRING(name), PyBytes_GET_SIZE(name),
                )
                copy_pair = True
            if type(value) is not bytes:
                value = PyBytes_FromStringAndSize(
                    PyBytes_AS_STRING(value), PyBytes_GET_SIZE(value),
                )
                copy_pair = True
        if copy_pair:
            if isinstance(item, NeverIndexedHeader):
                item = NeverIndexedHeader(name, value)
            else:
                item = (name, value)
        result.append(item)
    return result


cdef _nghttp2.nghttp2_nv *_make_headers(
    list headers,
    size_t count,
) except NULL:
    """Borrow field bytes held by the caller-owned snapshot through submit."""
    cdef _nghttp2.nghttp2_nv *native = NULL
    cdef size_t index
    cdef object header, name, value
    cdef bint never_indexed

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
            if not PyBytes_Check(name) or not PyBytes_Check(value):
                raise TypeError("each header must be a pair of bytes")
            # isinstance() on a plain tuple falls back to a __class__ lookup.
            never_indexed = type(header) is NeverIndexedHeader or (
                type(header) is not tuple
                and isinstance(header, NeverIndexedHeader)
            )
            # Custom pairs can yield fresh bytes unrelated to their storage.
            if type(header) is not tuple and type(header) is not NeverIndexedHeader:
                headers[index] = (
                    NeverIndexedHeader(name, value)
                    if never_indexed
                    else (name, value)
                )
            native[index].name = <uint8_t *>PyBytes_AS_STRING(name)
            native[index].value = <uint8_t *>PyBytes_AS_STRING(value)
            native[index].namelen = PyBytes_GET_SIZE(name)
            native[index].valuelen = PyBytes_GET_SIZE(value)
            native[index].flags = (
                _nghttp2.NGHTTP2_NV_FLAG_NO_INDEX if never_indexed else 0
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
        try:
            key = integer_index(key)
            value = integer_index(value)
        except TypeError:
            raise TypeError("settings must map integers to integers") from None
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


cdef long long _integer(object value, str name, int *overflow) except? -1:
    """Convert an integer argument in C; ``overflow`` reports its sign past 64 bits."""
    try:
        value = integer_index(value)
    except TypeError:
        raise TypeError(f"{name} must be an integer") from None
    return PyLong_AsLongLongAndOverflow(value, overflow)


cdef int _stream_id(object value) except -1:
    """Validate and return a nonzero HTTP/2 stream identifier."""
    cdef int overflow
    cdef long long result = _integer(value, "stream_id", &overflow)
    if overflow or result <= 0 or result > 0x7FFFFFFF:
        raise ValueError("stream_id is out of range")
    return <int>result


cdef uint32_t _uint32(object value, str name) except *:
    """Validate and return an unsigned 32-bit integer."""
    cdef int overflow
    cdef long long result = _integer(value, name, &overflow)
    if overflow or result < 0 or result > 0xFFFFFFFF:
        raise ValueError(f"{name} is out of range")
    return <uint32_t>result


cdef uint64_t _uint64(object value, str name) except *:
    """Validate and return an unsigned 64-bit integer."""
    try:
        value = integer_index(value)
    except TypeError:
        raise TypeError(f"{name} must be an integer") from None
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"{name} is out of range")
    return value


cdef size_t _size(object value, str name) except *:
    """Validate and return a platform-sized non-negative integer."""
    try:
        value = integer_index(value)
    except TypeError:
        raise TypeError(f"{name} must be an integer") from None
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    if value > <size_t>-1:
        raise ValueError(f"{name} is too large for this platform")
    return value


cdef size_t _positive_size(object value, str name) except *:
    """Validate and return a platform-sized positive integer."""
    value = _size(value, name)
    if value == 0:
        raise ValueError(f"{name} must be positive")
    return value


cdef int32_t _uint31(object value, str name) except -1:
    """Validate an unsigned 31-bit protocol value."""
    cdef int overflow
    cdef long long result = _integer(value, name, &overflow)
    if overflow or result < 0 or result > 0x7FFFFFFF:
        raise ValueError(f"{name} is out of range")
    return <int32_t>result


cdef Py_ssize_t _nonnegative_size(object value, str name) except -1:
    """Validate and return a non-negative platform-sized integer."""
    cdef int overflow
    cdef long long result = _integer(value, name, &overflow)
    if overflow < 0 or (not overflow and result < 0):
        raise ValueError(f"{name} must be non-negative")
    if overflow or <size_t>result > ((<size_t>-1) >> 1):
        raise ValueError(f"{name} is too large for this platform")
    return <Py_ssize_t>result


cdef dict _settings_snapshot(_nghttp2.nghttp2_session *session, bint local):
    """Copy native local or peer SETTINGS values into a Python mapping."""
    cdef dict result = {}

    for setting in Setting:
        if local:
            result[setting] = _nghttp2.nghttp2_session_get_local_settings(
                session, setting,
            )
        else:
            result[setting] = _nghttp2.nghttp2_session_get_remote_settings(
                session, setting,
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
    if error_code == _nghttp2.NGHTTP2_ERR_DATA_EXIST:
        return StreamStateError(message)
    if error_code == _nghttp2.NGHTTP2_ERR_BAD_CLIENT_MAGIC:
        return ConnectionProtocolError(message)
    if error_code in (
        _nghttp2.NGHTTP2_ERR_FLOODED,
        _nghttp2.NGHTTP2_ERR_TOO_MANY_CONTINUATIONS,
    ):
        return DenialOfServiceError(message)
    if error_code == _nghttp2.NGHTTP2_ERR_INVALID_ARGUMENT:
        return ValueError(message)
    if error_code == _nghttp2.NGHTTP2_ERR_TOO_MANY_SETTINGS:
        return ValueError(message)
    return InternalError(message)


cdef object _frame_not_sent_error(int error_code):
    """Translate a delayed frame failure into the event error hierarchy."""
    if error_code == _nghttp2.NGHTTP2_ERR_FRAME_SIZE_ERROR:
        return StreamProtocolError(
            "outbound header block exceeds max_send_header_block_length",
        )
    if error_code in (
        _nghttp2.NGHTTP2_ERR_PROTO,
        _nghttp2.NGHTTP2_ERR_INVALID_STREAM_STATE,
    ):
        return StreamProtocolError(_error_message(error_code))
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


cdef void _random_bytes(uint8_t *destination, size_t length) noexcept:
    """Seed the native stream map with operating-system randomness."""
    cdef bytes value

    memset(destination, 0, length)
    try:
        value = urandom(length)
        memcpy(destination, PyBytes_AS_STRING(value), length)
    except BaseException:
        # The native callback cannot report failure. A deterministic seed
        # matches libnghttp2's documented behavior when no callback exists.
        pass


cdef char *_reserve_output(Connection connection, size_t length) except NULL:
    """Return space for more output, growing the staging buffer geometrically."""
    cdef Py_ssize_t used = connection._output_size
    cdef Py_ssize_t capacity = PyByteArray_GET_SIZE(connection._output)
    cdef Py_ssize_t target

    if length > <size_t>(((<size_t>-1) >> 1) - <size_t>used):
        raise MemoryError("outbound data is too large")
    target = used + <Py_ssize_t>length
    if target > capacity:
        # Doubling a capacity this large could overflow Py_ssize_t.
        if capacity < (((<size_t>-1) >> 2)):
            target = max(target, 2 * capacity, 4096)
        PyByteArray_Resize(connection._output, target)
    connection._output_size = used + <Py_ssize_t>length
    return PyByteArray_AS_STRING(connection._output) + used


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

    if connection._output_remaining >= 0:
        if connection._output_remaining == 0:
            return _nghttp2.NGHTTP2_ERR_WOULDBLOCK
        accepted = min(accepted, <size_t>connection._output_remaining)
    try:
        memcpy(_reserve_output(connection, accepted), data, accepted)
    except BaseException as error:
        return _callback_failed(connection, error)
    if connection._output_remaining >= 0:
        connection._output_remaining -= accepted
    return accepted


cdef inline size_t _copy_body(
    Connection connection,
    _BodySource body,
    char *destination,
    size_t length,
) except? -1:
    """Consume queued chunks into an already allocated frame buffer."""
    cdef bytes chunk
    cdef size_t available, copied = 0, take

    while body.head < len(body.chunks) and copied < length:
        chunk = body.chunks[body.head]
        available = len(chunk) - body.offset
        take = min(available, length - copied)
        memcpy(destination + copied, PyBytes_AS_STRING(chunk) + body.offset, take)
        copied += take
        body.offset += take
        body.queued_size -= take
        connection._queued_body_size -= take
        if body.offset == len(chunk):
            # Release sent bytes now; the list slot is reclaimed below.
            body.chunks[body.head] = None
            body.head += 1
            body.offset = 0
    # Removing the sent prefix shifts the rest, so do it only once the prefix is
    # at least half the list; draining then stays linear in the chunk count.
    if body.head == len(body.chunks):
        body.chunks.clear()
        body.head = 0
    elif body.head >= 32 and 2 * body.head >= len(body.chunks):
        del body.chunks[:body.head]
        body.head = 0
    return copied


cdef int _send_body(
    _nghttp2.nghttp2_session *session,
    _nghttp2.nghttp2_frame *frame,
    const uint8_t *frame_header,
    size_t length,
    _nghttp2.nghttp2_data_source *source,
    void *user_data,
) noexcept:
    """Collect a whole DATA frame without an intermediate native body copy."""
    cdef Connection connection = <Connection>user_data
    cdef _BodySource body
    cdef size_t copied
    cdef char *destination

    try:
        # No padding callback is installed; _read_body only uses NO_COPY
        # when the whole frame fits the remaining output limit.
        if frame.data.padlen or 0 <= connection._output_remaining < length + 9:
            raise InternalError("unexpected DATA output mode")
        body = connection._bodies[frame.hd.stream_id]
        if length > ((<size_t>-1) >> 1) - 9:
            raise MemoryError("outbound data is too large")
        destination = _reserve_output(connection, length + 9)
        memcpy(destination, frame_header, 9)
        copied = _copy_body(connection, body, destination + 9, length)
        if copied != length:
            raise InternalError("DATA source did not provide the prepared body")
        if connection._output_remaining >= 0:
            connection._output_remaining -= length + 9
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef _nghttp2.nghttp2_ssize _read_body(
    _nghttp2.nghttp2_session *session,
    int32_t stream_id,
    uint8_t *buffer,
    size_t length,
    uint32_t *data_flags,
    _nghttp2.nghttp2_data_source *source,
    void *user_data,
) noexcept:
    """Prepare queued body bytes and emit the stream's terminal marker.

    Queue counters are reduced when the engine pulls bytes into a DATA frame.
    Empty, unfinished queues defer DATA generation until the application
    queues more bytes.
    """
    cdef Connection connection = <Connection>user_data
    cdef _BodySource body
    cdef size_t copied
    cdef bint complete
    cdef list trailers
    cdef _nghttp2.nghttp2_nv *native_headers = NULL
    cdef int result

    try:
        body = connection._bodies[stream_id]
        copied = min(length, body.queued_size)
        if (
            connection._output_remaining < 0
            or copied + 9 <= <size_t>connection._output_remaining
        ):
            # The NO_COPY callback must accept a complete frame atomically.
            complete = body.ended and copied == body.queued_size
            data_flags[0] |= _nghttp2.NGHTTP2_DATA_FLAG_NO_COPY
        else:
            copied = _copy_body(connection, body, <char *>buffer, length)
            complete = body.ended and body.head == len(body.chunks)
        if complete:
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
        if copied:
            return copied
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
            > <size_t>connection._max_inbound_header_list_size
        ):
            raise DenialOfServiceError("received header list exceeds configured size")
        if (
            len(connection._current_headers)
            >= connection._max_inbound_header_count
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


cdef int _invalid_header(
    _nghttp2.nghttp2_session *session,
    const _nghttp2.nghttp2_frame *frame,
    const uint8_t *name,
    size_t name_length,
    const uint8_t *value,
    size_t value_length,
    uint8_t flags,
    void *user_data,
) noexcept:
    """Reject invalid regular fields instead of silently discarding them."""
    return _nghttp2.NGHTTP2_ERR_TEMPORAL_CALLBACK_FAILURE


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
    cdef object header
    cdef bytes status = b""
    cdef int category

    headers = tuple(connection._current_headers)
    category = frame.headers.cat
    if category == _nghttp2.NGHTTP2_HCAT_REQUEST:
        connection._events.append(RequestReceived(
            frame.hd.stream_id,
            headers,
            bool(frame.hd.flags & _nghttp2.NGHTTP2_FLAG_END_STREAM),
        ))
    else:
        for header in headers:
            if header[0] == b":status":
                status = header[1]
                break
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
    if payload and not connection._auto_window_update:
        connection._unconsumed[frame.hd.stream_id] = (
            connection._unconsumed.get(frame.hd.stream_id, 0)
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
    connection._closing = True
    connection._close_error_code = frame.goaway.error_code
    connection._close_debug_data = PyBytes_FromStringAndSize(
        <const char *>frame.goaway.opaque_data,
        frame.goaway.opaque_data_len,
    )
    connection._events.append(GoAwayReceived(
        frame.goaway.last_stream_id,
        frame.goaway.error_code,
        connection._close_debug_data,
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
    cdef object local_error = None

    try:
        body = connection._bodies.pop(stream_id, None)
        if body is not None:
            connection._queued_body_size -= body.queued_size
        connection._data_chunks.pop(stream_id, None)
        connection._responses.discard(stream_id)
        connection._deferred_resets.pop(stream_id, None)
        if connection._local_stream_errors:
            local_error = connection._local_stream_errors.pop(stream_id, None)
        connection._events.append(StreamClosed(
            stream_id,
            error_code,
            local_error,
        ))
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef int _frame_sent(
    _nghttp2.nghttp2_session *session,
    const _nghttp2.nghttp2_frame *frame,
    void *user_data,
) noexcept:
    """Submit deferred resets and remember the final GOAWAY reason."""
    cdef Connection connection = <Connection>user_data
    cdef object error_code
    cdef int result
    cdef bint ends_stream = (
        connection._deferred_resets
        and frame.hd.flags & _nghttp2.NGHTTP2_FLAG_END_STREAM
        and frame.hd.type in (_nghttp2.NGHTTP2_DATA, _nghttp2.NGHTTP2_HEADERS)
    )

    if not ends_stream and frame.hd.type != _nghttp2.NGHTTP2_GOAWAY:
        return 0

    try:
        if ends_stream:
            error_code = connection._deferred_resets.pop(
                frame.hd.stream_id, None,
            )
            if error_code is not None and not (
                _nghttp2.nghttp2_session_get_stream_remote_close(
                    session, frame.hd.stream_id,
                )
            ):
                result = _nghttp2.nghttp2_submit_rst_stream(
                    session, _nghttp2.NGHTTP2_FLAG_NONE,
                    frame.hd.stream_id, error_code,
                )
                if result < 0:
                    _raise_nghttp2_error(result)
            return 0

        connection._closing = True
        connection._close_error_code = frame.goaway.error_code
        connection._close_debug_data = PyBytes_FromStringAndSize(
            <const char *>frame.goaway.opaque_data,
            frame.goaway.opaque_data_len,
        )
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)


cdef int _frame_not_sent(
    _nghttp2.nghttp2_session *session,
    const _nghttp2.nghttp2_frame *frame,
    int error_code,
    void *user_data,
) noexcept:
    """Fold delayed frame-preparation failures into stream lifecycle."""
    cdef Connection connection = <Connection>user_data
    cdef int result
    cdef int32_t stream_id

    try:
        if frame.hd.type == _nghttp2.NGHTTP2_HEADERS:
            stream_id = frame.hd.stream_id
        elif frame.hd.type == _nghttp2.NGHTTP2_PUSH_PROMISE:
            stream_id = frame.push_promise.promised_stream_id
        else:
            return 0

        if error_code in (
            _nghttp2.NGHTTP2_ERR_STREAM_CLOSED,
            _nghttp2.NGHTTP2_ERR_STREAM_CLOSING,
            _nghttp2.NGHTTP2_ERR_STREAM_SHUT_WR,
            _nghttp2.NGHTTP2_ERR_SESSION_CLOSING,
        ):
            return 0

        connection._local_stream_errors[stream_id] = (
            _frame_not_sent_error(error_code)
        )

        # libnghttp2 closes streams opened by failed request HEADERS and
        # PUSH_PROMISE itself. Existing streams need an explicit reset so the
        # application receives the same terminal StreamClosed lifecycle event.
        if (
            frame.hd.type == _nghttp2.NGHTTP2_HEADERS
            and frame.headers.cat != _nghttp2.NGHTTP2_HCAT_REQUEST
        ):
            result = _nghttp2.nghttp2_submit_rst_stream(
                session,
                _nghttp2.NGHTTP2_FLAG_NONE,
                stream_id,
                _nghttp2.NGHTTP2_INTERNAL_ERROR,
            )
            if result < 0 and result not in (
                _nghttp2.NGHTTP2_ERR_STREAM_CLOSED,
                _nghttp2.NGHTTP2_ERR_STREAM_CLOSING,
                _nghttp2.NGHTTP2_ERR_SESSION_CLOSING,
            ):
                raise _nghttp2_error(result)
        return 0
    except BaseException as error:
        return _callback_failed(connection, error)
