---
title: libnghttp2 v1.69 session state and data flow
description: Version-pinned account of session and stream ownership, active API effects, receive and send pipelines, callback timing, callback absence, flow control, scheduling, and error domains.
topics: [http2, libnghttp2, session, streams, state-machine, callbacks, data-flow, flow-control, scheduling]
checked_at: 2026-07-25
---

# libnghttp2 v1.69 Session State And Data Flow

## Scope And Evidence

This document describes libnghttp2 itself. It does not decide which native
facts a language binding should expose or how a binding should represent them.

The implementation observations are pinned to libnghttp2 `v1.69.0`, commit
[`68cb6900fde14c77f0cd7add0e094a862960eb99`](https://github.com/nghttp2/nghttp2/tree/68cb6900fde14c77f0cd7add0e094a862960eb99).
Public contracts come from the pinned
[`nghttp2.h`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h).
Details labelled **observed implementation** come from the pinned session and
stream sources and are not stable public ABI:

- [`nghttp2_session.h`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.h)
- [`nghttp2_session.c`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c)
- [`nghttp2_stream.h`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_stream.h)

The complete function inventory, callback arguments and contracts, construction
options, and deprecation replacements are in
[libnghttp2 public API and callback contracts](libnghttp2-api.md).

## Protocol Ownership Hierarchy

One `nghttp2_session` represents one endpoint's HTTP/2 protocol state for one
connection. It is not a socket or TLS object. The application moves bytes
between its transport and the session.

```text
socket / TLS / event loop, owned by the application
                         |
                  ordered byte stream
                         |
                  nghttp2_session
             +-----------+-----------+
             | connection-wide state |
             | stream map             |
             | HPACK contexts         |
             | inbound parser         |
             | outbound scheduler     |
             | callbacks and options  |
             +-----------+-----------+
                         |
          +--------------+--------------+
          |              |              |
       stream 1       stream 3       stream 5
```

**Observed implementation:** the session owns the stream map, connection-level
windows, local and remote SETTINGS, GOAWAY state, next stream ID, HPACK encoder
and decoder, one incremental inbound-frame parser, urgent and regular outbound
queues, a new-stream HEADERS queue, RFC 9218 DATA queues, and the active
outbound item. Source:
[`struct nghttp2_session`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.h#L206-L379).

Each native stream stores its stream ID, protocol state, local and remote
half-closure, connection-independent flow-control values, content-length
accounting, priority, user data, and at most one attached outbound
DATA/HEADERS item. Source:
[`struct nghttp2_stream`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_stream.h#L145-L214).

State is therefore maintained at both levels, but driving remains
session-wide:

| Dimension | Session-wide | Stream-specific |
|---|---|---|
| Input | `recv()` or `mem_recv2()` consumes the connection byte stream. | The parser reads the frame stream ID and updates the matching native stream. |
| Output | `send()` or `mem_send2()` drains one connection scheduler. | Submitted work and DATA providers are associated with a stream ID. |
| Flow control | The connection has send and receive credit. | Each stream has additional send and receive credit. DATA requires both levels. |
| Compression | One HPACK encoder and one decoder belong to the session. | Header blocks belong to streams but use the connection's HPACK contexts. |
| Lifecycle | SETTINGS, PING, GOAWAY, connection errors, and stream-ID allocation are session state. | HEADERS, DATA, RST_STREAM, END_STREAM, and push reservations change individual streams. |

Most stream operations therefore take `nghttp2_session *` plus `stream_id`.
There is no public operation that independently feeds bytes to, or drains bytes
from, an `nghttp2_stream`.

`nghttp2_session_find_stream()` returns a borrowed opaque stream handle.
Except for the imaginary root stream, the pointer is valid only until the next
`send()`, `mem_send2()`, `recv()`, or `mem_recv2()` call. The current public
handle supports state and stream-ID inspection; the old dependency-tree
accessors are deprecated. Source:
[`find_stream()` and stream accessors](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L6665-L6840).

## Session Lifecycle Phases

libnghttp2 does not expose one public session-state enum. The following phases
are a synthesis of its public construction, drive, GOAWAY, fatal-error, and
destruction contracts rather than names of internal enum values.

| Phase | Native facts and permitted progress |
|---|---|
| Configuration | The application allocates a callback set and optional option object. Setters only change those configuration objects. |
| Construction | A client or server constructor copies the callback and option contents into a new session. The configuration objects may then be deleted. A `new3` constructor also copies a custom allocator table. |
| Preface and initial SETTINGS | For normal direct HTTP/2 startup, a client session has the 24-byte client magic ready for output, a server normally expects that magic, and both roles expect the peer's first frame to be SETTINGS. The application must submit its own initial SETTINGS. Upgrade APIs establish their documented post-HTTP/1.1 state separately. |
| Active | The application alternates input driving, output driving, and submission/state APIs. Input may queue automatic output. Submission usually queues work rather than serializing it. |
| Draining or closing | Sent or received GOAWAY prevents some new streams and lets eligible active streams finish. `want_read()` and `want_write()` eventually both become false. |
| Fatal failure | For a library error strictly below `NGHTTP2_ERR_FATAL`, the public header permits only `nghttp2_session_del()` on that session. |
| Destruction | `nghttp2_session_del()` frees native session and stream state. Application-owned user data and retained callback inputs remain governed by their own ownership contracts. |

Sources: [constructors and session drive APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3270-L3743),
[GOAWAY and termination APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5074-L5304),
and [fatal error contract](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L430-L479).

### Stream states

The public `nghttp2_stream_proto_state` exposes seven RFC stream states:

- idle;
- open;
- reserved local;
- reserved remote;
- half-closed local;
- half-closed remote;
- closed.

Source:
[`nghttp2_stream_proto_state`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L6696-L6736).

An outbound request submission reserves and returns a stream ID before the
native stream object is opened. The stream is opened during outbound frame
preparation. An inbound opening HEADERS creates or advances its stream while
input is processed. PUSH_PROMISE creates a reserved stream. END_STREAM
half-closes one direction; RST_STREAM, some protocol failures, and completion
of both directions close the stream. Stream closure can invoke
`on_stream_close` before native cleanup removes the stream.

Sources: [`submit_request2()` warning](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4459-L4597)
and [stream-close callback](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1825-L1865).

## What Active API Calls Inject

Submission success generally means immediate validation succeeded and native
work or provider state was queued. It does not mean the frame has been
serialized, returned to the application, written to a transport, or accepted by
the peer.

| Active API family | Immediate native effect | Later processing |
|---|---|---|
| Session constructors | Copy callbacks, options, role, allocator, and user data; allocate connection and parser state. | The session later consumes or produces the connection preface and frames. |
| `submit_settings()` | Validate entries, retain pending local values, and queue an urgent SETTINGS item. | Serialization sends the frame; a matching ACK advances in-flight local SETTINGS state. |
| `submit_request2()` | Validate and reserve a client stream ID; copy the provider descriptor; copy or retain header bytes according to NV flags; queue request HEADERS. | Outbound preparation opens the stream, HPACK-encodes headers, and later pulls DATA from the provider. |
| `submit_response2()` | Validate an existing stream; copy the provider descriptor; copy or retain header bytes according to NV flags; queue response HEADERS. | Outbound preparation validates current stream/message state, encodes headers, and later pulls DATA. |
| `submit_headers()` / `submit_trailer()` | Copy or retain header fields according to NV flags and queue a HEADERS item. | Native state determines its header category, validity, serialization, and END_STREAM transition. |
| `submit_push_promise()` | Reserve and return a server-initiated promised stream ID; queue PUSH_PROMISE. | Preparation validates push state and encodes the promised request fields. |
| `submit_data2()` | Copy one provider descriptor and attach or queue one DATA item for an existing stream. | The scheduler later invokes the provider. A second unfinished DATA/HEADERS item for the stream is rejected. |
| `submit_ping()` | Queue PING or explicit ACK. | PING/SETTINGS use the highest outbound queue class in the pinned implementation. |
| `submit_rst_stream()` | Queue RST_STREAM and cancel pending HEADERS and DATA for the same stream. | Successful transmission closes the affected stream. |
| `submit_goaway()` / termination APIs | Queue GOAWAY and update closing intent. | Successful transmission changes which streams remain eligible and eventually ends session read/write interest. |
| `consume*()` | Record application consumption at connection, stream, or both levels. | Native thresholds may queue WINDOW_UPDATE. These APIs are relevant when automatic receive-window updates are disabled. |
| `set_local_window_size()` | Change an absolute connection or stream receive-window target without consuming the unacknowledged-data count. | An increase may queue WINDOW_UPDATE; a reduction may remain effective only after received data drains. |
| `submit_window_update()` | Apply a low-level delta and alter unacknowledged receive accounting according to its contract. | A positive update is queued; it is not the application-consumption API. |
| `resume_data()` | Clear user-deferred state for one stream. | **Observed implementation:** DATA is schedulable only when no other deferral reason, including flow control, remains. |
| `session_upgrade2()` | Apply already parsed and base64url-decoded HTTP2-Settings and establish stream 1 upgrade state. | Normal HTTP/2 input/output driving continues; HTTP/1.1 parsing remains outside the library. |
| `submit_extension()` | Retain an application payload pointer and queue a non-critical extension item. | A pack callback must serialize its payload; absence of that callback makes submission fail with `INVALID_STATE`. |

Sources: [message and control submission APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4459-L5739),
[flow-control APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3820-L4238),
and [upgrade APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4239-L4336).

Two pinned header/source conflicts affect active-call interpretation:

- `set_local_window_size()` documents `INVALID_ARGUMENT` for a negative
  `stream_id`; the implementation instead rejects a negative `window_size` and
  returns success when a nonzero stream lookup produces no stream.
- `submit_trailer()` says `stream_id == -1` can succeed and only names zero as
  invalid; the implementation rejects every `stream_id <= 0`.

Sources: [`set_local_window_size()` header](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5348-L5386),
[`set_local_window_size()` implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_submit.c#L334-L405),
[`submit_trailer()` header](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4750-L4803),
and [`submit_trailer()` implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_submit.c#L128-L140).

## Receive Pipeline

`mem_recv2(session, bytes, length)` drives the parser synchronously. The
callback-driven `recv(session)` obtains bytes from `recv_callback2` and then
uses the same protocol-processing path.

```text
application input bytes
        |
        v
client magic / first SETTINGS checks
        |
        v
9-byte frame header
        |
        v
header-level size/type handling
        |
        +--> normal processing path --> on_begin_frame
        |
        v
frame-type, connection, stream, and flood validation
        |
        +--> HEADERS / PUSH_PROMISE
        |       |
        |       +--> on_begin_headers
        |       +--> HPACK decode
        |       +--> on_header or on_invalid_header, once per field
        |       +--> CONTINUATION consumed internally until END_HEADERS
        |
        +--> DATA
        |       |
        |       +--> padding and flow-control accounting
        |       +--> on_data_chunk_recv, possibly more than once
        |
        +--> extension
        |       |
        |       +--> built-in decode, or extension-chunk and unpack callbacks
        |
        +--> standard control frame
                |
                +--> SETTINGS/PING ACK, window, GOAWAY, RST, or other state
        |
        v
on_frame_recv for a valid completed logical frame
        |
        +--> on_stream_close when processing closes a stream
        |
        v
mem_recv2 / recv returns
```

HEADERS plus its CONTINUATION sequence produces header-field callbacks and one
final `on_frame_recv` for the logical HEADERS or PUSH_PROMISE. CONTINUATION has
no member in the public `nghttp2_frame` union. Receiving input can queue
automatic SETTINGS ACK, PING ACK, WINDOW_UPDATE, RST_STREAM, or GOAWAY, but the
receive call does not return those serialized bytes; output must be driven
separately.

Sources: [`session_recv()` callback timeline](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3570-L3688)
and [pinned receive implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3525-L7150).

### Receive callback inputs and absence

All callbacks below run synchronously inside `recv()` or `mem_recv2()`.
`session` and session `user_data` are omitted from the parameter column.

| Callback | Significant inputs and permitted control | If not registered |
|---|---|---|
| `recv_callback2` | Writable `buf`, capacity `length`, and currently-zero flags. Returns bytes read, `WOULDBLOCK`, `EOF`, or callback failure. Zero is treated as `WOULDBLOCK`. | `mem_recv2()` is unaffected. `recv()` has no input source and requires a receive callback. |
| `on_begin_frame` | Borrowed `frame_hd` after header-level checks select a normal processing path. CONTINUATION can invoke it. **Observed implementation:** early frame-size-error and native-ignore paths skip it. Must return zero. | Header/payload processing continues without this frame-start notification where native processing otherwise continues. |
| `on_begin_headers` | Borrowed HEADERS or PUSH_PROMISE frame before fields. A documented temporal failure resets the subject stream. | HPACK decoding, HTTP validation, and per-field callbacks continue. |
| `on_header2` / `on_header` | Frame, field name/value, and NV flags. The rcbuf form takes precedence. May pause input or request documented stream-local failure. | Accepted fields are not delivered to the application; native HPACK, message validation, and stream processing continue. |
| `on_invalid_header2` / `on_invalid_header` | Only invalid regular fields eligible for application policy; pseudo-header and uppercase-name failures bypass it. The rcbuf form takes precedence. Zero ignores the field; temporal failure resets the subject stream. | The eligible invalid regular field is silently ignored. Other invalid-header classes retain their native failure behavior. |
| `on_data_chunk_recv` | Frame flags, stream ID, borrowed DATA bytes, and length. It may pause input. The flag value is not a reliable whole-stream completion signal. | Payload bytes are not delivered to the application; frame, stream, message, and flow-control processing continue. |
| `on_extension_chunk_recv` | Extension frame header and borrowed payload chunk. `CANCEL` stops processing that extension frame. | User-defined extension payload bytes are not delivered in chunks. Built-in extension handling is independent. |
| `unpack_extension` | Frame header and output payload pointer after registered extension chunks. It may create an application-owned payload object or cancel. | A type enabled as a user extension is silently ignored; its extension-chunk, unpack, and completed-frame callbacks do not run; and the pinned implementation counts the frame through its glitch rate limiter. |
| `on_invalid_frame_recv` | Unpacked invalid non-DATA frame and a library error code. It is observation, not a veto, and must return zero. | Native code still queues its selected RST_STREAM or GOAWAY; only the notification is absent. |
| `on_frame_recv` | Borrowed completed valid frame after native processing. Header arrays are empty because fields were emitted separately. Must return zero. | Native frame and stream processing, including automatic responses, continues without completion notification. |
| `on_stream_close` | Stream ID and close error code; stream user data remains available during the callback. The code is usually an HTTP/2 wire code but is not guaranteed to be one. | Native stream closure and cleanup continue without application notification. |
| `error_callback2` | Library error code and unstable human-readable diagnostic text. Normally returns zero. | No diagnostic text is formatted for the application; protocol behavior is unchanged. |

Invalid input is not one callback domain. Invalid DATA processing, bad client
magic, frame-size errors found before a usable frame exists, HPACK failure,
flood detection, and excessive CONTINUATION can be expressed as a negative
drive return, queued native control frames, or session state without reaching
`on_invalid_frame_recv`.

Sources: [receive callback typedefs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1584-L2110),
[pinned frame-header dispatch](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L5509-L6127),
[extension and diagnostic callback typedefs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L2230-L2457),
[user-extension dispatch](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L5878-L5910),
and [invalid-frame dispatch](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3240-L3524).

### Receive callback memory lifetime

Header and DATA pointers are application-borrowed, but their exact validity is
not always limited to the callback return:

- when a byte-range header callback pauses `mem_recv2()`, its frame, name, and
  value pointers remain valid until the next `mem_recv2()` or `recv()` call;
- the application must also retain the input bytes because those pointers may
  refer directly into the supplied input region;
- when a DATA callback pauses `mem_recv2()`, its data pointer remains valid
  until the next `mem_recv2()` or `recv()` call, and the corresponding input
  bytes must also be retained;
- an `on_header_callback2` rcbuf can be retained with `nghttp2_rcbuf_incref()`
  and later released with `nghttp2_rcbuf_decref()`;
- with a `new3` custom allocator, its free function must remain callable for as
  long as retained rcbuf objects can outlive the session.

Sources: [DATA callback lifetime](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1711-L1749)
and [header callback lifetimes](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1923-L2037).

## Outbound Pipeline

An outbound operation first creates native queued work. `send()` or
`mem_send2()` later selects, prepares, serializes, and completes that work.

### Scheduling before preparation

**Observed implementation:** `v1.69.0` chooses the next outbound item in this
order:

1. urgent PING and SETTINGS;
2. regular non-DATA work;
3. stream-creating HEADERS, if the outgoing concurrent-stream limit permits;
4. DATA, if the connection remote window is positive.

DATA is selected from urgency queues `0` through `7`. Incremental server
streams can be rescheduled using their last written length. Sources:
[`get/pop_next_ob_item`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L2303-L2358)
and [RFC 9218 DATA scheduler](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L820-L1001).

The pinned Programmer's Guide calls this ordering internal and subject to
change. Its scheduling section still says DATA uses an RFC 7540 dependency
tree, while its later priority section says that tree was removed and
recommends RFC 9218. The pinned source above resolves current behavior, but the
ordering is not a stable public contract. Sources:
[older scheduling text](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L186-L220)
and [priority migration text](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L482-L507).

### Non-DATA path

```text
selected queued item
        |
        v
prepare and validate against current session/stream state
        |
        +--> failure: optional on_frame_not_send, then native cleanup
        |
        +--> HEADERS/PUSH_PROMISE: HPACK encode and optional padding
        |
        v
request stream may be opened during preparation
        |
        v
optional before_frame_send
        |
        +--> CANCEL: optional on_frame_not_send, then cleanup
        |
        v
prepared serialized bytes enter output path
        |
        +--> send_callback2, possibly over several calls
        |         or
        +--> one mem_send2-owned chunk
        |
        v
on_frame_send
        |
        v
stream transition/closure and on_stream_close where applicable
```

**Observed implementation:** `before_frame_send` is called only for non-DATA
frames. The generic `session_send()` header timeline places the callback after
the padding step that names DATA as well, so the public comment and pinned
implementation are not fully aligned. Source:
[pinned send loop](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L2834-L3039).

`on_frame_not_send` is restricted by the implementation to non-DATA
preparation failures. It is also suppressed for native WINDOW_UPDATE failure
and for RST_STREAM rejected solely because the stream is already closed.

### DATA-provider path

```text
DATA stream selected by scheduler
        |
        v
connection and stream remote windows permit progress
        |
        +--> optional data_source_read_length callback
        |       chooses next read ceiling
        |
        v
data_source_read callback
        |
        +--> copies 0..length body bytes
        +--> EOF / NO_END_STREAM / NO_COPY flags
        +--> DEFERRED / PAUSE / temporal or fatal failure
        |
        +--> optional select_padding
        |
        v
DATA frame prepared
        |
        +--> ordinary serialized buffer path
        |         or
        +--> NO_COPY send_data_callback writes the whole DATA frame
        |
        v
on_frame_send
        |
        v
connection and stream remote windows decrease;
provider detaches at EOF or stream is rescheduled
```

The provider is pull-based. It is invoked only when native scheduling and flow
control select that stream. It receives a writable buffer and a maximum
`length`, copies at most that many application bytes, returns the copied count,
and can set:

- `EOF` to finish the source;
- `NO_END_STREAM` with EOF to leave the stream open for trailers;
- `NO_COPY` to move complete DATA-frame output into `send_data_callback`.

It can instead return:

- `DEFERRED` before producing data, which removes the stream from DATA
  scheduling until `resume_data()`;
- `PAUSE`, which returns from the current output drive;
- `TEMPORAL_CALLBACK_FAILURE`, which resets that stream with INTERNAL_ERROR
  unless the application submitted a different reset;
- callback failure, which is fatal to the session.

Source:
[`nghttp2_data_source_read_callback2`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L986-L1056).

### Outbound callback inputs and absence

| Callback | Significant inputs and permitted control | If not registered |
|---|---|---|
| `send_callback2` | Borrowed serialized bytes and length. Returns accepted count, `WOULDBLOCK` before accepting bytes, or callback failure. Partial acceptance is supported. | `mem_send2()` is unaffected. `session_send()` requires either the current or deprecated send callback. |
| `data_source_read_length2` | DATA frame type, stream ID, connection and stream remote windows, and peer maximum frame size. Returns the desired next read ceiling; native code clamps an excessive value and treats a non-positive result as callback failure. | Native code uses its normal DATA read limit, at most 16 KiB by default and still bounded by flow control and peer frame size. |
| `data_source_read_callback2` | Stream ID, writable buffer, maximum body length, output flags, and application source pointer. | A body-bearing provider cannot operate without its read function. A null request/response provider produces headers with END_STREAM. |
| `select_padding2` | Prepared frame and maximum allowed payload length. Returns total payload length including padding, not the number of trailing zero bytes. | No padding is added. |
| `before_frame_send` | Prepared non-DATA frame. Zero continues; `CANCEL` cancels it; other nonzero results are fatal. | No application veto or pre-send observation occurs. |
| `pack_extension2` | Writable payload buffer, capacity, and queued extension frame with the original opaque payload pointer. Returns encoded payload length or `CANCEL`. | `submit_extension()` reports `INVALID_STATE`; built-in extension senders use their native encoders. |
| `send_data` | DATA frame, serialized 9-byte header, application-data length, and source pointer after provider `NO_COPY`. It must write the complete frame. | A provider that returns `NO_COPY` fails; ordinary copied DATA is unaffected. |
| `on_frame_send` | Borrowed completed frame after the native output path accepts it. Must return zero. | Native completion, flow-control updates, stream transitions, and cleanup continue without application notification. |
| `on_frame_not_send` | Borrowed non-DATA frame and library failure code after delayed preparation failure or cancellation. Must return zero. | Native cancellation and any applicable stream transition or cleanup continue without application notification. |
| `rand_callback` | Destination and requested unpredictable-byte length during session construction. It must fill the destination and has no error return. | **Observed implementation:** the native stream-map seed is zero. |

Sources: [outbound callback typedefs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1459-L1824),
[provider and policy callback typedefs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L887-L1056),
and [session construction seed](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L607-L617).

### Memory-send, send-callback, and NO_COPY boundaries

For ordinary copied frames:

- `session_send()` invokes `on_frame_send` only after its send callback has
  accepted the complete frame;
- `mem_send2()` advances the internal buffer and invokes `on_frame_send` before
  returning the final chunk pointer and length to its caller;
- neither path proves socket, TLS, peer, or remote-application acceptance.

Source:
[`mem_send2()` completion order](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3127-L3151).

NO_COPY crosses the memory-output boundary. If a provider sets
`NGHTTP2_DATA_FLAG_NO_COPY`, even `mem_send2()` invokes
`send_data_callback`, and that callback must write the complete DATA frame
directly. No DATA payload bytes for that frame are returned through
`mem_send2()`. Source:
[NO_COPY send state](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L2990-L3098).

### Submission, native completion, and delivery

| Milestone | Established | Not established |
|---|---|---|
| Submit call succeeds | Immediate validation passed and an item/provider was queued or attached. | Current-state preparation, serialization, output, and delivery have not necessarily occurred. |
| DATA provider returns bytes | Native scheduling and current flow control allowed a body read. | The full frame has not necessarily left the native output path. |
| `on_frame_send` runs | The complete frame crossed the selected native output boundary described above. | Application return from `mem_send2()`, transport write, peer receipt, and peer processing are not uniformly established. |
| Application writes output | Bytes reached the application's chosen transport call. | libnghttp2 receives no kernel, TLS, peer, or remote-application acknowledgement. |

## Flow-Control Data Movement

Outbound DATA consumes both connection and stream remote windows. A positive
window is required at both levels before the provider can make progress.
Received WINDOW_UPDATE and SETTINGS_INITIAL_WINDOW_SIZE changes can make
flow-deferred DATA schedulable again. SETTINGS_INITIAL_WINDOW_SIZE changes
stream windows; connection credit is changed through connection-level
WINDOW_UPDATE.

Inbound DATA consumes both connection and stream local receive credit.
Padding, including the one-byte Pad Length field, is part of DATA payload
length and consumes flow-control credit even though padding is not delivered as
application data. **Observed implementation:** inbound padding is immediately
marked consumed by native code, including in manual-update mode; application
consumption applies to delivered DATA bytes.

With automatic receive-window updates enabled, native code manages
WINDOW_UPDATE according to its thresholds. With automatic updates disabled,
the application reports consumed bytes through:

- `nghttp2_session_consume()` for connection and stream accounting together;
- `nghttp2_session_consume_connection()` for only connection accounting;
- `nghttp2_session_consume_stream()` for only one stream.

`set_local_window_size()` declares an absolute receive-window target.
`submit_window_update()` applies a delta and also affects received-but-not-yet
acknowledged accounting. They are not interchangeable with `consume*()`.

Sources: [flow-control APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3820-L4238),
[window target/update APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L5305-L5386),
and [inbound DATA/padding accounting](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L6800-L6860).

## Error And Control Domains

Three numeric domains appear in the public API and must be interpreted from the
specific function or callback contract:

| Domain | Examples | Meaning |
|---|---|---|
| Library errors, `nghttp2_error` | `ERR_PROTO`, `ERR_STREAM_CLOSED`, `ERR_NOMEM` | Negative local engine, state, argument, resource, or callback results. `nghttp2_strerror()` describes this domain. |
| HTTP/2 wire errors, `nghttp2_error_code` | `PROTOCOL_ERROR`, `CANCEL`, `REFUSED_STREAM` | Non-negative error codes carried by RST_STREAM and GOAWAY. `nghttp2_http2_strerror()` describes this domain. |
| Callback control values | `WOULDBLOCK`, `EOF`, `DEFERRED`, `PAUSE`, `TEMPORAL_CALLBACK_FAILURE`, `CANCEL` | Negative values from `nghttp2_error` that have special non-identical meaning only in documented callback positions. |

`nghttp2_is_fatal(code)` returns nonzero when the library code is strictly less
than `NGHTTP2_ERR_FATAL` (`-900`). In `v1.69.0` the defined fatal values are
out-of-memory, callback failure, bad client magic, flooding, and excessive
CONTINUATION. After such a return, the header permits only session deletion.

Native invalid-frame handling maps selected library errors to HTTP/2 wire codes
before it queues RST_STREAM or GOAWAY. `on_invalid_frame_recv` sees the library
error; `on_stream_close` normally sees a wire error code but its public
contract says that is not guaranteed.

Sources: [library errors](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L268-L479),
[wire error codes](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L773-L834),
[fatal classification](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L82-L88),
and [library-to-wire mapping](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L3362-L3384).

## Queue And Readiness Observability

`nghttp2_session_want_write()` accounts for an active outbound item, urgent and
regular queues, schedulable DATA with positive connection send credit, and
eligible new-stream HEADERS. It answers whether the session currently wants its
output path driven; it does not count bytes or promise that the application has
transport output ready.

The public comment for `nghttp2_session_get_outbound_queue_size()` says it
counts queued frames excluding deferred DATA. **Observed implementation:** it
only sums the urgent, regular, and new-stream HEADERS queues. It excludes all
stream-attached DATA, not only user-deferred DATA, and excludes the active item
already popped for processing. Its source contains a TODO to account for items
attached to streams. It is therefore not a total pending-work, schedulable-frame,
serialized-frame, or delivery count.

Sources: [`want_write()` implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L7150-L7168)
and [`get_outbound_queue_size()` implementation](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_session.c#L7665-L7671).

## Reentrancy And Thread Boundary

One session may be used by only one thread at a time. The official guide also
forbids direct or indirect calls to `send()`, `mem_send2()`, `recv()`, or
`mem_recv2()` from any libnghttp2 callback and says doing so leads to a crash.
Submission functions may be called from documented callbacks; the application
returns from the callback before it resumes the drive loop.

Source:
[pinned Programmer's Guide remarks](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L84-L104).
