# Changelog

User-visible changes to ngh2 are recorded here.

## [Unreleased]

### Added

- `reset_stream(..., after_end_stream=True)` sends the stream's queued
  headers, body bytes, and trailers before RST_STREAM, so a server can stop
  an unneeded request body with `NO_ERROR` after a complete response.
- `StreamStateError`, raised when a call does not fit one stream's current
  state, such as sending body bytes after the stream ended.

### Changed

- **Breaking:** `acknowledge_received_data(amount, stream_id)` is now
  `consume_received_data(stream_id, amount)`. The stream comes first, like
  every other stream method, and the name no longer suggests an HTTP/2 ACK.
- **Breaking:** Local misuse no longer raises protocol errors. Calling a
  method from the wrong role raises `ConnectionStateError` instead of
  `ConnectionProtocolError`, and invalid stream operations raise
  `StreamStateError` instead of `StreamProtocolError`.
  `StreamUnavailableError` and `PushDisabledError` now derive from
  `StreamStateError`; `ConnectionClosingError` and `NoAvailableStreamIDError`
  derive from `ConnectionStateError`. Protocol errors are reserved for HTTP/2
  rule violations.
- **Breaking:** `remote_window_size` and `local_window_size` are methods that
  take an optional `stream_id`, with `0` selecting the connection. They
  replace the properties of the same names and `stream_remote_window_size()`
  and `stream_local_window_size()`.
- **Breaking:** `ping()` is now `send_ping()`, matching the other frame
  methods.
- **Breaking:** `Configuration.peer_max_concurrent_streams` is now
  `initial_peer_max_concurrent_streams`, since it applies only until the
  peer's first SETTINGS frame.
- Event `error_code` fields report known codes as `ErrorCode` members, and
  `SettingsReceived.settings`, `local_settings`, and `remote_settings` key
  known identifiers by `Setting` members. Unknown values remain integers.
- `reset_stream()`, `send_goaway()`, and `terminate_connection()` show their
  defaults as `ErrorCode` members.
- `reset_stream()` and `terminate_connection()` document that they discard
  frames still queued for the affected streams.
- Lower per-call overhead for integer arguments, role checks, header
  submission, body queues, output staging, and received response headers. A
  small request/response exchange with trailers and manual flow control uses
  about 13% less CPU.
- `data_to_send(amount)` copies body bytes once when a whole DATA frame fits
  the requested amount, as it already did without a limit.

### Fixed

- All public `bytes` inputs accept subclasses, including byte-valued enums:
  header names and values, body data, h2c settings, PING and GOAWAY payloads,
  extension-frame fields, and event constructor arguments.
- Protocol serialization uses the underlying byte contents and lengths even
  when a subclass overrides `__len__`, `__bool__`, or `__bytes__`.
- Queued trailer fields snapshot byte subclasses so their finalizers cannot
  re-enter the connection during trailer serialization and crash the process.

## [0.3.0] - 2026-10-20

### Added

- Header-taking APIs accept iterables of byte pairs, including generators and
  `headers.items()`.
- Support for CPython 3.15 and free-threaded CPython 3.15t, with wheels for
  both.
- Wheels for musl-based Linux distributions such as Alpine (`musllinux_1_2`
  on x86_64 and aarch64), which previously built from the source distribution.

### Changed

- Reduced intermediate body copies when `data_to_send()` is called without
  a byte limit.
- Release temporary output buffers before `data_to_send()` returns instead of
  retaining a duplicate until the next call.
- Argument conversion now completes before connection-state checks. Calls
  with both invalid arguments and invalid connection state may therefore
  report the input error first.

### Fixed

- Header submission retains valid field bytes from lazy sequences and custom
  tuple subclasses. Deferred trailers take a stable snapshot when queued.
- ORIGIN serialization validates the actual bytes buffer and uses its storage
  length, including for bytes subclasses.
- Uninitialized connections and inputs that invalidate a connection during
  conversion raise `ConnectionStateError` safely.
- Output failures after serialization begins invalidate the connection rather
  than allowing later output to silently lose frame bytes.
- Configuration limits consistently use the integer values validated during
  construction, including values supplied through the integer index protocol.
- Corrected the priority example and guide to show that client priority signals
  are applied automatically when extensible priorities are enabled.

## [0.2.2] - 2026-08-01

### Changed

- Updated the vendored libnghttp2 dependency to v1.70.0.

### Fixed

- CONTINUATION frame limits no longer count partial frame-header reads, so
  valid fragmented input is accepted independently of transport chunking.
- Failed push promises for unavailable associated streams no longer consume the
  next promised stream identifier.
- PRIORITY_UPDATE payload sizes and server priority urgency values are validated
  before crossing the native boundary.

## [0.2.1] - 2026-07-26

This maintenance release changes distribution metadata, documentation hosting,
and release infrastructure only. The Python API and HTTP/2 behavior are
unchanged from 0.2.0.

### Fixed

- Published package metadata and README links now lead to stable, versioned
  documentation on Read the Docs after the hosting migration.

## [0.2.0] - 2026-07-25

### Added

- Absolute connection- and stream-level receive-window adjustment with
  `Connection.set_local_window_size()`.
- `ConnectionClosed` for the terminal HTTP/2 connection lifecycle.

### Changed

- The outbound body queue query is now `Connection.queued_body_size()` and
  reports only body bytes still waiting for HTTP/2 framing.
- `StreamClosed.local_error` now reports a delayed local stream-operation
  failure alongside the terminal HTTP/2 error code.
- Invalid peer header fields now produce stream-scoped protocol failure instead
  of being silently ignored.
- Configuration and wire integers reject non-integer values without truncation;
  `max_settings` must be positive.
- `SettingsReceived.settings` is now a read-only snapshot.
- Native stream lookup now uses a per-session randomized seed.

### Fixed

- h2c upgrade now preserves callback-side Python exceptions and reports an
  excessive HTTP2-Settings payload as invalid input instead of an internal
  engine failure.

### Removed

- `FrameNotSent`; delayed outbound failures now follow the affected stream's
  normal `StreamClosed` lifecycle.
- `FrameType`, which no longer has a public event field to describe.

## [0.1.0] - 2026-07-20

### Added

- Initial Python package for Sans-I/O HTTP/2 powered by libnghttp2.
- Client and server connections, h2c upgrade, flow control, server push,
  priority, extension frames, and typed protocol events.
- Support for GIL-enabled CPython 3.10 through 3.14 and free-threaded CPython
  3.14t.
