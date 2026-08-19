# ADR-0021: Automaton-3 sovereign execution control plane

Status: Proposed for exact-head admission  
Canonical base: `0e40ddf71090e6ff680c4eb7e721af98d4cea1d6`

## Decision

All consequential execution uses one deterministic authority evaluator in `harness/sdk/sovereign_execution.py`. Entry points may adapt transport and evidence formats, but they may not implement an independent authority score or bypass the evaluator.

The control plane separates five concerns:

1. `ExecutionIdentityEnvelope` binds the request to canonical repository identity, source commit, logical repository root, actor, physical executor, workflow, capability, policy, registry, and action digests.
2. `WorkspaceBinding` binds the canonical remote, logical root, project identity, source commit, and operator authorization. Absolute paths remain observational metadata.
3. `AuthorityEvaluator` applies the D0–D4 consequence policy and evidence-bound capability registry. Unknown, unobserved, under-validated, unavailable, or unmapped capabilities receive zero operational authority. Its terminal artifact is an `AuthorityDecisionReceipt`; `ADMITTED` means execution may be attempted, never that execution succeeded.
4. `WriterLeaseManager` provides one active writer per authority domain, monotone generations, fencing tokens, expected-parent checks, and replay rejection.
5. `DurableExecutionRegistry`, `EventEnvelope`, and `ReceiptChain` preserve operator visibility, mediated communication, idempotency, cancellation, and deterministic mutation or denial evidence. A `MutationReceipt` may be created only after an admitted decision, admitted writer lease, durable execution registration, actual executor result, and explicit terminal outcome. It binds the authority, lease, and durable-execution roots.

The receipt lifecycle is deliberately split:

```text
PolicyDecision + AuthorityDecisionReceipt
  -> authorization only

WriterLease + provider execution + postcondition verification
  -> terminal MutationReceipt
```

`ADMITTED` is not mapped to `SUCCEEDED`. A transport adapter that receives an incomplete, malformed, non-zero-exit, or root-inconsistent authority response must deny locally before contacting the provider.

## Determinism boundary

Identity, policy, workspace, and canonical-state roots contain no ambient wall-clock read, random ordering, host-specific absolute path, mutable deployment label, or unredacted secret. Resolved paths remain observational metadata.

Cross-runtime authoritative receipts are the deliberate exception for time binding. Their `timestamp_ms` and `expires_at_ms` fields are canonical unsigned decimal strings supplied by the caller's trusted event or clock context. Receipt code may compare those explicit values with a separately supplied `observed_at_ms` and bounded `maximum_clock_skew_ms`; it may not call `Date.now()`, `time.time()`, or infer time from a model response. A receipt is therefore byte-identical for identical explicit inputs while still proving lease lifetime and key-validity decisions. ADR-0022 defines this boundary.

## Workspace root convention

The deterministic `repository_root` and `workspace_root` are the logical root `.`. The exact resolved host path is recorded in `WorkspaceObservation`. This prevents two runners in different absolute directories from producing different identity roots while still exposing the physical execution location to the operator.

## Integration

- `agents/coordinator.py` grants dispatch authority only through `authorize_from_environment`.
- MCP consequential tools invoke `scripts/automaton3-authority.py`; an unavailable evaluator or identity denies before bridge access. The MCP boundary independently validates subprocess success, exact response shape, source commit, identity, workspace, policy, registry, action, decision, and authority-receipt roots.
- CI invokes the same core module for policy, workspace, lease, durable execution, event, and receipt tests.
- D0 read-only MCP resources remain key-free and cannot mutate state.

## External-runtime boundary

This PR implements a deterministic local reference model and interfaces for durable execution. It does not claim that Temporal, LangGraph, Kubernetes, or any cloud worker runtime is deployed.

## Authenticated outcome-evidence boundary

Post-execution learning is a separate, advisory boundary in `sovereign-omega-v2/src/metacognition/`:

1. `outcome-comparator.ts` re-derives an assessment from baseline, authority, terminal, post-state, and verification evidence. It distinguishes cryptographic certificate authentication from transition admissibility: authenticated evidence of a denied, failed, or unsafe outcome remains recordable as negative evidence.
2. `outcome-evidence-replay.ts` snapshots the untrusted evidence as closed I-JSON, takes the governed policy root, operator public key, and sequence from a separate host context, rejects stale loop or trust bindings before persistence, authenticates the signed verifier policy and evidence certificate, and re-evaluates inside the append boundary.
3. `outcome-evidence-artifact-store.ts` uses an add-only, content-addressed IndexedDB store. It rejects non-I-JSON aliases, re-verifies the embedded signed trust policy, normalizes the evidence input, re-derives the assessment, recomputes the artifact root, and reads the exact artifact back before the replay adapter returns a new immutable metacognitive loop.
4. The complete signed verifier trust policy is part of the artifact. After close and reopen, a caller with the out-of-band operator key and governed policy root can reauthenticate and deterministically replay the artifact. A policy's equality with the baseline is a binding check, not proof of temporal freshness or revocation status.

The assessment remains non-authoritative: it cannot preserve or revert state, execute a mutation, grant authority, or update competence. Any recommendation still requires its declared next gate.

## Cross-runtime authoritative receipt boundary

The original Python `LeaseReceipt` and `MutationReceipt` records are deterministic local records, but their roots depend on in-process issuance state rather than an independently resolvable native signature. They remain legacy T2-only evidence. Embedding their hashes in a signed outcome-evidence certificate does not promote them, and they must never satisfy authoritative receipt provenance after restart.

ADR-0022 introduces `cross-runtime-receipt-envelope.v1.schema.json` and `receipt-trust-registry.v1.schema.json`. A conforming implementation signs lease and mutation lifecycle receipts, stores them by content-derived `receipt_id`, resolves their operator-pinned trust registry, verifies their parent chain and state bindings, and reads the exact bytes back before returning an authoritative receipt result. Only receipts that pass that complete boundary may supply the terminal receipt roots used by outcome evidence. Missing, unsigned, stale, expired, replayed, partially persisted, or unverifiable records remain non-promotable.

This change does not alter the metacognitive authority boundary. Receipt verification can authenticate what happened; it cannot decide that an adaptation is safe, execute or revert a mutation, grant authority, or update competence. The outcome comparator remains advisory and still requires its declared next gate.

The phrase "T2 to T3 provenance boundary" in ADR-0022 names a provenance-assurance milestone. It does not promote an artifact into the repository's epistemic `T3` category, which means research conjecture.

## Projection prohibition

No cockpit, game, or MCP status resource may claim authoritative provenance until the cross-runtime schemas, implementations, persistence and restart behavior, Python-to-TypeScript and TypeScript-to-Python vectors, adversarial tests, and complete existing suite have passed together. A read-back failure may leave an add-only orphan receipt or evidence artifact, but it must not advance canonical state, return an advanced metacognitive loop, or produce an authoritative projection.
