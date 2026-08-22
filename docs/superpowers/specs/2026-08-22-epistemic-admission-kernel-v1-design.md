# Epistemic Admission Kernel v1 — Design

**Status:** DRAFT IMPLEMENTATION SPEC

**Canonical parent:** `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`

**Historical source artifact:** Google Drive document `AEGIS Ω — Epistemic Debugging Lexicon and Failure Ledger — 2026-08-02`, Drive file ID `1DtXRg-xlQ3m__UlpDNn0hXhSlvGGGNeI2rmm9j2A_7k`.

## Purpose

Turn the observed failure patterns F-01–F-18 into an executable admission boundary. The kernel does not establish truth by itself. It constrains which claim states may become load-bearing and records why a claim was served, reviewed, or quarantined.

Core invariant:

> No claim may possess greater epistemic authority than the weakest verified transition required to establish it.

## Scope

This v1 slice intentionally does four things only:

1. defines machine-readable claim, source-binding, applicability, retrieval, and failure-locus contracts;
2. implements a deterministic fail-closed verifier for those contracts;
3. adds falsifier tests for the historical failure classes that motivated the design;
4. injects a compact epistemic bootstrap into Claude session/prompt hooks so model-side fluency cannot silently stand in for status.

It does **not** grant external-effect authority, replace CEL v1.1, alter frozen constitutional semantics, infer consciousness/identity, or promote model output into authority.

## Epistemic model

### Claim status

Every consequential claim MUST expose one status:

- `VERIFIED`
- `DERIVED`
- `ATTESTED`
- `INFERRED`
- `ASSUMED`
- `NOT_CHECKED`

`PROPOSED` remains manuscript-facing vocabulary in `docs/CLAIMS_LEDGER.md`; runtime normalization maps proposal/hypothesis states to `ASSUMED` unless a more specific local policy exists.

### Field authority

Each load-bearing field MUST declare a field provenance class:

- `DECLARED`
- `DERIVED`
- `ATTESTED`
- `VERIFIED`

A `DECLARED` load-bearing field is inadmissible.

### Applicability

Historical validity and current applicability are orthogonal:

```text
historically_valid = verifier succeeded for original subject
currently_applicable = subject binding still matches current subject
```

For git-backed evidence, exact-head admission requires:

```text
receipt.subject_sha == current_head_sha
```

A mismatch preserves historical evidence but routes current admission to `QUARANTINE`.

### Source binding

For sourced claims the kernel evaluates three independent predicates:

```text
claim_status(claim)
provenance_integrity(source)
source_entails(source, claim)
```

No predicate substitutes for another. A genuine source with intact custody may still fail citation entailment.

### Negative retrieval

A failed retrieval may emit `NOT_FOUND_BY_THIS_QUERY`. It MUST NOT emit `NONEXISTENT` unless a separately defined authoritative registry verifier establishes nonexistence for the scoped identifier/domain.

### Route

The verifier returns exactly one route:

- `SERVE`
- `REVIEW`
- `QUARANTINE`

Routing is independent from attribution and update authority.

### Failure locus

The v1 structured failure loci are:

- `NARRATOR`
- `ADMISSION_POLICY`
- `PROVENANCE_SYSTEM`
- `CONTENT_VERIFIER`
- `CITATION_ENTAILMENT_FAILURE`
- `ENFORCEMENT`
- `ENUMERATION_PROCEDURE`
- `SUBJECT_BINDING`
- `NONE_ESTABLISHED`

A single event may carry multiple loci.

## Runtime interfaces

### `EpistemicClaimV1`

Required fields:

```text
claim_id: str
claim_text: str
status: ClaimStatus
subject: SubjectBindingV1
authority_scope: AuthorityScopeV1
evidence_window: EvidenceWindowV1
load_bearing_fields: list[LoadBearingFieldV1]
sources: list[SourceBindingV1]
```

### `AdmissionDecisionV1`

```text
route: SERVE | REVIEW | QUARANTINE
claim_id: str
subject_match: bool
violations: list[str]
failure_loci: list[FailureLocus]
current_applicability: bool
historically_valid: bool | null
```

The decision is evidence about admission policy execution. It is not Effect/Admission authority for external state transitions.

## Deterministic verifier rules

The verifier MUST be pure over its supplied input.

1. missing or unknown claim status -> `REVIEW`;
2. any load-bearing field with provenance `DECLARED` -> `QUARANTINE`;
3. historical receipt SHA mismatch against current head -> `QUARANTINE`, while `historically_valid` remains unchanged;
4. source with `provenance_integrity=true` and `entails_claim=false` -> `QUARANTINE` with `CITATION_ENTAILMENT_FAILURE`;
5. negative search represented as universal nonexistence -> `QUARANTINE`;
6. unresolved authorship/input provenance may not be promoted into instruction/memory authority -> `QUARANTINE` when load-bearing;
7. if no violation exists but required verification is incomplete -> `REVIEW`;
8. `SERVE` requires all required load-bearing predicates to be resolved and satisfied for the specified scope.

## Bootstrap behavior

The existing `.claude/hooks/user-prompt-intake.sh` currently reports `MetacognitiveLoop(live)` and `temporal-mass`. V1 replaces that authority-ambiguous wording with an explicit integrity-only observation-chain statement:

```text
ObservationChain(integrity-only): ...
Non-equiv: chain-integrity≠truth | chain-integrity≠identity | chain-integrity≠consciousness
Claim-status-required: VERIFIED|DERIVED|ATTESTED|INFERRED|ASSUMED|NOT_CHECKED
```

A new repo-local bootstrap file is loaded on session start. It contains the compact operational rules A–S and the F-01–F-18 failure labels, but does not claim fresh repository state.

## Test obligations

The first implementation must include falsifiers for at least these historical classes:

- F-02/F-04: exact-head mismatch preserves historical validity but quarantines current admission;
- F-03: aggregation without completeness proof cannot be served;
- F-07: cross-session reconstruction claim without mechanism separation cannot be verified;
- F-12/F-13: search miss cannot become nonexistence;
- F-14/F-17: consequential claim without explicit status/external verifier is not served as verified;
- F-18: provenance PASS + entailment FAIL remains citation-binding failure;
- declared load-bearing field cannot carry authority.

## CI

Add a dedicated `AEGIS Epistemic Admission` workflow. It must:

- run on pull requests and merge groups targeting `main`;
- checkout the exact candidate SHA;
- run the falsifier suite;
- validate the machine-readable schema/contracts;
- use immutable action SHAs if trusted pinned SHAs are already present in repository history; otherwise avoid introducing a new mutable supply-chain dependency in this PR.

## Non-equivalences

The implementation MUST preserve these explicit boundaries:

```text
valid_hash_chain != true_content
provenance_integrity != citation_entailment
verification_pass != universal_truth
historical_validity != current_applicability
user_channel != human_authorship
search_miss != nonexistence
model_fluency != correctness
model_output != authority
operator_approval_metadata != production_authorization
```

## Promotion criterion

This slice is eligible for promotion only when the exact PR head has:

- all dedicated Epistemic Admission falsifiers GREEN;
- no test weakening relative to this spec;
- exact-head evidence for the candidate SHA;
- no representation that the kernel itself grants production Effect/Admission authority.
