# RFC 0001 — AEGIS Operator-Sovereign Control Plane

**Status:** Design candidate; implementation is not claimed  
**Ground-truth date:** 2026-07-18  
**Repository baseline:** `31bcb7ef93d27d3c101694347f3638796162be21`  
**Operator:** Tarik Skalić  
**Source design artifact SHA-256:** `b4651b4754ec41a21f3ed4c0c5257f5a398b519cc02ae8c0d3095038df1bd896`

## 1. Definition

```text
AEGIS = functional coordination
      + governed autonomy
      + deterministic provenance
      + operator sovereignty
```

AEGIS is not complete because it contains many agents, extensive mythology, or sophisticated demonstrations. It is complete only when every consequential action is bounded, attributable, replayable, fail-closed, and visible to the operator.

Functional consciousness is treated only as system architecture. Functional integration, memory, recursive monitoring, self-modeling, and continuity MUST NOT be represented as proof of subjective experience.

## 2. Root law

```text
Granted Autonomy <= Replay Verifiability <= Operator Observability
```

No component may receive more authority than the system can independently reconstruct and expose to the operator.

A consequential transition MUST fail closed when any required authorization, validation, signature, provenance, policy, state-parent, approval, or observability check is missing, invalid, stale, ambiguous, or unavailable.

## 3. Complete transition state

At transition `t`:

```text
A_t = (F_t, J_t, P_t)
```

where:

```text
F_t = (integration, memory, self_model, continuity, action, monitoring)
J_t = (structure, equivalence, governance, contraction, replay, integrity)
P_t = (actor, session, executor, workspace, authority, receipt)
```

The provenance plane is mandatory. A logical decision without physical and administrative attribution is not an admissible consequential transition.

## 4. Non-negotiable invariants

### 4.1 One canonical state root

Every consequential state MUST resolve to one `CanonicalStateRootV1` binding at minimum:

- repository full name;
- repository commit SHA;
- tree or executable artifact digest;
- constitutional bundle digest;
- claims-ledger root;
- policy identifier and digest;
- deployment or environment identity;
- workflow and run identity;
- signer issuer, subject, and key identifier;
- parent canonical root;
- schema version.

A root omitting any required binding is not canonical and MUST NOT authorize consequential execution.

### 4.2 One writer per authority domain

Each mutable authority domain MUST have one current writer lease.

Every write requires:

- authority-domain identifier;
- lease identifier;
- monotonically increasing fencing token;
- expected parent canonical root;
- expected repository HEAD when Git is involved;
- holder and executor identity;
- issued-at and expiry values;
- authorization reference.

Expired leases, stale fencing tokens, unexpected HEAD, unexpected parent root, or concurrent holders MUST be rejected before mutation.

### 4.3 Fail-closed consequential execution

Consequential actions include repository writes and merges, deployments, database privilege changes, cloud IAM changes, outbound messages, publication, submission, invoicing, spending, destructive changes, and durable autonomous processes holding write authority.

Before execution, AEGIS MUST verify:

1. schema validity;
2. request identity;
3. approval identity and state;
4. authority grant;
5. policy version and digest;
6. expected parent root;
7. writer lease and fencing token;
8. target and before-state;
9. executable artifact identity;
10. signing identity;
11. durable-execution registration;
12. replay-package completeness.

A missing verifier is a denial, not a warning.

### 4.4 Complete mutation receipts

Every attempted consequential transition, including denied and failed attempts, MUST emit a `MutationReceiptV1` containing:

- receipt, request, task, and correlation identifiers;
- actor and model/provider identity where applicable;
- session identity;
- physical or cloud executor identity;
- workspace, worktree, or container identity;
- authority domain, lease, and fencing token;
- command, tool, and action identity;
- exact target resource;
- canonical arguments digest;
- before-state digest;
- expected and observed parent roots;
- after-state digest or explicit null;
- resulting canonical root or explicit null;
- authorization and approval references;
- policy identifier and digest;
- signer identity and signature;
- admitted timestamps;
- outcome: `DENIED`, `NO_OP`, `FAILED`, `SUCCEEDED`, or `REVERTED`;
- bounded diagnostic;
- replay-package reference;
- operator-notification reference.

A success response without a complete receipt MUST be treated as failure.

### 4.5 Visible durable execution

Any workflow, queue item, cloud worker, remote session, scheduled task, or model session that may outlive its initiating client MUST register a `DurableExecutionRecordV1` before receiving consequential authority.

The record MUST expose:

- execution and parent-execution identifiers;
- owner/operator;
- purpose and bounded scope;
- current phase and status;
- held authority domains and leases;
- executor location and identity;
- code and artifact digest;
- start time, heartbeat, and expiry;
- provider workflow, queue, and run identifiers;
- pending approvals;
- last emitted receipt;
- cancellation and emergency-stop mechanism;
- terminal receipt and reason.

Unknown, expired, or unobservable execution MUST lose write authority.

### 4.6 Law of Silence correction

Agents MUST NOT exchange uncontrolled raw messages or mutate shared state through ungoverned channels. Inter-agent coordination MUST occur through admitted, typed, attributable event or artifact channels.

The Law of Silence MUST NEVER suppress:

- operator notification;
- safety escalation;
- audit emission;
- denial explanation;
- durable-execution heartbeat;
- emergency-stop acknowledgement;
- independent verifier communication.

Operator notification is a privileged governance channel, not agent-to-agent communication.

## 5. Canonical records

The first implementation series MUST define versioned schemas and cross-runtime golden vectors for:

- `CanonicalStateRootV1`
- `AuthorityLeaseV1`
- `ApprovalRecordV1`
- `MutationReceiptV1`
- `DurableExecutionRecordV1`
- `OperatorNotificationV1`

Canonicalization MUST be singular, frozen by version, and demonstrated byte-identical across Python, TypeScript, and Rust before the schemas authorize live writes.

Approval states MUST be explicit and terminal:

```text
REQUESTED -> VALIDATED -> PENDING_OPERATOR -> APPROVED -> EXECUTING -> SUCCEEDED
         \-> DENIED
APPROVED -> EXPIRED | REVOKED
EXECUTING -> FAILED | REVERTED
```

No component may infer approval from silence, task existence, model output, a prior session, or an unsigned database row.

## 6. Controller governance

The controller is governed by the same laws as subordinate agents. It MUST NOT:

- self-grant authority;
- hide or rewrite its mutation history;
- suppress operator notifications;
- continue consequential execution after observability expires;
- treat a provider success response as proof of after-state;
- use model output as cryptographic authorization;
- replace independent verification with self-reporting.

The controller MUST expose its own session, executor, workspace, tool calls, held authority, and receipts in the provenance plane.

## 7. Claims and Mythos

Claims are first-class governed state. Each claim requires a stable identifier, exact statement, evidence tier, supporting artifact digests, source commit and environment, verifier identity, status, scope, validity interval, contradictions, and promotion or demotion receipt.

The claims-ledger root MUST be bound into the canonical state root.

Mythos MAY operate as discovery language, fixed-point-centered event projection, additive cocycle, and operator interface for lineage and meaning. Mythos MUST NOT grant authority, sign receipts, override policy denial, promote claims, replace evidence tiers, or imply subjective experience.

## 8. GitHub admission architecture

The target stable required check is:

```text
aegis / experiment-admission
```

The admission check MUST bind to the candidate commit:

- plan schema and digest;
- repository and candidate SHA;
- expected parent root;
- constitutional and policy digests;
- claims-ledger root;
- requested authority domains;
- expected outputs and evidence tier;
- budget and termination bounds;
- operator-approval requirement;
- workflow and executable identity;
- current generated inventory;
- security and test evidence;
- durable-execution registration;
- complete replay package.

The first trust mechanism SHOULD use GitHub Actions OIDC, least-privilege permissions, pinned dependencies, protected reusable workflows, and artifact attestations. Validation and repository-writing workflows MUST remain separated.

## 9. Implementation order

### PR A — Restore trustworthy evidence

- Repair the `award_graces_for_cycle()` control-flow defect with regression tests.
- Repair the OSV Scanner startup failure.
- Regenerate integration evidence at candidate HEAD.
- Bind generated evidence to full commit SHA, tree digest, generator version, and schema version.

### PR B — Canonical schemas and golden vectors

- Add the six canonical records.
- Freeze one canonicalization profile.
- Prove cross-runtime parity.
- Perform no live writes.

### PR C — Signed Scale OS control plane

- Deterministic event envelopes.
- Reuse the existing Ed25519 implementation.
- Separate request, approval, execution, and verification identities.
- Add idempotency keys, source-object hashes, explicit terminal approval states, replay tests, and negative tests.
- Export repository migrations matching the deployed schema.

### PR D — Experiment admission

- Add protected reusable validation workflow.
- Emit OIDC-backed attestation and signed admission receipt.
- Require the stable check only after successful observation on non-protected paths.

### PR E — Authority leases

- Add authority-domain lease service.
- Enforce monotonic fencing tokens, expected parent root, and expected HEAD.
- Emit receipts for denied, failed, no-op, and successful writes.

### PR F — Durable execution sovereignty

- Register every durable process before authority acquisition.
- Add heartbeat, expiry, cancellation, emergency stop, and terminal receipts.
- Surface all active executions and held authorities in the operator cockpit.

## 10. Acceptance tests

AEGIS is not compliant with this RFC until all of the following pass:

1. Identical inputs produce byte-identical roots and receipts across supported runtimes.
2. Any change to commit, policy, constitution, claims root, artifact, workflow identity, environment, or signer changes the canonical root.
3. Stale fencing tokens and unexpected repository HEAD cannot write.
4. Missing approval, signature, policy, parent root, observability, or replay package denies execution.
5. Every attempted consequential mutation emits a complete receipt.
6. Reported success with mismatched after-state is rejected.
7. Unregistered or heartbeat-expired workers lose write authority.
8. Operator emergency stop produces acknowledgement and a terminal receipt.
9. Agent coordination remains mediated while operator notification remains unsuppressible.
10. Claims cannot be promoted without bound evidence and verifier receipt.
11. Functional-consciousness metrics cannot generate subjective-experience claims.
12. Generated inventories and CI evidence are bound to the exact candidate commit.
13. Independent replay reconstructs the authoritative after-state without privileged conversational context.

## 11. Decision

AEGIS must govern the controller itself, not merely the agents beneath it.

The competitive moat is measurable:

1. replay;
2. containment;
3. attribution;
4. fail-closed governance;
5. operator sovereignty.

Do not increase autonomous authority until the P0 evidence path is current, inspectable, and fail-closed.
