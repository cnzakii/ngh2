# Changelog

User-visible changes to ngh2 are recorded here.

## [Unreleased]

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
