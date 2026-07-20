---
title: Dependency, vendoring, and license evidence
description: Source-supported facts for dependency scope, vendored native sources, source distributions, wheels, and third-party license notices.
topics: [dependencies, vendoring, native-libraries, sdist, wheels, licenses, supply-chain]
checked_at: 2026-07-18
---

# Dependency, Vendoring, And License Evidence

This document records packaging contracts and pinned implementation practice.
It is not legal advice, a dependency approval list, or a project decision.

## Dependency Scope

The following scope model is **methodological synthesis**:

| Scope | Evidence question |
|---|---|
| Runtime | Must installed code import, link, or load the dependency? |
| Build | Is the dependency required to produce an artifact? |
| Test/development | Is it used only to create verification evidence? |
| Vendored source | Are upstream source bytes included in an sdist or repository? |
| Bundled binary | Are upstream machine-code bytes included in a wheel? |
| System library | Does the target environment provide the native library? |
| Transitive | Is the dependency introduced through another dependency? |

One dependency can occupy several scopes. A lockfile, build declaration, source
tree, and binary dependency listing answer different questions; none alone
proves the complete contents of every release artifact.

## Source Distributions And Native Sources

**Official guidance:** PyPA recommends publishing the source used to build a
binary extension as well as binary wheels. This lets unsupported platforms and
downstream distributors build from source.

Source: [PyPA, packaging binary extensions](https://packaging.python.org/en/latest/guides/packaging-binary-extensions/).

scikit-build-core normally derives sdist contents from source-control and ignore
information. Its `sdist.include` setting explicitly includes paths that default
selection might skip, and its sdist generation is reproducible by default.

Source: [scikit-build-core source-file inclusion](https://scikit-build-core.readthedocs.io/en/latest/configuration/index.html#configuring-source-file-inclusion).

**Methodological synthesis:** a configure-time URL plus content hash fixes the
accepted archive bytes but does not place those bytes in the sdist. It also
retains network and remote-host availability as build inputs. Vendoring places
the selected source in the sdist, while making upstream updates an explicit
source-tree change.

## Vendored, Bundled, And System Models

Observed native packages use several models:

| Model | Source-build property | Wheel property |
|---|---|---|
| Vendored source, static link | sdist contains selected native source | extension contains linked native code |
| System source build, bundled official wheel | local build discovers a system library | release automation fixes and bundles selected libraries |
| System runtime dependency | local build or Python code locates system library | environment supplies native artifact and ABI |

No Python packaging specification requires one universal model. The models
assign update, ABI, availability, and license-notice ownership differently.
Static linking avoids a separate loader path but requires rebuilding wheels to
deliver a native-library security update.

## Observed Practice In Versioned Bindings

### httptools 0.8.0

**Observed practice:** httptools defaults to compiling its vendored llhttp and
http-parser C sources. Build flags allow the caller to opt into system
libraries. Its manifest includes the vendor C sources, headers, readmes, and
license files in the sdist. Project metadata lists the project and vendor
license files explicitly.

Sources:

- [`setup.py`](https://github.com/MagicStack/httptools/blob/v0.8.0/setup.py#L109-L140)
- [`MANIFEST.in`](https://github.com/MagicStack/httptools/blob/v0.8.0/MANIFEST.in)
- [`pyproject.toml`](https://github.com/MagicStack/httptools/blob/v0.8.0/pyproject.toml#L19-L25)

### uvloop 0.22.1

**Observed practice:** uvloop keeps libuv under `vendor/libuv`, builds that copy
by default, and provides an option to link a system libuv. Its sdist manifest
recursively includes the vendor tree while excluding selected repository and
documentation material. The build ensures generated configure files exist
before creating an sdist.

Sources:

- [`setup.py`](https://github.com/MagicStack/uvloop/blob/v0.22.1/setup.py#L28-L63)
- [`MANIFEST.in`](https://github.com/MagicStack/uvloop/blob/v0.22.1/MANIFEST.in)

### python-zstandard 0.25.0

**Observed practice:** python-zstandard includes a selected zstd source under
`zstd/` and compiles it by default. A system-zstd mode links `zstd` instead;
the build documentation requires the system headers and library to match the
binding's expected version. Its manifest grafts the vendored source into the
sdist.

Sources:

- [`setup_zstd.py`](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/setup_zstd.py#L28-L129)
- [`MANIFEST.in`](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/MANIFEST.in)

These three projects establish that vendored-by-default plus optional-system
builds are established practice. They do not prove that every Python binding
must offer both modes.

## License Metadata And Notices

PEP 639 defines separate distribution metadata:

- `license` is an SPDX expression for the distribution archive;
- `license-files` lists project-relative glob patterns for license and legal
  notice files.

Build tools must include every matched `license-files` entry in distribution
archives and record it through `License-File` metadata. Wheels using metadata
2.4 place those paths below `.dist-info/licenses/`.

Sources:

- [PyPA project metadata, `license-files`](https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#license-files)
- [wheel license-file layout](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)

The libnghttp2 MIT license permits copying, modification, distribution,
sublicensing, and sale provided that copies or substantial portions retain its
copyright and permission notice.

Source: [libnghttp2 v1.69.0 `COPYING`](https://github.com/nghttp2/nghttp2/blob/68cb6900fde14c77f0cd7add0e094a862960eb99/COPYING).

**Methodological synthesis:** preserving the upstream license file beside
vendored source supplies source provenance and gives packaging metadata a
canonical notice to include. Moving the same text into another file can still
preserve the notice, but it creates a second copy that must remain synchronized
with the selected upstream source.

## Verification Layers

The following is methodological synthesis:

1. Inspect upstream source and registry metadata for version and license claims.
2. Inspect the exact sdist for native source and required notice files.
3. Inspect the exact wheel for native modules, bundled libraries, and
   `.dist-info/licenses` contents.
4. Inspect dynamic dependencies with platform tools; a successful import does
   not prove that a wheel is self-contained.
5. Re-run the inspection whenever the native dependency, build mode, platform,
   or repair tooling changes.
