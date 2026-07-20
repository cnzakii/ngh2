# Contributing to ngh2

Bug fixes, tests, documentation, API feedback, performance improvements, and
changes that simplify the binding are welcome. Please open an issue before
adding public API or changing protocol behavior. Report vulnerabilities through
[SECURITY.md](SECURITY.md), not a public issue.

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
also tests supported CPython 3.10 through 3.14, free-threaded CPython 3.14t,
prerelease CPython 3.15 and 3.15t,
and native builds on Linux, macOS, and Windows.

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

The generic h2spec suite runs when the external `h2spec` executable is
installed:

```console
uv run --locked pytest -m h2spec
```

Add or update tests for observable behavior changes. Keep public exports, type
stubs, documentation, and native behavior synchronized. Include reproducible
measurements for performance claims.

## Releases

Prepare a release on `main` by updating `src/ngh2/_version.py` and moving the
relevant changelog entries under `## [X.Y.Z] - YYYY-MM-DD`. Then tag that commit:

```console
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The tag builds and tests the source distribution and platform wheels, publishes
them to PyPI through Trusted Publishing, and creates the GitHub release. PyPI
files are immutable; fix a broken release with a new version rather than
reusing an uploaded filename.

Before the first release, register a pending PyPI Trusted Publisher for the
`release.yml` workflow and its `release` environment, then create that protected
environment on GitHub.

By contributing, you agree that your contribution is licensed under the
project's [MIT License](LICENSE).
