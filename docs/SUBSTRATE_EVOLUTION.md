# Substrate Evolution Governance
## Epistemic Tier: T0
## Scope: crates/constitutional-substrate/

The constitutional substrate must remain smaller than the governance layer. Ontology
pressure must not migrate downward into primitives. This document is the constitutional
gate for all changes to the Rust substrate.

---

## Admission Rules

### RULE-01 — Provenance Review Required
Every primitive addition must link to at least one T0–T2 source document in TRACEABILITY.md
before the PR is mergeable. A primitive without provenance linkage is a migration rule
violation. Absence of provenance at T0 is constitutional grounds for PR rejection.

### RULE-02 — Ontology Registration Required
Every new type or constant exported from `constitutional-substrate` must appear in
docs/ONTOLOGY.md with a canonical definition before it may be referenced from any
other module. The ontology entry precedes the implementation, not the reverse.
Rationale: prevents semantic aliases from proliferating across the codebase.

### RULE-03 — Serialization Version Increment Required
Any change to the wire format of an existing type requires a `minor` version increment
in `ArchiveVersion` if backward-compatible, or a `major` version increment if breaking.
No silent format changes are permitted. Version bumps are permanent.
Serialization canon decisions are effectively irreversible once replay archives accumulate.

### RULE-04 — Deprecated Primitives Remain Replay-Decodable
Deprecated types may not be removed from the codebase if any v1.x archive could contain
them. A deprecated type must remain decodable (from_bytes must still work) until a
major version boundary is declared. Deprecation is not deletion.

### RULE-05 — Entropy Impact Must Be Documented
Every primitive that participates in entropy measurement or threshold enforcement must
document its entropy impact in the PR description:
- Does this primitive increase system entropy headroom (good) or compress it (risk)?
- What is the worst-case entropy contribution if the primitive misbehaves?
- Is the entropy impact bounded (computable) or unbounded (disqualifying)?

### RULE-06 — Interoperability Proof Required for Admission
Every new primitive must include:
1. A serialization roundtrip test (to_bytes → from_bytes → assert_eq)
2. A serialization stability test (two calls → identical bytes)
3. A boundary/invariant test (invalid input → correct rejection)
The three tests constitute the minimum interoperability proof. Primitives without all
three tests are not admitted.

---

## Evolution History

| Version | Date | Change | Admission Reviewer |
|---------|------|--------|-------------------|
| 1.0.0 | 2026-05-19 | Initial constitutional release — 8 primitive types, 5 modules, 50 tests | ChatGPT adversarial audit CONFIDENCE 0.98 |

---

## Substrate Size Budget

The substrate's complexity budget is intentionally constrained:

| Metric | Limit | Rationale |
|--------|-------|-----------|
| Modules | ≤ 8 | Beyond 8, governance logic is leaking into the substrate |
| Exported types | ≤ 16 | Type proliferation = ontology inflation |
| Lines of non-test code | ≤ 800 | Substrate must be auditable in one sitting |
| External dependencies | 0 | Constitutional minimalism |

If any limit is approached, a constitutional review is required before adding more.

---

## What Must NOT Live in the Substrate

The following are governance-layer concerns and must remain in the TypeScript/Python layers:

- Business rules (VCG error thresholds, PGCS pass criteria)
- Ralph Loop cycle logic
- Telemetry aggregation
- Holonic scale reasoning
- Ontology interpretation
- Invariant semantics (invariant-checker.ts owns this)

The substrate enforces invariants. It does not define what the invariants mean.
