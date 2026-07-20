---
title: Python and Cython language and API conventions
description: Official Python and Cython naming, visibility, source-file, lifecycle, documentation, comment, and typing conventions for native extension modules.
topics: [python, cython, api, naming, visibility, lifecycle, documentation, comments, docstrings, typing]
checked_at: 2026-07-19
---

# Python And Cython Language And API Conventions

This document records official language and tooling behavior plus clearly
labelled synthesis. It does not prescribe a project layout, formatter, public
API, or comment policy.

## Python Naming And Public Interfaces

**Official guidance:** PEP 8 prioritizes consistency within a project or module
when strict adherence would reduce readability or conflict with established
code.

- Packages and modules use short lowercase names. Module underscores can aid
  readability; package underscores are discouraged.
- Classes use `CapWords`. Functions, methods, and variables use lowercase words
  separated by underscores. Module constants use uppercase words separated by
  underscores.
- Error exception classes normally end in `Error` when they represent errors.
- A single leading underscore marks a non-public name by convention. A module
  can enumerate its public interface with `__all__`.
- Imported names are implementation details unless documented or deliberately
  re-exported.

Source: [PEP 8](https://peps.python.org/pep-0008/), including
[naming](https://peps.python.org/pep-0008/#naming-conventions) and
[public interfaces](https://peps.python.org/pep-0008/#public-and-internal-interfaces).

The typing specification applies additional static-interface rules. In a typed
package, underscore-prefixed modules and symbols are private by default;
`__all__` and explicit re-export forms can make names public to type checkers.
Source: [typing specification, library interface](https://typing.python.org/en/latest/spec/distributing.html#library-interface-public-and-private-symbols).

## Docstrings And Ordinary Comments

**Official guidance:** PEP 257 defines docstrings for public modules, functions,
classes, and methods. A one-line docstring states an effect rather than
repeating the signature. A multi-line docstring has a summary line, a blank
line, and further description. Function documentation can cover arguments,
return values, side effects, exceptions, and calling restrictions.

Source: [PEP 257](https://peps.python.org/pep-0257/).

PEP 8 distinguishes block comments, inline comments, and docstrings:

- block comments apply to the following code and are indented with it;
- inline comments are separated from code by at least two spaces and are used
  sparingly;
- comments that contradict the code are worse than no comments and must be kept
  current;
- comments should be complete sentences when they are phrases or sentences;
- documentation strings follow PEP 257 rather than ordinary comment syntax.

Source: [PEP 8, Comments](https://peps.python.org/pep-0008/#comments).

**Methodological synthesis:** a repository-specific marker inside a comment is
not a Python or Cython convention merely because both languages accept the
comment syntax. Such a marker is a project or tool protocol and needs a current
consumer to have operational meaning.

## Cython Source Roles

**Official guidance:** Cython distinguishes three source roles:

| Suffix | Role |
|---|---|
| `.py` or `.pyx` | implementation compiled by Cython |
| `.pxd` | declarations shared with Cython modules, analogous to a C header |
| `.pxi` | text included into another Cython source file |

Extended Cython syntax such as `cdef` requires `.pyx`; pure Python syntax can be
compiled from `.py`. A same-named `.pxd` is processed before its `.pyx` or `.py`
implementation.

Sources:

- [Cython language basics, file types](https://cython.readthedocs.io/en/3.1.x/src/userguide/language_basics.html#cython-file-types)
- [Cython `.pxd` files](https://cython.readthedocs.io/en/3.1.x/src/tutorial/pxd_files.html)

## Cython Callable And Attribute Visibility

**Official guidance:** a `def` function uses the Python calling convention and
is callable from interpreted Python. A `cdef` function uses a C calling
convention and is not directly callable from interpreted Python. A `cpdef`
function provides both Python and Cython call paths and can be overridden from
Python where documented by Cython.

Source: [Cython, Python functions versus C functions](https://cython.readthedocs.io/en/3.1.x/src/userguide/language_basics.html#python-functions-vs-c-functions).

Attributes of a Cython extension type are not Python-accessible by default.
`public` makes a supported attribute readable and writable through Python;
`readonly` makes it readable. Direct Cython access is a separate boundary.

Source: [Cython extension-type attributes](https://cython.readthedocs.io/en/3.1.x/src/userguide/extension_types.html#static-attributes).

**Methodological synthesis:** Python visibility, Cython compilation visibility,
and C-library symbol visibility are separate surfaces. Exposing a name at one
surface does not automatically expose or document it at the others.

## Cython Extension-Type State And Initialization

**Official guidance:** extension-type attributes are stored in the object's C
structure and must be declared at compile time. In a `.pyx` extension type,
plain `cdef` declares an internal field, `cdef readonly` exposes read-only
Python access, and `cdef public` exposes read-write Python access. Attribute
annotations are the corresponding syntax for Cython's pure-Python mode; they
are not required alongside `cdef` declarations in `.pyx` files.

Object allocation clears C fields and initializes Python-object fields before
`__cinit__()`. Cython guarantees that `__cinit__()` runs exactly once, including
when construction goes through the type's `__new__()` directly. In contrast,
direct `__new__()` calls and subclasses that omit `super().__init__()` can skip
the base `__init__()`. Cython therefore identifies `__cinit__()` as the place
for basic C-level safety initialization, potentially including native resources
owned by the instance. `__dealloc__()` is the corresponding native cleanup
hook and should avoid operations on Python state that may already be partially
destroyed.

Sources:

- [Cython extension-type attributes](https://cython.readthedocs.io/en/3.1.x/src/userguide/extension_types.html#static-attributes)
- [Cython extension-type initialization and finalization](https://cython.readthedocs.io/en/3.1.x/src/userguide/special_methods.html#initialisation-methods-cinit-and-init)

## External C Declarations

**Official guidance:** `cdef extern from "header.h"` places an include of the
real header into generated C, suppresses duplicate generated declarations, and
treats declarations in the block as external. Large structures may be declared
with only the fields used by the binding because the C compiler uses the full
definition from the included header.

For many external declarations, Cython documents putting them in a `.pxd`
namespace and `cimport`ing that namespace from `.pyx`. This supports reuse,
namespacing, and renaming without runtime lookup.

Source: [Cython, interfacing with external C code](https://cython.readthedocs.io/en/3.1.x/src/userguide/external_C_code.html).

The Cython declarations must match the relevant C declaration form closely
enough for generated references to be valid. Cython does not replace the C
compiler or the upstream header as the native ABI authority.

## Compiler-Directive Comments

**Official guidance:** a header comment such as
`# cython: language_level=3, boundscheck=False` is a compiler directive, not an
ordinary explanatory comment. It must appear before code, although other
comments or whitespace can precede it. Directives can also be supplied through
the build command or locally through decorators and context managers; the
documented precedence rules determine which value applies.

Disabling checks such as `boundscheck` changes runtime safety behavior and can
turn an indexing error into memory corruption. Directive spelling therefore
has executable consequences.

Source: [Cython compiler directives](https://cython.readthedocs.io/en/stable/src/userguide/source_files_and_compilation.html#compiler-directives).

## Type Information For Extension Modules

The typing specification states that stub files are the way to provide static
type information for extension modules. A `.pyi` file is valid Python syntax
with restricted bodies and describes the public interface without executing.
A package that ships type information uses a `py.typed` marker; the marker
applies recursively to the package.

Stubs targeting Python 3.10 and later must remain parseable by the supported
Python versions when portability across type checkers is required. If a stub is
found, a type checker uses it instead of reading the runtime extension module.

Source: [typing specification, distributing type information](https://typing.python.org/en/latest/spec/distributing.html).

## Synthesis Boundaries

The following conclusions are methodological synthesis:

- Python naming and documentation conventions describe caller-facing
  readability; they do not choose the correct protocol abstraction.
- `.pxd` separation becomes useful when declarations are shared or numerous;
  file count alone is not evidence that a separate declaration module is
  required.
- An underscore reduces accidental public exposure but does not enforce native
  pointer, callback, buffer, or GIL ownership.
- Comments and docstrings preserve reasoning and contracts only when their
  audience and governed code are identifiable. They are not a substitute for a
  focused test or the upstream C header.
