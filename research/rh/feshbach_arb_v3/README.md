# Feshbach certificate at L = 9/5: integer inputs, parity split, two fail-closed checkers (v3)

Extends `research/rh/feshbach_arb_v2/L1.8` (commit 0c1477fb, branch `research/rh-krein-receipt-v2-l105-convergence`).
Claim class: interval arithmetic and exact integer arithmetic, **not Lean, not RH**.

Claim: Q(G) ≥ μ‖G‖² for every moment-zero G in L²[0, 9/5], prime powers 2, 3, 4, 5, with

| Certificate | Blocks | μ certified | First μ refused |
|---|---|---|---|
| v2 receipt (mixed weights, `schur_arb.py`) | 799 | 4e-17 | 4.2e-17 |
| joint, weights g0 (`TAIL_WEIGHTS=global`) | 799 | **4.21e-17** | 4.22e-17 |
| parity split, g0 renormalised per sector (p/P) | 400 + 399 | **4.23e-17** (even binds; odd passes 5e-17) | 4.24e-17 |
| joint, external V9 weights | 799 | 4.05e-17 | 4.1e-17 |

Both checkers (`schur_mid.py` and `cert_congr.py`) give the same verdict for every row. Ceiling for N = 400 with any
tail weights: about 4.31e-17, because `Rout(u₁)` alone is 70 % of `C_B(u₁)` (v2 analysis). More needs a larger N or c_∞.

## What changed against v2

1. **Integer τ layer.** `tau80/` computes α_n (n ≤ 16000) and the diagonal CC/XC in fixed point (2^120, directed rounding) instead of digamma. `reproduce.sh` regenerates both input files first (~20 s) and checks their pinned sha256 (d5374e04…, efae4a0a…); they are not committed.
2. **KS tail.** The |n| > NP tail now adds a rigorous majorant for the terms k ≥ 200 of the geometric series.
3. **Parity split** (`src/v8p.py`, the single block generator; without `PARITY_*` it produces the joint blocks).
   - Reflection n → −n leaves Q invariant, so the even and odd sectors decouple. Every tail atom has definite parity (asserted), so τ(v) = τ(v_e) + τ(v_o).
   - Each sector gets its own weight budget. Renormalising the joint weights cannot lose: that is `schur_renorm` in Lean (`CvSTailRenormV1`).
   - `PARITY_STREAM=1` evaluates only rows n > N and doubles: `RRe = 2Σ(R_nB_e)ᵀ(R_nB_e)`.
   - The generator aborts unless α is odd for every n ≤ NP and `Qb` is reflection-invariant. The negative controls `PARITY_BREAK`/`PARITY_BREAK_OUT` must abort.
4. **c_∞ is bound.**
   - Both checkers take a manifest that pins the blocks' sha256 and derive `c_∞ ≤ m − trPTP_upper` from `inputs_L18/krein_slack.log` (m = 1.05 CERTIFIED) and `inputs_L18/trace_arb.json`. Both are copies of the v2 files, with the same sha256 as in the v2 receipt.
   - `schur_mid.py blocks c_inf mu` without a manifest never exits 0.
5. **Two checkers.**
   - `schur_mid.py` (Rump): Arb Cholesky of `mid(S) − r·I`, with r ≥ ‖S − mid(S)‖₂.
   - `cert_congr.py`: exact integers only. T S Tᵀ for an untrusted lower-triangular integer T (FLINT `fmpz_mat`), then Gershgorin.
   - `tests/test_certifiers.py` covers both, including the counterexample A_M = [[1, M], [M, M² + 1]], M = 1e14 (pivots 1, yet radius 1e-28 admits an indefinite member). It must refuse 1e-28 and accept 5e-29.

## Reproduce

```
bash reproduce.sh            # tau80 inputs, four block sets, sha256 vs manifests, both checkers, refusals, tests
bash reproduce.sh split check
```

Needs python3, python-flint 0.9.0 and numpy. Each block set takes about 3 min and 0.75 GB. `cert_congr.py` on the 799 block takes about 75 s per μ and 1.6 GB.
Blocks (130 MB each) are not committed; the manifests pin their sha256 and `reproduce.sh` rebuilds them byte-identically.
`runs/*/` keeps the original logs.

## Lean (`lean/`, kernel-checked with `--trust=0`)

Lean v4.33.1, Mathlib `0df444a3` (the formal-conjectures toolchain). `#print axioms` lists only propext, Classical.choice and Quot.sound for every theorem; the logs are in `lean/*.trust0.log`.

- `CvSTailRenormV1`: `schur_mono`, `renorm_eq`, `schur_renorm`, `schur_renorm_sum`. Renormalising tail weights p ↦ p/P (P ≤ 1) can only enlarge the Schur matrix, so a per-sector budget never loses against the joint one.
- `CvSParitySplitV1`: `cross_zero` (Beᵀ S Bo = 0 when Pᵀ S = S P, P Be = Be, P Bo = −Bo), `blocks_posSemidef`, `congr_posSemidef` (Tᵀ S T ⪰ 0 for S ⪰ 0).

These are the abstract linear-algebra steps. That the actual band matrix commutes with the reflection is checked in Arb by `v8p.py` (asserted entrywise), not in Lean.

## Not machine-checked

- **From v2:**
  - CvS matrix = restricted Weil form on the trigonometric basis;
  - hat Krein pairing;
  - Feshbach inequality;
  - order-8 weighted Cauchy–Schwarz bound for |n| > NP.
- **New:**
  - the reflection invariance of the actual matrices (Arb assertion, not Lean);
  - the sector tail split τ(v) = τ(v_e) + τ(v_o).
