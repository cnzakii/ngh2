---
title: libnghttp2 architecture and capability boundary
description: Version-pinned facts about libnghttp2 Sans-I/O behavior, public APIs, HTTP/2 coverage, lifecycle constraints, builds, compatibility, licensing, security, and performance evidence.
topics: [http2, libnghttp2, sans-io, api, callbacks, flow-control, hpack, compatibility, licensing, security, performance]
checked_at: 2026-07-18
---

# libnghttp2 Architecture And Capability Boundary

## Evidence Baseline

The implementation observations in this document are pinned to libnghttp2
`v1.69.0`, commit
[`68cb6900fde14c77f0cd7add0e094a862960eb99`](https://github.com/nghttp2/nghttp2/tree/68cb6900fde14c77f0cd7add0e094a862960eb99),
released on 2026-04-19. The online documentation currently identifies itself as
`1.70.0-DEV`; mutable online documentation must not be treated as evidence of
stable `v1.69.0` behavior without checking the pinned source.

- **Observed practice:** [`v1.69.0` release](https://github.com/nghttp2/nghttp2/releases/tag/v1.69.0)
- **Observed practice:** [`v1.69.0` public header](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h)
- **Official guidance:** [current Programmer's Guide](https://nghttp2.org/documentation/programmers-guide.html)

## Sans-I/O Architecture

**Official guidance:** libnghttp2 does not perform I/O. It consumes byte strings,
updates HTTP/2 state, invokes application callbacks, and produces byte strings.
The application is responsible for transporting output to the peer. The primary
object is the opaque `nghttp2_session`.

Source: [pinned Programmer's Guide, Architecture](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L4-L39).

The library does not own:

- socket creation, connection, listening, reading, writing, or closure;
- TCP, TLS, certificate verification, or ALPN negotiation;
- an event loop, async runtime, or connection pool;
- HTTP/1.1 parsing;
- application-level client or server behavior;
- timeout scheduling for connections, PING, or SETTINGS.

The source does read system time for internal rate limiting, including glitch
and Rapid Reset defenses. This is not network I/O or timer scheduling, but it
means rate-limit results can depend on input arrival timing rather than only on
the byte sequence. Source: [`nghttp2_time.c`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/nghttp2_time.c).

## Session And Threading Model

The library provides separate client and server constructors, callbacks and
options objects, custom allocation in the `new3` constructors, session-level
user data, stream-level user data, and explicit destruction:

- `nghttp2_session_client_new2()` / `client_new3()`;
- `nghttp2_session_server_new2()` / `server_new3()`;
- `nghttp2_session_callbacks_new()` / `callbacks_del()`;
- `nghttp2_option_new()` / `option_del()`;
- `nghttp2_session_del()`.

Multiple sessions may exist concurrently, but one session must only be used by
one thread at a time. Source: [pinned threading guidance](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L33-L39).

Session, callbacks, options, HPACK state, and stream handles are opaque types.
This lets the implementation change their internal layouts without making those
layouts part of the public ABI. Source: [opaque declarations](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L135-L176).

## Input And Output APIs

The same session can be driven through application I/O callbacks or through
memory APIs:

| Direction | Callback-driven API | Memory API |
|---|---|---|
| Input | `nghttp2_session_recv()` | `nghttp2_session_mem_recv2()` |
| Output | `nghttp2_session_send()` | `nghttp2_session_mem_send2()` |

`recv()` and `send()` invoke application-provided read or write callbacks; the
callbacks, not libnghttp2, may perform I/O. Official guidance recommends the
memory APIs when in doubt because they are simpler, and notes that memory receive
may be faster because it avoids a callback. Source: [pinned input/output guidance](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L41-L74).

`mem_recv2()` processes as much input as possible and synchronously invokes
registered callbacks. A callback can return `NGHTTP2_ERR_PAUSE`; the return value
then reports the number of bytes consumed up to the paused callback.

`mem_send2()` returns one internally owned serialized chunk per call and must be
called repeatedly until it returns zero. The returned pointer is valid only
until the next `mem_send2()` or `send()` call. The library may produce small
chunks and leaves aggregation to the application.

Sources:

- [`nghttp2_session_mem_recv2()`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3690-L3743)
- [`nghttp2_session_mem_send2()`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L3505-L3569)

`nghttp2_session_want_read()` and `want_write()` indicate when the session no
longer needs protocol input or output. They do not account for bytes already
copied out of the session but not yet transmitted by the application.

## Callback Ordering And Reentrancy

Receive callbacks cover frame start, complete frame, invalid frame, header-block
start, each header field, invalid headers, DATA chunks, stream closure, extension
payload, and errors. Send callbacks cover before-send, sent, not-sent, padding,
DATA source, and extension packing.

HEADERS followed by CONTINUATION frames are processed atomically by the library;
the application receives header callbacks and the final frame callback rather
than separate CONTINUATION events.

**Official warning:** an application must not call `send()`, `recv()`,
`mem_send2()`, or `mem_recv2()` directly or indirectly from a libnghttp2
callback. The documentation states that this leads to a crash. Frames may be
submitted from a callback, but receive/send processing must resume after the
callback returns. Source: [pinned Programmer's Guide, Remarks](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L84-L104).

## Protocol Capabilities

**Observed practice in `v1.69.0`:**

| Area | Public capability |
|---|---|
| Framing and state | Frame parsing/serialization, connection state, stream state, half-closure, SETTINGS, GOAWAY, RST_STREAM, PING |
| Headers | Integrated HPACK encoder/decoder, HEADERS/CONTINUATION assembly, header callbacks |
| Messages | Request, response, informational headers, DATA, and trailers |
| Flow control | Connection and stream windows, automatic or manual receive-window consumption |
| Stream creation | Client request stream IDs and server promised stream IDs |
| Push | PUSH_PROMISE and `SETTINGS_ENABLE_PUSH` |
| h2c | HTTP/1.1 Upgrade post-processing through `nghttp2_session_upgrade2()` |
| Extended CONNECT | `SETTINGS_ENABLE_CONNECT_PROTOCOL` and `:protocol` validation |
| Extensions | ALTSVC, ORIGIN, PRIORITY_UPDATE, and user-defined non-critical extension frames |
| Priorities | RFC 9218 urgency/incremental and PRIORITY_UPDATE; old RFC 7540 dependency priorities deprecated or removed |
| HPACK leaf API | Independent deflater/inflater lifecycle, encode/decode, table sizing, and entry queries |
| Utilities | ALPN selection, header validation helpers, version and error-string queries |

The library does not parse the HTTP/1.1 Upgrade request or decode its base64url
`HTTP2-Settings` value. It performs H2 session post-processing after the
application has handled those HTTP/1.1 responsibilities.

The upstream README says the project is updating the implementation for RFC
9113; it does not claim that every RFC 9113 requirement is completely
implemented. Source: [pinned Development Status](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/README.rst#L14-L22).

## HTTP Messaging Validation

By default, libnghttp2 validates many HTTP messaging rules, including:

- pseudo-header ordering, presence, and uniqueness;
- request, response, informational response, and trailer sequencing;
- lowercase field names;
- forbidden connection-specific fields and `TE` restrictions;
- method, path, authority, status, and CONNECT forms;
- `Content-Length` syntax, uniqueness, and body-length consistency.

The official guide explicitly says that not everything in the HTTP messaging
section is validated. Source: [pinned HTTP Messaging section](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/doc/programmers-guide.rst#L106-L181).

The header callback documentation requires the application to impose a limit on
accumulated header storage. HPACK can represent a large decoded header set with
a comparatively small compressed block, so collecting headers without an
application limit can lead to excessive memory use. Source: [header callback warning](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L1930-L2010).

## DATA Providers And Ownership

Outbound DATA uses `nghttp2_data_provider2` and a read callback rather than a
single buffer consumed immediately. The library pulls body data later according
to outbound scheduling and flow-control availability. A provider can signal EOF,
defer production, pause, or use the no-copy path. Deferred DATA is resumed with
`nghttp2_session_resume_data()`.

Only one unfinished DATA or HEADERS provider may be active on a stream. The
application retains ownership of provider state until completion, cancellation,
not-send, or stream closure. Source: [`nghttp2_data_source_read_callback2`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L977-L1056).

## Flow Control

Receive-side window updates are automatic by default. With
`nghttp2_option_set_no_auto_window_update()`, the application reports consumed
bytes through:

- `nghttp2_session_consume()`;
- `nghttp2_session_consume_connection()`;
- `nghttp2_session_consume_stream()`.

The public API also exposes connection and stream local, effective-local, and
remote window queries. Source: [flow-control APIs](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/includes/nghttp2/nghttp2.h#L4140-L4207).

**Methodological synthesis:** automatic protocol-window updates do not express
whether a higher-level consumer has processed queued body data. A binding or
adapter that promises consumer-driven backpressure must account for this
separate ownership boundary.

## API Evolution And Deprecated Surface

`v1.69.0` retains deprecated APIs for source and ABI compatibility. Major groups
include:

- system-`ssize_t` APIs replaced by `nghttp2_ssize` `*2` variants;
- `mem_send()` / `mem_recv()` replaced by `mem_send2()` / `mem_recv2()`;
- older DATA providers and callback signatures replaced by `*2` forms;
- request, response, and DATA submission replaced by `*2` forms;
- older HPACK inflate/deflate entry points replaced by `hd2`, `hd3`, or `vec2`;
- `session_upgrade()` replaced by `session_upgrade2()`;
- RFC 7540 dependency-tree priority APIs, many now no-op;
- `no_closed_streams`, which no longer has an effect.

The project says it generally follows Semantic Versioning, may issue PATCH
releases for severe security fixes, and has no plan to make an API-breaking
soname bump for the foreseeable future. Source: [pinned Versioning section](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/README.rst#L1451-L1460).

Opaque handles reduce ABI exposure, but public frame structs and unions are not
all opaque. A consumer that persists or re-exports their memory layout creates a
separate compatibility boundary.

## Build And Platform Facts

The release tarball contains generated build files. The documented Autotools
`--enable-lib-only` option disables applications, examples, and HPACK tools.
For a lib-only build, the upstream requirements list only `pkg-config >= 0.20`;
OpenSSL-compatible TLS libraries, libev, zlib, c-ares, and other dependencies
belong to the bundled applications rather than core libnghttp2.

Source: [pinned build requirements](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/README.rst#L45-L88).

CMake supports library-only, shared, and static builds. The static target defines
`NGHTTP2_STATICLIB`. Source: [pinned `lib/CMakeLists.txt`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/lib/CMakeLists.txt#L75-L119).

The pinned upstream CI contains builds for Linux, macOS, Windows/MSVC, MinGW,
ARM, and Android. This is evidence of upstream C-library build coverage, not
evidence that a particular language binding publishes wheels for those targets.

## License

libnghttp2 is distributed under the MIT License. The license permits use,
copying, modification, merging, publication, distribution, sublicensing, and
sale. Copies or substantial portions must retain the copyright and permission
notice. Static linking does not introduce a copyleft obligation, but a binary
distribution still needs to preserve the notice.

Source: [pinned `COPYING`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/COPYING).

## Security Maintenance

The project publishes a security process that uses private reporting and
coordinates a fixed release with disclosure. Source: [pinned `SECURITY.md`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/SECURITY.md).

The official repository advisory list includes fixes for assertion-failure DoS,
CONTINUATION-frame CPU exhaustion, memory leakage, Rapid Reset, and oversized
SETTINGS processing. Current mutable status must be checked at the [official
security page](https://github.com/nghttp2/nghttp2/security).

nghttp2 is integrated with Google OSS-Fuzz and is built with multiple fuzzing
engines and sanitizers. Source: [OSS-Fuzz nghttp2 project](https://github.com/google/oss-fuzz/tree/master/projects/nghttp2).

**Methodological synthesis:** statically bundled consumers isolate themselves
from system-library ABI drift, but they must rebuild and redistribute their own
artifacts to deliver an upstream security fix.

## Performance Evidence

No current official benchmark was found that quantifies libnghttp2 against a
Python HTTP/2 implementation or predicts the throughput of a Python binding.

- `h2load` is an HTTP/2/HTTP/3 load generator for endpoints, not an isolated
  libnghttp2 microbenchmark.
- The `v1.69.0` release includes HPACK Huffman-decoding optimizations without
  published reproducible comparative numbers.
- The upstream server benchmark page is from 2014, targets an obsolete HTTP/2
  draft, and warns that server configuration affects results. Source: [Server
  Benchmark Round H2-10](https://github.com/nghttp2/nghttp2/wiki/ServerBenchmarkRoundH210).

The official guide says memory receive could be faster than callback receive
because it avoids a callback. That narrow statement does not establish
end-to-end binding performance.

**Methodological synthesis:** binding-level results depend on callback frequency,
header and event object creation, DATA copying, output aggregation, GIL behavior,
and outbound provider calls. Those claims require a benchmark of the completed
binding boundary rather than extrapolation from the C implementation language.
