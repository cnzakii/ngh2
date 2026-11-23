# ngh2 Repository Guidance

Read [CONTRIBUTING.md](CONTRIBUTING.md) first: its setup, checks, code
conventions and test rules apply to every change. This file adds what an
agent needs beyond them.

## Product Boundary

- `ngh2` is a Sans-I/O HTTP/2 protocol library for Python, implemented as a
  Cython binding over the vendored libnghttp2 source.
- libnghttp2 owns HTTP/2 connection and stream state, framing, HPACK, flow
  control, scheduling, and protocol validation. Do not reimplement native
  behavior in the binding without a demonstrated need.
- Keep sockets, TLS, async runtimes, HTTP clients and servers, connection pools,
  routing, retries, and application timeouts outside this package.
- The binding owns Python-facing objects, event and error translation, buffer
  lifetimes, configuration mapping, type information, and distribution
  packaging.

## Repository Map

- `src/ngh2`: Python API, Cython implementation, C declarations, and type stubs.
- `vendor/nghttp2`: pinned upstream Git submodule; update it as a dependency,
  not by editing vendored source in place.
- `tests`: behavior, lifecycle, limits, hyper-h2 interoperability, and h2spec
  adapter coverage. `test_upstream.py` records the RFC rules the pinned
  libnghttp2 does not follow.
- `benchmarks`: reproducible public-API comparison workloads and rendering.
- `examples`: standalone teaching programs exercised by the test suite.
- `docs/site`: authored source for the public documentation website.

## Working Rules

- Read affected callers, tests, exports, stubs, and configuration before
  editing. Establish the requested outcome and its non-goals before adding
  files, features, or tooling.
- Open an issue before adding public API or changing protocol behavior, as
  CONTRIBUTING.md asks.
- Use focused tests while iterating, such as
  `uv run --locked pytest tests/test_connection.py`, then run the checks in
  CONTRIBUTING.md. Run `uv run --locked pytest -m h2spec` when the external
  `h2spec` executable is installed and the change affects protocol
  interoperability.
- Report exactly which checks ran and their results. Never claim that a check
  passed without running it.
- Read the Docs publishes the documentation from `.readthedocs.yaml`; keep
  GitHub Actions responsible for validation rather than adding a second
  publishing path.
- Keep generated C files, build output, local environments, editor state,
  temporary reports, and personal instructions out of version control.

Work is complete only after the relevant focused tests and the local gate in
CONTRIBUTING.md pass.
