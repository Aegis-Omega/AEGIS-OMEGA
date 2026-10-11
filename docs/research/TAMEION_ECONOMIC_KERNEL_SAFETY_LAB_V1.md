# Tameion Economic Kernel + Transaction Safety Lab v0.1

## Exact upstream boundary

Proposed integration source: `Aegis-Omega/AEGIS-OMEGA` PR #700 head `ca76fdcec1f91b13264414f584981c95dcba69b3`. This proposal is **post-demo**, not part of the frozen Tameion 150/150 replay at `a812d3abdbb273254d7492723820852d6126f4cc`. It must not silently change the competition demo or represent new traction.

## Composition, not new authority

`audit_economic_boundary` consumes the existing `OpenMeterPaymentObligation`, `OpenMeterArcIntentBinding`, `ArcTransferPlan`, `ArcUnsignedTransferCall`, `TameionPreSettlementBundle` and `PolicyDecision`. It replays the existing source-to-plan binding, checks an externally pinned policy and authority/mutation evidence roots, and writes a deterministic finding. It does **not** construct an `ADMITTED` decision, authorize real value, sign, call Circle, broadcast, assert settlement, or replace `AuthorityEvaluator`.

The findings' `BOUNDARY_CHECKS_PASSED` means **only that the supplied synthetic/local inputs passed deterministic comparisons**, never that a wallet may spend. Its output explicitly declares `authority_effect=NONE`, `network_effect=NONE`, `settlement_asserted=false`, `scope=EVIDENCE_ONLY_NON_AUTHORITATIVE`.

## Test scope (Safety Lab)

The adversarial matrix covers pins/substituted decision/receipt, wrong authority context, recipient/network substitution, forged bundle, unsigned-call escalation, replay, reserved+spent demo budget overflow, capability escalation, malformed/floating amounts, and canonical capability identifiers. All tests are synthetic. No external calls or credentials.

## Live-operation gaps (fail closed)

- An independently trusted caller must obtain and authenticate all three pins. A self-referential hash is **not an authentic signature**.
- A production spend limit requires a durable, atomic and fenced reservation ledger, not caller-supplied spent/reserved integers; this is a deterministic simulation only.
- A production idempotency guarantee requires an external durable attempt store. `prior_attempt_ids` is an input, not a secure replay database.
- A caller-created `PolicyDecision` dataclass is not itself proof of an AEGIS admission; the real upstream authority evaluator and trusted registry must supply it.
- Formal verification and hosted exact-head replay are separate gates; local test results cannot assert production authority.
- Capability inspection must not rely solely on identifiers claimed by a vendor. A future sandbox/attestation verifier is necessary before actual activation.

## Replay

```bash
python -m unittest -v sovereign-omega-v2/python/tests/test_tameion_economic_kernel.py
```

Run on source where Tameion PR #700 dependency modules are present. Existing Tameion replay workflow should include this file as a separate, no-network step.

## v0.2: SQLite atomic reservation safety lab (PR #772 follow-up)

Added `0harness/sdk/tameion_economic_reservations.py` and
`0sovereign-omega-v2/python/tests/test_tameion_economic_reservations.py`.

- Single local SQLite database uses `0BEGIN IMMEDIATE` for mutually exclusive
  reservations, immutable per-scope budget and policy pin, and a monotone
  generation used for local fencing; no wallets, keys, custody, signer, RPC or
  broadcast logic is present.
- The journal retains all `0RESERVED`, `0OUTCOME_UNKNOWN`, and
  `0OBSERVATION_RECORDED` amounts against the scope budget; it **never**
  automatically releases an unknown payment. A stored observation root is only
  a digest of supplied evidence, not a verified claim of settlement or finality.
- Idempotency is scoped to `0(scope, attempt_id)`, with exact content
  replay and collision rejection. Each observation root can be used only once
  in this database. No claim of global cross-database uniqueness is made.
- `0reserve_tameion_evidence` recomputes existing Tameion boundary checks
  using **persisted** observed/reserved/unknown totals before attempting atomic
  reservation. Generation mismatch is denied: the caller must re-read and
  re-evaluate, never auto-submit or retry a transfer.
- This remains **local** SQLite evidence infrastructure. Each separately
  initialized database, filesystem lock failure, forged upstream policy pin or
  detached source adapter lies outside its guarantee. Real-value spending
  requires centrally enforced authority, authenticated upstream decisions,
  persistent provider reconciliation, secure fencing, and independently
  tested integration of the signer/broadcast boundary (currently absent).

Local tested independently: 24 SQLite reservation tests PASS including 12
concurrent threads, restart, replay collision, observation-reuse and unknown
holds. 29 synthetic Tameion compatibility tests PASS, of which two exercise the
new native OpenMeter/Arc + reservation bridge. **These are local tests, not
an exact-head GitHub-hosted native replay**. That status must be checked on the
exact PR commit and cannot be inherited from earlier Tameion evidence.

Run the new native test in a full checkout:

`0`0`0bash
python -m unittest -v sovereign-omega-v2/python/tests/test_tameion_economic_reservations.py sovereign-omega-v2/python/tests/test_tameion_economic_kernel.py
`0`0`0