---
name: ngh2-audit
description: Review ngh2 code, diffs, APIs, architecture, tests, Cython/libnghttp2 boundaries, packaging, documentation, or release surfaces for evidence-backed defects and unnecessary complexity. Use for read-only audits and after implementation; never modify files.
---

# ngh2 Audit

Review the current artifact independently and remain read-only.

## Workflow

1. Read `AGENTS.md`, the requested scope, affected files, applicable tests, and
   the public contract under review.
2. Inspect current checkout facts instead of trusting historical reports or the
   implementation author's conclusion.
3. Select only relevant lenses: protocol behavior, state/data ownership,
   Python/native boundaries, public API usability, resource and callback
   safety, tests, packaging, naming, or maintenance cost.
4. Use `ngh2-knowledge` when a finding depends on an external fact. Treat
   protocol sources, official guidance, pinned implementation observations, and
   engineering judgment as different evidence classes.
5. Challenge new surface and machinery:
   - identify the current caller, contract, failure, or source that requires it;
   - identify which layer owns its state, validation, errors, and lifecycle;
   - check whether an existing direct path provides the same behavior;
   - require evidence that matches correctness, interoperability, safety, or
     performance claims.
6. For a public API difference from a mature reference, state the observable
   reference boundary and the caller action enabled by the difference. Report a
   defect when consumers must reconstruct hidden protocol state or no consumer
   action depends on the added surface.
7. Report findings first, ordered by demonstrated consequence. Then list only
   genuine open questions or evidence gaps.

## Finding Standard

Report a finding only when all four are present:

1. a precise current artifact fact;
2. a governing source, explicit contract, reproduction, or clearly labelled
   engineering judgment;
3. a concrete correctness, interoperability, usability, safety, performance, or
   maintenance consequence;
4. the smallest credible resolution direction.

Set severity from consequence and likelihood. Reserve high severity for
plausible contract failures, interoperability breaks, state/data loss,
exploitable boundaries, or release blockers.

Do not report style preferences without a consequence, hypothetical risks
without a present boundary, unmeasured performance concerns, missing
abstractions where direct code is clear, or compatibility concerns for an
unreleased surface unless compatibility is required.

If no finding meets the standard, say so clearly and identify only residual
verification gaps.
