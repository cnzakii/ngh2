---
name: ngh2-implementation
description: Implement requested changes in the ngh2 Python package, Cython/libnghttp2 binding, tests, packaging, CI, or project documentation. Use when creating, modifying, fixing, refactoring, replacing, or migrating ngh2 behavior or repository files. Do not use for read-only audits or factual research.
---

# ngh2 Implementation

Deliver the smallest complete change that satisfies the request and preserves
the repository boundaries in `AGENTS.md`.

## Workflow

1. Read `AGENTS.md` and every affected file before editing. Inspect callers,
   tests, public exports, type information, and configuration that share the
   changed contract.
2. Establish the requested outcome and explicit non-goals. Do not add adjacent
   features, compatibility layers, reports, or tooling without a current need.
3. Trace the owning layer before choosing the fix. Keep HTTP/2 protocol state
   in libnghttp2, transport/runtime ownership outside the package, and
   Python-facing vocabulary natural for Python.
4. Use `ngh2-knowledge` when a decision depends on protocol requirements,
   libnghttp2 behavior, established tooling behavior, packaging rules, native
   extension practice, or licenses. Separate source facts from project choices.
5. Implement the smallest coherent design. Update all affected layers required
   for correctness, including Python exports, type information, and tests when
   their contract changes.
6. Add the smallest check that would fail for a changed behavior. Match evidence
   to the claim: focused tests for behavior, interoperability for real peers,
   fuzzing for hostile input/state exploration, and benchmarks for performance.
7. Run focused checks first, then the broader gate required by `AGENTS.md`.
   Read fresh output before claiming success.
8. Review the final changes with `ngh2-audit`. Address blocking findings through
   this workflow and rerun the affected checks.

## Implementation Boundaries

- Keep socket, TLS, async runtime, client, server, and connection-pool ownership
  outside the Sans-I/O binding.
- Do not reimplement behavior already owned by libnghttp2 without demonstrated
  need.
- Prefer existing language features and mature dependencies over local
  machinery.
- Replace incorrect pre-release APIs directly. Do not retain aliases, shims, or
  duplicate implementations unless compatibility is explicitly required.
- Do not invent protocol behavior, resource limits, safety claims, or
  performance claims without evidence.
- Do not add tests that only restate constants, types, or implementation
  spelling without protecting observable behavior.

Stop and report the conflict instead of patching around missing authority,
unclear ownership, or an environment that cannot verify the requested result.
