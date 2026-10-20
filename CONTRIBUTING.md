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

The default development interpreter is Python 3.12. Continuous integration
also tests supported CPython 3.10 through 3.15, free-threaded CPython 3.14t and
3.15t, and native builds on Linux (glibc and musl), macOS, and Windows.

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

The generic h2spec suite runs when the external `h2spec` executable is
installed:

```console
uv run --locked pytest -m h2spec
```

Add or update tests for observable behavior changes. Keep public exports, type
stubs, documentation, and native behavior synchronized. Include reproducible
measurements for performance claims.

The coverage job traces the Cython extension and fails below 95.9% line
coverage. Keep behavior tests focused on observable results rather than
forcing impossible internal states to reach every line. Allocation-failure
tests run in isolated, untraced subprocesses: failing the interpreter's
allocator also interferes with coverage's own bookkeeping. These tests still
gate correctness where CPython provides `_testcapi`, but their child-process
execution is not included in the coverage percentage. Remaining gaps include
native allocation failures, rare error translations, and internal consistency
guards.

## Performance measurements

Run both implementations from the same checkout and locked environment on an
otherwise idle machine. Each workload checks that both endpoints complete the
expected requests, responses, and body transfers before timing starts.
Connections and HPACK state are reused; timings exclude connection setup,
sockets, TLS, and application work.

```console
uv sync --locked
uv run --locked python benchmarks/compare_h2.py \
  --processes 20 --values 3 --warmups 3 --min-time 0.1 \
  -o build/python-benchmark.json
uv run --locked python -m pyperf convert build/python-benchmark.json \
  --update-metadata "ngh2_revision=$(git rev-parse HEAD)" \
  --stdout > docs/assets/python-benchmark.json
uv run --locked python benchmarks/render_results.py \
  docs/assets/python-benchmark.json \
  --svg docs/assets/python-benchmark.svg \
  --table docs/assets/python-benchmark.md
```

Use a fresh output filename for each run; `pyperf` does not overwrite existing
results. Record the measured source revision only when the implementation
matches that commit. Keep the generated table and the README performance
section synchronized, and inspect `pyperf` warnings before publishing results.
The multiplexed workload reports time per exchange within a 100-stream batch.

## Documentation and examples

Keep the documented learning path in protocol order: first exchange, protocol
model, multiplexing, complete messages, transport integration, flow control,
event handling, recovery, then optional controls.

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
