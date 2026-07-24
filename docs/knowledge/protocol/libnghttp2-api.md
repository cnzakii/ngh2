---
title: libnghttp2 v1.69 public API and callback contracts
description: Version-pinned reference for libnghttp2's integration model, callback contracts, options, complete public function families, deprecations, and observable capability boundaries.
topics: [http2, libnghttp2, api, callbacks, options, flow-control, hpack, deprecations]
checked_at: 2026-07-25
---

# libnghttp2 v1.69 Public API And Callback Contracts

## Scope And Evidence

This document describes libnghttp2 itself. It does not decide which capabilities
a Python binding should expose or how such a binding should model them.

**Observed practice:** the baseline is libnghttp2 `v1.69.0`, commit
[`68cb6900fde14c77f0cd7add0e094a862960eb99`](https://github.com/nghttp2/nghttp2/tree/68cb6900fde14c77f0cd7add0e094a862960eb99).
The inventory contains all 181 functions declared with `NGHTTP2_EXTERN` in the
pinned
[`nghttp2.h`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h).
The function count does not include public typedefs or macros. Their complete
families are inventoried below because callback control values, frame layouts,
flags, and error domains change how the functions can be used.

When an application translation unit defines `NGHTTP2_NO_SSIZE_T`, 15
deprecated system-`ssize_t` function declarations are hidden and 166 current
function declarations remain visible. This consumer-side declaration filter
does not remove the old symbols from a normal libnghttp2 build:
`BUILDING_NGHTTP2` explicitly undefines `NGHTTP2_NO_SSIZE_T`. Sources:
[conditional declaration guard](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L50-L84)
and [deprecated compatibility declarations](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L910-L1100).

The online documentation currently identifies itself as `1.70.0-DEV`.
Consequently:

- official recommendations are read from the pinned
  [Programmer's Guide](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst);
- API contracts and deprecation notices are read from the pinned public header;
- ambiguous documentation is resolved, and explicitly identified as such, by
  the pinned implementation source;
- the current [package README](https://nghttp2.org/documentation/package_README.html)
  is an entry point, not evidence of stable `v1.69.0` behavior.

The package README describes the complete nghttp2 distribution: libnghttp2,
client, server, proxy, load generator, and HPACK tools. Its statement that the
HTTP/2 framing layer is reusable and HPACK has a public API applies to
libnghttp2; the executable programs and their TLS, event-loop, and application
dependencies are separate products. A library-only build is explicitly
supported. Sources: [pinned README, development status and requirements](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/README.rst#L9-L88).
The same README explicitly calls the generated documentation incomplete, which
is why public-header and implementation verification remain necessary. Source:
[pinned documentation build section](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/README.rst#L304-L322).

## Public Object Model

The main public objects and value types are:

| Type | Role and ownership boundary |
|---|---|
| `nghttp2_session` | Opaque client- or server-side HTTP/2 connection state. One session may only be used by one thread at a time. |
| `nghttp2_session_callbacks` | Opaque callback configuration. A constructor copies its members; the session does not retain the callback-set object. |
| `nghttp2_option` | Opaque construction-time options. A `new2`/`new3` constructor reads but does not retain it. |
| `nghttp2_frame` | Tagged public union passed to frame callbacks. CONTINUATION is handled internally and has no union member. |
| `nghttp2_nv` | Header name/value view plus indexing and no-copy flags. |
| `nghttp2_data_provider2` | A copied pair of application data source and pull callback; the pointed-to source remains application-owned. |
| `nghttp2_rcbuf` | Reference-counted header buffer used by the zero-copy header callback family. |
| `nghttp2_stream` | Borrowed opaque native stream handle returned by lookup APIs. |
| `nghttp2_hd_deflater` / `nghttp2_hd_inflater` | Independent HPACK codec state, separate from the codecs owned by a session. |
| `nghttp2_mem` | Custom allocator function table accepted by `new3` and HPACK `new2` constructors. |
| `nghttp2_extpri` | RFC 9218 urgency and incremental priority values. |
| `nghttp2_error` | Negative local library errors and callback control values. |
| `nghttp2_error_code` | Non-negative HTTP/2 wire error codes used by RST_STREAM and GOAWAY. |

Sources: [opaque declarations](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L135-L178),
[frame and data types](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L850-L1458),
and [session construction](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3270-L3422).

### Complete public type and constant families

The pinned public header defines these 10 enum families:

| Enum | Contract dimension |
|---|---|
| `nghttp2_error` | Local library errors, fatal threshold, and callback control values. |
| `nghttp2_error_code` | HTTP/2 wire errors carried in RST_STREAM and GOAWAY. |
| `nghttp2_frame_type` | Standard and built-in extension frame type codes. |
| `nghttp2_flag` | Frame flags whose interpretation depends on frame type. |
| `nghttp2_settings_id` | SETTINGS identifiers recognized by the library. |
| `nghttp2_data_flag` | DATA-provider EOF, trailer, and NO_COPY output flags. |
| `nghttp2_nv_flag` | HPACK indexing and header name/value ownership flags. |
| `nghttp2_headers_category` | Request, response, push response, or additional HEADERS classification. |
| `nghttp2_hd_inflate_flag` | Incremental standalone HPACK decoder output state. |
| `nghttp2_stream_proto_state` | Seven public stream protocol states. |

The public scalar typedef `nghttp2_ssize` is the signed counterpart of
`size_t` and is defined as `ptrdiff_t`.

The 26 concrete public record or union typedefs are:

```text
nghttp2_info                 nghttp2_vec
nghttp2_nv                   nghttp2_frame_hd
nghttp2_data_source          nghttp2_data_provider
nghttp2_data_provider2       nghttp2_data
nghttp2_priority_spec        nghttp2_headers
nghttp2_priority             nghttp2_rst_stream
nghttp2_settings_entry       nghttp2_settings
nghttp2_push_promise         nghttp2_ping
nghttp2_goaway               nghttp2_window_update
nghttp2_extension            nghttp2_frame
nghttp2_mem                  nghttp2_extpri
nghttp2_ext_altsvc           nghttp2_origin_entry
nghttp2_ext_origin           nghttp2_ext_priority_update
```

The seven opaque public object types are `nghttp2_session`, `nghttp2_rcbuf`,
`nghttp2_session_callbacks`, `nghttp2_option`, `nghttp2_hd_deflater`,
`nghttp2_hd_inflater`, and `nghttp2_stream`.

The header defines 32 callback function-pointer typedefs: the current and
deprecated I/O, DATA-provider, frame, header, padding, extension, diagnostic,
random, and debug forms. `nghttp2_malloc`, `nghttp2_free`, `nghttp2_calloc`,
and `nghttp2_realloc` are four additional allocator function-pointer typedefs.

Excluding include guards and symbol-visibility machinery, `nghttp2.h` exposes
22 protocol and default-value macros covering protocol IDs, weights, flow
control, HPACK defaults, client magic, SETTINGS limits, concurrency, and RFC
9218 urgency. The generated `nghttp2ver.h` adds `NGHTTP2_VERSION` and
`NGHTTP2_VERSION_NUM`.

Sources: [public value and frame types](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L135-L1458),
[callback and allocator types](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1459-L2952),
[extension and stream types](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5030-L6848),
and [version macro template](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2ver.h.in).

## Error And Callback-Control Domains

Three domains share integer-shaped values but have different contracts:

| Domain | Examples | Interpretation |
|---|---|---|
| `nghttp2_error` library results | `ERR_PROTO`, `ERR_STREAM_CLOSED`, `ERR_NOMEM` | Negative local engine, state, resource, or callback results. |
| `nghttp2_error_code` wire results | `PROTOCOL_ERROR`, `CANCEL`, `REFUSED_STREAM` | Non-negative HTTP/2 codes carried by RST_STREAM and GOAWAY. |
| Callback control values from `nghttp2_error` | `WOULDBLOCK`, `EOF`, `DEFERRED`, `PAUSE`, `TEMPORAL_CALLBACK_FAILURE`, `CANCEL` | Special results accepted only by the callback contracts that name them. |

`nghttp2_strerror()` formats library errors;
`nghttp2_http2_strerror()` formats wire errors. `nghttp2_is_fatal()` returns
nonzero only for a library value strictly below `NGHTTP2_ERR_FATAL` (`-900`).
The defined fatal values in `v1.69.0` are `NOMEM`, `CALLBACK_FAILURE`,
`BAD_CLIENT_MAGIC`, `FLOODED`, and `TOO_MANY_CONTINUATIONS`. After receiving
one, the header permits only `nghttp2_session_del()` on that session.

`on_invalid_frame_recv` receives a library error. Native code maps selected
library errors to wire errors before queuing RST_STREAM or GOAWAY.
`on_stream_close` usually receives a wire error, but its public contract says
that is not guaranteed.

Sources: [library errors](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L268-L479),
[wire errors](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L773-L834),
[fatal classification](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L82-L88),
and [library-to-wire mapping](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3362-L3384).

## Official Integration Model

### Minimal lifecycle

The public API is designed around this lifecycle:

1. Allocate a callback set and register only the hooks the application needs.
2. Optionally allocate and populate an option object.
3. Create one client or server session. The constructor copies callbacks and
   options, so their configuration objects may then be freed.
4. Submit the initial SETTINGS frame. A client session itself serializes the
   24-byte client magic; the application is still responsible for submitting
   SETTINGS.
5. Feed received bytes into the session and drain newly available serialized
   bytes from it.
6. Submit requests, responses, control frames, and body providers. Submission
   generally queues work; it does not synchronously serialize or transport it.
7. Continue driving input and output until both `want_read()` and `want_write()`
   are false, while separately accounting for bytes already removed from the
   session but not yet written to the transport.
8. Delete the session.

Sources: [pinned architecture and remarks](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L4-L104)
and [constructor ownership](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3270-L3422).
For the connection/session ownership hierarchy and full input/output callback
timelines, see [session state and data flow](libnghttp2-session.md).

### Memory-driven and callback-driven I/O

| Direction | Memory-driven API | Callback-driven API | Official guidance |
|---|---|---|---|
| Input | `nghttp2_session_mem_recv2(session, bytes, len)` | `nghttp2_session_recv(session)` pulls through `nghttp2_recv_callback2` | Use `mem_recv2()` when in doubt; it is simpler and can avoid callback overhead. |
| Output | Repeatedly call `nghttp2_session_mem_send2(session, &ptr)` until it returns 0 | `nghttp2_session_send(session)` pushes through `nghttp2_send_callback2` until blocked, flow-controlled, or empty | Use `mem_send2()` when in doubt; `send()` can fit a fixed-size application output buffer more naturally. |

`mem_send2()` returns one internally owned chunk at a time. The pointer is
invalidated by the next `mem_send2()` or `send()` call, and the caller must
consume the whole returned chunk before asking for another. Either output path
may produce small chunks, so aggregation is the application's responsibility.
Sources: [input/output guide](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L41-L82)
and [`mem_send2()` contract](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3505-L3569).

The guide's sentence at lines 69–73 names `mem_send2()` before `mem_recv2()`,
although its stated rationale is that processing input can enqueue output.
Pinned official examples implement that rationale as receive-then-send:
[`libevent-server.c`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/examples/libevent-server.c#L278-L301)
and
[`libevent-client.c`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/examples/libevent-client.c#L431-L455).
The literal order in that guide sentence is therefore internally inconsistent
with both its explanation and the examples.

### Reentrancy and thread boundary

A session is not concurrently thread-safe. More strongly, none of `send()`,
`mem_send2()`, `recv()`, or `mem_recv2()` may be called directly or indirectly
from a libnghttp2 callback; the guide says doing so leads to a crash. Submission
functions may be called from callbacks, after which the application resumes the
drive loop outside the callback. Source: [pinned guide, remarks](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L84-L104).

## Submission, Serialization, And Delivery Are Different Milestones

The outbound API has at least four distinct milestones:

| Milestone | What libnghttp2 establishes | What it does not establish |
|---|---|---|
| Submission returns success | Parameters passed immediate validation and an outbound item was queued, or provider state was attached. | The item has not necessarily been prepared, serialized, or assigned a live stream object. |
| DATA provider is called | Native scheduling and current remote flow-control credit allow libnghttp2 to pull up to `length` bytes. | Those bytes have not necessarily been returned to the application's transport buffer. |
| `on_frame_send` runs | With `session_send()`, its callback sink has accepted the complete frame. With `mem_send2()`, native completion runs before the call returns its final chunk to the application. | Application return from `mem_send2()`, socket/TLS acceptance, peer receipt, and remote-application processing are not uniformly established. |
| Application writes returned bytes | Bytes have reached the application's selected transport boundary. | libnghttp2 has no acknowledgement of kernel, TLS peer, HTTP/2 peer, or application processing. |

For a new request, `nghttp2_submit_request2()` returns an assigned stream ID
before the native stream is opened. The stream opens during outbound
preparation, before `before_frame_send`; most operations on that stream are
invalid before then, with a documented special case for setting stream user
data. Source: [`submit_request2()` warning](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4459-L4597).

`submit_request2()` and `submit_response2()` attach one persistent
`nghttp2_data_provider2`. The library pulls from it as flow control and
scheduling permit. `submit_data2()` instead queues another provider, but only
one unfinished DATA or HEADERS item is allowed per stream. Its own documentation
recommends the request/response provider path for ordinary HTTP because chaining
`submit_data2()` requires waiting for `on_frame_send` before submitting the next
provider. Source: [`submit_data2()` contract and recommendation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4881-L4980).

`NGHTTP2_DATA_FLAG_NO_COPY` is a separate output boundary. It makes
libnghttp2 invoke `nghttp2_send_data_callback` to write a complete DATA frame,
even when the application drives ordinary output with `mem_send2()`. That DATA
payload is not returned through the memory-send result. Source:
[pinned NO_COPY send path](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L2990-L3098).

## Callback Contract

### Common rules

Most session callbacks receive the current `nghttp2_session *` and the
constructor's current `user_data`. Frame, header, and DATA pointers are borrowed
inputs, but some receive callbacks extend their validity when processing is
paused:

- a paused byte-range header callback keeps its frame, name, and value pointers
  valid until the next `mem_recv2()` or `recv()` call;
- the application must retain the corresponding input bytes because those
  pointers may refer into the input buffer;
- when a DATA callback pauses `mem_recv2()`, its data pointer remains valid
  until the next `mem_recv2()` or `recv()` call, and the corresponding input
  bytes must also be retained;
- `on_header_callback2` rcbuf values can be retained with `incref()` and
  released with `decref()`;
- if retained rcbuf values came from a session using a custom allocator, that
  allocator's free function must outlive those values, even after session
  destruction.

Unless a callback explicitly documents another return value:

- return `0` to continue;
- any nonzero return is converted to `NGHTTP2_ERR_CALLBACK_FAILURE`;
- callback failure is fatal to the current drive call and generally the
  session;
- registration requirements and absent behavior are callback-specific; a
  missing observation hook can be inert, while a missing transport, body,
  extension, or NO_COPY callback can make its corresponding API path unusable.

`NGHTTP2_ERR_PAUSE` stops the current drive call without declaring protocol
failure. `NGHTTP2_ERR_TEMPORAL_CALLBACK_FAILURE` requests stream-local failure
where documented. `NGHTTP2_ERR_CANCEL` cancels the current optional operation
where documented. These values are not interchangeable.

Sources: [callback typedefs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1459-L2460)
and [callback dispatch implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3161-L3350).
Exact receive-buffer lifetimes are documented by the
[DATA and header callbacks](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1711-L2037).

### Input and receive callbacks

| Callback and parameters beyond `session`, `user_data` | When registered | Accepted result | When absent |
|---|---|---|---|
| `nghttp2_recv_callback2(buf, length, flags)` | `session_recv()` asks the application for up to `length` input bytes. `flags` is currently 0. | Byte count; `WOULDBLOCK`; `EOF`; `CALLBACK_FAILURE`. Returning 0 means `WOULDBLOCK`. | `mem_recv2()` needs no receive callback. Calling `session_recv()` requires one. |
| `nghttp2_on_begin_frame_callback(hd)` | Runs after header-level checks select a normal processing path and precedes `on_begin_headers` for a header block. CONTINUATION can invoke it. **Observed implementation:** early frame-size-error and native-ignore paths skip it. | `0` only. | No frame-start observation where native parsing otherwise continues. |
| `nghttp2_on_begin_headers_callback(frame)` | Starts a HEADERS or PUSH_PROMISE header block after the frame is accepted for processing. | `0`; `TEMPORAL_CALLBACK_FAILURE` resets the subject stream with INTERNAL_ERROR unless an RST with another code was submitted; fatal callback failure. | Header decoding and header callbacks continue without a begin notification. |
| `nghttp2_on_header_callback(frame, name, namelen, value, valuelen, flags)` | Emits each accepted field as borrowed byte ranges. Header data may refer to input memory. | `0`; `PAUSE`; `TEMPORAL_CALLBACK_FAILURE`; fatal callback failure. | Fields are not delivered to the application, but HPACK and HTTP validation still run. |
| `nghttp2_on_header_callback2(frame, name_rcbuf, value_rcbuf, flags)` | Same semantic event using reference-counted buffers. It takes precedence over the byte-range callback. | Same as `on_header_callback`. | The byte-range callback is used if present; otherwise fields are not delivered. |
| `nghttp2_on_invalid_header_callback(frame, name, lengths, value, flags)` | Receives only invalid regular fields considered ignorable by HTTP validation, and only while HTTP messaging validation is enabled. | `0` ignores the field; `PAUSE`; `TEMPORAL_CALLBACK_FAILURE` resets the subject stream; other nonzero is fatal. | If neither invalid-header callback is set, such a regular field is silently ignored. |
| `nghttp2_on_invalid_header_callback2(frame, name_rcbuf, value_rcbuf, flags)` | Same policy point with rcbuf values and precedence over the byte-range callback. | Same dispatch behavior as the byte-range callback. | Falls back to the byte-range callback; if neither is present, the field is ignored. |
| `nghttp2_on_data_chunk_recv_callback(flags, stream_id, data, len)` | Emits each received DATA payload chunk. `END_STREAM` on this chunk is not a reliable whole-stream completion signal. | `0`; `PAUSE`; other nonzero is fatal. | Payload bytes are not delivered to the application; native frame, stream, and flow-control processing continue. |
| `nghttp2_on_frame_recv_callback(frame)` | Runs after a valid complete frame is processed. HEADERS plus CONTINUATION are one callback; header arrays in the frame are empty because fields were emitted separately. | `0` only. | No completed-frame notification; native state and automatic responses continue. |
| `nghttp2_on_invalid_frame_recv_callback(frame, lib_error_code)` | Reports an unpacked invalid non-DATA frame. This is notification after or alongside native classification, not a veto. | `0` only. | Native handling still queues RST_STREAM or GOAWAY; only application notification is absent. |
| `nghttp2_on_stream_close_callback(stream_id, error_code)` | Runs when a stream, including a reserved stream, closes. Stream user data is still available during the callback. The code is usually an HTTP/2 wire error code, but the header says this is not guaranteed. | `0` only. | Native stream cleanup still occurs without an application close notification. |

Sources: [receive callback definitions](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1584-L2110),
[`session_recv()` callback timeline](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3570-L3682),
and [pinned frame-header dispatch](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L5509-L6127).

The application must impose its own accumulated header-size limit. HPACK can
make a large decoded field set inexpensive for an attacker to transmit.
Source: [`on_header_callback` warning](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1930-L2010).

### Invalid input is not one callback domain

| Invalid input class | Callback visibility | Native action |
|---|---|---|
| Invalid regular header eligible for application policy | `on_invalid_header` or `on_invalid_header2` | `0` ignores the field. `TEMPORAL_CALLBACK_FAILURE` queues stream RST. Without either callback, the field is silently ignored. |
| Invalid pseudo-header or a field name containing uppercase | Not passed to invalid-header callbacks | Treated as HTTP/message error and the subject stream is reset. |
| Unpacked invalid non-DATA frame | `on_invalid_frame_recv` if registered | Native code automatically queues RST_STREAM for stream errors or GOAWAY for connection errors whether or not the callback exists. |
| Invalid DATA processing, bad client magic, flooding, HPACK failure, or failures detected before a usable frame exists | Not guaranteed to reach `on_invalid_frame_recv` | Expressed through native state, queued control frames, or a negative receive return according to the specific failure. |
| Human-readable diagnostic text | `error_callback2` if registered | Returning 0 adds diagnostics only; it does not replace protocol callbacks or native recovery. A nonzero return is still a fatal callback failure. |

Sources: [invalid-frame callback contract](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1701-L1736),
[invalid-header contracts](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2011-L2110),
and [pinned invalid-input dispatch](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3240-L3475).

The two invalid-header typedef comments disagree about the default RST error
code: the byte-range version says `PROTOCOL_ERROR`, while the rcbuf version says
`INTERNAL_ERROR`. In `v1.69.0`, both callbacks share
`session_call_on_invalid_header`; a temporal failure is then handled as
`NGHTTP2_ERR_HTTP_HEADER`, which
[`get_error_code_from_lib_error_code()` maps to `PROTOCOL_ERROR`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3362-L3379).
The pinned source therefore resolves the header-comment conflict in favor of
`PROTOCOL_ERROR`.

### Outbound and DATA-provider callbacks

| Callback and parameters beyond `session`, `user_data` | When registered | Accepted result | When absent |
|---|---|---|---|
| `nghttp2_send_callback2(data, length, flags)` | `session_send()` offers serialized bytes; it may call repeatedly for one frame. `flags` is currently 0. | Accepted byte count; `WOULDBLOCK`; `CALLBACK_FAILURE`. | `mem_send2()` needs none. `session_send()` has no valid push sink. |
| `nghttp2_data_source_read_callback2(stream_id, buf, length, data_flags, source)` | Native scheduling pulls at most `length` body bytes. | Byte count; `DEFERRED`; `PAUSE`; `TEMPORAL_CALLBACK_FAILURE`; fatal callback failure. It may set EOF, NO_END_STREAM, or NO_COPY. | A body-bearing provider cannot function without its read callback. A null provider makes request/response HEADERS carry END_STREAM. |
| `nghttp2_data_source_read_length_callback2(frame_type, stream_id, connection_window, stream_window, peer_max_frame_size)` | Chooses a DATA read ceiling before the provider read; native flow-control limits still cap it. | A positive length in the documented range; an excessive value is clamped and a non-positive value fails the session callback path. | Native uses its normal DATA read limit, at most 16 KiB by default and still bounded by flow control and peer frame size. |
| `nghttp2_select_padding_callback2(frame, max_payloadlen)` | Chooses total payload length for HEADERS, PUSH_PROMISE, or DATA when padding is possible. | A value from unpadded `frame->hd.length` through the supplied maximum. | Native adds no padding. |
| `nghttp2_before_frame_send_callback(frame)` | Runs after a non-DATA frame is prepared and a request stream is opened, immediately before serialization is handed out. | `0`; `CANCEL`; fatal callback failure. | No application veto or pre-send hook. |
| `nghttp2_on_frame_send_callback(frame)` | Runs after a complete frame passes the native output path. With memory-send it runs before the call returns the final chunk; with callback-send it runs after the sink accepts the frame. | `0` only. | Native processing and stream transitions still occur; there is no application completion notification. |
| `nghttp2_on_frame_not_send_callback(frame, lib_error_code)` | Reports certain queued non-DATA frames that fail preparation or are cancelled. | `0` only. | Native drops/cancels the item and performs any applicable stream transition or cleanup without application notification. |
| `nghttp2_send_data_callback(frame, framehd, length, source)` | Required only after a provider sets `NO_COPY`; the application must emit the complete DATA frame, including header and padding. | `0`; `WOULDBLOCK` only before writing anything; `PAUSE` after completion; `TEMPORAL_CALLBACK_FAILURE`; fatal callback failure. | A provider returning `NO_COPY` fails the callback path. Ordinary copy mode is unaffected. |

Sources: [send and DATA callback definitions](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L910-L1057),
[outbound callback definitions](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1459-L1905),
and [`session_send()` timeline](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3423-L3504).

`on_frame_not_send` is narrower than its name:

- it is never a DATA-frame callback;
- pinned source suppresses it for library-generated WINDOW_UPDATE;
- pinned source also suppresses it for an RST_STREAM rejected solely because
  the stream is already closed;
- it reports native preparation/cancellation failure, not transport failure.

Source: [pinned outbound preparation and suppression rules](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L2838-L2960).

The generic `session_send()` comment places `before_frame_send` after a
padding step that names DATA, but the `v1.69.0` send loop invokes it only when
the selected frame is not DATA. DATA preparation instead runs the read-length,
provider, and padding callbacks. Sources:
[`session_send()` timeline](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3423-L3504)
and [pinned send loop](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L2838-L3039).

For `mem_send2()`, the pinned implementation calls native completion,
including `on_frame_send`, before it returns the final internal chunk pointer
and length. Source:
[`mem_send2()` completion order](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3127-L3151).

The official guide also documents a sequencing use for `on_frame_send`:
submitting RST_STREAM immediately cancels queued HEADERS and DATA for the same
stream, so an application that intentionally wants the RST only after those
frames must submit it from a later frame-send callback. Source: [pinned
transmission ordering guide](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L183-L226).

### Extension, diagnostic, and random callbacks

| Callback | Registered behavior | Behavior when absent |
|---|---|---|
| `nghttp2_pack_extension_callback2(buf, len, frame)` | Serializes only the payload for `submit_extension`; native code serializes the frame header. `CANCEL` triggers `on_frame_not_send`. | `submit_extension()` returns `NGHTTP2_ERR_INVALID_STATE`. Built-in extension submitters do not use this callback. |
| `nghttp2_on_extension_chunk_recv_callback(hd, data, len)` | Receives payload chunks for extension types enabled through the user-extension option. `CANCEL` aborts that frame. | Payload bytes are not delivered. The unpack callback still runs if registered, but receives only the frame header and application state, not the raw payload. |
| `nghttp2_unpack_extension_callback(payload**, hd)` | Converts application-collected user-extension bytes into an application-owned opaque payload later exposed through `frame->ext.payload`. | A type enabled as a user extension is silently ignored; its extension-chunk, unpack, and completed-frame callbacks do not run; and the pinned implementation counts the frame through its glitch rate limiter. |
| `nghttp2_error_callback2(lib_error_code, msg, len)` | Receives unstable human-oriented diagnostic text and a library error code. The `*2` callback takes precedence over the old text-only callback. | No diagnostic text is formatted or delivered; protocol behavior is unchanged. |
| `nghttp2_rand_callback(dest, destlen)` | Supplies unpredictable bytes during session construction. `v1.69.0` uses them as the internal stream-map hash seed. | The seed is exactly zero. The setter is optional for compatibility, but the header explicitly recommends registration against suspicious remote activity. |

Sources: [extension and diagnostic callback definitions](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2220-L2460),
[extension framework guide](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L228-L474),
[user-extension dispatch](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L5878-L5910),
and [random-seed construction path](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L607-L613).

**Methodological synthesis:** the random seed changes how stream IDs are placed
into the internal hash map; it
does not change stream ID values, parity, allocation order, or protocol state.
The map adds the seed to each key before hashing, and resolves collisions by
probing. A peer that can open or reserve many streams can otherwise predict the
bucket layout and target extra collision work. A per-session unpredictable seed
makes that layout unavailable to the peer in advance. Sources:
[pinned map index and insertion](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_map.c#L76-L171)
and [session seed installation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L607-L613).

## Construction Options

All option setters mutate an `nghttp2_option` before session construction. The
session constructor copies their effects and does not retain the option object.
Sources: [option API](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2960-L3269).

| Option | Set behavior | Default or behavior when not set |
|---|---|---|
| `nghttp2_option_set_no_auto_window_update` | Makes application consumption calls responsible for restoring receive credit. The header explicitly says not to use raw `submit_window_update()` for this purpose. | Native code automatically manages receive WINDOW_UPDATE. |
| `nghttp2_option_set_peer_max_concurrent_streams` | Installs a provisional peer limit before initial peer SETTINGS arrives. | 100 outgoing streams provisionally; initial peer SETTINGS then replaces it with the advertised or protocol-default value. |
| `nghttp2_option_set_no_recv_client_magic` | Server stops consuming/validating the 24-byte client magic but still expects the following SETTINGS. | Server consumes and validates the client magic. |
| `nghttp2_option_set_no_http_messaging` | Disables libnghttp2's HTTP message-rule subset for non-HTTP uses. Client/server request roles remain enforced. | HTTP messaging validation is enabled. |
| `nghttp2_option_set_max_reserved_remote_streams` | Client bounds server-pushed streams in reserved(remote); excess pushes close without user callbacks. No server effect. | 200. |
| `nghttp2_option_set_user_recv_extension_type` | Enables a non-critical type above `0x9` for application chunk/unpack callbacks. May be called for multiple types. | Unknown extension types are ignored; sending extensions needs no receive option. |
| `nghttp2_option_set_builtin_recv_extension_type` | Enables a supported built-in decoder. User decoding takes precedence if the same type is enabled both ways. | Built-in extension frames of that type are not surfaced by the built-in handler. |
| `nghttp2_option_set_no_auto_ping_ack` | Disables automatic PING ACK so the application must submit it. | Native code automatically queues ACK for non-ACK PING. |
| `nghttp2_option_set_max_send_header_block_length` | Bounds estimated outbound header-block size; oversized preparation fails with FRAME_SIZE_ERROR. | 64 KiB. |
| `nghttp2_option_set_max_deflate_dynamic_table_size` | Caps the encoder table below the peer's advertised maximum. | 4 KiB cap. |
| `nghttp2_option_set_no_closed_streams` | Officially deprecated and has no effect because closed streams are no longer retained. | Same behavior. |
| `nghttp2_option_set_max_outbound_ack` | Caps queued SETTINGS ACK plus PING ACK frames before treating the peer as flooding. | 1000. |
| `nghttp2_option_set_max_settings` | Caps entries accepted in one SETTINGS frame. | 32. |
| `nghttp2_option_set_server_fallback_rfc7540_priorities` | Officially deprecated and has no effect because the old dependency tree was removed. | Same behavior. |
| `nghttp2_option_set_no_rfc9113_leading_and_trailing_ws_validation` | Disables RFC 9113 outer-whitespace validation for ordinary field values; stricter pseudo-fields remain unaffected. | Validation enabled. |
| `nghttp2_option_set_stream_reset_rate_limit` | Server-only token bucket for incoming RST_STREAM; exhaustion queues GOAWAY. | Burst 1000, refill 33 tokens/second. |
| `nghttp2_option_set_max_continuations` | Caps CONTINUATION frames following one header frame; excess closes the session. | 8. |
| `nghttp2_option_set_glitch_rate_limit` | Token bucket for native-defined suspicious activities; exhaustion queues GOAWAY with ENHANCE_YOUR_CALM. | Burst 10000, refill 330 tokens/second. |

The GOAWAY error used when the glitch bucket is exhausted is an implementation
observation in
[`session_update_glitch_ratelim`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3408-L3419);
the public option comment documents teardown but does not name that wire code.

## Complete Public Function Catalog

The tables below classify every `NGHTTP2_EXTERN` function in the pinned header.
“Use case” describes the native operation for which the function exists; it is
not a recommendation for any particular binding.

### Reference-counted buffers: 4

Source: [rcbuf API](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L479-L545).

| Function | Operation and use case |
|---|---|
| `nghttp2_rcbuf_incref` | Retain an rcbuf beyond the current callback. |
| `nghttp2_rcbuf_decref` | Release a retained reference; zero frees it. |
| `nghttp2_rcbuf_get_buf` | Obtain the underlying pointer/length view. |
| `nghttp2_rcbuf_is_static` | Detect static backing, useful to avoid duplicating interned/static header strings. |

### Callback-set lifecycle and registration: 31

The setter stores a function pointer; the corresponding typedef tables above
define invocation, arguments, allowed returns, and missing-callback behavior.
Sources: [callback setters](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2461-L2860).

| Function or comparable family | Operation and use case |
|---|---|
| `nghttp2_session_callbacks_new`, `nghttp2_session_callbacks_del` | Allocate a NULL-initialized reusable callback set; free it after constructors have copied it. |
| `nghttp2_session_callbacks_set_send_callback`, `nghttp2_session_callbacks_set_send_callback2` | Register push-output sink. Old system-`ssize_t` form is deprecated; `*2` uses `nghttp2_ssize`. |
| `nghttp2_session_callbacks_set_recv_callback`, `nghttp2_session_callbacks_set_recv_callback2` | Register pull-input source for `session_recv`. Old form is deprecated. |
| `nghttp2_session_callbacks_set_on_begin_frame_callback` | Register frame-start observation for normally processed frames, including CONTINUATION. |
| `nghttp2_session_callbacks_set_on_begin_headers_callback` | Register header-block start handling. |
| `nghttp2_session_callbacks_set_on_header_callback`, `nghttp2_session_callbacks_set_on_header_callback2` | Register copied/borrowed byte-view or rcbuf header delivery; `*2` takes precedence. |
| `nghttp2_session_callbacks_set_on_invalid_header_callback`, `nghttp2_session_callbacks_set_on_invalid_header_callback2` | Register invalid regular-field policy; `*2` takes precedence. |
| `nghttp2_session_callbacks_set_on_data_chunk_recv_callback` | Register inbound DATA chunk delivery. |
| `nghttp2_session_callbacks_set_on_frame_recv_callback` | Register completed valid-frame delivery. |
| `nghttp2_session_callbacks_set_on_invalid_frame_recv_callback` | Register invalid non-DATA frame notification. |
| `nghttp2_session_callbacks_set_on_stream_close_callback` | Register native stream-close notification. |
| `nghttp2_session_callbacks_set_before_frame_send_callback` | Register pre-send veto/hook for non-DATA frames. |
| `nghttp2_session_callbacks_set_on_frame_send_callback` | Register native frame-send completion. |
| `nghttp2_session_callbacks_set_on_frame_not_send_callback` | Register delayed non-DATA preparation/cancellation failure. |
| `nghttp2_session_callbacks_set_select_padding_callback`, `nghttp2_session_callbacks_set_select_padding_callback2` | Register outbound padding policy. Old form is deprecated. |
| `nghttp2_session_callbacks_set_data_source_read_length_callback`, `nghttp2_session_callbacks_set_data_source_read_length_callback2` | Register DATA payload-length policy. Old form is deprecated. |
| `nghttp2_session_callbacks_set_send_data_callback` | Register complete-frame writer for provider NO_COPY mode. |
| `nghttp2_session_callbacks_set_pack_extension_callback`, `nghttp2_session_callbacks_set_pack_extension_callback2` | Register user-extension encoder. Old form is deprecated. |
| `nghttp2_session_callbacks_set_on_extension_chunk_recv_callback`, `nghttp2_session_callbacks_set_unpack_extension_callback` | Register user-extension payload collection and decode. |
| `nghttp2_session_callbacks_set_error_callback`, `nghttp2_session_callbacks_set_error_callback2` | Register human diagnostics. Old text-only form is deprecated; `*2` takes precedence. |
| `nghttp2_session_callbacks_set_rand_callback` | Register unpredictable-byte source used at session creation. |

### Option lifecycle and setters: 20

The detailed defaults and effects are in [Construction Options](#construction-options).

| Function or family | Operation and use case |
|---|---|
| `nghttp2_option_new`, `nghttp2_option_del` | Allocate and free construction-time option sets. |
| `nghttp2_option_set_no_auto_window_update` | Select application-driven receive consumption. |
| `nghttp2_option_set_peer_max_concurrent_streams` | Set provisional peer concurrency before peer SETTINGS. |
| `nghttp2_option_set_no_recv_client_magic` | Move server-side client-magic handling to the application. |
| `nghttp2_option_set_no_http_messaging` | Disable the HTTP message validation layer. |
| `nghttp2_option_set_max_reserved_remote_streams` | Bound remotely reserved push streams. |
| `nghttp2_option_set_user_recv_extension_type`, `nghttp2_option_set_builtin_recv_extension_type` | Enable user-defined or built-in extension receive handling. |
| `nghttp2_option_set_no_auto_ping_ack` | Move PING acknowledgement to the application. |
| `nghttp2_option_set_max_send_header_block_length`, `nghttp2_option_set_max_deflate_dynamic_table_size` | Bound outbound header block and HPACK encoder resources. |
| `nghttp2_option_set_no_closed_streams` | Deprecated no-op. |
| `nghttp2_option_set_max_outbound_ack`, `nghttp2_option_set_max_settings` | Bound ACK retention and SETTINGS entries. |
| `nghttp2_option_set_server_fallback_rfc7540_priorities` | Deprecated no-op. |
| `nghttp2_option_set_no_rfc9113_leading_and_trailing_ws_validation` | Relax one RFC 9113 field-value check. |
| `nghttp2_option_set_stream_reset_rate_limit`, `nghttp2_option_set_glitch_rate_limit` | Configure native token-bucket abuse controls. |
| `nghttp2_option_set_max_continuations` | Bound header-block fragmentation. |

### Session construction, drive loop, and application data: 20

Sources: [constructors and drive APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3270-L3834).

| Function or comparable family | Operation and use case |
|---|---|
| `nghttp2_session_client_new`, `nghttp2_session_server_new` | Create client/server sessions from callbacks and user data. |
| `nghttp2_session_client_new2`, `nghttp2_session_server_new2` | Same, adding copied construction options. |
| `nghttp2_session_client_new3`, `nghttp2_session_server_new3` | Same, adding a custom memory allocator. |
| `nghttp2_session_del` | Destroy session state; NULL is accepted. |
| `nghttp2_session_send`, `nghttp2_session_mem_send2` | Push serialized output through a callback, or return one native chunk. |
| `nghttp2_session_mem_send` | Deprecated system-`ssize_t` memory-output form; use `mem_send2`. |
| `nghttp2_session_recv`, `nghttp2_session_mem_recv2` | Pull input through a callback, or consume caller-supplied bytes. |
| `nghttp2_session_mem_recv` | Deprecated system-`ssize_t` memory-input form; use `mem_recv2`. |
| `nghttp2_session_resume_data` | Requeue a provider that previously returned DEFERRED. |
| `nghttp2_session_want_read`, `nghttp2_session_want_write` | Query whether native protocol state still wants input/output. External buffered bytes are not counted. |
| `nghttp2_session_get_stream_user_data`, `nghttp2_session_set_stream_user_data` | Read/replace per-stream opaque application association. |
| `nghttp2_session_set_user_data` | Replace session-wide callback user data. |
| `nghttp2_session_get_outbound_queue_size` | Publicly described as a queued-frame count excluding deferred DATA. The pinned implementation only sums urgent, regular, and new-stream HEADERS queues; it excludes all stream-attached DATA and the active popped item. |

The `send_callback2` setter says it is unnecessary for a memory-send-only
application, while the basic constructor comments say it “must be specified.”
Pinned source copies a NULL callback and `mem_send2()` does not invoke it;
`session_send()` dereferences a send callback path. This is a documentation
inconsistency: the callback is operationally required by `session_send`, not by
`mem_send2`. Sources:
[`send_callback2` setter](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2522-L2536),
[constructor wording](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3270-L3333),
and [pinned send paths](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3123-L3180).

The queue-size implementation ends with a TODO to account for items attached
to streams. It cannot be interpreted as total pending work, schedulable frames,
serialized output, or delivery progress. `want_write()` separately observes
the active item and schedulable DATA. Sources:
[`get_outbound_queue_size()`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L7665-L7671)
and [`want_write()`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L7150-L7168).

### Flow-control, settings, lifecycle, and state: 39

Sources: [session queries and lifecycle](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3819-L4460)
and [window operations](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5270-L5385).

| Function or comparable family | Operation and use case |
|---|---|
| `nghttp2_session_get_stream_effective_recv_data_length`, `nghttp2_session_get_effective_recv_data_length` | Query stream/connection received bytes not yet reflected in WINDOW_UPDATE, adjusted for manual window changes. |
| `nghttp2_session_get_stream_effective_local_window_size`, `nghttp2_session_get_effective_local_window_size` | Query configured stream/connection receive-window target without subtracting received data. |
| `nghttp2_session_get_stream_local_window_size`, `nghttp2_session_get_local_window_size` | Query remaining peer send credit at stream/connection scope. Actual stream credit is their minimum. |
| `nghttp2_session_get_stream_remote_window_size`, `nghttp2_session_get_remote_window_size` | Query remaining local send credit advertised by peer at stream/connection scope. |
| `nghttp2_session_get_stream_local_close`, `nghttp2_session_get_stream_remote_close` | Query either half-closed direction; `-1` means stream absent. |
| `nghttp2_session_get_hd_inflate_dynamic_table_size`, `nghttp2_session_get_hd_deflate_dynamic_table_size` | Inspect session HPACK dynamic-table memory use. |
| `nghttp2_session_get_remote_settings`, `nghttp2_session_get_local_settings` | Read effective peer settings or locally acknowledged settings. |
| `nghttp2_session_set_next_stream_id`, `nghttp2_session_get_next_stream_id` | Advance or inspect outgoing stream-ID allocation. Exhaustion is represented by `1 << 31`. |
| `nghttp2_session_consume` | Mark bytes consumed at both stream and connection scope in manual receive-window mode. |
| `nghttp2_session_consume_connection`, `nghttp2_session_consume_stream` | Mark consumption independently at one flow-control scope. |
| `nghttp2_submit_window_update` | Apply a raw signed adjustment and, when positive, queue WINDOW_UPDATE. It also changes native unacknowledged-byte accounting. |
| `nghttp2_session_set_local_window_size` | Set an absolute stream or connection receive-window target; native code may queue WINDOW_UPDATE or defer a reduction until in-flight data drains. |
| `nghttp2_session_terminate_session`, `nghttp2_session_terminate_session2` | Queue terminal GOAWAY using native or explicit last-stream selection; native want flags end after transmission. |
| `nghttp2_submit_shutdown_notice` | Server-only first graceful-shutdown GOAWAY with maximum last stream; it does not itself begin final native termination. |
| `nghttp2_submit_goaway` | Queue non-terminal GOAWAY while allowing eligible remaining streams to continue. |
| `nghttp2_session_get_last_proc_stream_id` | Read the most recent peer stream delivered through `on_frame_recv`, suitable for GOAWAY boundaries. |
| `nghttp2_session_check_request_allowed` | Advisory check for client request admission considering role, IDs, GOAWAY, and native state. |
| `nghttp2_session_check_server_session` | Query immutable native session role. |
| `nghttp2_session_change_stream_priority`, `nghttp2_session_create_idle_stream` | Deprecated RFC 7540 priority-tree no-ops. |
| `nghttp2_session_upgrade`, `nghttp2_session_upgrade2` | Post-process already parsed and base64url-decoded h2c upgrade settings; `upgrade2` additionally records whether stream 1 was a HEAD request. |
| `nghttp2_pack_settings_payload`, `nghttp2_pack_settings_payload2` | Serialize the six-byte-per-entry HTTP2-Settings payload before application base64url encoding. Old form is deprecated. |
| `nghttp2_strerror`, `nghttp2_http2_strerror` | Convert library-internal negative errors or HTTP/2 wire error codes to strings. |
| `nghttp2_priority_spec_init`, `nghttp2_priority_spec_default_init`, `nghttp2_priority_spec_check_default` | Deprecated RFC 7540 dependency-priority value helpers. |

The receive-window APIs represent three different quantities:

- `local_window_size` is remaining credit after received bytes;
- `effective_local_window_size` is the configured window before subtracting
  received bytes;
- `effective_recv_data_length` is received/uncredited data adjusted by raw
  window changes.

`consume*()` reports application consumption in manual-auto-update mode.
`set_local_window_size()` sets an absolute target. `submit_window_update()`
applies a low-level delta and the header explicitly warns that it is not the
consumption API. These operations are related but not interchangeable.

The pinned `set_local_window_size()` header and implementation disagree on
argument validation. The header names a negative `stream_id` as invalid; the
implementation checks a negative `window_size` instead and returns success
when a nonzero stream lookup produces no stream. Sources:
[public comment](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5348-L5386)
and [pinned implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_submit.c#L334-L405).

### HTTP messages, control frames, and extensions: 21

Sources: [submission APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4459-L5739).

| Function or comparable family | Operation and use case |
|---|---|
| `nghttp2_submit_request`, `nghttp2_submit_request2` | Queue client request HEADERS and optional persistent body provider; return the reserved stream ID. Old provider form is deprecated. |
| `nghttp2_submit_response`, `nghttp2_submit_response2` | Queue server final/push response HEADERS and optional body provider. Informational headers use `submit_headers`. Old form is deprecated. |
| `nghttp2_submit_headers` | Low-level HEADERS for new requests, informational/additional headers, or explicit END_STREAM control. |
| `nghttp2_submit_trailer` | Queue terminal trailer HEADERS. When it follows a persistent request/response provider, that provider must report EOF plus NO_END_STREAM so DATA does not close the stream first. |
| `nghttp2_submit_data`, `nghttp2_submit_data2` | Queue an additional DATA provider; only one unfinished DATA/HEADERS item is allowed. Old form is deprecated. |
| `nghttp2_submit_rst_stream` | Queue stream reset and cancel pending HEADERS/DATA for the same stream. |
| `nghttp2_submit_settings` | Store pending local settings and queue SETTINGS. Flags are ignored. |
| `nghttp2_submit_push_promise` | Server reserves and returns a promised stream ID associated with an existing peer-initiated stream. |
| `nghttp2_submit_ping` | Queue PING or explicit ACK. Native automatic ACK normally handles received non-ACK PING. |
| `nghttp2_submit_priority` | Deprecated RFC 7540 PRIORITY no-op. |
| `nghttp2_submit_extension` | Queue a user-defined non-critical extension; requires a pack callback and keeps payload application-owned until send/not-send. |
| `nghttp2_submit_altsvc` | Server-only built-in ALTSVC serialization. Connection-scoped use requires a nonempty origin; stream-scoped use requires the origin field to be empty. |
| `nghttp2_submit_origin` | Server-only built-in ORIGIN serialization. It copies entries but does not validate each origin string. |
| `nghttp2_submit_priority_update` | Client queues RFC 9218 PRIORITY_UPDATE when peer settings permit it. |
| `nghttp2_session_change_extpri_stream_priority`, `nghttp2_session_get_extpri_stream_priority` | Server changes/reads native RFC 9218 scheduling state when it has opted out of RFC 7540 priorities. |
| `nghttp2_extpri_parse_priority` | Parse a Priority field value into urgency/incremental fields without first initializing unspecified fields. |
| `nghttp2_nv_compare_name` | Lexicographically compare two header names. |

Header submitters normally copy and lowercase names while preserving field
order. `NGHTTP2_NV_FLAG_NO_COPY_NAME` or `NO_COPY_VALUE` transfers a longer
lifetime obligation to the application: retain the referenced bytes until
`on_frame_send` or `on_frame_not_send`. The NO_COPY_NAME case also requires the
application to provide lowercase bytes. Source: [`submit_headers()` ownership](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4800-L4880).

Built-in extension transmission and reception are independent. Submitters can
send without enabling reception. Reception requires the matching built-in
option. For a frame type enabled both as user-defined and built-in, the
user-defined handler wins. Source: [built-in extension guide](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L441-L474).

The pinned `submit_trailer()` header and implementation disagree on nonpositive
stream IDs. The comment says `-1` can succeed and names only zero as invalid;
the implementation rejects every `stream_id <= 0`. Sources:
[public comment](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4750-L4803)
and [pinned implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_submit.c#L128-L140).

### Negotiation, version, error, and field validation: 10

Sources: [utility APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5740-L5970).

| Function or family | Operation and use case |
|---|---|
| `nghttp2_select_next_protocol` | Deprecated server ALPN helper whose output pointer is not const-correct; use `select_alpn`. |
| `nghttp2_select_alpn` | Select from a length-prefixed peer ALPN list; returns 1 for `h2`, 0 for `http/1.1`, and -1 when there is no supported overlap. |
| `nghttp2_version` | Query runtime library version and optional minimum version. |
| `nghttp2_is_fatal` | Classify a negative library error as session-fatal. |
| `nghttp2_check_header_name` | Validate HTTP/2 field-name bytes, including lowercase requirement. |
| `nghttp2_check_header_value` | Obsolete RFC 7230-era value validator. |
| `nghttp2_check_header_value_rfc9113` | Validate field-value bytes including RFC 9113 whitespace rules. |
| `nghttp2_check_method` | Validate method token bytes. |
| `nghttp2_check_path` | Validate allowed path characters, not complete URI/path syntax. |
| `nghttp2_check_authority` | Check allowed bytes for an authority/Host field. It does not validate complete authority syntax and explicitly treats `@` as an allowed character. |

These helpers validate isolated byte strings. They do not reproduce the
session's sequencing, pseudo-header presence, content-length, or stream-state
validation.

### Standalone HPACK codec: 25

These functions operate independent codec objects. A session already owns its
own inflater and deflater; the standalone API exists for HPACK tools or other
callers that need raw header-block compression outside session framing.
Sources: [HPACK API](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5971-L6664).

| Function or comparable family | Operation and use case |
|---|---|
| `nghttp2_hd_deflate_new`, `nghttp2_hd_deflate_new2`, `nghttp2_hd_deflate_del` | Create/destroy an encoder, optionally with custom allocation. |
| `nghttp2_hd_deflate_change_table_size` | Apply peer SETTINGS_HEADER_TABLE_SIZE to encoder state, bounded by construction maximum. |
| `nghttp2_hd_deflate_hd`, `nghttp2_hd_deflate_hd2` | Encode one header set to a contiguous buffer. Old system-`ssize_t` form is deprecated. |
| `nghttp2_hd_deflate_hd_vec`, `nghttp2_hd_deflate_hd_vec2` | Encode across caller buffer vectors. Old form is deprecated. |
| `nghttp2_hd_deflate_bound` | Compute an upper bound required for one field set. |
| `nghttp2_hd_deflate_get_num_table_entries`, `nghttp2_hd_deflate_get_table_entry` | Inspect the combined static and dynamic encoder table. |
| `nghttp2_hd_deflate_get_dynamic_table_size`, `nghttp2_hd_deflate_get_max_dynamic_table_size` | Inspect current and maximum encoder dynamic-table size. |
| `nghttp2_hd_inflate_new`, `nghttp2_hd_inflate_new2`, `nghttp2_hd_inflate_del` | Create/destroy a decoder, optionally with custom allocation. |
| `nghttp2_hd_inflate_change_table_size` | Apply local SETTINGS_HEADER_TABLE_SIZE between header blocks. |
| `nghttp2_hd_inflate_hd` | Deprecated original system-`ssize_t` incremental decoder; its direct replacement was `hd2`. |
| `nghttp2_hd_inflate_hd2` | Deprecated intermediate decoder returning borrowed `nghttp2_nv`; use `hd3`. |
| `nghttp2_hd_inflate_hd3` | Incrementally decode and emit rcbuf-backed fields. |
| `nghttp2_hd_inflate_end_headers` | End one header block and reset per-block decoder state. |
| `nghttp2_hd_inflate_get_num_table_entries`, `nghttp2_hd_inflate_get_table_entry` | Inspect the combined static and dynamic decoder table. |
| `nghttp2_hd_inflate_get_dynamic_table_size`, `nghttp2_hd_inflate_get_max_dynamic_table_size` | Inspect current and maximum decoder dynamic-table size. |

An encoder that fails with a header-compression error is documented to keep
failing on later encode attempts. Incremental decoding may return after each
emitted field, and the caller must signal the end of each complete block.

### Native stream handles and debug output: 11

Sources: [stream and debug APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L6665-L6875).

| Function or family | Operation and use case |
|---|---|
| `nghttp2_session_find_stream` | Return a borrowed native stream handle by ID, or NULL. |
| `nghttp2_stream_get_state` | Read the RFC stream state of a borrowed handle. |
| `nghttp2_stream_get_stream_id` | Read its stream ID. |
| `nghttp2_session_get_root_stream` | Deprecated old dependency-tree root accessor. |
| `nghttp2_stream_get_parent`, `nghttp2_stream_get_next_sibling`, `nghttp2_stream_get_previous_sibling`, `nghttp2_stream_get_first_child` | Deprecated dependency-tree accessors that now always return NULL. |
| `nghttp2_stream_get_weight` | Deprecated accessor that now always returns the default weight. |
| `nghttp2_stream_get_sum_dependency_weight` | Deprecated accessor that now always returns 0. |
| `nghttp2_set_debug_vprintf_callback` | Install process-global native debug print hook; it is a no-op unless libnghttp2 was built with `DEBUGBUILD`. |

## Deprecation And Replacement Matrix

These are official `v1.69.0` header annotations, not inferred obsolescence.

### System-`ssize_t` compatibility family

When `NGHTTP2_NO_SSIZE_T` is defined, these 15 old functions are not declared.
Their `*2` replacements use the library-defined signed `nghttp2_ssize`.
Source: [pinned compatibility declarations](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L910-L1100).

| Deprecated function | Replacement |
|---|---|
| `nghttp2_session_callbacks_set_send_callback` | `nghttp2_session_callbacks_set_send_callback2` |
| `nghttp2_session_callbacks_set_recv_callback` | `nghttp2_session_callbacks_set_recv_callback2` |
| `nghttp2_session_callbacks_set_select_padding_callback` | `nghttp2_session_callbacks_set_select_padding_callback2` |
| `nghttp2_session_callbacks_set_data_source_read_length_callback` | `nghttp2_session_callbacks_set_data_source_read_length_callback2` |
| `nghttp2_session_callbacks_set_pack_extension_callback` | `nghttp2_session_callbacks_set_pack_extension_callback2` |
| `nghttp2_session_mem_send` | `nghttp2_session_mem_send2` |
| `nghttp2_session_mem_recv` | `nghttp2_session_mem_recv2` |
| `nghttp2_pack_settings_payload` | `nghttp2_pack_settings_payload2` |
| `nghttp2_submit_request` | `nghttp2_submit_request2` |
| `nghttp2_submit_response` | `nghttp2_submit_response2` |
| `nghttp2_submit_data` | `nghttp2_submit_data2` |
| `nghttp2_hd_deflate_hd` | `nghttp2_hd_deflate_hd2` |
| `nghttp2_hd_deflate_hd_vec` | `nghttp2_hd_deflate_hd_vec2` |
| `nghttp2_hd_inflate_hd` | `nghttp2_hd_inflate_hd2`, which is itself deprecated |
| `nghttp2_hd_inflate_hd2` | `nghttp2_hd_inflate_hd3` |

The associated old typedefs `nghttp2_send_callback`,
`nghttp2_recv_callback`, `nghttp2_select_padding_callback`,
`nghttp2_data_source_read_length_callback`, `nghttp2_pack_extension_callback`,
`nghttp2_data_source_read_callback`, and `nghttp2_data_provider` are also
officially deprecated in favor of their `*2` forms.

The official notices appear with the
[callback setters](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2499-L2795),
[memory drive APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3481-L3743),
[settings payload helper](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4337-L4408),
[message submitters](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4460-L4980),
and [standalone HPACK functions](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L6045-L6609).

### Removed RFC 7540 dependency-priority model

The Programmer's Guide says the RFC 7540 dependency-tree implementation has
been removed and recommends RFC 9218. These retained functions are deprecated
compatibility surface:

| Functions | Current documented behavior |
|---|---|
| `nghttp2_session_change_stream_priority`, `nghttp2_session_create_idle_stream`, `nghttp2_submit_priority` | No-op, always 0. |
| `nghttp2_priority_spec_init`, `nghttp2_priority_spec_default_init`, `nghttp2_priority_spec_check_default` | Deprecated value helpers for ignored dependency specs. |
| `nghttp2_session_get_root_stream` | Deprecated root handle. |
| `nghttp2_stream_get_parent`, `nghttp2_stream_get_next_sibling`, `nghttp2_stream_get_previous_sibling`, `nghttp2_stream_get_first_child` | Always NULL. |
| `nghttp2_stream_get_weight` | Always default weight. |
| `nghttp2_stream_get_sum_dependency_weight` | Always 0. |
| `nghttp2_option_set_server_fallback_rfc7540_priorities` | No effect. |

Sources: [priority migration guidance](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L482-L507)
and the official notices on
[session tree operations](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4208-L4238),
[priority value helpers](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4409-L4459),
[`submit_priority`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4982-L4997),
[the no-op option](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3191-L3207),
and [stream-tree accessors](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L6737-L6840).

### Other deprecated or obsolete functions

| Function | Official status and replacement |
|---|---|
| `nghttp2_session_callbacks_set_error_callback` and `nghttp2_error_callback` | Deprecated; use the `*2` setter and typedef to also receive the library error code. [Typedef](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2394-L2420), [setter](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2814-L2848) |
| `nghttp2_option_set_no_closed_streams` | Deprecated no-op because closed streams are no longer retained. [Header](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3156-L3171) |
| `nghttp2_session_upgrade` | Deprecated in favor of `upgrade2`, which adds the HEAD-request fact required for response body-length validation. [Header](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4239-L4336) |
| `nghttp2_select_next_protocol` | Deprecated; use `nghttp2_select_alpn`. [Header](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5741-L5868) |
| `nghttp2_check_header_value` | Officially “considered obsolete”; use `nghttp2_check_header_value_rfc9113`. [Header](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5894-L5918) |

## Capability Boundary

**Official guidance:** the public session API owns:

- HTTP/2 connection and stream state;
- frame parsing, validation, scheduling, and serialization;
- HPACK state and header-block assembly;
- local and remote flow-control accounting;
- HTTP message validation documented by the library;
- automatic protocol actions such as SETTINGS ACK, PING ACK, and many
  RST_STREAM/GOAWAY responses;
- built-in ALTSVC, ORIGIN, and PRIORITY_UPDATE framing;
- non-critical user-extension plumbing.

It deliberately does not own:

- sockets, TLS, certificate validation, ALPN invocation, or HTTP/1.1 parsing;
- event loops, async runtimes, timeouts, retries, or connection pools;
- complete application request/response policy;
- transport delivery receipts or peer acknowledgements for serialized frames;
- automatic storage limits for application-collected header fields or bodies;
- base64url encoding/decoding and HTTP/1.1 parsing for h2c Upgrade.

The callback surface is therefore not merely a way to “receive events.” Some
callbacks are observation hooks, some supply bytes, some own policy, some
control native scheduling, and some only provide diagnostics. Whether a
callback is registered can range from “no notification” to “different protocol
behavior,” so each callback's absent case must be read as part of its contract.
Sources: [pinned architecture](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L4-L39)
and [public session API](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2461-L5739).
