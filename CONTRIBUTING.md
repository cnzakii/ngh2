# Contributing to ngh2

Bug fixes, tests, documentation, API feedback, performance improvements, and
changes that simplify the binding are welcome. Please open an issue before
adding public API or changing protocol behavior. Report vulnerabilities through
[SECURITY.md](SECURITY.md), not a public issue.
Participation is governed by the
[Code of Conduct](https://github.com/cnzakii/ngh2/blob/main/CODE_OF_CONDUCT.md).

## Development Setup

You need Git, uv, and a C compiler supported by CPython: Visual Studio Build
Tools on Windows, Xcode Command Line Tools on macOS, or the platform compiler
toolchain on Linux. Clone the nghttp2 submodule with the repository:

```console
git clone --recurse-submodules https://github.com/cnzakii/ngh2.git
cd ngh2
uv sync --locked
```

`.python-version` sets the development interpreter. Continuous integration
also tests supported CPython 3.10 through 3.15, free-threaded CPython 3.14t and
3.15t, and native builds on Linux (glibc and musl), macOS, and Windows, and
runs the test suite under AddressSanitizer and UBSan.

Enable the repository's pre-commit checks once after cloning:

```console
uv run --locked pre-commit install
```

## Running Checks

Run the same static checks as the pre-commit hook:

```console
uv run --locked pre-commit run --all-files
```

Run the test suite and build both distribution formats:

```console
uv run --locked pytest -m "not h2spec"
uv build
```

Build the documentation with strict link validation:

```console
uv run --locked --no-dev --group docs zensical build --strict
```

Use `zensical serve` with the same `--no-dev --group docs` arguments for local
preview.

The full h2spec suite runs, with its expected failures listed in
`tests/test_interop_h2spec.py`, when the external `h2spec` executable is
installed:

```console
uv run --locked pytest -m h2spec
```

The coverage job traces the Cython extension and fails below 95.9% line
coverage. Keep behavior tests focused on observable results rather than
forcing impossible internal states to reach every line. Allocation-failure
tests run in isolated, untraced subprocesses: failing the interpreter's
allocator also interferes with coverage's own bookkeeping. These tests still
gate correctness where CPython provides `_testcapi`, but their child-process
execution is not included in the coverage percentage. Remaining gaps include
native allocation failures, rare error translations, and internal consistency
guards.

## Code Conventions

### Scope

- Back protocol and libnghttp2 claims with RFCs, official documentation, or
  pinned source, and cite them in the pull request. Treat mature
  implementations such as hyper-h2 as observed practice, not authority.
- Follow the trade-offs libnghttp2 makes deliberately. When it misses an RFC
  rule it could fix, do not work around it in the binding: record the rule as
  a strict expected failure in `tests/test_upstream.py` and in the table in
  `tests/interop/README.md`.
- Prefer the standard library and existing dependencies. Add a dependency
  only for a current need.
- Before 1.0, an incorrect design is replaced directly, without compatibility
  aliases or shims.

### Boundaries

- Validate protocol ranges, ownership, and C conversion boundaries where
  values enter from the caller. Do not add checks that only restate type hints
  unless they stabilize a public error contract.
- Treat callback pointers and borrowed native buffers as callback-scoped
  unless the upstream API explicitly guarantees a longer lifetime. Comment
  ownership and callback lifetimes where they are not obvious.

### Naming and Style

- Public names and docstrings follow Python conventions and describe HTTP/2
  behavior rather than C binding mechanics.
- When a Python contract changes, update runtime behavior, public exports,
  `.pyi` stubs, documentation, and tests together.
- Ruff and ty do not read Cython source. Binding changes must also pass
  `cython-lint`, compile, and run the relevant tests.

### Tests

- Add the smallest test that fails when the changed behavior breaks. Use
  behavior tests for documented results, hyper-h2 or h2spec interoperability
  for bytes on the wire, and reproducible measurements for performance claims.
- Do not add tests that only restate constants, types, or implementation
  spelling.

## Performance measurements

Run both implementations from the same checkout and locked environment on an
otherwise idle machine. Each workload checks that both endpoints complete the
expected requests, responses, and body transfers before timing starts.
Connections and HPACK state are reused; timings exclude connection setup,
sockets, TLS, and application work.

```console
uv sync --locked
rm -f build/python-benchmark.json
uv run --locked python benchmarks/compare_h2.py \
  --processes 20 --values 3 --warmups 3 --min-time 0.1 \
  -o build/python-benchmark.json
cp build/python-benchmark.json docs/assets/python-benchmark.json
uv run --locked python benchmarks/render_results.py \
  docs/assets/python-benchmark.json \
  --table docs/assets/python-benchmark.md \
  --readme README.md
```

The result records the measured checkout with `git describe --dirty`, so it is
written outside tracked files while measuring. The renderer updates the README
table between its markers; a test fails if the two drift apart. Inspect
`pyperf` warnings before publishing results. Times are per iteration: one
request, or ten for the concurrent scenarios. The module
docstring of `benchmarks/compare_h2.py` lists the terms both libraries are held
to.

Refresh the published comparison for each release. Between releases,
[CodSpeed](https://codspeed.io/) runs the ngh2 side of the same workloads on
every pull request and reports changes against `main`. Run them locally with:

```console
uv run --locked pytest benchmarks/test_codspeed.py --codspeed
```

## Documentation and examples

Keep the documented learning path in protocol order: first exchange, protocol
model, multiplexing, complete messages, transport integration, flow control,
event handling, recovery, then optional controls.

The README, runnable examples, and `docs/site` are coordinated entry points;
reuse the canonical example source instead of maintaining copies. Keep
tutorials progressive and connected, guides task-oriented, and the API
reference complete and neutral. Explain what the user does, why, and what they
observe, without binding internals that do not change how ngh2 is used.

Examples are standalone teaching programs. Explain important protocol phases
and ownership decisions with comments, show the observable result in the
matching guide, and add deterministic programs to `tests/test_examples.py`.
Do not replace a runnable lesson with assertion-oriented test code or hide its
setup in a shared test helper.

Pull requests build the documentation with strict validation. Read the Docs
also builds pull request previews, `latest` from `main`, `stable` from the
newest release, and versioned documentation from release tags using
`.readthedocs.yaml`.

## Releases

ngh2 publishes final releases as `X.Y.Z`:

- increment `X` for incompatible public API or behavior changes after the
  public API becomes stable at 1.0;
- increment `Y` for backward-compatible public functionality; before 1.0,
  also use it for intentional incompatible public changes;
- increment `Z` for backward-compatible fixes for bugs, security issues,
  installation and packaging failures, or faults in published release
  artifacts or metadata.

A security fix that must break public compatibility follows the incompatible
change rule instead.

Documentation, tests, CI, and internal tooling changes do not by themselves
trigger a package release. Development documentation is published from `main`
as `latest`, and those changes are included in the next qualifying release.
Security issues and broken published artifacts may require an immediate
maintenance release; otherwise, related changes are released together.

Every release starts with a pull request that updates `src/ngh2/_version.py`
and moves the relevant changelog entries under
`## [X.Y.Z] - YYYY-MM-DD`. Tag the release pull request's merge commit only
after the required checks have passed and no release-blocking issue is known:

```console
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The tag builds and tests the source distribution and platform wheels, publishes
them to PyPI through Trusted Publishing, and creates the GitHub release. PyPI
files are immutable; fix a broken release with a new version rather than
reusing an uploaded filename. Pull requests that change the release workflow,
`pyproject.toml`, or `src/ngh2/_version.py`, including release pull requests,
run the same wheel and source distribution builds and tests without
publishing.

After publication, verify the PyPI files and installation, the GitHub release,
and the `stable` documentation build on Read the Docs.

By contributing, you agree that your contribution is licensed under the
project's [MIT License](LICENSE).
