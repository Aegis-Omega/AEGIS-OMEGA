# ADR-0021: Automaton-3 sovereign execution control plane

Status: Proposed for exact-head admission  
Canonical base: `0e40ddf71090e6ff680c4eb7e721af98d4cea1d6`

## Decision

All consequential execution uses one deterministic authority evaluator in `harness/sdk/sovereign_execution.py`. Entry points may adapt transport and evidence formats, but they may not implement an independent authority score or bypass the evaluator.

The control plane separates six concerns:

1. `ExecutionIdentityEnvelope` binds the request to canonical repository identity, source commit, logical repository root, actor, physical executor, workflow, capability, policy, registry, and action digests.
2. `WorkspaceBinding` binds the canonical remote, logical root, project identity, source commit, and operator authorization. Absolute paths remain observational metadata.
3. `AuthorityEvaluator` applies the D0–D4 consequence policy and evidence-bound capability registry. Unknown, unobserved, under-validated, unavailable, or unmapped capabilities receive zero operational authority.
4. `WriterLeaseManager` provides one active writer per authority domain, monotone generations, fencing tokens, expected-parent checks, and replay rejection.
5. `DurableExecutionRegistry`, `EventEnvelope`, and `ReceiptChain` preserve operator visibility, mediated communication, idempotency, cancellation, and deterministic mutation or denial evidence.
6. `AgentTrajectoryRecord` and `TrajectoryChain` bind observed approval, tool, network-policy, and result evidence to the exact execution identity and policy decision without granting authority.

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

Agent trajectory records are an evidence surface, not an authority surface. A trajectory record cannot admit a request, mint or extend an approval, acquire a writer lease, or substitute for `AuthorityEvaluator`. Consequential execution remains governed exclusively by the existing authority path.

Each trajectory record binds the execution identity root, policy-decision root, approval reference, tool identity, requested-action digest, network-policy outcome, network-destination digest, tool-input digest, result digest, outcome, sequence, and parent trajectory root. Raw tool inputs, outputs, credentials, tokens, prompt secrets, cookies, authorization material, and network destinations are not stored in the record; deterministic redaction and domain-separated digests preserve evidence without retaining those values.

Network-capable observations fail closed unless the network-policy outcome is explicitly `ALLOW` or `DENY` and a destination digest is present. A `DENY` observation cannot claim `SUCCEEDED`. Non-network observations require `NOT_APPLICABLE` and a zero destination digest. `TrajectoryChain` rejects sequence and parent-root breaks, so replay evidence cannot be silently reordered or spliced.

This layer is standard-library only and introduces no new service, database, model provider, credential, approval path, or operational authority.

## External-runtime boundary

This PR implements a deterministic local reference model and interfaces for durable execution. It does not claim that Temporal, LangGraph, Kubernetes, or any cloud worker runtime is deployed.
