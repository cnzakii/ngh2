---
title: User-facing technical documentation
description: Source-based distinctions between project summaries, tutorials, how-to guides, reference, explanation, procedures, and executable examples.
topics: [documentation, project-description, readme, tutorials, how-to, reference, explanation, procedures, examples]
checked_at: 2026-07-24
---

# User-Facing Technical Documentation

This document records official guidance and clearly labelled methodological
synthesis about user-facing technical documentation. It does not define a site
map, select a documentation tool, or make project-specific content decisions.

## Project Summary And Full Description

**Official specification:** Python project metadata separates a one-line
`project.description`, which maps to the core metadata `Summary`, from
`project.readme`, which supplies the full `Description` and its content type.
Tools may reject a summary that contains multiple lines.

Source:
[PyPA `pyproject.toml` specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/#description).

**Methodological synthesis:** the summary and full description are separate
reader surfaces. A summary identifies the package in one line. A full
description has room to establish audience, scope, constraints, and a path to a
first useful result. This distinction does not determine the wording or length
of either surface.

## Four Documentation Needs

**Official framework:** Diátaxis distinguishes documentation by the user need
it serves:

| Mode | User need | Defining property |
|---|---|---|
| Tutorial | Acquire skill | A guided, practical learning experience whose author is responsible for the learner's progress and success |
| How-to guide | Apply skill | Practical directions for a competent user pursuing a real-world goal |
| Reference | Apply knowledge | Accurate, complete, neutral facts whose structure follows the thing described where possible |
| Explanation | Acquire knowledge | Context and background that connect ideas and answer why |

Source:
[Diátaxis, "Start here"](https://diataxis.fr/start-here/).

Diátaxis presents these modes as a diagnostic guide rather than a required
top-level information architecture. Its workflow explicitly discourages
creating four empty sections in advance and instead describes improving
existing material in small iterations until an appropriate structure emerges.

Source:
[Diátaxis as a guide to work](https://diataxis.fr/how-to-use-diataxis/).

**Methodological synthesis:** a page's mode is determined by the need it
serves, not by its title or directory. Mixing modes can interrupt the user's
task: for example, extended background can break a tutorial's learning
sequence, while procedural directions can make reference less neutral and
scannable.

## Procedures

**Official guidance:** Google's developer documentation style guide defines a
procedure as a sequence of numbered steps for completing a task. Its guidance
includes:

- introduce the procedure with context when the heading alone is insufficient;
- normally use one step for each action;
- place the action first, followed when needed by the command, placeholder
  definitions, explanation, output, and result;
- distinguish optional steps explicitly;
- reference repeated procedures instead of duplicating them; and
- when multiple methods exist, favor the shortest and simplest method and
  organize alternatives separately.

Source:
[Google developer documentation style guide, Procedures](https://developers.google.com/style/procedures).

**Methodological synthesis:** a procedure can be checked as an observable
sequence: prerequisites and starting state are known, each step asks for an
action, and expected output or state changes show whether the reader can
continue. That check does not establish that the underlying behavior is
correct; behavior still requires tests or authoritative product evidence.

## Code Examples

**Official guidance:** Google's code-sample guidance says to introduce a sample
with a sentence or paragraph, follow the applicable language or project style,
and mark omitted code with a comment in the language's syntax. A sample with
omitted code should not be presented as click-to-copy.

Source:
[Google developer documentation style guide, Code samples](https://developers.google.com/style/code-samples).

Python's `doctest` executes text that resembles an interactive Python session
and verifies that its output matches. The standard-library documentation lists
up-to-date docstring examples, regression tests, and tutorial-style executable
documentation as common uses. It also warns that output matching is exact,
which makes unstable ordering and address-bearing representations unsuitable
without normalization or directives.

Source:
[Python `doctest` documentation](https://docs.python.org/3/library/doctest.html).

**Methodological synthesis:** the following properties are independent and
need separate evidence:

- **copyable:** the displayed sample contains everything the reader must enter;
- **runnable:** the sample executes in a stated environment;
- **verified:** an automated check exercises the displayed source or an
  identical maintained source;
- **instructive:** surrounding prose explains the goal, important state
  changes, and result.

Passing an executable-example check establishes only the behavior that the
example asserts. It does not establish that the example teaches the right
concept, covers relevant failure paths, or remains the best entry point.

## API Reference

Diátaxis describes reference as factual, neutral material whose architecture
should reflect the architecture of the subject where possible. Python and
Cython docstring, visibility, and static-interface facts are recorded
separately in
[Python and Cython language and API conventions](language-api.md).

**Methodological synthesis:** generated reference can reduce duplication
between source metadata and rendered pages, but generation is not a completeness
guarantee. Public-symbol selection, signatures, cross-links, rendering, and the
installed extension module still require verification against the actual
Python-facing API.

## Evidence Boundary

The framework and style sources above describe documentation forms and writing
mechanics. They do not establish:

- which pages a particular project needs;
- whether a README, tutorial, example, or reference page is factually correct;
- which static-site generator is suitable; or
- whether documentation leads users to successful real-world use.

Those claims require project evidence, tool verification, and user observation
respectively.
