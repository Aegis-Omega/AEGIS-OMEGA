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
