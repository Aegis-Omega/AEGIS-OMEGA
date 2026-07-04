# AEGIS-Ω — the verifiable envelope, proven across two categories

**Tier: T2.** Constitutional law: `AdaptivePower(T) ≤ ReplayVerifiability(T)`.

The genomics proof (`../genomics/`) claimed its hash-chain envelope is stage-agnostic.
This directory makes that claim **concrete and tested**: the same envelope, applied to a
completely different domain, plus a cross-check that it is byte-identical to the genomics
one.

## Files

| File | What it is |
|------|-----------|
| `chain.py` | The domain-agnostic envelope — `canon()` (RFC 8785 → bytes, rejects float), `sha256_hex()`, `StageRecord`, `LineageChain` (append / `terminal_hash` / `certify`). The genomics proof inlines this for zero-dependency portability; here it is shared infra. |
| `compliance_pipeline.py` | A **regulated decision-audit** pipeline (`INTAKE → EXTRACT → SCORE → DECISION`) — AEGIS's stated market: EU AI Act Article 12 tamper-evident decision records. Integer scorecard, adverse-action reason codes, integer threshold. |
| `test_generality.py` | The proof. Exit 0 = all four claims hold. |

## What is proven

```
python3 verifiable/test_generality.py
[1] DECISION DETERMINISM   3 runs -> one terminal hash c67e7e8efd367644…
[2] DECISION TAMPER-EVIDENT forged outcome -> certify invalid, broken_at="DECISION"
[3] SCORE BINDING          an applicant crossing the threshold flips the terminal hash
[4] SAME ENVELOPE          genomics-inline canon+hash == shared canon+hash (byte-identical)
```

Claim [4] is the load-bearing one: it runs the **genomics** `canon`/`sha256_hex` and the
**shared** `canon`/`sha256_hex` on the same payload and asserts identical output, and
asserts both reject `float` in hashed state. So this is genuinely one primitive across two
categories — not two lookalikes.

## Why a loan/benefit decision, of all things

Because it is the same problem as the genomics one, in the market AEGIS actually targets. A
high-stakes automated decision is only defensible if its record is **reproducible** (an
auditor re-runs the inputs and gets the identical decision record) and **provably
un-edited** (no one changed the score or the outcome after the fact). Step [2] shows a
forged `DECISION` outcome is caught and localized; step [3] shows the record actually
depends on the decision, not just its shape.

## The substrate certifies itself

`certify_all.py` runs every proof in this substrate and folds the results into the same
hash chain, emitting one reproducible **session certificate** — the system eating its own
dogfood. Each proof contributes an integer exit code plus (for the two pipelines) its
deterministic terminal hash; there is no wall-clock or RNG, so the certificate is itself
deterministic.

```
python3 certify_all.py --twice
  anchors  genomics=f8cb0093b9b7447c… compliance=c67e7e8efd367644…
  PASS   genomics.determinism
  PASS   genomics.governed_interpretation
  PASS   verifiable.generality
  PASS   verifiable.cross_runtime
chain certifies : True
session cert    : 9b360cad56518c8a5a8c42ac2c97fe4bb17948bf1778b513f7c7db041ad6d142
reproducible    : True
```

The CI gate (`.github/workflows/verifiable-proofs.yml`) pins this session certificate and
asserts it is identical on Ubuntu x86-64 and macOS arm64 — so the whole proof substrate,
not just one hash, is confirmed cross-platform reproducible on every change.

## Honest scope

The scorecard is a toy — four features, fixed integer points. The claim is the audit
**envelope** (reproducibility + tamper-evidence + lineage), not that this is a validated
credit model. Same discipline as genomics: integer arithmetic only, sorted list-shaped
state, no dict-iteration order in the hashed payload, no wall-clock, no RNG. T2 → T1 is a
wrapping exercise: swap the toy stages for a real deterministic scorer; the envelope is
unchanged.

## The point

One envelope now carries two unrelated domains — a variant caller and a regulated
decision — with byte-identical guarantees. That is the generality behind "take any
trending wishlist; if its intermediate state can be canonicalized, this certifies it."
```
        ┌─────────────────────────────┐
        │  verifiable/chain.py          │  ← one primitive (RFC 8785 → SHA-256 chain)
        └───────────────┬──────────────┘
        ┌───────────────┴──────────────┐
   genomics variant caller      regulated decision-audit
   (REFERENCE…ANNOTATE)         (INTAKE…DECISION)
   + governed cached AI          + adverse-action codes
```
