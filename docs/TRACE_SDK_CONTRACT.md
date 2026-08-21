# AEGIS Ω Proof Trace SDK v1

Status: implementation contract on a stacked DRAFT branch. This document does not reopen the frozen UCI research/property scope.

## Purpose

Ordinary tracing answers: **what happened?**

AEGIS Proof Trace answers a stricter question:

> **Which exact observations, receipts, state bindings, causal dependencies, and authority transitions support the claim that a transition happened as asserted?**

The Trace SDK is therefore an evidence container and replay surface, not an authority producer.

```text
Trace != Authority
Span != Receipt
Decision != Effect
Observation != Truth
External telemetry != AEGIS admission
```

The runtime contract is implemented in `harness/sdk/proof_trace.py`.

## 1. Trace header

Every trace binds:

- deterministic `trace_id` derived from workflow + exact source commit + nonce unless explicitly supplied;
- exact source commit;
- exact policy commitment;
- genesis control-state root;
- optional group identity;
- metadata by digest only;
- the fixed semantic discriminator `TRACE_IS_EVIDENCE_CONTAINER_NOT_AUTHORITY`.

The header has its own domain-separated root.

## 2. Spans are typed epistemic objects

Supported span kinds:

```text
MODEL
TOOL
HANDOFF
GUARDRAIL
DECISION
EXECUTION
EFFECT
ADMISSION
MEMORY
HERITAGE
JOINT_FAILURE
VERIFIER
EXTERNAL
CUSTOM
```

Authority classes are deliberately smaller:

```text
NONE
DECISION_AUTHORITY
ADMISSION_AUTHORITY
```

`MODEL`, `TOOL`, `HANDOFF`, `GUARDRAIL`, `EXECUTION`, `EFFECT`, `MEMORY`, `HERITAGE`, `JOINT_FAILURE`, `VERIFIER`, `EXTERNAL`, and `CUSTOM` are structurally evidence-only. A trace cannot re-label one of these as authority.

A `DECISION` span may carry `DECISION_AUTHORITY` only when it is bound to an exact `transition_id` and at least one receipt root.

An `ADMISSION` span may carry `ADMISSION_AUTHORITY` only when it is bound to an exact `transition_id` and at least one receipt root.

No other span may carry those authority classes.

This preserves the existing receipt separation rather than inventing a generic "verified span" that silently collapses epistemic types.

## 3. Control-state linearization inside the trace

Each started span captures the current AEGIS control-state root.

Non-admission spans are prohibited from changing that tracked root.

Only an `ADMISSION` span with `ADMISSION_AUTHORITY` may advance:

```text
S_n --AdmissionReceipt-bound ADMISSION--> S_n+1
```

Two admissions started against the same `S_n` cannot both advance the local trace state. After one commits `S_n -> S_n+1`, the losing span fails with:

```text
ADMISSION_CONTROL_STATE_STALE
```

This is a local Trace SDK serializability property. It is **not** a claim that arbitrary external infrastructure effects are transactionally atomic with the AEGIS control state.

## 4. Effect evidence stays effect evidence

An `EFFECT` span requires:

- exact `transition_id`; and
- an effect receipt root or independent evidence root.

It may record observed pre/post state roots, but it always has `authority_class=NONE`.

Therefore:

```text
DecisionReceipt(PERMIT)
    != ExecutionReceipt
    != EffectReceipt / EffectEvidence
    != AdmissionRecord
```

A trace binds these artifacts together without allowing one nominal type to impersonate another.

## 5. Causal graph and structural graph

The SDK records two separate relationships.

`parent_span_id` is structural nesting: an agent span may structurally contain a tool span even if the child completes before the parent.

`causal_parent_ids` are stronger. A causal parent must already be completed before the dependent span starts. Export verification rejects forward causal edges.

Structural parentage must form an acyclic graph.

This distinction prevents UI nesting from being mistaken for causal proof.

## 6. Hash commitments

Each span is domain-separated and hashed.

At trace close, spans are committed in completion order through:

```text
Commit_1 = H(span_1, ZERO)
Commit_2 = H(span_2, Commit_1)
...
Commit_n = H(span_n, Commit_n-1)
```

The bundle additionally commits:

- terminal commit root;
- final control-state root;
- deduplicated receipt/evidence artifact manifest root;
- complete typed span payloads;
- trace header root.

Changing a span changes its span root; unchanged commit objects then fail independent replay verification.

## 7. Portable verification

`ProofTraceBundleV1.to_json()` emits a deterministic JSON representation plus its computed bundle root.

`bundle_from_json()` re-materializes nominal types.

`verify_trace_bundle()` independently checks:

- bundle/header/span discriminators;
- sequence continuity;
- unique span IDs and allocation IDs;
- structural parent existence and acyclicity;
- causal parent existence and prior completion;
- authority-kind separation;
- transition and receipt/evidence binding requirements;
- control-state advancement rules;
- commit-chain integrity;
- terminal commitment;
- artifact manifest;
- final control-state root.

This verifier requires no model call and no network access.

## 8. Sensitive-data boundary

The SDK stores digests, not raw model prompts, completions, tool arguments, tool outputs, exception text, or external trace IDs.

`digest_payload(value)` is a commitment helper, not encryption. Low-entropy or guessable sensitive values should be redacted or keyed/externally protected before hashing when confidentiality matters.

Unhandled exceptions are represented by the machine code:

```text
UNHANDLED_EXCEPTION
```

The exception body is not stored by the Trace SDK.

## 9. OpenAI Agents SDK interoperability

OpenAI Agents SDK tracing has end-to-end traces, nested spans, custom spans, trace metadata, and custom tracing processors. AEGIS does not replace that observability layer.

Instead:

1. OpenAI tracing remains useful for debugging, visualization, model/tool/handoff timing, and eval analysis.
2. A custom processor or application hook can call `record_external_span(...)` to commit an OpenAI span into the AEGIS graph as **T2 evidence-only**.
3. `openai_trace_metadata(bundle)` emits only non-sensitive AEGIS commitment metadata, including the AEGIS bundle root and terminal commit root.
4. OpenAI trace identity never becomes AEGIS receipt identity or admission authority.

This gives a dual surface:

```text
OpenAI Trace
  -> rich operational observability
  -> provider-hosted trace visualization/evals

AEGIS Proof Trace
  -> deterministic evidence graph
  -> receipt/state/authority separation
  -> offline replay verification
  -> portable proof bundle
```

The bridge is dependency-free in v1; `openai-agents` is not added to the repository merely to verify the AEGIS proof format.

## 10. What v1 establishes

Passing the v1 falsifier suite establishes only the implemented contract on the exact tested head:

- trace objects cannot themselves become authority;
- evidence-only spans cannot be authority-labeled;
- decision and admission authority are nominally separated;
- effect evidence cannot mutate control state;
- only receipt-bound admission authority can advance trace control state;
- stale concurrent admissions fail closed;
- causal edges and structural nesting are independently checked;
- exported bundles can be replay-verified;
- basic tampering is detected through span/commit/bundle commitments;
- external observability spans remain T2 evidence-only.

It does not establish:

- universal security;
- external-effect serializability;
- RFC 8785 conformance;
- cryptographic signer identity or non-repudiation;
- trusted wall-clock ordering;
- world truth;
- AGI;
- independence of multiple agents;
- a replacement for the existing Decision/Execution/Effect/Admission receipt types.

## 11. Next depth

The v1 surface is deliberately positioned so deeper layers can be added without changing the frozen epistemic boundary:

- Ed25519/OIDC attestation over the final bundle root;
- cross-process append service with Redis/Postgres linearization;
- OpenTelemetry/W3C trace-context bridge as evidence-only metadata;
- direct adapters for OpenAI Agents SDK tracing processors;
- receipt schema lookup and semantic validation during binding;
- witness inclusion proofs for selected spans/artifacts;
- bitemporal memory replay anchors;
- heritage lineage bundles (`Parent + Delta -> Child`) inside the same causal graph;
- UCI campaign trial traces and joint-failure certificates bound as evidence artifacts;
- effect-time state freshness gates that consume the trace state root at the actual mutation boundary.
