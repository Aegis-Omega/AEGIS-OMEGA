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
