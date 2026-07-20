---
title: Python bindings for native C libraries
description: Officially documented binding approaches, callback and buffer constraints, build backends, binary-wheel tooling, native dependency distribution, and CPython ABI choices.
topics: [python, c, native-extensions, cython, cffi, ctypes, pybind11, nanobind, swig, packaging, build-backends, setuptools, hatchling, scikit-build-core, meson-python, uv, cmake, meson, wheels, abi3]
checked_at: 2026-07-18
---

# Python Bindings For Native C Libraries

## Layer Model

Binding implementation, native compilation, wheel production, and wheel repair
are separate concerns:

```text
project and build frontend
  uv / build / pip

binding implementation
  CPython C API / Cython / CFFI / ctypes / SWIG / C++ binding framework

native build backend
  setuptools / scikit-build-core + CMake / meson-python + Meson

pure-Python build backend
  Hatchling / uv_build / other PEP 517 backends

wheel matrix
  cibuildwheel

native dependency repair
  auditwheel / delocate / delvewheel
```

No tool in one layer automatically replaces all the other layers.

## Binding Implementations

### CPython C API

**Official guidance:** a C extension can create Python types and call C-library
functions directly through `Python.h`. The interface is CPython-specific;
Python's documentation suggests considering `ctypes` or CFFI when the main need
is calling a C library.

Source: [Extending Python with C or C++](https://docs.python.org/3/extending/extending.html).

This route exposes reference counting, object construction, module/type
definitions, exception state, GIL handling, and destruction directly to the
binding author. It provides maximum control but does not generate ownership or
error-handling policy automatically.

### Cython

**Official guidance:** wrapping existing C libraries is a primary Cython use
case. `cdef extern from` declarations include the real C header in generated C
and let the C compiler check the declarations. Cython itself does not parse the
header, so the binding still maintains matching Cython declarations.

Sources:

- [Interfacing with External C Code](https://cython.readthedocs.io/en/stable/src/userguide/external_C_code.html)
- [Calling C Functions](https://cython.readthedocs.io/en/stable/src/tutorial/external.html)
- [Source Files and Compilation](https://cython.readthedocs.io/en/stable/src/userguide/source_files_and_compilation.html)

Cython translates `.pyx` or compiled pure-Python syntax into C/C++ and then
builds a regular Python extension module. It supports opaque structs, function
pointers, C callbacks, extension types, explicit GIL annotations, and direct
linking with static or shared C libraries.

### CFFI

CFFI distinguishes API from ABI mode and inline from out-of-line preparation.

**Official guidance:** API mode compiles a wrapper and lets the C compiler fill
in layout and declaration details. ABI mode calls an already installed shared
library through libffi. CFFI describes ABI mode as more fragile and slower, and
recommends API mode when compilation is available.

Source: [CFFI Overview](https://cffi.readthedocs.io/en/stable/overview.html).

Out-of-line API mode provides `extern "Python"` callbacks and
`ffi.new_handle()` / `ffi.from_handle()` for passing a Python owner through a C
`void *`. CFFI recommends `extern "Python"` over its older dynamic callback
mechanism because it is faster and avoids libffi callback limitations.

Source: [CFFI callbacks and handles](https://cffi.readthedocs.io/en/stable/using.html#extern-python-new-style-callbacks).

### ctypes

`ctypes` is part of the Python standard library and loads shared libraries at
runtime. It can declare functions, structures, pointers, and callbacks without
compiling a project-specific extension.

The official documentation warns that incorrect declarations or pointer use can
corrupt memory or crash the process. A `CFUNCTYPE` callback object must remain
strongly referenced for as long as C might call it; otherwise the callback may
be garbage-collected and a later C call can crash.

Source: [`ctypes`](https://docs.python.org/3/library/ctypes.html), including
[callback functions](https://docs.python.org/3/library/ctypes.html#callback-functions).

### pybind11 And nanobind

pybind11 and nanobind are C++ binding frameworks. They can wrap a C library
through a C++ adapter, but their native abstractions, type casters, and ownership
model are designed primarily for C++.

Sources:

- [pybind11 documentation](https://pybind11.readthedocs.io/en/stable/)
- [nanobind documentation](https://nanobind.readthedocs.io/en/latest/)
- [nanobind packaging](https://nanobind.readthedocs.io/en/latest/packaging.html)

Using either framework for a pure C API introduces a C++ compilation and adapter
layer. That can be useful when C++ RAII or an existing C++ object model is part
of the surrounding code; it is not required merely because the dependency is C.

### SWIG

SWIG generates wrappers for C and C++ APIs and supports Python among many target
languages. It remains useful for broad mechanical exposure of an existing API,
with custom typemaps available for ownership and conversions.

Source: [SWIG and Python](https://www.swig.org/Doc4.3/Python.html).

Generated coverage does not remove the need to define Python-facing ownership,
callback, exception, and object-model semantics.

## Callback, GIL, And Exception Boundaries

Python objects may only be manipulated while the relevant Python thread state
and GIL requirements are satisfied. Cython callbacks invoked without the GIL can
declare `with gil`; CFFI's callback machinery enters Python through its generated
bridge.

Sources:

- [Cython and external callbacks](https://cython.readthedocs.io/en/stable/src/userguide/external_C_code.html#acquiring-and-releasing-the-gil)
- [CPython thread state and GIL](https://docs.python.org/3/c-api/init.html#thread-state-and-the-global-interpreter-lock)

A Python exception cannot unwind through an ordinary C callback ABI. CFFI
documents that an exception in `extern "Python"` is converted to a configured
error result and optionally handled by `onerror`; it is not propagated through
C. Equivalent handwritten or Cython bindings must establish their own C return
code and pending-error policy.

**Methodological synthesis:** for a synchronous C API that calls back before the
outer Python-to-C call returns, a reusable error boundary is:

1. catch or fetch the Python exception in the callback;
2. store it on the binding-owned context;
3. return an allowed C error code;
4. restore and raise the Python exception after the outer C call returns.

The owner of a callback function pointer and any `void *user_data` handle must
outlive every possible callback. Destruction must first prevent future native
callbacks and then release Python references.

## Buffer Lifetime

The CPython Buffer Protocol can provide a pointer into an existing exporter
without copying. A successful `PyObject_GetBuffer()` must be paired exactly once
with `PyBuffer_Release()`, and `Py_buffer` holds a strong reference to the
exporter while the view is active.

Source: [Buffer Protocol](https://docs.python.org/3/c-api/buffer.html).

**Methodological synthesis:**

- if C reads the pointer only during the current call, a contiguous borrowed
  buffer can be sufficient;
- if C retains the pointer after return, the binding must copy the data or keep
  the exporter and buffer view alive until C signals completion;
- callback pointers are only safe after callback return when the C API provides
  an explicit retained/reference-counted lifetime;
- a binding framework does not make a zero-copy design correct automatically.

## Build Frontends, Backends, And Official Scope

The PEP 517 model separates the command a developer runs from the backend that
turns a source tree into an sdist or wheel. `uv build` acts as a build frontend:
it selects a Python interpreter and invokes the backend declared in
`[build-system]`; the backend controls the build contents and filenames.

Source: [uv building distributions](https://docs.astral.sh/uv/concepts/projects/build/).

`uv_build` is a separate backend shipped by Astral. Its current documentation
states that it supports pure Python code only and that a different backend is
required for extension modules. `uv` can invoke other PEP 517 backends and does
not require a project to use `uv_build`.

Source: [uv build backend](https://docs.astral.sh/uv/concepts/build-backend/).

The Python Packaging User Guide explicitly avoids making a blanket build-backend
recommendation. Its extension-module section enumerates build systems with
dedicated compiled-language support: setuptools for C and C++, meson-python for
languages supported by Meson, scikit-build-core for languages supported by
CMake, and Maturin for Rust. The same guide lists Hatchling among popular
pure-Python backends.

Source: [PyPA tool recommendations](https://packaging.python.org/en/latest/guides/tool-recommendations/#build-backends).

The PyPA packaging tutorial uses Hatchling by default for its simple example,
while stating that backend capabilities differ, including extension-module
support. This tutorial default is not presented as a universal backend ranking.

Source: [PyPA packaging tutorial](https://packaging.python.org/en/latest/tutorials/packaging-projects/#choosing-a-build-backend).

Astral's current `uv init` documentation has built-in extension-project
templates for Maturin and scikit-build-core. It describes the latter template as
covering C, C++, Fortran, and Cython and generating CMake configuration. This is
the scope of `uv init` scaffolding; `uv build` itself can invoke any conforming
PEP 517 backend.

Source: [uv projects with extension modules](https://docs.astral.sh/uv/concepts/projects/init/#projects-with-extension-modules).

## Native Build Backends

These backends occupy the same PEP 517 layer but delegate native compilation in
different ways:

| Backend | Native build description | Documented Cython path | Additional build description |
|---|---|---|---|
| setuptools | `Extension` objects are compiled and linked by setuptools | A `.pyx` source is compiled when Cython is installed; otherwise an equivalent generated `.c` or `.cpp` may be used | `pyproject.toml`; optional `setup.py` for programmatic configuration |
| scikit-build-core | CMake configures and builds targets; installed CMake targets are collected into the wheel | Current getting-started example declares Cython and `cython-cmake` as build requirements | `CMakeLists.txt` |
| meson-python | Meson configures and builds targets; installed Meson targets are collected into the wheel | Meson has native Cython language support and accepts `.pyx` sources in Python extension targets | `meson.build` |
| Hatchling with a build hook | Hatchling runs a plugin hook which produces native artifacts for inclusion | Hatch documents `hatch-cython` and scikit-build-core as known third-party hooks | Hook-specific configuration or code |

The table describes official integration mechanisms, not relative quality or a
project-specific choice.

### setuptools

setuptools can compile C and C++ extension modules from declared sources,
include directories, macros, libraries, library directories, and linker flags.
When a declared source is Cython `.pyx`, setuptools uses Cython if it is present
in the isolated build environment; otherwise it looks for an equivalent
generated C or C++ source. Cython can be declared in `[build-system].requires`,
or generated C can be distributed with the source package.

Source: [setuptools extension modules](https://setuptools.pypa.io/en/latest/userguide/ext_modules.html).

Setuptools supports declaring extension modules in `pyproject.toml`, but its
current documentation marks the declarative `ext-modules` table experimental.
An optional `setup.py` remains a supported configuration file when programmatic
configuration is required.

Direct command-line invocations such as `python setup.py install`, `sdist`, or
`bdist_wheel` are deprecated. Setuptools itself, and `setup.py` as a
configuration file, are not deprecated; modern frontends invoke
`setuptools.build_meta` through `pyproject.toml`.

Sources:

- [setuptools `pyproject.toml` configuration](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html)
- [PyPA: Is `setup.py` deprecated?](https://packaging.python.org/en/latest/discussions/setup-py-deprecated/)

### scikit-build-core And CMake

scikit-build-core is a PEP 517 build backend that uses CMake to build Python
modules. It is a ground-up rewrite of classic scikit-build and does not depend
on setuptools, distutils, or wheel. Its documented features include automatic
CMake/Ninja provisioning when required, cross-compilation support, editable
installs, reproducible sdist generation, and Limited API/Stable ABI wheel
configuration.

Source: [scikit-build-core](https://scikit-build-core.readthedocs.io/en/latest/).

Its native `pyproject.toml` backend is `scikit_build_core.build`; a project also
provides CMake targets and install rules in `CMakeLists.txt`. The current Cython
starter declares `scikit-build-core`, `cython`, and the separate `cython-cmake`
package as build requirements. scikit-build-core does not itself replace the
binding generator.

Sources:

- [scikit-build-core getting started](https://scikit-build-core.readthedocs.io/en/latest/guide/getting_started.html)
- [scikit-build-core migration guide](https://scikit-build-core.readthedocs.io/en/latest/guide/migration_guide.html#cmake-changes)

scikit-build-core also publishes optional integration plugins for setuptools
and Hatchling. Those integrations are separate from using its native PEP 517
backend directly.

Source: [scikit-build-core backend overview](https://scikit-build-core.readthedocs.io/en/latest/).

### meson-python And Meson

meson-python implements Python build hooks for Meson projects and can build
extensions written in C, C++, Cython, Rust, and other Meson-supported languages.
The build backend is `mesonpy`, and the native project is described by
`meson.build`.

Source: [meson-python](https://mesonbuild.com/meson-python/).

Meson has native Cython language support: a project can declare `cython` as a
language and pass `.pyx` sources directly to its Python `extension_module()`
target. Meson does not interpret setuptools/distutils directives embedded in a
Cython source file; equivalent options must be expressed in Meson configuration.

Sources:

- [Meson Cython support](https://mesonbuild.com/Cython.html)
- [Meson Python module](https://mesonbuild.com/Python-module.html)

meson-python documents both static and bundled-shared-library models for native
subprojects. A static library can be linked directly into an extension; a shared
library requires installation placement and loader-path handling. Its current
documentation describes static linking as avoiding RPATH and DLL-search-path
adjustments.

Source: [meson-python shared libraries](https://mesonbuild.com/meson-python/how-to-guides/shared-libraries.html).

### Hatchling Build Hooks

Hatchling supports build-hook plugins which run before and after selected build
targets and can add generated artifacts to a wheel. Hatch's official plugin
reference lists `hatch-cython` and scikit-build-core as known third-party build
hooks for Cython and CMake extension modules respectively; these are not native
compilers built into Hatchling itself.

Source: [Hatch build-hook plugins](https://hatch.pypa.io/latest/plugins/build-hook/reference/).

### Build Isolation And Dependency Constraints

PEP 517 frontends normally create an isolated environment and install the
requirements declared in `[build-system].requires`. A project runtime lock and
the backend's isolated build requirements are separate inputs.

`uv build` supports build-constraint files, including hash enforcement, for
constraining the backend and other isolated build requirements. Its
documentation states that `uv build` invokes the selected backend rather than
deciding the backend's file contents or output naming.

Sources:

- [uv build isolation](https://docs.astral.sh/uv/concepts/projects/config/#build-isolation)
- [uv building distributions](https://docs.astral.sh/uv/concepts/projects/build/#build-constraints)

## Wheels And Source Distributions

PyPA distinguishes source distributions from wheels. A pure Python project can
usually publish one generic wheel; a compiled extension normally requires a
wheel for each supported interpreter ABI, operating system, and CPU
architecture, unless a Stable ABI removes the CPython-minor dimension.

Sources:

- [The Packaging Flow](https://packaging.python.org/en/latest/flow/)
- [Package Formats](https://packaging.python.org/en/latest/discussions/package-formats/)
- [Packaging Binary Extensions](https://packaging.python.org/en/latest/guides/packaging-binary-extensions/)

PyPA recommends publishing the source used to build a binary extension in
addition to binary wheels. This allows unsupported platforms and downstream
distributions to build from source.

`cibuildwheel` builds and tests wheels across Python versions and platforms. Its
default repair stage uses auditwheel on Linux and delocate on macOS; Windows
projects can configure delvewheel when DLL bundling or loader repair is needed.

Sources:

- [cibuildwheel](https://cibuildwheel.pypa.io/en/stable/)
- [repair-wheel-command](https://cibuildwheel.pypa.io/en/stable/options/#repair-wheel-command)
- [auditwheel](https://github.com/pypa/auditwheel)
- [delocate](https://github.com/matthew-brett/delocate)
- [delvewheel](https://github.com/adang1345/delvewheel)

auditwheel documents that it cannot automatically discover libraries loaded at
runtime through `dlopen`, `ctypes`, or CFFI ABI mode. Such dependencies require
explicit packaging work. Source: [auditwheel limitations](https://github.com/pypa/auditwheel#limitations).

## Native Dependency Distribution

Three recurring distribution models have different compatibility ownership:

| Model | Installation property | Maintenance property |
|---|---|---|
| Static library linked into extension | Self-contained native module | Rebuild every wheel to deliver a native-library security update |
| Shared library bundled in wheel | Self-contained wheel after loader/RPATH repair | Preserve an additional native artifact and its loader metadata |
| Runtime system-library dependency | Smaller project artifact | User environment supplies a compatible library and security updates |

All models remain platform-specific when they contain or depend on native
machine code. Bundling or statically linking a third-party library also carries
that library's license-notice and redistribution obligations.

## CPython Limited API And Stable ABI

The CPython Limited API is a subset of the C API. Extensions restricted to it
can use the Stable ABI and an `abi3` wheel tag to run across multiple CPython
minor versions on the same platform.

Official limitations include:

- Stable ABI does not remove the OS and CPU dimensions;
- it does not guarantee another C library's ABI;
- Limited API calls can be slower than version-specific inlined or macro APIs;
- extensions still need testing on every claimed Python version;
- behavioral compatibility is broader than symbol/link compatibility.

Source: [CPython C API Stability](https://docs.python.org/3/c-api/stable.html).

Cython supports Limited API compilation from Cython 3.1, describes its support
as close to feature-complete, and documents remaining missing features and
forward-compatibility caveats. It states that alternative Python implementations
such as PyPy and GraalPy do not use CPython's Limited API path.

Source: [Cython Limited API and Stable ABI](https://cython.readthedocs.io/en/stable/src/userguide/limited_api.html).

An `abi3` tag is a packaging claim, not proof that an extension used only Stable
ABI symbols. Build configuration and wheel tagging must agree.

## Framework-Neutral Source Shape

**Methodological synthesis:** mature native packages commonly separate the
Python import package from private native sources, while only adding a CMake,
Meson, or vendor directory when the selected build actually needs it:

```text
project/
├── pyproject.toml
├── src/
│   └── package/
│       ├── __init__.py
│       ├── _core.pyx | _core.c | _core.cpp | build_ffi.py
│       └── optional Python modules and type information
├── tests/
├── CMakeLists.txt | meson.build     # only for that native backend
└── vendor/ | third_party/           # only when source is bundled
```

This layout does not require a separate public Python facade. Some packages
expose high-level native types directly; others keep a stable Python facade over
one or more private native backends.
