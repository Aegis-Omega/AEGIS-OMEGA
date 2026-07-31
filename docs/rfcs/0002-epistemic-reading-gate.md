# RFC 0002 — Epistemic Reading Gate and Holonic Reconciliation Protocol

Status: Proposed normative analysis protocol  
Date: 2026-07-31  
Scope: repository analysis, review, reconciliation, refactoring, deletion, supersession, and authority claims

## Decision

No AEGIS artifact may be interpreted, patched, deleted, promoted, or declared authoritative before it is located in the current organism, authority order, temporal lineage, and evidentiary role.

This protocol turns `START_HERE.md` and `REPO_MAP.md` from passive indexes into a mandatory anti-hallucination gate.

## Mandatory authority order

Every analysis must inspect evidence in this order:

1. live system and observed runtime behavior;
2. wired code and active deployment path;
3. tests and CI that actually execute the relevant path;
4. `START_HERE.md`;
5. `REPO_MAP.md` and current repository topology audit;
6. old documentation, dormant claims, mythology, design intent, and historical artifacts.

A lower layer may preserve intent, provenance, failure knowledge, or semantic ancestry. It may not silently override a higher layer.

## Reading-gate preflight

Before analysis of any file, module, test, workflow, schema, PR, receipt, issue, or asset, the analyst MUST:

1. identify the exact artifact and inspected commit or deployment;
2. determine its current organism status;
3. state the authority chain used for interpretation;
4. separate execution truth, verification truth, and mythic/provenance truth;
5. identify known and unresolved semantic ancestors;
6. state what cannot be inferred from comments or old documents;
7. list current consumers, entry points, tests, CI jobs, deployment surfaces, and durable records;
8. emit a reconciliation record before recommending mutation or deletion.

Failure to complete the preflight makes the analysis non-admissible.

## Organism status

Each artifact receives exactly one current structural status for the inspected state:

- `WIRED`: imported, invoked, built, deployed, or otherwise part of a demonstrated active path;
- `TESTED_ONLY`: executable code whose demonstrated consumers are tests or model checks only;
- `DORMANT`: present but no current importer, entry point, CI path, deployment, or live consumer has been demonstrated;
- `BROKEN`: intended path exists but cannot currently compile, start, validate, or complete its contract;
- `DEAD_DUP`: duplicate or orphaned representation with no demonstrated unique runtime role.

`DEAD_DUP` is not deletion authorization. It only removes current execution authority.

## Three truth dimensions

Every claim MUST be classified independently across these dimensions.

### Execution truth

What does the system actually execute, admit, deny, persist, deploy, or expose?

Evidence examples: live probes, deployment receipts, entry points, imports, calls, durable state transitions, provider logs.

### Verification truth

What do tests, CI, formal models, replay packages, or independent verifiers actually establish?

A passing unit test does not prove production reachability. A model-checking result does not prove implementation refinement unless that boundary is separately evidenced.

### Mythic and provenance truth

Why was the artifact created, what problem was it trying to solve, which conceptual lineage shaped it, and what failure or design knowledge does it preserve?

Mythic/provenance truth has evidentiary value but no automatic execution or mutation authority.

## Semantic ancestry check

Each important artifact or claim MUST be evaluated against the following ancestry classes:

- `MYTHOS_DESCENDANT`: descendant of the Full Mythos model system card or its recorded principles;
- `FABLE5_RESET_DESCENDANT`: descendant of the Fable-5 epistemic repository reset;
- `ROOT_MAP_DESCENDANT`: descendant of `REPO_MAP.md`, `START_HERE.md`, or later topology reconciliation;
- `INDEPENDENT_INTERVENTION`: later work with a separate lineage;
- `RESET_REGRESSION`: later work that ignored, bypassed, or contradicted the epistemic reset;
- `UNKNOWN`: insufficient evidence.

Ancestry may be Git-based, semantic, operational, or operator-attested. These forms MUST remain distinct.

## Authority and supersession are multidimensional

Supersession MUST identify its dimension:

- `SUPERSEDE_EXECUTION`;
- `SUPERSEDE_CLAIM`;
- `SUPERSEDE_REPRESENTATION`;
- `SUPERSEDE_AUTHORITY`.

A newer implementation may supersede execution while preserving the older artifact as provenance or failure evidence. Semantic ancestry is not Git ancestry. Historical value is not current authority.

## Allowed dispositions

Final recommendations MUST use one or more explicit dispositions:

- `KEEP_AUTHORITATIVE`;
- `KEEP_PROVENANCE`;
- `KEEP_FAILURE_EVIDENCE`;
- `SUPERSEDE_EXECUTION`;
- `SUPERSEDE_CLAIM`;
- `SUPERSEDE_REPRESENTATION`;
- `SUPERSEDE_AUTHORITY`;
- `DELETE_BYTE_DUPLICATE_ONLY`;
- `QUARANTINE_BROKEN`.

Deletion is admissible only after confirming byte duplication or absence of unique execution, provenance, semantic, historical, or failure evidence.

## Reconciliation record requirement

The result of analysis is not an informal comment. It is a structured reconciliation record conforming to `schemas/reconciliation-record.v1.schema.json`.

At minimum the record binds:

- artifact identity and inspected state;
- observed behavior;
- organism status;
- authority chain;
- three truth dimensions;
- semantic ancestry and confidence;
- temporal voice;
- unique evidence and failure knowledge;
- conflicts and supersession dimensions;
- current authority;
- recommended disposition;
- required tests and unresolved questions;
- receipt state.

## Gate-specific four-layer analysis

For governance, admission, mutation, routing, policy, and verifier artifacts, analysis MUST cover:

1. **Runtime role** — what the artifact demonstrably intercepts, permits, denies, mutates, or records;
2. **Test authority** — which behaviors are verified and whether those tests exercise the live path;
3. **Epistemic alignment** — whether interpretation follows the root authority order;
4. **Mythos alignment** — whether the intervention reconstructs the organism before acting on it.

A component can be technically wired while epistemically mispositioned. That conflict must be recorded, not flattened.

## Invariant

Reconciliation may change execution, claim, representation, or authority status. It MUST NOT erase temporal voice, semantic ancestry, evidence, or unique failure knowledge.

## Canonical operating rule

> Do not analyze an artifact until it has been located in the living organism, authority order, temporal origin, and evidentiary role.
