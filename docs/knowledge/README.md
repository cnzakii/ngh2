---
title: ngh2 engineering knowledge
description: Source-based reference material for HTTP/2, libnghttp2, Python native extensions, packaging, and engineering conventions.
topics: [index]
---

# ngh2 Engineering Knowledge

This collection is a source-based reference library. It does not contain
product code, audits, implementation plans, benchmark results, release
decisions, or project recommendations.

## Evidence Labels

- **Normative source:** applicable RFC and BCP requirements and updates.
- **Authoritative registry:** current IANA names and registration metadata.
- **Official guidance:** documentation from a language, library, or tool owner.
- **Observed practice:** behavior or structure in an immutable source revision
  or exact release. It is not a universal requirement.
- **Methodological synthesis:** a conclusion derived across sources.

## Contents

- Protocol:
  [libnghttp2 architecture and capability boundary](protocol/libnghttp2.md)
- Python native extensions:
  [binding and packaging tooling](python-native/binding-tooling.md) and
  [version-pinned reference bindings](python-native/reference-bindings.md)
- Engineering:
  [Python and Cython language and API conventions](engineering/language-api.md)
  and [dependency, vendoring, and license evidence](engineering/dependency-licenses.md)

## Freshness

`checked_at` means every external factual claim in a document was reviewed on
that date. Stable specifications and pinned source observations remain tied to
their cited version; mutable claims must be checked live when they matter.
