# AEGIS Ω — Weekly Research Boundary Falsifier Intake

Status: IMPLEMENTATION-TEST SLICE / NO FROZEN-SCOPE REOPEN
Parent integration spine: `security/daybreak-blue-hardening-v1@05de13c499baf74470a9fb4d8b5aa0765b77210a`

This slice records an operator-supplied research intake as test inspiration only. External paper results are not promoted into AEGIS implementation claims. AEGIS claims in this slice are limited to exact code and test behavior on the candidate head.

## Frozen synthesis preserved

- Model output != Authority.
- Decision != Effect.
- Memory != Truth.
- Replication != Heritage.
- Multiple agents != Independent evidence.

## New falsifiers

1. Authorization composition: two actions may each be individually permitted while their accumulated sequence is denied; A→B→C delegation may only contract task-bound scope, action budget, and compute budget.
2. Effect-time freshness: a prior PERMIT becomes REVERIFY when policy-state root, authority epoch, or fence changes before the effect gate.
3. Memory non-amplification/non-revival: derived memory cannot exceed the weakest source tier/weight; source retraction transitively withholds derivatives, including after deterministic replay from genesis and attempted rewrite.
4. True heritage differential: a copied child without a committed parent-bound delta is replication-only; heritage requires exact independent reconstruction `Child = Apply(Parent, Delta)`.
5. Joint-failure evidence: redundancy/independence is never inferred from role names or provider diversity. Paired co-execution counts are recorded descriptively; this slice deliberately does not implement or claim a formal independence test or the literature's LP certificate.

## Explicit boundaries

- These tests do not establish universal delegation soundness.
- The effect-time freshness helper is a falsifier contract; it does not by itself make an external side effect transactionally atomic with policy-state mutation.
- Memory replay correctness here is a narrow deterministic reference model, not a world-truth guarantee.
- Reconstructible heritage proves lineage for the encoded genome/delta representation only; it does not establish open-ended self-replication or AGI.
- Joint-failure measurement does not prove independence. `independence_claim_admissible` remains false even when paired evidence exists.

The intended use is adversarial regression: if a future implementation violates any of these boundaries, the candidate must go RED rather than silently upgrading authority.
