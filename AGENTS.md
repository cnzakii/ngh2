# ngh2 Repository Guidance

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
  adapter coverage.
- `benchmarks`: reproducible public-API comparison workloads and rendering.
- `docs/knowledge`: source-based facts, not project decisions or audit reports.
- `.agents/skills`: project workflows for implementation, audit, and knowledge
  work.

## Development

Install locked development dependencies with:

```console
uv sync --locked
```

Use focused tests while iterating, then run the local gate:

```console
uv run --locked pytest tests/test_connection.py
uv run --locked pre-commit run --all-files
uv run --locked pytest -m "not h2spec"
uv build
```

Run `uv run --locked pytest -m h2spec` when the external `h2spec` executable is
installed and the changed behavior affects protocol interoperability.

## Change Rules

- Read affected callers, tests, exports, stubs, and configuration before
  editing. Update runtime behavior, public exports, `.pyi` files, and tests
  together when a Python contract changes.
- Keep public names and docstrings natural for Python and describe HTTP/2
  behavior rather than C binding mechanics. Comment internal ownership and
  callback lifetimes where they are not obvious.
- Validate protocol ranges, ownership, and C conversion boundaries. Do not add
  defensive checks that only restate type hints unless they stabilize a public
  error contract.
- Treat callback pointers and borrowed native buffers as callback-scoped unless
  the upstream API explicitly guarantees a longer lifetime.
- Ruff and ty do not validate Cython source. Binding changes must also pass
  `cython-lint`, compile, and execute relevant tests; the pre-commit gate runs
  the configured static checks.
- Back protocol and libnghttp2 claims with RFCs, official documentation, or
  pinned source observations. Treat mature implementations as observed
  practice, not authority.
- Keep generated C files, build output, local environments, editor state,
  temporary reports, and personal instructions out of version control.

## Project Skills

- Use `ngh2-implementation` for changes to code, tests, packaging, CI, or
  project documentation.
- Use `ngh2-audit` for read-only review after implementation or on request.
- Use `ngh2-knowledge` for source-based factual research and explicitly
  requested maintenance of `docs/knowledge`.

Work is complete only after the relevant focused checks and local gate finish
successfully, followed by a read-only audit of the final changes.
