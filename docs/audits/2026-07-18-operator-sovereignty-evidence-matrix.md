# AEGIS Operator-Sovereignty Evidence Matrix — 2026-07-18

**Status:** Verified gap analysis against `Aegis-Omega/AEGIS-OMEGA` at `31bcb7ef93d27d3c101694347f3638796162be21`  
**Purpose:** Convert the operator-sovereign architecture into an evidence-bound implementation sequence.  
**Mutation boundary:** This document authorizes no merge, deployment, IAM change, database permission change, outbound message, publication, spending, or destructive action.

## Executive determination

AEGIS contains substantial deterministic replay, state-root, fixed-point, constitutional-checking, and cryptographic-verification primitives. Those primitives are not yet composed into one authoritative control plane governing every consequential transition.

The present maturity assessment is:

```text
Replay substrate:                 strong, fragmented
Operator-sovereign control plane: specified, not implemented
Canonical physical provenance:    incomplete
Single-writer enforcement:        not found
Durable execution visibility:     not unified
Admission evidence:               currently unreliable on P0 paths
```

## Evidence-quality rules

This matrix uses the following classifications:

- **T0 — Verified:** Mechanically established by code, tests, signed artifacts, or independently reproducible execution.
- **T1 — Observed:** Empirically observed in repository or CI state, but not universal or formally proved.
- **T2 — Engineering precursor:** Implemented or specified with bounded evidence, but not production proof.
- **U — Unresolved:** The artifact exists, but exact deployment, identity, execution, or proof binding is missing.

A prose claim is not accepted as implementation evidence. A passing test is not accepted as deployment evidence. A generated artifact is not current unless its source commit is an ancestor of, or exactly equal to, the evaluated commit.

## Invariant matrix

| Invariant | Existing evidence | Current tier | Material gap | Admission test required |
|---|---|---:|---|---|
| One canonical state root | `sovereign-omega-v2/src/ledger/state-capsule.ts`, `block.ts`, node checkpoints and epoch seals bind local ledger state | T2 | No single root binds repository commit, constitutional bundle, claims ledger, policy, deployed artifact, workflow identity, environment and signer | Cross-runtime golden vectors produce byte-identical `CanonicalStateRootV1`; every consequential receipt references the exact root |
| One writer per authority domain | Expected-HEAD behavior exists in normal Git operations; isolated worktrees are documented | U | No repository-wide authority lease service, monotonic fencing token, expiry or stale-writer rejection was found | Concurrent-writer test proves the lower fencing token and unexpected HEAD cannot mutate state |
| Fail-closed consequential execution | Constitutional gates, frozen-file membrane and selected database assertions exist | T1/T2 | Enforcement is not uniform; CI can fail before jobs start, and some runtime helpers explicitly fall back or continue | Required admission check denies on missing verifier, unsigned event, stale root, missing approval or unavailable observability |
| Complete mutation receipts | Ledger entries and replay records capture hashes, sequence and governance decisions | T2 | Actor, model, session, physical executor, workspace, authority, tool, target, before/after state, authorization and operator notification are not bound in one receipt | Schema test rejects any successful consequential result without a complete signed `MutationReceiptV1` |
| Visible durable execution | GitHub Actions, scheduled tasks, cloud workers and sessions expose provider-specific run state | U | No unified registry, heartbeat, held-authority view, cancellation control or terminal receipt | A worker cannot acquire or retain write authority without a live `DurableExecutionRecordV1` |
| Law of Silence with operator channel | Autonomous swarm mediates downstream context through a shared artifact store | T1 | No formal privileged channel guarantees operator notification, audit emission, safety escalation and emergency-stop acknowledgement | Tests prove agent communication remains mediated while operator and verifier notifications cannot be suppressed |
| Capability separated from assurance | Constitutional substrate explicitly limits scope and marks epistemic tiers | T1/T2 | Runtime, product copy and generated analysis still contain claims whose evidence package is not machine-bound | Claims admission rejects publication or high-assurance use when claim tier exceeds evidence tier |

## P0 blockers

### P0-1 — Integration Ledger is not admissible current-state evidence

`INTEGRATION_LEDGER.md` identifies `6646a7ac` as its generating commit. GitHub comparison against current `main` shows that commit and `31bcb7ef` have diverged, with merge base `05249ad`; the generated ledger therefore cannot be treated as a current commit-bound inventory.

**Impact:** Any governance decision using its `WIRED`, `LINKED`, `DORMANT`, or `ORPHAN` counts can be wrong for current `main`.

**Required repair:**

1. Regenerate the ledger from the candidate commit inside CI.
2. Embed full commit SHA, tree digest, generator version and schema version.
3. Fail the admission check when the embedded commit differs from `GITHUB_SHA`.
4. Publish the generated ledger and machine-readable JSON as workflow artifacts.
5. Prevent hand-edited status promotion.

### P0-2 — Grace-chain mutation helper is structurally broken

In `sovereign-omega-v2/python/platform_helpers.py`, `award_graces_for_cycle()` terminates after the quarantine guard. The intended Supabase RPC loop is located inside `query_fitness_trend()` after that function begins.

**Impact:** APPROVED and FLAG cycles do not execute the documented grace chain, while an unrelated read-only fitness function contains misplaced write logic and variables outside its declared contract.

**Required repair:**

1. Restore the RPC setup and loop inside `award_graces_for_cycle()`.
2. Keep `query_fitness_trend()` read-only and return a dictionary consistently.
3. Add tests for APPROVED, FLAG, QUARANTINE, empty artifacts, missing configuration and RPC failure.
4. Assert exact request count and ordered `from_dept -> to_dept` payloads.
5. Do not deploy the repair in the same change as the sovereign-control RFC.

### P0-3 — OSV Scanner starts no jobs on open PRs

The OSV workflow concludes `startup_failure` on PR #201 and PR #203, and GitHub reports no jobs for the failed runs.

**Impact:** Dependency-vulnerability evidence is absent even though the check appears in the workflow set. A missing scanner cannot count as a passing security gate.

**Required repair:**

1. Inspect the GitHub Actions reusable-workflow startup error with authenticated `gh` logs or API metadata.
2. Pin a valid immutable action or reusable-workflow reference.
3. Verify required permissions and event compatibility.
4. Add a minimal workflow syntax/dispatch validation path.
5. Require a real OSV job result before admission.

### P0-4 — Scale OS control-plane events are unsigned

The Scale OS handoff records that current events are audit records, not cryptographically signed envelopes.

**Impact:** Events cannot yet serve as tamper-evident authorization, execution or verification records.

**Required repair:** Implement deterministic event canonicalization, reuse the existing Ed25519 path, separate request/approval/execution/verification identities, and test replay, tamper, duplicate and invalid-state transitions.

## Quantified evidence posture

The seven non-negotiable areas above currently classify as:

| Classification | Count | Share |
|---|---:|---:|
| T0 complete | 0 | 0% |
| T1/T2 partial | 4 | 57% |
| Unresolved/not unified | 3 | 43% |

This is not a score of overall repository quality. It measures only whether each operator-sovereignty invariant is implemented end to end across the consequential execution boundary.

## Ordered implementation program

### Slice A — Restore trustworthy evidence

- Repair OSV startup failure.
- Regenerate the Integration Ledger at candidate HEAD.
- Repair and test grace-chain control flow.
- Add commit-bound evidence metadata.

**Exit condition:** CI produces complete, current, inspectable evidence; missing evidence fails closed.

### Slice B — Establish canonical schemas

Implement versioned schemas and golden vectors for:

- `CanonicalStateRootV1`
- `AuthorityLeaseV1`
- `ApprovalRecordV1`
- `MutationReceiptV1`
- `DurableExecutionRecordV1`
- `OperatorNotificationV1`

**Exit condition:** Python, TypeScript and Rust implementations agree on canonical bytes and hashes.

### Slice C — Sign the Scale OS control plane

- Deterministic event envelope.
- Existing Ed25519 adapter.
- Explicit approval lifecycle.
- Idempotency and source-object hashes.
- Repository migrations matching deployed schema.

**Exit condition:** Unsigned, duplicate, stale-parent and invalid-approval events are rejected.

### Slice D — Enforce single-writer authority

- Lease service per authority domain.
- Monotonic fencing tokens.
- Expected-parent-root and expected-HEAD checks.
- Expiry, revocation and denied-attempt receipts.

**Exit condition:** Concurrent hidden mutation is mechanically prevented.

### Slice E — Govern durable autonomy

- Registration before authority acquisition.
- Heartbeat and expiry.
- Operator-visible status and held authorities.
- Cancellation and emergency stop.
- Terminal receipt.

**Exit condition:** No remote or persistent process can remain operationally invisible while retaining write authority.

## Stable admission check

The target required check is:

```text
aegis / experiment-admission
```

It must deny admission unless all of the following resolve to the candidate commit:

- current generated inventory;
- constitutional and policy digests;
- claims-ledger root;
- signed approval state;
- requested authority domains;
- expected parent root and repository HEAD;
- workflow and executable identity;
- test and security evidence;
- operator-observability registration;
- complete replay package.

## Current decision

Do not increase autonomous authority yet. First make the evidence path current and fail-closed. The next code PR should be the smallest independently testable P0 repair, followed by signed Scale OS envelopes and the authority-lease protocol.
