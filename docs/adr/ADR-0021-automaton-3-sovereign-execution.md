# ADR-0021: Automaton-3 sovereign execution control plane

Status: Proposed for exact-head admission  
Canonical base: `0e40ddf71090e6ff680c4eb7e721af98d4cea1d6`

## Decision

All consequential execution uses one deterministic authority evaluator in `harness/sdk/sovereign_execution.py`. Entry points may adapt transport and evidence formats, but they may not implement an independent authority score or bypass the evaluator.

The control plane separates five concerns:

1. `ExecutionIdentityEnvelope` binds the request to canonical repository identity, source commit, logical repository root, actor, physical executor, workflow, capability, policy, registry, and action digests.
2. `WorkspaceBinding` binds the canonical remote, logical root, project identity, source commit, and operator authorization. Absolute paths remain observational metadata.
3. `AuthorityEvaluator` applies the D0–D4 consequence policy and evidence-bound capability registry. Unknown, unobserved, under-validated, unavailable, or unmapped capabilities receive zero operational authority.
4. `WriterLeaseManager` provides one active writer per authority domain, monotone generations, fencing tokens, expected-parent checks, and replay rejection.
5. `DurableExecutionRegistry`, `EventEnvelope`, and `ReceiptChain` preserve operator visibility, mediated communication, idempotency, cancellation, and deterministic mutation or denial evidence.

## Determinism boundary

Deterministic roots contain no wall-clock timestamp, random ordering, host-specific absolute path, mutable deployment label, or unredacted secret. Operational time and resolved paths are attached as observational metadata and are not hashed into identity, policy, lease, event, or mutation roots.

## Workspace root convention

The deterministic `repository_root` and `workspace_root` are the logical root `.`. The exact resolved host path is recorded in `WorkspaceObservation`. This prevents two runners in different absolute directories from producing different identity roots while still exposing the physical execution location to the operator.

## Integration

- `agents/coordinator.py` grants dispatch authority only through `authorize_from_environment`.
- MCP consequential tools invoke `scripts/automaton3-authority.py`; an unavailable evaluator or identity denies before bridge access.
- CI invokes the same core module for policy, workspace, lease, durable execution, event, and receipt tests.
- D0 read-only MCP resources remain key-free and cannot mutate state.


## Agent trajectory evidence

`AgentTrajectoryRecord` and `TrajectoryChain` add an append-only, deterministic
observability layer for governed agent/tool execution. A trajectory record binds
the execution identity root, policy-decision root, action class, authority domain,
approval reference, tool, requested-action digest, network-policy outcome,
destination digest, redacted-input digest, result digest, outcome, sequence, and
parent trajectory root.

This layer is evidence-only. It cannot mint, increase, preserve, or substitute
operational authority, and it does not participate in `AuthorityEvaluator`
admission. D2–D4 trajectory evidence is invalid without an explicit approval
reference. Network-capable observations are invalid without an explicit
`ALLOW` or `DENY` network-policy result and a destination digest; non-network
observations must use `NOT_APPLICABLE`.

Raw prompts, credentials, authorization material, tool inputs, tool outputs, and
network destinations are not retained in trajectory records. Sensitive fields are
deterministically redacted before hashing, so replay can prove equality without
turning the audit chain into a secret or prompt store.


## External-runtime boundary

This PR implements a deterministic local reference model and interfaces for durable execution. It does not claim that Temporal, LangGraph, Kubernetes, or any cloud worker runtime is deployed.
