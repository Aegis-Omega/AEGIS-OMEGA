# AEGIS-Ω — the verifiable envelope, proven across two categories

**Tier: T2.** Constitutional law: `AdaptivePower(T) ≤ ReplayVerifiability(T)`.

The genomics proof (`../genomics/`) claimed its hash-chain envelope is stage-agnostic.
This directory makes that claim **concrete and tested**: the same envelope, applied to a
completely different domain, plus a cross-check that it is byte-identical to the genomics
one.

## Files

| File | What it is |
|------|-----------|
| `chain.py` | The domain-agnostic envelope — `canon()` (`aegis-integer-json-v2` → bytes, rejects float), `sha256_hex()`, `StageRecord`, `LineageChain` (append / `terminal_hash` / `certify`). The genomics proof inlines this for zero-dependency portability; here it is shared infra. |
| `compliance_pipeline.py` | A **regulated decision-audit** pipeline (`INTAKE → EXTRACT → SCORE → DECISION`) — AEGIS's stated market: EU AI Act Article 12 tamper-evident decision records. Integer scorecard, adverse-action reason codes, integer threshold. |
| `test_generality.py` | The proof. Exit 0 = all four claims hold. |

## What is proven

```
python3 verifiable/test_generality.py
[1] DECISION DETERMINISM   3 runs -> one terminal hash fd53645d33e5b097…
[2] DECISION TAMPER-EVIDENT forged outcome -> certify invalid, broken_at="DECISION"
[3] SCORE BINDING          an applicant crossing the threshold flips the terminal hash
[4] SAME ENVELOPE          genomics-inline canon+hash == shared canon+hash (byte-identical)
```

Claim [4] is the load-bearing one: it runs the **genomics** `canon`/`sha256_hex` and the
**shared** `canon`/`sha256_hex` on the same payload and asserts identical output, and
checks exact composed/decomposed Unicode, rejects unsupported values, and compares
whole stage hashes including the profile identifier across a two-stage chain.

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
  anchors  genomics=ab4c952b476a9d74… compliance=fd53645d33e5b097…
  PASS   genomics.determinism
  PASS   genomics.semantic_integrity
  PASS   genomics.governed_interpretation
  PASS   verifiable.generality
  PASS   verifiable.cross_runtime
chain certifies : True
session cert    : 0749d65b0642c0f1dcba2982bed797cf8635faf7a1ecf24ee83fda475927537b
reproducible    : True
```

The CI gate (`.github/workflows/verifiable-proofs.yml`) pins this session certificate and
asserts it is identical on Ubuntu x86-64 and macOS arm64 — so the whole proof substrate,
not just one hash, is checked for cross-platform reproducibility on every change.
Local v2 validation ran on Windows x86-64; the new Ubuntu/macOS matrix run must still pass.

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
        │  verifiable/chain.py          │  ← one primitive (v2 profile → SHA-256 chain)
        └───────────────┬──────────────┘
        ┌───────────────┴──────────────┐
   genomics variant caller      regulated decision-audit
   (REFERENCE…ANNOTATE)         (INTAKE…DECISION)
   + governed cached AI          + adverse-action codes
```

## v2 receipt migration

The shared and genomics-inline envelopes now use `aegis-integer-json-v2`, which
preserves exact Unicode and binds the profile identifier into every stage. This is
not full RFC 8785. All old unversioned stage, compliance and session hashes change;
historical receipts must not be relabelled as v2. The regenerated fixture and CI pins
come from successful Python/Node/Rust replay and two complete session runs.
The session now includes the 20 semantic integrity regression tests.

Cross-runtime replay deliberately supports only integers in JavaScript's safe range;
Python's general-purpose envelope accepts arbitrary integers. Replayers reject
missing/unknown profiles and the negative harness exercises profile, tamper, exact
Unicode and numeric rejection. Hashes bind recorded fields, not provider identity
or scientific/clinical authority, and require an independently trusted digest to
detect wholesale replacement.

On Windows, put Git Bash before WSL Bash on PATH when running `certify_all.py`.
It resolves that Bash executable and passes the current Python interpreter to the
replay script; direct `verify.sh` also accepts a `PYTHON` executable override.
