# AEGIS Ω — Tokenized Evolution Contract / Local Lifecycle v1

Scope: **offline, branch-only, non-executing. Not an on-chain smart contract**.
Extends the existing agents/evolution_contract_spine.py and its
AEGIS_INFORMATIONAL_EVOLUTION_TOKEN_V1, rather than adding another coordinator,
authority system, cryptocurrency, or learning engine.

## Existing work reused

- #734 work board and #749 typed work DAG
- #746 exact-head delivery, #752 existing AuthorityEvaluator
- #753 provenance, #754 capability routing, #755 independent review
- #757 independently measured outcomes, #758 candidate evolution
- agents/issue_evolution.py, dendrite_workplane.py, dendrite_system.py,
  evolution_contract_spine.py, evolution.py

The existing spine mints **informational content hashes**, not permissions.
A hash alone cannot prevent event replay, identify the signing relay,
distinguish proposer from verifier or prevent truncated revocation history.

## Local token contract

Actions are closed and role-bound:

| Event | Key role | Transition |
| --- | --- | --- |
| REQUEST_REVIEW | proposer | OBSERVED_UNVERIFIED → LOCAL_REVIEW_REQUESTED |
| ATTEST_LOCAL_REVIEW | verifier | LOCAL_REVIEW_REQUESTED → LOCAL_REVIEW_ATTESTED_EXTERNAL_ADMISSION_REQUIRED |
| REVOKE | operator | Any live state → REVOKED_NOT_ADMITTED |

The verifier must use a **different actor and key** from the proposer. A local
HMAC proves only possession of the secret, not independent GitHub/user identity.
A revoked token cannot be reinstated by another event in the **complete replay**.

No PROMOTE, GRANT, TRANSFER, MERGE, DEPLOY, SETTLE, spend or capability
operation exists. Every result continues to state:
admission=DENIED; promotion_applied=false; capability_granted=false;
authority_effect=NONE; execution_effect=NONE.

The signed event binds: issue, token ID, source HEAD, action, actor, key ID,
evidence SHA256, nonce, per-token sequence, previous-event hash, issued_at,
expires_at, and explicit NONE operational effects. HMAC-SHA256 uses a fixed
domain prefix and operator-provisioned secrets of at least 32 bytes.

## Two separate trust anchors

1. trusted_spine_hash is supplied by the caller from an **independently
   trustworthy source**. The reducer rehashes the entire spine and each token,
   rejecting escalation fields and mismatched issue/source/graph roots.
2. trusted_journal_digest, when independently pinned, detects journal
   modification or history truncation. If absent, the reducer explicitly returns
   UNANCHORED_NO_ROLLBACK_PROTECTION. A hash computed by the same untrusted
   producer does not protect against a forged or deleted revocation.

EXTERNAL_DIGEST_MATCHED means byte consistency with the supplied digest,
**not** the authenticity of its origin, a true blockchain audit, or consensus.

## Reproduction

Run these from the isolated PR #773 checkout:

    PYTHONPATH=. python3 -m unittest agents.tests.test_evolution_token_lifecycle agents.tests.test_evolution_token_lifecycle_integration -v

Python API (keys provisioned independently outside Git and logs):

    from agents.evolution_token_lifecycle import evaluate_lifecycle
    state = evaluate_lifecycle(
        spine, events, trusted_spine_hash=trusted_spine_hash,
        trusted_keys=trusted_keys, now=logical_timestamp,
        trusted_journal_digest=anchored_journal_sha256,
    )
    assert state["admission"] == "DENIED"

The spine must be produced with the existing compose_spine(...) and its
source/issue data independently verified. These are pure functions: no GitHub
write, network, wallet, registry mutation, agent dispatch, or kernel invocation.

## Known limits and stop rules

- Stateless replay cannot guarantee historical completeness without a
  separate immutable journal or trusted checkpoint. A fresh root submitted
  alongside attacker-modified history provides **no** protection.
- HMAC is shared-key authentication only. No public-key/real-person identity,
  multi-party key custody, trusted clock, production token registry or blockchain.
- Claims about independently verified benchmarks, Lean proofs, model competence,
  operator approval or tier promotion are NOT established.
- Native exact-head CI must actually execute; skipped/zero-step work is
  NOT_VERIFIED. Commits must satisfy signed/protected-main admission and
  independent review before any merge.
- No automatic action from these tokens. Existing AuthorityEvaluator is the
  only execution-authorization authority.


## v1.1 — Operator checkpoint with historical observation-time binding

Problem reproduced using the old implementation:
- A valid REQUEST_REVIEW at logical time 100, expiring at 110, followed by
  an operator REVOKE is correctly replayed at 100 and 110.
- Auditing that same signed history at time 111 or 200 returned EVENT_EXPIRED.
  This conflated historical event validity with current wall-clock freshness
  and prevented durable replay of revocation.

Small repair to the existing agents/evolution_token_lifecycle.py:
- Default no-checkpoint behavior remains fail-closed; expired events supplied
  to a fresh unanchored evaluation still fail.
- The optional trusted_observation_times list binds the timestamp when
  each event was accepted. Historical replay evaluates each event at that
  observed time. Times must be integer, monotone, bounded by audit now, and
  digest-bound to the exact journal.
- Both trusted_journal_digest and trusted_observations_digest are required.
  A caller-supplied digest BY ITSELF is NOT an authenticated time oracle.
  Do not pass timestamps and hashes copied from the same untrusted input and
  call them trusted.

The new agents/evolution_token_checkpoint.py creates and verifies an operator
HMAC-SHA256 checkpoint on top of existing Issue contract and token reducer.
It covers the exact issue-spine root, entire journal hash, all event observation
times, deterministic resulting state hash, checkpoint sequence, previous
checkpoint ID, signing key ID and logical as_of. It recomputes source state
during independent read-back and refuses key reuse between token actors and
the operator checkpoint signer.

Successor checkpoint rules:
- An independently saved previous checkpoint ID must be provided.
- The previous checkpoint MAC and state are replayed and verified.
- Exact old events and observation times must remain byte-equivalent in the
  prefix of the successor journal.
- At least one new event is required; times cannot regress.
- Revoked tokens remain terminal. No agent permission is granted.

The public API is:

    from agents.evolution_token_checkpoint import seal_checkpoint, verify_checkpoint
    checkpoint = seal_checkpoint(
        spine, events, observed_at,
        trusted_spine_hash=trusted_spine_hash,
        trusted_event_keys=keyring,
        checkpoint_key_id="separate_operator_checkpoint_key",
        checkpoint_secret=operator_checkpoint_secret,
        as_of=recorded_logical_time,
    )
    checkpoint_id = checkpoint["checkpoint_id"]
    # Independently pin checkpoint_id and secure its operator checkpoint key.
    # Do NOT derive the trusted ID from an attacker-provided checkpoint when
    # reading it. The digest must originate in a separate trusted channel.

    receipt = verify_checkpoint(
        spine, events, observed_at, checkpoint,
        trusted_spine_hash=trusted_spine_hash,
        trusted_event_keys=keyring,
        trusted_checkpoint_keys={"separate_operator_checkpoint_key":
                                 operator_checkpoint_secret},
        trusted_checkpoint_id=checkpoint_id_from_independent_trusted_record,
    )
    assert receipt["production_admission"] == "DENIED"

Use separate operator event and checkpoint keys; do not check either secret
into Git, CI logs, issue text, or this document.

To run the original 33 token tests and 25 new historical checkpoint tests:

    PYTHONPATH=. python3 -m unittest \
      agents.tests.test_evolution_token_lifecycle \
      agents.tests.test_evolution_token_lifecycle_integration \
      agents.tests.test_evolution_token_checkpoint -v

Security and operational limits:
- No separate immutable/WORM storage or trusted timestamping service is
  provisioned by this change. The checkpoint ID MUST be durably retained in
  another trusted channel; otherwise rollback is not prevented. No actual
  cloud/on-chain anchoring is claimed.
- A checkpoint MAC authenticates only a local shared-secret holder, not the
  GitHub author, original witness, independent reviewer, or external truth.
- The operator must capture reliable observation times when ingesting events;
  an after-the-fact signer can certify a false timestamp if the operator
  itself is malicious or compromised. There is no secure clock oracle.
- This v1.1 does not implement trusted key rotation; a successor verifies
  the predecessor using the same checkpoint key.
- Even a successful verifier result means only LOCAL_OPERATOR_CHECKPOINT_MAC_VERIFIED.
  AuthorityEvaluator, independent proof review, signed commits, and protected
  main admission are not bypassed.
- This remains a candidate PR until native exact-head tests actually run;
  zero-step/skip checks do not count as PASS.


## v1.2 — Local atomic CAS checkpoint store (not external anchoring)

A real POSIX filesystem module is now available at
agents/evolution_checkpoint_store.py. It extends, rather than replaces,
the existing seal_checkpoint() and verify_checkpoint() pure reducers.

### What is implemented

publish(root, spine, events, observed_at, checkpoint, *,
expected_current_id, trusted_spine_hash, trusted_event_keys,
trusted_checkpoint_keys):

- Accepts ONLY an absolute, private, current-user-owned store path.
  Root and objects/ are 0700; lock, head and snapshot objects are 0600.
  Nonregular files, unexpected hard links and direct symlinks are denied.
- Uses a dedicated fcntl.flock over .anchor.lock to serialize processes.
- Reads the current HEAD and compares it to operator-supplied
  expected_current_id. Stale writers fail ANCHOR_COMPARE_AND_SWAP_CONFLICT.
- Replays the existing stored checkpoint with supplied trusted keys before
  accepting a successor. The successor must preserve exact prior events and
  recorded observation times; a signed but rewritten history is rejected.
- Verifies new checkpoint MAC, journal, state, source-spine and predecessor.
- Writes the snapshot as a content-addressed 0600 object using fsync and an
  exclusive hard-link; publishes HEAD using atomic replace and directory
  fsync. If a process crashes after writing the object but before replacing
  HEAD, retry accepts ONLY byte-identical orphaned data.
- Returns LOCAL_ATOMIC_CAS_COMMITTED_NOT_EXTERNALLY_ANCHORED,
  admission=DENIED, authority_effect=NONE and execution_effect=NONE.

read_pinned(root, spine, *, trusted_head_id, trusted_spine_hash,
trusted_event_keys, trusted_checkpoint_keys):

- Requires the caller to supply a separately retained trusted HEAD ID.
- Rejects an old HEAD, missing or tampered snapshots, unsafe files or a
  mismatched sequence; independently replays the current checkpoint.
- Returns LOCAL_PINNED_SNAPSHOT_MATCHED_NOT_EXTERNAL_PROOF.

### Example

Local API usage, with keys and independently stored HEAD ID outside the local
writable directory:

    from pathlib import Path
    from agents.evolution_checkpoint_store import publish, read_pinned
    # spine / events / observed_at / checkpoint are outputs of existing modules.
    receipt = publish(
        Path("/private/operator/aegis-evolution"),
        spine, events, observed_at, checkpoint,
        expected_current_id=previous_head_from_independent_store,
        trusted_spine_hash=independently_verified_spine_hash,
        trusted_event_keys=trusted_event_keys,
        trusted_checkpoint_keys=trusted_checkpoint_keys,
    )
    next_head_id = receipt["checkpoint_id"]
    # Deliberately save next_head_id to a DIFFERENT, trusted medium.

    replay = read_pinned(
        Path("/private/operator/aegis-evolution"), spine,
        trusted_head_id=head_id_from_independent_store,
        trusted_spine_hash=independently_verified_spine_hash,
        trusted_event_keys=trusted_event_keys,
        trusted_checkpoint_keys=trusted_checkpoint_keys,
    )
    assert replay["admission"] == "DENIED"

### Reproduction

    PYTHONPATH=. python3 -m unittest agents.tests.test_evolution_checkpoint_store -v

The local collection with the previous lifecycle/checkpoint tests totals 86:

    PYTHONPATH=. python3 -m unittest agents.tests.test_evolution_token_lifecycle agents.tests.test_evolution_token_lifecycle_integration agents.tests.test_evolution_token_checkpoint agents.tests.test_evolution_checkpoint_store -v

### Explicit trust limits

1. This is same-user local durability, NOT a third-party notary, trusted
   timestamp, immutable WORM storage or deployed smart contract. An attacker
   with complete user, filesystem or operator-key control can replace the
   entire store. A latest-ID pin held separately can expose that reversal,
   but no such independent external medium is provisioned by this module.
2. expected_current_id / trusted_head_id must NOT be taken from untrusted
   local HEAD and returned as independent proof.
3. File checks do not protect against all malicious ancestor-directory
   substitution, kernel compromise, power-loss modes or device corruption.
   POSIX fcntl/fsync required; not portable to Windows.
4. Snapshot content is 0600 local plaintext; no encryption at rest.
5. No wallet, on-chain mint, agent dispatch, settlement, promotion,
   automatic CI admission, approval or protected-main merge.
6. Source graphs remain bound to the SAME frozen issue contract spine.
   Updating that spine requires a separate trusted migration process.
7. GitHub native exact-head Python checks must actually execute. A skipped
   job or zero-step check is NOT_VERIFIED.

This is a bounded incremental foundation for later independently anchored
notarization, not a claim that local files have blockchain immutability.
