# AEGIS Pocket Auditor V1

Status: **DRAFT / MONETIZATION LANE**

## Product

AEGIS Pocket Auditor is a small iOS/macOS audit layer built on the existing
fail-closed `GemmaEdge` constitutional verifier.

The free path performs local verification and emits a bounded report.

The premium path may expose deeper replay/report guidance only when the
RevenueCat entitlement `pocket_auditor_pro` is active.

An entitlement never changes the underlying constitutional verdict.

## Revenue boundary

Implemented:

- RevenueCat Swift Package dependency.
- `PocketAuditorCore` free/premium report boundary.
- `PocketAuditorRevenueCat` entitlement checker.
- RevenueCat failures or configuration errors fail closed to **no premium access**.
- Hosted Swift replay on exact code-bearing head
  `bfc89603cb2934e6c2e8cb0b7b0f6cb09abf6b36`.

Not yet configured:

- RevenueCat project.
- App Store / StoreKit product.
- RevenueCat entitlement/offerings in a live dashboard.
- Paywall UI.
- Store release.
- Any real purchase.

## Intended commercial funnel

```
free local audit
    ↓
evidence-limited findings
    ↓
Pocket Auditor Pro entitlement
    ↓
premium replay/report guidance
    ↓
optional Aegis Omega Labs Agent Action Boundary Audit
```

The paid mobile entitlement must never grant repository, signer, deployment,
payment, or other execution authority.

## Hackathon relevance

The implementation is suitable as the software core for a RevenueCat Shipaton
submission once the event registration/eligibility requirements and RevenueCat
project configuration are completed. Submission claims must remain limited to
what is actually implemented and demonstrated.
