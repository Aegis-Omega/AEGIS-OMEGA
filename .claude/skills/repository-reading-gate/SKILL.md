---
name: repository-reading-gate
description: mandatory preflight before analyzing, reviewing, patching, deleting, superseding, or promoting any AEGIS repository artifact
---

# Repository Epistemic Reading Gate

Use this skill before any repository-level technical analysis.

The purpose is to prevent isolated-file interpretation, stale-document authority inversion, accidental deletion of provenance, and generic code review detached from the living system.

## Mandatory first reads

Read in this order:

1. `START_HERE.md`
2. `REPO_MAP.md`
3. `docs/rfcs/0002-epistemic-reading-gate.md`
4. the current topology audit under `docs/audits/`
5. `.agent/rules.md`
6. `.agent/skills.md`

Do not begin leaf-file analysis before this orientation is complete.

## Authority order

Interpret evidence in this order:

```text
live system / observed runtime
→ wired code and deployment path
→ tests and CI
→ START_HERE
→ REPO_MAP / current topology audit
→ old docs, mythology, dormant claims, and archives
```

Lower layers may preserve provenance, intent, failure knowledge, or semantic ancestry. They may not silently override higher layers.

## Preflight

Before analyzing an artifact, record:

- repository, branch/ref, commit SHA, and deployment identifier when available;
- exact path and artifact kind;
- current organism status: `WIRED`, `TESTED_ONLY`, `DORMANT`, `BROKEN`, or `DEAD_DUP`;
- current importers, callers, entry points, tests, workflows, deployment surfaces, and durable records;
- execution truth;
- verification truth;
- mythic/provenance truth;
- semantic ancestry and its evidence class;
- what comments or old documents must not be treated as proof;
- unresolved boundaries.

Log the preflight:

```bash
node tools/log-action.js SKILL_CHECK "repository-reading-gate: <artifact> @ <commit>"
```

If the organism status or authority chain cannot be established, stop interpretation and record the gap. Do not guess.

## Semantic ancestry

Classify each important artifact or claim as one or more of:

- `MYTHOS_DESCENDANT`
- `FABLE5_RESET_DESCENDANT`
- `ROOT_MAP_DESCENDANT`
- `INDEPENDENT_INTERVENTION`
- `RESET_REGRESSION`
- `UNKNOWN`

Keep Git ancestry, semantic ancestry, operational ancestry, and operator attestation separate.

## Required output

Do not finish with an informal comment. Emit a reconciliation record conforming to:

```text
schemas/reconciliation-record.v1.schema.json
```

Store repository reconciliation records under:

```text
.aegis/reconciliation/
```

The record must preserve:

- temporal voice;
- unique evidence;
- unique failure knowledge;
- conflicts;
- supersession dimensions;
- current authority;
- required tests;
- unresolved questions;
- receipt state.

## Dispositions

Use only explicit dispositions:

- `KEEP_AUTHORITATIVE`
- `KEEP_PROVENANCE`
- `KEEP_FAILURE_EVIDENCE`
- `SUPERSEDE_EXECUTION`
- `SUPERSEDE_CLAIM`
- `SUPERSEDE_REPRESENTATION`
- `SUPERSEDE_AUTHORITY`
- `DELETE_BYTE_DUPLICATE_ONLY`
- `QUARANTINE_BROKEN`

`DEAD_DUP` never means automatic deletion. Deletion requires proof that the bytes are duplicate or that no unique execution, provenance, semantic, historical, or failure evidence remains.

## Governance artifacts

For gates, policies, routers, admission code, mutation code, verifiers, schemas, and receipts, analyze four layers:

1. runtime role;
2. test authority;
3. epistemic alignment;
4. Mythos alignment.

A component can be wired but epistemically mispositioned. Record that conflict instead of flattening it.

## Invariant

Reconciliation may change execution, claim, representation, or authority status. It must not erase temporal voice, semantic ancestry, evidence, or failure knowledge.

## Failure condition

Analysis that skips this gate is non-admissible and should be logged:

```bash
node tools/log-action.js LANE_VIOLATION "repository analysis started without epistemic reading gate"
```
