from libc.stdint cimport int32_t, uint8_t, uint32_t, uint64_t


cdef extern from "nghttp2/nghttp2.h":
    ctypedef Py_ssize_t nghttp2_ssize

    ctypedef struct nghttp2_session:
        pass

    ctypedef struct nghttp2_session_callbacks:
        pass

    ctypedef struct nghttp2_option:
        pass

    ctypedef struct nghttp2_frame_hd:
        size_t length
        int32_t stream_id
        uint8_t type
        uint8_t flags
        uint8_t reserved

    ctypedef struct nghttp2_priority_spec:
        int32_t stream_id
        int32_t weight
        uint8_t exclusive

    ctypedef struct nghttp2_nv:
        uint8_t *name
        uint8_t *value
        size_t namelen
        size_t valuelen
        uint8_t flags

    ctypedef struct nghttp2_settings_entry:
        int32_t settings_id
        uint32_t value

    ctypedef union nghttp2_data_source:
        int fd
        void *ptr

    ctypedef nghttp2_ssize (*nghttp2_data_source_read_callback2)(
        nghttp2_session *session,
        int32_t stream_id,
        uint8_t *buf,
        size_t length,
        uint32_t *data_flags,
        nghttp2_data_source *source,
        void *user_data,
    ) noexcept

    ctypedef struct nghttp2_data_provider2:
        nghttp2_data_source source
        nghttp2_data_source_read_callback2 read_callback

    ctypedef struct nghttp2_data:
        nghttp2_frame_hd hd
        size_t padlen

    ctypedef struct nghttp2_headers:
        nghttp2_frame_hd hd
        size_t padlen
        nghttp2_priority_spec pri_spec
        nghttp2_nv *nva
        size_t nvlen
        int cat

    ctypedef struct nghttp2_rst_stream:
        nghttp2_frame_hd hd
        uint32_t error_code

    ctypedef struct nghttp2_settings:
        nghttp2_frame_hd hd
        size_t niv
        nghttp2_settings_entry *iv

    ctypedef struct nghttp2_push_promise:
        nghttp2_frame_hd hd
        size_t padlen
        nghttp2_nv *nva
        size_t nvlen
        int32_t promised_stream_id
        uint8_t reserved

    ctypedef struct nghttp2_ping:
        nghttp2_frame_hd hd
        uint8_t opaque_data[8]

    ctypedef struct nghttp2_goaway:
        nghttp2_frame_hd hd
        int32_t last_stream_id
        uint32_t error_code
        uint8_t *opaque_data
        size_t opaque_data_len
        uint8_t reserved

    ctypedef struct nghttp2_window_update:
        nghttp2_frame_hd hd
        int32_t window_size_increment
        uint8_t reserved

    ctypedef struct nghttp2_extension:
        nghttp2_frame_hd hd
        void *payload

    ctypedef struct nghttp2_ext_altsvc:
        uint8_t *origin
        size_t origin_len
        uint8_t *field_value
        size_t field_value_len

    ctypedef struct nghttp2_origin_entry:
        uint8_t *origin
        size_t origin_len

    ctypedef struct nghttp2_ext_origin:
        size_t nov
        nghttp2_origin_entry *ov

    ctypedef struct nghttp2_ext_priority_update:
        int32_t stream_id
        uint8_t *field_value
        size_t field_value_len

    ctypedef struct nghttp2_extpri:
        uint32_t urgency
        int inc

    ctypedef union nghttp2_frame:
        nghttp2_frame_hd hd
        nghttp2_data data
        nghttp2_headers headers
        nghttp2_rst_stream rst_stream
        nghttp2_settings settings
        nghttp2_push_promise push_promise
        nghttp2_ping ping
        nghttp2_goaway goaway
        nghttp2_window_update window_update
        nghttp2_extension ext

    ctypedef nghttp2_ssize (*nghttp2_send_callback2)(
        nghttp2_session *session,
        const uint8_t *data,
        size_t length,
        int flags,
        void *user_data,
    ) noexcept

    ctypedef int (*nghttp2_on_frame_recv_callback)(
        nghttp2_session *, const nghttp2_frame *, void *
    ) noexcept
    ctypedef int (*nghttp2_on_data_chunk_recv_callback)(
        nghttp2_session *, uint8_t, int32_t, const uint8_t *, size_t, void *
    ) noexcept
    ctypedef int (*nghttp2_on_stream_close_callback)(
        nghttp2_session *, int32_t, uint32_t, void *
    ) noexcept
    ctypedef int (*nghttp2_on_begin_headers_callback)(
        nghttp2_session *, const nghttp2_frame *, void *
    ) noexcept
    ctypedef int (*nghttp2_on_header_callback)(
        nghttp2_session *, const nghttp2_frame *, const uint8_t *, size_t,
        const uint8_t *, size_t, uint8_t, void *
    ) noexcept
    ctypedef int (*nghttp2_on_frame_not_send_callback)(
        nghttp2_session *, const nghttp2_frame *, int, void *
    ) noexcept

    enum:
        NGHTTP2_ERR_WOULDBLOCK
        NGHTTP2_ERR_NOMEM
        NGHTTP2_ERR_CALLBACK_FAILURE
        NGHTTP2_ERR_DEFERRED
        NGHTTP2_ERR_INVALID_ARGUMENT
        NGHTTP2_ERR_STREAM_ID_NOT_AVAILABLE
        NGHTTP2_ERR_STREAM_CLOSED
        NGHTTP2_ERR_STREAM_CLOSING
        NGHTTP2_ERR_STREAM_SHUT_WR
        NGHTTP2_ERR_INVALID_STREAM_ID
        NGHTTP2_ERR_DEFERRED_DATA_EXIST
        NGHTTP2_ERR_START_STREAM_NOT_ALLOWED
        NGHTTP2_ERR_PUSH_DISABLED
        NGHTTP2_ERR_DATA_EXIST
        NGHTTP2_ERR_SESSION_CLOSING
        NGHTTP2_ERR_BAD_CLIENT_MAGIC
        NGHTTP2_ERR_FLOODED
        NGHTTP2_ERR_TOO_MANY_CONTINUATIONS
        NGHTTP2_FLAG_NONE
        NGHTTP2_FLAG_ACK
        NGHTTP2_FLAG_END_STREAM
        NGHTTP2_NV_FLAG_NO_INDEX
        NGHTTP2_DATA_FLAG_EOF
        NGHTTP2_DATA_FLAG_NO_END_STREAM
        NGHTTP2_DATA
        NGHTTP2_HEADERS
        NGHTTP2_RST_STREAM
        NGHTTP2_SETTINGS
        NGHTTP2_PUSH_PROMISE
        NGHTTP2_PING
        NGHTTP2_GOAWAY
        NGHTTP2_WINDOW_UPDATE
        NGHTTP2_ALTSVC
        NGHTTP2_ORIGIN
        NGHTTP2_PRIORITY_UPDATE
        NGHTTP2_HCAT_REQUEST
        NGHTTP2_HCAT_RESPONSE
        NGHTTP2_HCAT_PUSH_RESPONSE
        NGHTTP2_HCAT_HEADERS

    int nghttp2_session_callbacks_new(
        nghttp2_session_callbacks **callbacks_ptr,
    )
    void nghttp2_session_callbacks_del(nghttp2_session_callbacks *callbacks)
    void nghttp2_session_callbacks_set_send_callback2(
        nghttp2_session_callbacks *callbacks,
        nghttp2_send_callback2 send_callback,
    )
    void nghttp2_session_callbacks_set_on_frame_recv_callback(
        nghttp2_session_callbacks *, nghttp2_on_frame_recv_callback
    )
    void nghttp2_session_callbacks_set_on_data_chunk_recv_callback(
        nghttp2_session_callbacks *, nghttp2_on_data_chunk_recv_callback
    )
    void nghttp2_session_callbacks_set_on_stream_close_callback(
        nghttp2_session_callbacks *, nghttp2_on_stream_close_callback
    )
    void nghttp2_session_callbacks_set_on_begin_headers_callback(
        nghttp2_session_callbacks *, nghttp2_on_begin_headers_callback
    )
    void nghttp2_session_callbacks_set_on_header_callback(
        nghttp2_session_callbacks *, nghttp2_on_header_callback
    )
    void nghttp2_session_callbacks_set_on_frame_not_send_callback(
        nghttp2_session_callbacks *, nghttp2_on_frame_not_send_callback
    )

    int nghttp2_option_new(nghttp2_option **option_ptr)
    void nghttp2_option_del(nghttp2_option *option)
    void nghttp2_option_set_no_auto_window_update(
        nghttp2_option *option,
        int val,
    )
    void nghttp2_option_set_peer_max_concurrent_streams(
        nghttp2_option *option,
        uint32_t val,
    )
    void nghttp2_option_set_max_reserved_remote_streams(
        nghttp2_option *option,
        uint32_t val,
    )
    void nghttp2_option_set_max_send_header_block_length(
        nghttp2_option *option,
        size_t val,
    )
    void nghttp2_option_set_max_deflate_dynamic_table_size(
        nghttp2_option *option,
        size_t val,
    )
    void nghttp2_option_set_max_outbound_ack(
        nghttp2_option *option,
        size_t val,
    )
    void nghttp2_option_set_max_settings(
        nghttp2_option *option,
        size_t val,
    )
    void nghttp2_option_set_stream_reset_rate_limit(
        nghttp2_option *option,
        uint64_t burst,
        uint64_t rate,
    )
    void nghttp2_option_set_max_continuations(
        nghttp2_option *option,
        size_t val,
    )
    void nghttp2_option_set_glitch_rate_limit(
        nghttp2_option *option,
        uint64_t burst,
        uint64_t rate,
    )
    void nghttp2_option_set_builtin_recv_extension_type(
        nghttp2_option *, uint8_t
    )

    int nghttp2_session_client_new2(
        nghttp2_session **session_ptr,
        const nghttp2_session_callbacks *callbacks,
        void *user_data,
        const nghttp2_option *option,
    )
    int nghttp2_session_server_new2(
        nghttp2_session **session_ptr,
        const nghttp2_session_callbacks *callbacks,
        void *user_data,
        const nghttp2_option *option,
    )
    void nghttp2_session_del(nghttp2_session *session)
    int nghttp2_session_send(nghttp2_session *session)
    nghttp2_ssize nghttp2_session_mem_recv2(
        nghttp2_session *session, const uint8_t *data, size_t length
    )
    int nghttp2_session_resume_data(nghttp2_session *session, int32_t stream_id)
    int nghttp2_submit_settings(
        nghttp2_session *, uint8_t, const nghttp2_settings_entry *, size_t
    )
    int32_t nghttp2_submit_request2(
        nghttp2_session *, const nghttp2_priority_spec *, const nghttp2_nv *,
        size_t, const nghttp2_data_provider2 *, void *
    )
    int nghttp2_submit_response2(
        nghttp2_session *, int32_t, const nghttp2_nv *, size_t,
        const nghttp2_data_provider2 *
    )
    int32_t nghttp2_submit_headers(
        nghttp2_session *, uint8_t, int32_t, const nghttp2_priority_spec *,
        const nghttp2_nv *, size_t, void *
    )
    int nghttp2_submit_trailer(
        nghttp2_session *, int32_t, const nghttp2_nv *, size_t
    )
    int32_t nghttp2_submit_push_promise(
        nghttp2_session *, uint8_t, int32_t, const nghttp2_nv *, size_t, void *
    )
    int nghttp2_submit_rst_stream(
        nghttp2_session *, uint8_t, int32_t, uint32_t
    )
    int nghttp2_submit_ping(nghttp2_session *, uint8_t, const uint8_t *)
    int nghttp2_submit_goaway(
        nghttp2_session *, uint8_t, int32_t, uint32_t,
        const uint8_t *, size_t
    )
    int nghttp2_submit_window_update(
        nghttp2_session *, uint8_t, int32_t, int32_t
    )
    int nghttp2_session_consume_stream(nghttp2_session *, int32_t, size_t)
    int nghttp2_session_consume(nghttp2_session *, int32_t, size_t)
    int nghttp2_session_want_read(nghttp2_session *)
    int nghttp2_session_want_write(nghttp2_session *)
    uint32_t nghttp2_session_get_next_stream_id(nghttp2_session *)
    int nghttp2_session_check_request_allowed(nghttp2_session *)
    int32_t nghttp2_session_get_last_proc_stream_id(nghttp2_session *)
    int nghttp2_submit_shutdown_notice(nghttp2_session *)
    int nghttp2_session_terminate_session(nghttp2_session *, uint32_t)
    int nghttp2_session_terminate_session2(
        nghttp2_session *, int32_t, uint32_t
    )
    int nghttp2_session_upgrade2(
        nghttp2_session *, const uint8_t *, size_t, int, void *
    )
    nghttp2_ssize nghttp2_pack_settings_payload2(
        uint8_t *, size_t, const nghttp2_settings_entry *, size_t
    )
    int nghttp2_submit_altsvc(
        nghttp2_session *, uint8_t, int32_t, const uint8_t *, size_t,
        const uint8_t *, size_t
    )
    int nghttp2_submit_origin(
        nghttp2_session *, uint8_t, const nghttp2_origin_entry *, size_t
    )
    int nghttp2_submit_priority_update(
        nghttp2_session *, uint8_t, int32_t, const uint8_t *, size_t
    )
    int nghttp2_session_change_extpri_stream_priority(
        nghttp2_session *, int32_t, const nghttp2_extpri *, int
    )
    int nghttp2_session_get_extpri_stream_priority(
        nghttp2_session *, nghttp2_extpri *, int32_t
    )
    int32_t nghttp2_session_get_remote_window_size(nghttp2_session *)
    int32_t nghttp2_session_get_stream_remote_window_size(
        nghttp2_session *, int32_t
    )
    int32_t nghttp2_session_get_local_window_size(nghttp2_session *)
    int32_t nghttp2_session_get_stream_local_window_size(
        nghttp2_session *, int32_t
    )
    int nghttp2_session_get_stream_local_close(nghttp2_session *, int32_t)
    uint32_t nghttp2_session_get_local_settings(nghttp2_session *, int32_t)
    uint32_t nghttp2_session_get_remote_settings(nghttp2_session *, int32_t)
    const char *nghttp2_strerror(int lib_error_code)
    int nghttp2_is_fatal(int lib_error_code)
