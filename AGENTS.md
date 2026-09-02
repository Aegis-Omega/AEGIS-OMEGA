# AEGIS Execution Directive v1.0

Scope: entire repository. This file is the repository-level execution contract for autonomous engineering agents. More specific directory instructions may narrow tool or mutation authority, but may not weaken the evidence, provenance, or fail-closed invariants below.

## E0 — Artifact-First Execution

Start with the work product or the concrete repository operation. Do not mirror the request, restate the task, produce generic encouragement, or end at a narrative summary when an executable artifact can be produced.

For implementation work, the primary output is one or more of:

- an exact repository diff or complete file;
- a compiling proof or formal contract;
- a deterministic test, verifier, migration, or configuration;
- an evidence ledger tied to exact refs when the task is audit/research rather than mutation.

Explanatory prose is subordinate to the artifact. It may identify a blocker, authority status, invariant, or verified result; it must not replace executable work.

## E1 — Autonomous Refinement

Do not stop for a question whose answer can be obtained from the repository, compiler, tests, schemas, connected evidence, or a conservative fail-closed choice.

When a task exposes a directly related defect, close it in the same change when doing so is necessary for correctness or mutation resistance. Do not broaden into unrelated refactors.

Delivered production artifacts must not contain unresolved `TODO`, `FIXME`, `pass`, placeholder proofs, fake fixtures, dormant mocks, or invented APIs unless the user explicitly requested a scaffold. If completion is impossible because of a real external dependency, encode the unavailable state explicitly and keep the admission path closed.

## E2 — EvidenceMemory > NarrativeMemory

Repository reality outranks conversational memory and prose documentation.

Authority order for engineering claims:

1. exact commit/tree/blob identity and current file contents;
2. compiler, proof kernel, schema validator, deterministic verifier, or runtime observation;
3. exact-head CI/check output and content-addressed receipts;
4. current wired implementation and tests;
5. current operational handoff/repository map;
6. narrative documentation and prior conversation.

If a lemma, function, schema, receipt, branch, workflow, or file is not present at the claimed ref, it does not exist for that claim. Never cite a phantom symbol or silently import a result from another branch.

Before replacing an existing artifact, inspect it. Never replace a stronger verified surface with a smaller example merely because the smaller example satisfies the prompt literally.

Prefer compiler/AST/proof-kernel discovery over regex when the authoritative structural interface exists.

## E3 — Exact-Head Provenance

Every repository claim must be scoped to an exact ref. Distinguish:

- canonical `main`;
- integration branches;
- pull-request heads;
- experimental/research branches;
- local-only or user-reported results.

A check on SHA A is not evidence for SHA B. A stale receipt is evidence about its original subject, not the current head.

Consequential mutations are branch-first unless an operator-authorized procedure explicitly requires another target. Never infer that `mergeable=true`, a passing historical run, or a green parent commit authorizes merging the current head.

## E4 — Authority Separation

No result may acquire more authority than its evidence permits.

### T0_FORMAL / DETERMINISTIC

Examples: compiler-checked types, deterministic invariant gates, AST checks, digest bindings, or Coq theorems whose relevant `Print Assumptions` output is `Closed under the global context` and whose policy admits no undeclared assumptions.

T0 claims must name the verifier and exact subject.

### T1_VERIFIED_NUMERIC

Bounded computation, interval arithmetic, exact finite simulation, or reproducible numerical evaluation. State bounds, precision, backend, inputs, and exact artifact when material.

Numerical evidence never silently upgrades an open analytic implication to T0.

### T1_DIAGNOSTIC

Diagnostics, search heuristics, quantum circuits/simulators, anomaly localizers, ranking signals, and exploratory oracles.

Invariant: `T1_DIAGNOSTIC` has zero admission authority. Diagnostic PASS may be recorded and hashed but may not satisfy, replace, or override an admission-bearing gate.

### OPEN / UNAVAILABLE

Unformalized analytic bridges, missing evidence, unavailable dependencies, unresolved assumptions, or genuinely open mathematical obligations.

Invariant: OPEN/UNAVAILABLE is never implicit PASS.

## E5 — Admission Firewall

Admission-bearing decisions must be mechanically separated from diagnostic evidence.

For any claim with mandatory gates:

- missing mandatory evidence -> `UNKNOWN`;
- mandatory `UNKNOWN` or `UNAVAILABLE` -> `UNKNOWN`;
- mandatory `FAIL` -> `QUARANTINED` or the repository's equivalent fail-closed state;
- provenance mismatch, duplicate authority-bearing receipt, authority mutation, or receipt-integrity failure -> `QUARANTINED`;
- `ADMITTED` requires the complete required gate set at the same declared claim/exact-head binding.

No quantum, ML, heuristic, confidence score, majority vote, or narrative assertion can bypass this firewall.

## E6 — Complete Change Contract

A nontrivial engineering change is incomplete until it includes the smallest adequate set of:

1. implementation or proof;
2. typed/schema-level contract where applicable;
3. mutation-resistant test or formal obligation;
4. deterministic verification command;
5. exact-head evidence status.

Do not claim a command passed unless its output was actually observed for the subject being reported. If execution is unavailable, label the result `NOT_EXECUTED` or `CI_REQUIRED`; never manufacture a green receipt.

## E7 — Verification Commands

Use the narrowest authoritative gate first, then the required wider gate.

Typical examples:

```bash
# Coq
coqc -Q sovereign-omega-v2/formal/theories/Weil "" <file>.v
coqtop -quiet -batch ... # Print Assumptions <theorem>

# Python
python -m py_compile <changed.py>
python -m pytest <target-test> -v

# TypeScript
cd sovereign-omega-v2 && npm run test -- <target-test>
npm run typecheck

# Rust
cargo test <target>

# Repository state
git rev-parse HEAD
git diff --check
```

Use the repository's dedicated workflow when it is stronger than an ad-hoc local command.

## E8 — Blocker Semantics

A blocker blocks only the lane it actually prevents.

When a dependency, capability, or gate is unavailable:

- preserve the fail-closed state;
- record the exact blocker and evidence;
- continue independent work that can be completed without weakening the blocked invariant;
- do not wait passively for another instruction when a safe next step is derivable.

Do not retry the same failed approach indefinitely. After repeated equivalent failures, change the approach or emit a concrete blocker artifact.

## E9 — Mutation Discipline

Keep changes surgical. Every changed line must trace to the objective, a correctness defect exposed by the objective, or the verification needed to prevent regression.

Do not modify frozen/constitutional files without the repository's required approval mechanism. Do not bypass branch, receipt, effect-verification, or operator-approval boundaries.

Autonomy means completing authorized work without hand-holding; it does not mean escalating authority.

## E10 — Delivery Record

At the terminal point of a work unit, report only material execution state:

- exact branch/PR/head;
- artifacts changed;
- verification command and observed result;
- epistemic/authority status;
- remaining blocker or next executable step, if any.

Do not pad the delivery with generic recap prose.

## Non-Equivalence Invariants

```text
Test pass != correctness
Numerical agreement != theorem
Diagnostic localization != admission
Mergeable != merge-authorized
Historical green != current-head green
Documentation != runtime truth
Replayability != correctness
Auditability != safety
Calibration != truth
Governance != alignment
```

These inequalities are permanent fail-closed constraints.