---
title: Reference Python bindings for C libraries
description: Version-pinned observations of mature Python packages using Cython, handwritten CPython C, CFFI API mode, and runtime CFFI, including facade, ownership, dependency, and wheel patterns.
topics: [python, c, bindings, cython, cffi, c-api, packaging, wheels, observed-practice]
checked_at: 2026-07-18
---

# Reference Python Bindings For C Libraries

## Method And Scope

This is a deliberately varied sample of mature projects, not a download-ranked
or statistically representative survey. It supports statements about observed
practice in the named versions only; it cannot establish one binding technology
as the universal industry standard.

| Project | Release | Pinned commit |
|---|---|---|
| lxml | `6.1.1` | [`b4a4c595fb875d6f50ae113449834209a364643a`](https://github.com/lxml/lxml/tree/b4a4c595fb875d6f50ae113449834209a364643a) |
| Pillow | `12.3.0` | [`bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d`](https://github.com/python-pillow/Pillow/tree/bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d) |
| PycURL | `7.47.0` | [`dbff9bc25f2211e0a0db719162f49448538b463c`](https://github.com/pycurl/pycurl/tree/dbff9bc25f2211e0a0db719162f49448538b463c) |
| Psycopg | `3.3.4` | [`83f110367cdd249cc0a352e2246ecea9e878e5a0`](https://github.com/psycopg/psycopg/tree/83f110367cdd249cc0a352e2246ecea9e878e5a0) |
| python-zstandard | `0.25.0` | [`7a77a7510b8ce068e4a103d29aea1b5ec829d8b6`](https://github.com/indygreg/python-zstandard/tree/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6) |
| cairocffi | `1.7.1` | [`0f45d6a42a352d4255a8ffec4b77ae648f19d654`](https://github.com/Kozea/cairocffi/tree/0f45d6a42a352d4255a8ffec4b77ae648f19d654) |
| cmarkgfm | `2025.10.22` | [`db8af88d2075eb4baf29641e389dad88d3b56077`](https://github.com/theacodes/cmarkgfm/tree/db8af88d2075eb4baf29641e389dad88d3b56077) |

## Comparative Map

**Observed practice:**

| Project | Binding | Public facade | Native dependency model | Build and wheel model | `abi3` in pinned release |
|---|---|---|---|---|---|
| lxml | Cython | High-level API largely in Cython extension types | System libraries for local source builds; fixed static dependencies in official wheels | setuptools, Cython, cibuildwheel, auditwheel | No |
| Pillow | Handwritten CPython C API | Thick Python `PIL` package over private extensions | System discovery locally; fixed image-library dependencies in official wheels | Custom setuptools backend and cibuildwheel | No |
| PycURL | Handwritten CPython C API | Mostly native types with a thin Python package | `curl-config` for source builds; vcpkg-built libcurl and dependencies in wheels | setuptools, cibuildwheel, platform repair tools | No |
| Psycopg | Cython plus pure-Python/ctypes option | Strong Python facade over selectable implementations | System libpq for `psycopg[c]`; separately distributed bundled `psycopg[binary]` | setuptools and cibuildwheel for binary package | No for native packages |
| python-zstandard | Handwritten C default, CFFI alternative, optional Rust backend | Python facade normalizes backends | Vendored zstd by default; optional system zstd | setuptools and cibuildwheel | No |
| cairocffi | CFFI ABI mode | Entire public API in Python | Runtime system Cairo through `dlopen` | Flit; generic pure-Python wheel for project code | Not applicable |
| cmarkgfm | CFFI out-of-line API mode | Python wrapper above generated CFFI module | Vendored cmark source compiled into extension | setuptools `cffi_modules` and cibuildwheel | No |

Wheel tags and published artifact sets were checked against the pinned PyPI
release pages:
[lxml 6.1.1](https://pypi.org/project/lxml/6.1.1/#files),
[Pillow 12.3.0](https://pypi.org/project/pillow/12.3.0/#files),
[PycURL 7.47.0](https://pypi.org/project/pycurl/7.47.0/#files),
[psycopg 3.3.4](https://pypi.org/project/psycopg/3.3.4/#files),
[psycopg-binary 3.3.4](https://pypi.org/project/psycopg-binary/3.3.4/#files),
[zstandard 0.25.0](https://pypi.org/project/zstandard/0.25.0/#files),
[cairocffi 1.7.1](https://pypi.org/project/cairocffi/1.7.1/#files), and
[cmarkgfm 2025.10.22](https://pypi.org/project/cmarkgfm/2025.10.22/#files).

## lxml 6.1.1

### Structure

```text
pyproject.toml
setup.py
buildlibxml.py
src/lxml/
├── etree.pyx
├── objectify.pyx
├── parser.pxi
├── proxy.pxi
├── extensions.pxi
├── includes/*.pxd
└── Python helpers and subpackages
```

The declarations for libxml2 and libxslt are concentrated in Cython `.pxd`
files, including [`tree.pxd`](https://github.com/lxml/lxml/blob/b4a4c595fb875d6f50ae113449834209a364643a/src/lxml/includes/tree.pxd).
[`etree.pyx`](https://github.com/lxml/lxml/blob/b4a4c595fb875d6f50ae113449834209a364643a/src/lxml/etree.pyx)
is itself a high-level public object API rather than only a low-level `_core`
hidden behind a large Python facade.

[`parser.pxi`](https://github.com/lxml/lxml/blob/b4a4c595fb875d6f50ae113449834209a364643a/src/lxml/parser.pxi)
contains parser callbacks, GIL transitions, stored exception handling, and parser
context cleanup. [`proxy.pxi`](https://github.com/lxml/lxml/blob/b4a4c595fb875d6f50ae113449834209a364643a/src/lxml/proxy.pxi)
coordinates ownership of libxml2 node and document pointers.

The pinned [`pyproject.toml`](https://github.com/lxml/lxml/blob/b4a4c595fb875d6f50ae113449834209a364643a/pyproject.toml)
uses setuptools and Cython and configures cibuildwheel. The wheel workflow uses
[`buildlibxml.py`](https://github.com/lxml/lxml/blob/b4a4c595fb875d6f50ae113449834209a364643a/buildlibxml.py)
to build fixed dependency versions for static official wheels, while source
builds can use system development libraries.

## Pillow 12.3.0

### Structure

```text
pyproject.toml
setup.py
_custom_build/backend.py
src/
├── _imaging.c
├── decode.c
├── encode.c
├── libImaging/
└── PIL/*.py
```

[`_imaging.c`](https://github.com/python-pillow/Pillow/blob/bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d/src/_imaging.c)
uses the CPython C API directly for native types, reference counting, and
deallocation. Decoder and encoder lifecycles are implemented in
[`decode.c`](https://github.com/python-pillow/Pillow/blob/bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d/src/decode.c)
and [`encode.c`](https://github.com/python-pillow/Pillow/blob/bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d/src/encode.c).

The user-facing product is largely the Python `PIL` package, including
[`PIL/Image.py`](https://github.com/python-pillow/Pillow/blob/bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d/src/PIL/Image.py),
rather than direct interaction with `_imaging`.

Local builds search for system JPEG, zlib, FreeType, WebP, TIFF, and related
libraries. The official wheel process fixes and builds dependencies in
[`wheels-dependencies.sh`](https://github.com/python-pillow/Pillow/blob/bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d/.github/workflows/wheels-dependencies.sh)
and drives builds through cibuildwheel in the repository workflows.

## PycURL 7.47.0

### Structure

```text
pyproject.toml
setup.py
src/
├── pycurl.h
├── module.c
├── easy.c
├── easycb.c
├── multi.c
└── pycurl/*.py
```

PycURL is a callback-heavy handwritten CPython C binding. Its
[`pycurl.h`](https://github.com/pycurl/pycurl/blob/dbff9bc25f2211e0a0db719162f49448538b463c/src/pycurl.h)
defines callback ownership fields and thread-state/GIL helpers.
[`easycb.c`](https://github.com/pycurl/pycurl/blob/dbff9bc25f2211e0a0db719162f49448538b463c/src/easycb.c)
turns libcurl write, read, socket, progress, and related callbacks into Python
calls, validates results, and handles exceptions.

[`easy.c`](https://github.com/pycurl/pycurl/blob/dbff9bc25f2211e0a0db719162f49448538b463c/src/easy.c)
stores owner pointers in libcurl user-data slots, retains Python callbacks, and
breaks native associations before releasing references in clear/deallocation
paths.

Source builds discover libcurl through `curl-config` or explicit Windows paths.
The pinned [`pyproject.toml`](https://github.com/pycurl/pycurl/blob/dbff9bc25f2211e0a0db719162f49448538b463c/pyproject.toml)
configures cibuildwheel; wheel builds use vcpkg-provided libcurl and platform
repair tools.

## Psycopg 3.3.4

### Structure

```text
psycopg/                     # public Python package
└── psycopg/pq/
    ├── __init__.py
    ├── pq_ctypes.py
    └── abc.py
psycopg_c/
├── pyproject.toml
├── build_backend/
└── psycopg_c/
    ├── _psycopg.pyx
    └── pq/
        ├── libpq.pxd
        ├── pgconn.pyx
        └── pgresult.pyx
```

The public
[`psycopg.pq.__init__.py`](https://github.com/psycopg/psycopg/blob/83f110367cdd249cc0a352e2246ecea9e878e5a0/psycopg/psycopg/pq/__init__.py)
selects a C, bundled-binary, or ctypes implementation behind one Python-facing
interface. [`libpq.pxd`](https://github.com/psycopg/psycopg/blob/83f110367cdd249cc0a352e2246ecea9e878e5a0/psycopg_c/psycopg_c/pq/libpq.pxd)
contains the C declarations.

[`pgconn.pyx`](https://github.com/psycopg/psycopg/blob/83f110367cdd249cc0a352e2246ecea9e878e5a0/psycopg_c/psycopg_c/pq/pgconn.pyx)
calls `PQfinish()` from deallocation and enters Python from notice callbacks with
the GIL. Callback exceptions are caught and logged instead of crossing the C
ABI.

The C package's
[`cython_backend.py`](https://github.com/psycopg/psycopg/blob/83f110367cdd249cc0a352e2246ecea9e878e5a0/psycopg_c/build_backend/cython_backend.py)
requires Cython for a repository checkout containing `.pyx`; generated C is
included in its sdist. `psycopg[c]` links to a system libpq located with
`pg_config`, while the separately published binary distribution builds and
bundles libpq and other dependencies through cibuildwheel.

## python-zstandard 0.25.0

### Structure

```text
pyproject.toml
setup.py
setup_zstd.py
make_cffi.py
zstandard/
├── __init__.py
└── backend_cffi.py
c-ext/
├── backend_c.c
├── compressor.c
└── decompressor.c
zstd/                       # vendored upstream source
rust-ext/                   # optional backend
```

[`zstandard/__init__.py`](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/zstandard/__init__.py)
uses the handwritten C backend by default on CPython and the CFFI backend by
default on PyPy, then supplies shared Python helpers above the selected backend.

Native ownership and GIL release are explicit in files such as
[`compressor.c`](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/c-ext/compressor.c).
[`make_cffi.py`](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/make_cffi.py)
builds the alternative CFFI interface.

[`setup_zstd.py`](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/setup_zstd.py)
uses vendored zstd by default and offers a system-zstd option. A PyO3 backend is
present but disabled by default in the pinned release's
[`setup.py`](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/setup.py).

## cairocffi 1.7.1

### Structure

```text
pyproject.toml
cairocffi/
├── __init__.py
├── constants.py
├── ffi.py
├── context.py
├── surfaces.py
├── patterns.py
└── fonts.py
```

[`ffi.py`](https://github.com/Kozea/cairocffi/blob/0f45d6a42a352d4255a8ffec4b77ae648f19d654/cairocffi/ffi.py)
declares the Cairo API through CFFI. The package locates and loads the system
Cairo shared library at runtime in
[`__init__.py`](https://github.com/Kozea/cairocffi/blob/0f45d6a42a352d4255a8ffec4b77ae648f19d654/cairocffi/__init__.py).

The user-visible types are Python classes. Files such as
[`surfaces.py`](https://github.com/Kozea/cairocffi/blob/0f45d6a42a352d4255a8ffec4b77ae648f19d654/cairocffi/surfaces.py)
use `ffi.gc()`, callbacks, and explicit keepalive collections for C pointers,
buffers, and callback lifetime.

The project itself publishes generic Python code rather than a compiled project
extension. Native compatibility is delegated to CFFI and to the system Cairo
installation; this is not the same as publishing an `abi3` extension.

## cmarkgfm 2025.10.22

### Structure

```text
pyproject.toml
setup.py
src/cmarkgfm/
├── build_cmark.py
├── cmark.cffi.h
├── cmark_module.h
├── _cmark
└── cmark.py
third_party/cmark/
generated/{unix,windows}/
```

[`cmark.cffi.h`](https://github.com/theacodes/cmarkgfm/blob/db8af88d2075eb4baf29641e389dad88d3b56077/src/cmarkgfm/cmark.cffi.h)
provides declarations for CFFI. The out-of-line API builder in
[`build_cmark.py`](https://github.com/theacodes/cmarkgfm/blob/db8af88d2075eb4baf29641e389dad88d3b56077/src/cmarkgfm/build_cmark.py)
compiles vendored `third_party/cmark` sources into the extension.

[`cmark.py`](https://github.com/theacodes/cmarkgfm/blob/db8af88d2075eb4baf29641e389dad88d3b56077/src/cmarkgfm/cmark.py)
provides direct wrappers and composed higher-level helpers and frees parser state
with `try/finally`. The pinned project uses setuptools `cffi_modules` and
cibuildwheel.

## Cross-Project Synthesis

### Binding Technology

The sample contains multiple long-lived production approaches:

- handwritten CPython C API: Pillow, PycURL, and the default
  python-zstandard backend;
- Cython: lxml and Psycopg's C backend;
- CFFI: cairocffi, cmarkgfm, and python-zstandard's alternative backend;
- Rust/PyO3: present only as a disabled alternative in the pinned
  python-zstandard release.

**Methodological synthesis:** the evidence does not support a single universal
binding language. Existing native code, callback density, desired Python object
model, supported interpreters, and native dependency distribution all affect the
choice.

### Public Facade Shape

The sample shows three recurring shapes:

1. high-level API implemented directly in native/Cython types, as in lxml;
2. a thin Python package that mostly exports native types, as in PycURL;
3. a substantial Python facade over one or more backends, as in Pillow,
   Psycopg, python-zstandard, cairocffi, and cmarkgfm.

**Methodological synthesis:** a private `_core` plus Python facade is common but
not mandatory. Adding a second facade solely to match a directory template is
not supported by this sample.

### Callback And Lifetime Ownership

Across tools, the same native constraints recur:

- one Python or native owner holds the C handle;
- the matching native destructor runs from deallocation, explicit close, or an
  `ffi.gc` finalizer;
- callback user data points back to the owner or a dedicated context;
- Python callables and buffers remain strongly referenced while C may use them;
- callbacks enter Python with the required GIL/thread state;
- Python exceptions do not unwind through the C ABI;
- pure native work may release the GIL, but Python callbacks reacquire it.

These are ownership requirements of the boundary, not features supplied
automatically by a particular binding syntax.

### Native Dependency Distribution

Several projects use different policies for official wheels and local source
builds:

- official wheels bundle or statically link fixed native dependencies for a
  predictable install;
- local/downstream source builds can use system libraries for distribution
  integration and independently patched dependencies.

lxml, Pillow, PycURL, and Psycopg demonstrate this dual policy.
python-zstandard and cmarkgfm default to compiling vendored source. cairocffi
always relies on a runtime system library.

### Wheels And Stable ABI

All six sampled projects that publish compiled project artifacts use
cibuildwheel in their release process. In the pinned releases, none of the
compiled bindings publishes `abi3` wheels; they publish interpreter-specific
CPython wheels, and some publish separate PyPy artifacts or provide a
Python/CFFI/ctypes backend.

This observation establishes that `abi3` is not required for a mature native
binding. It does not establish that Stable ABI is unsuitable for a new project.
