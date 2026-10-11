# AEGIS UWP-13 — Single-use research evidence admission v1

Scope: existing DRAFT PR #766; issues #765 and #757. CANDIDATE only, NOT_ADMITTED. This module is neither a production authorization gate nor proof that a website was visited.

## Reproduced threat

The existing pure research_intelligence.evaluate function returns READY_FOR_INDEPENDENT_TEST repeatedly for the same valid HMAC v2 snapshot, task ID, exact Git repo SHA and source ID. Task/head/source binding blocks relabeling but NOT reuse of the original complete signed record. Signatures do not demonstrate that a new independent observation occurred.

References:
- OWASP Verifying Third-Party Agent Execution Evidence: https://cheatsheetseries.owasp.org/cheatsheets/Verifying_Third_Party_Agent_Execution_Evidence_Cheat_Sheet.html
- SLSA Verifying Artifacts: https://slsa.dev/spec/v1.2/verifying-artifacts

## Actual implementation

scripts/research_admission.py exposes a separate explicit admit_once gate, leaving the original evaluator PURE and read-only.

* First verify entire existing signed capture receipts, source and task/head/source binding, UTC freshness and diversity. Require all proposals to qualify.
* Hash each unique qualifying complete signed capture; store only its digest, packet SHA, task/head and times in an owner-protected local SQLite journal. Do not store capture body, website text or keys in the DB.
* Use BEGIN IMMEDIATE, SQLite synchronous=EXTRA and a unique primary key inside one transaction. Reuse of ANY consumed capture rejects the complete later request. A failure between insertions rolls back the transaction. Multiple proposals in ONE packet can share a citation without consuming twice.
* Require an absolute file path ending in .sqlite3 inside a mode-0700 owner-owned parent; refuse untrusted/symlink/publicly readable DB files. Create database at mode 0600.
* CLI refuses execution until the operator supplies --allow-ledger-write. This is an explicit local disk mutation, not a background task, production write, checkout, web request or deployment.

The output status ADMITTED_ONCE_FOR_INDEPENDENT_TEST only means locally processed by this one ledger. Fields remain source_truth=NOT_VERIFIED; actual_execution=NOT_INDEPENDENTLY_OBSERVED; operator_authority=NOT_GRANTED; deployment_authority=NONE.

## Native replay

From the exact PR head:

  PYTHONWARNINGS=error::ResourceWarning python3 -m unittest discover -s scripts -p 'test_research*.py' -q

Local Python 3.13.5: 137/137 unittest PASS; 18 new anti-replay tests, including 1/12 winning thread claims and 1/4 winning independent CLI processes, durable repeat rejection, simulated interruption inside a transaction, rollback, permissions, symlink denial, no file creation on unready packet, and no local key/excerpt recorded. Existing 119 tests remain green. Tested source blobs must match the PR exact head.

Production-like command syntax is documented for independently trusted operators only:

  python3 scripts/research_admission.py /secure/packet.json --trusted-key-file /secure/key --trusted-key-id collector-key-1 --ledger /secure/owner-only/evidence.sqlite3 --allow-ledger-write

Replays exit with EVIDENCE_ALREADY_CONSUMED. Missing write opt-in is denied.

## Claims this candidate DOES NOT establish

1. A research agent able to choose a new empty ledger, delete an existing ledger or control the verifier can bypass replay prevention. The ledger must be fixed and protected by a real isolated trusted runner, not selected from untrusted task data.
2. Tests prove SQLite transactional atomicity under an injected code exception and local concurrency; not sudden power-loss resilience, cross-host distributed consensus or immutable globally auditable logs. No off-host non-equivocation witness exists.
3. No fresh unpredictable challenge is issued by an independent verifier. Different newly signed receipts describing the same unchanged evidence remain possible. Introduce trusted nonce issuance and ledger consumption before promoting live freshness claims.
4. Signer and verifier share a symmetric HMAC key. Protected workload identity, credential isolation, key rotation, independent boundary observation and externally anchored event lineage are OPEN.
5. Genuine public HTTPS capture, user task quality, blind heterogeneous holdout evaluation (#757), hosted exact-head source tests, independent review, signed commit and protected-main admission all remain OPEN.

The original read-only evaluate() can still give repeated *preflight* READY results. The single-use guarantee applies ONLY to admit_once() when all attempts share ONE trusted persistent ledger. This distinction is an invariant, not a fallback.
