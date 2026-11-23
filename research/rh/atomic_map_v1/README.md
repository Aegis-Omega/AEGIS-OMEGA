# RH lab: atomic claim map, dependency graph, and one next step (2026-11-21)

**RH is not proved.** Nothing in this report proves it, and no edge below closes it.

This report covers four things:

* a classification of every load-bearing claim in the AEGIS RH chain into one of five evidence classes;
* the dependency graph, with each missing edge and what it lacks;
* a test of the operator's statement that mixed prime-power resonances at fixed width are the main obstacle;
* one proposed next step, with a sub-lemma small enough to formalize directly.

The modules are the operator's work. This report replays, classifies and measures them; it does not modify them.

## 0. What I ran myself

| what | where | result |
|---|---|---|
| `lean --trust=0` on the full import closure of `WeilSeparatedArchBridgeV31` (26 modules, `AegisRH/PR606/*.lean`) | formal-conjectures `ce4868fd`, Lean 4.33.1, Mathlib `0df444a3` (the `v4.33.1` cache) | **26/26 exit 0**, 0 errors ([`trust0_replay.tsv`](trust0_replay.tsv); source hashes in [`trust0_sources.sha256`](trust0_sources.sha256)) |
| `#print axioms` on 14 theorems of that chain, at `--trust=0` | [`scripts/Audit.lean`](scripts/Audit.lean) | every one is `[propext, Classical.choice, Quot.sound]` ([`trust0_axioms.txt`](trust0_axioms.txt)) |
| Feshbach L = 9/5: the integer τ layer (`tau80.py`, `diag80.py`) | copy of `research/rh/feshbach_arb_v3` | both input files match the pinned sha256 (`d5374e04…`, `efae4a0a…`) |
| Feshbach L = 9/5: block regeneration and both checkers | same | blocks byte-identical; both checkers certify and refuse as the receipt says (§6) |
| `lean --trust=0` on the new modules `WeilDiagonalLogGainS1` (Mathlib only) and `WeilDiagonalLogGainV1` (on the 26-module closure) | [`lean/`](lean/), 2026-11-22 | **both exit 0**, no warnings, no `sorry`; 11 theorems, all `[propext, Classical.choice, Quot.sound]` (§4.6) |
| Fixed-width comb probe (float64, step-function model) | [`scripts/tower.py`](scripts/tower.py) | §3 |
| Legendre log-kernel identity: exact for n ≤ 8 (SymPy); full decomposition to 30 digits (mpmath) | [`scripts/legendre.py`](scripts/legendre.py), [`scripts/decomp.py`](scripts/decomp.py) | §4 |

The closure was resolved by [`scripts/closure.py`](scripts/closure.py). All 26 sources come from `AegisRH/PR606/` (none from `Compat/`, `Source/` or `.lean.src` snapshots). They were built at the commit given above. The branch has since moved to `cd8599e` (2026-11-19). The 26 modules are unchanged there, except that `RHNarrowMomentPacketV1` is not in this closure.

## 1. Evidence classes

* **(a)** Lean theorem replayed with `--trust=0`. **(a)** means I ran it. **(a)ᴿ** means only the operator's receipt or a CI log I did not read says so.
* **(b)** Lean theorem compiled only (default trust). The same ᴿ convention applies.
* **(c)** Interval-arithmetic or exact-integer certificate with a checker.
* **(d)** Numerical observation (floating point).
* **(e)** Prose, conjecture, or source that I could not tie to any compile receipt.

## 2. Atomic map

### 2.1 Three-block chain at width 1/32 (`AegisRH/PR606`) — class (a), replayed here

Common hypotheses throughout:

* `g : WeilCompactSmoothGV1`;
* `WidthOneThirtyTwoAt g a`: the log-support lies in `[a − 1/64, a + 1/64]`, so the total log-width is **1/32**;
* the blocks are `gMinus, gZero, gPlus = T_{−log 2} g, T_0 g, T_{log 2} g`.

There are no N or NP parameters: this is an analytic chain, not a matrix certificate.

| claim | declaration | extra hypotheses | class |
|---|---|---|---|
| translation preserves both moments and the energy | `V22.translate_preserves_moments`, `translate_energy` | `WeilMomentConditionsV1 g` | (a) |
| diagonal prime sum is 0 | `V23.diagonal_prime_sum_zero` | width | (a) |
| ‖C_g(u)‖ ≤ E; C_g(u) = 0 for u > 1/32 | `V25.norm_logCorrelation_le_energy_v25`, `logCorrelation_zero_of_width_v25` | — / width | (a) |
| diagonal: `103/100 · E ≤ −Re B(g,g)` | `V27.width_diagonal_103_over_100_v27` | width (**no moments used**) | (a) |
| mixed correlation of translates = C_g(u + d₂ − d₁) | `V28.logCross_translate_eq_logCorrelation_v28` | — | (a) |
| only m = 2 (adjacent) and m = 4 (outer) are hit | `V29.adjacent_/outer_mixed_inv_nat_zero_v29` | width | (a) |
| adjacent prime sum = `log2/√2 · E`; outer prime sum = `log2/2 · E` | `V30.adjacent_prime_sum_exact`, `outer_prime_sum_exact` | width | (a) |
| Archimedean mixed term ≤ `E/100` (centred kernel 6/5, error 4/25) | `V31.separated_arch_norm_bound`, `three_arch_bounds_of_moments` | width, moments, gap ≥ log 2 − 1/32 | (a) |
| ‖B₀₁‖, ‖B₁₂‖ ≤ 51/100·E and ‖B₀₂‖ ≤ 9/25·E | `V31.three_cross_bounds_of_moments` | width, moments | (a) |
| **Re RHS(autocorr(z₀g₋ + z₁g₀ + z₂g₊)) ≤ −(1/10)·energy** | `V31.three_block_bound_of_moments` | width, moments, any z ∈ ℂ³ | (a) |
| *new (§4.6):* diagonal `(103/100 + e^{−1/32}·log 2)·E ≤ −Re B(g,g)`, constant > 17/10 | `WeilDiagonalLogGainV1.width_diagonal_log_gain_v1`, `log_gain_constant_gt` | width (**no moments used**) | (a), this session |

On the handoff remark that "V30's downstream constants still use 1/100": they do, and that is consistent. V31 discharges exactly the `1/100` premise of `V30.three_block_bound_of_arch`, so the three-block chain is closed at class (a).

The in-flight `30/649` bound would only sharpen it. Its arithmetic checks out:

* (64/59)/(11/15)/32 = 30/649;
* 11/15 is the lower bound for 1 − ¼·e^{1/16} at D = log 2 − 1/32.

That module is in no repository, so it stays in class (e).

### 2.2 CvS window certificates and exhaustion (formal-conjectures checkpoints)

Shared hypotheses: `HalfWidthAt g r a`, `2r ≤ LT`, and `WeilMomentConditionsV1 g`.

Shared parameters:

* M = 4, L = 2, m = 33/20 and ε = 7/5;
* 311 atoms and trace bound T = 3 at K = 156;
* rows NP = 2000 and κ = 66, with |τ_n| ≤ 15 for |n| ≥ 2001;
* τ boxes for k ≤ 2000;
* prime powers 2, 3 and 4 enter, since log 5 > LT.

| window LT (frontier L₀ = LT/2) | declaration | class |
|---|---|---|
| 3/2 (3/4), 11/8 | `CvSWindowL32V1…`, earlier | (a)ᴿ / (b)ᴿ per checkpoint READMEs |
| 49/32 (49/64) | `CvSWindowL4932V1.window_L4932`, `RHWindowL4932ExhaustionV1.*` | (a)ᴿ (70/70 at both trust levels, local, 2026-11-12) |
| 31/20 (31/40) | `CvSWindowL3120V1.window_L3120` | (a)ᴿ (70/70 at both trust levels) |
| 39/25 (39/50) | `CvSWindowL3925V1.window_L3925` | (b)ᴿ: the committed README records default trust only, with `--trust=0` "running" |
| 8/5 | — | in flight: `--trust=0` at 92/112 per the handoff; not in any repository yet; **no class** |
| 13/8 | — | not started; **no class** |
| reduction `RiemannHypothesis ↔ ∀ L > L₀, WindowArithmeticNonpositiveV1 L` | `V13Scratch.final_sign_iff_rh_v13` and `WeilWindowExhaustionV1` | (a)ᴿ, inside the window receipts' closure |

The exhaustion theorems are **reductions**. Each one moves the open part to the windows L > L₀; none of them proves RH.

### 2.3 Feshbach/Schur at L = 9/5 (`AEGIS-OMEGA@71fb7215`, `research/rh/feshbach_arb_v3`)

| claim | parameters | class |
|---|---|---|
| the finite Schur/CvS system is positive definite with margin μ = 4.23·10⁻¹⁷ (parity split, renormalised g0) and 4.21·10⁻¹⁷ (joint); prime powers 2, 3, 4, 5 | N = 400, NP = 16000, order-8 tail, c_∞ ≤ 0.97992 bound to `krein_slack.log` | (c) for the matrix statement only — checkers `schur_mid` (Rump) and `cert_congr` (exact T·S·Tᵀ, then Gershgorin) |
| ⇒ Q(G) ≥ μ‖G‖² for every moment-zero G in L²[0, 9/5] | — | conditional on the class (e) row of this table |
| τ layer: fixed point at 2^120, directed rounding | NP = 16000, N = 400 | (c); inputs re-derived here and their sha256 match |
| `CvSTailRenormV1`: `schur_mono`, `renorm_eq`, `schur_renorm(_sum)` | abstract | (a)ᴿ (logs committed) |
| `CvSParitySplitV1`: `cross_zero`, `blocks_posSemidef`, `congr_posSemidef` | abstract | (a)ᴿ |
| CvS matrix = restricted Weil form; hat Krein pairing; the Feshbach inequality; the order-8 tail bound; reflection invariance of the actual matrices; the sector split of τ | — | **(e)**: listed as unformalised in `RECEIPT.json` |
| `feshbach_arb_v2`: ℓ = 1.2, 1.3, 1.4, 1.6 and 1.8, with μ from 5·10⁻⁵ down to 4·10⁻¹⁷ | per receipt | (c)ᴿ, not rerun here |

### 2.4 Dyadic and Gram modules (the operator's)

| module | key statement and hypotheses | class |
|---|---|---|
| `RHDyadicDiagonalV13` | `diagonal_lower`: for 0 < r ≤ 1/64 and `HalfWidthAt g r a`, `E·(cothTail(2r) − κ − r·e^{1/64}) ≤ −Re B(g,g)` | (e): `.lean.src` snapshot only; no compile receipt in either tree; not in the exhaustion closure (`20261113_source_truth_graph_check_v1`) |
| `RHDyadicWindowV13` | `gap_B_norm_bound`: if 2r ≤ 2^{−(k+1)} and r ≤ 1/64, then ‖B(T₀g, T_{k log 2}g)‖ ≤ (log 2·2^{−k/2} + 1/100)·E | (e), same as above |
| `RHDyadicTowerV13` | `dyadic_tower`: ∀N ∃m: the comb `Σ_{j≤N} z_j T_{j log 2} g` at half-width 2^{−m} is nonnegative on the zero side; here m = max(10, N+2) | (e), same as above. The **width shrinks with N** (see `AEGISOverlay/RH_GLOBALIZATION_OBSTRUCTION_V1.md`) |
| `RHActualLocalGramCoercivityV1`, `RHOptimizedSchurGlobalJoinV1` | Gram coercivity of narrow packets; `riemannHypothesis_of_optimized_actual_row_producer` is **conditional** on a producer hypothesis | (b)ᴿ: referenced by `rh-cofinal-actual-schur-v1.yml`; CI log not read |
| `CvSDyadicEnclosureV1` | `rescale_endpoint`, `enclosure_transport` (exact dyadic rescaling only) | (b)ᴿ (`DYADIC_KERNEL_RECEIPT.json`, PASS; no trust level stated) |

### 2.5 New on the branch since 2026-11-16 (`20261117_signed_fixedwidth_v1`, overlay)

| module | content | class |
|---|---|---|
| `RHSignedWeilMarginsV1` | rational margins at k = 7, 10, 11 (45737/448900 > 1/10, …) and the algebraic bridge `signed_real_of_prime_arch_bound` | (a)ᴿ per commit `a515381` (CI; log not read) |
| `WeilSignedPrimeKernelV1` | exact signed prime samples of translates; the continuum main term pairs to 0 with a moment-zero packet | (a)ᴿ per `97b63b4` (CI) |
| `RHNarrowFourBlockV2` | four blocks at width 1/40; SOS comparison with diagonal 5/4 | (e): the file states it is "NOT Lean-replayed" |
| `AEGIS_RH_Unconditional.lean` | `riemannHypothesis_of_actual_global_signed_weil (hcert : …)` | conditional on `hcert`. The file name says "Unconditional"; that is doc debt, not a finding against the content |

### 2.6 In flight, in no repository: class (e)

* `WeilLogCorrelationL1V1`: ∫‖C‖ du ≤ w·E;
* `WeilSeparatedArchL1BridgeV32`: Archimedean term ≤ E/200, and ≤ (30/649)·e^{−5D/2}·E.

## 3. Test of the claim "mixed prime-power resonances at fixed width are the main obstacle"

Model, class **(d)**:

* the comb `F = Σ_{j=0}^{N} z_j T_{j log 2} g` with g of total log-width w = 1/32 and both moments;
* g discretized as a step function on n cells (n = 32, 48, 96). λ_min and the absolute masses agree across meshes to about 1%. The per-gap prime-block norms for k ≥ 7 do **not** converge: at k = 10 they are 1.024, 0.690 and 1.105 for n = 32, 48 and 96. Treat that column as indicative only;
* the exact Weil form evaluated: prime powers up to 2^{N+1}·e^w, the Archimedean kernel by quadrature;
* full output in [`tower_n48.txt`](tower_n48.txt), [`tower_n32.txt`](tower_n32.txt) and [`tower_n96.txt`](tower_n96.txt).

| gap k | prime powers in `[k log 2 ± 1/32]` (list for k ≤ 7, **count** after) | Σ Λ(q)/√q | ‖prime block‖ on moment-zero (mesh-dependent, see above) |
|---|---|---|---|
| 1–6 | only 2^k | log 2·2^{−k/2} | the same |
| 7 | 125, 127, 128, 131 | 1.061 | 0.541 |
| 10 | 11 of them | 2.186 | 0.690 (n48) |
| 12 | 30 of them | 3.780 | 0.679 (n48) |
| 17 | 696 of them | 22.57 | 0.511 (n32) |

| blocks N+1 | λ_min (true form) | absolute-sum budget D − 2Σ mass | norm budget D − 2Σ‖G_k‖ |
|---|---|---|---|
| 4 | 2.45 | 1.49 | 1.49 |
| 7 | 1.76 | 0.73 | 0.73 |
| 8 | 1.60 | **−1.39** | **−0.35** |
| 13 | 0.99 | −25.1 | −6.9 |
| 18 (n32) | 0.82 | −152 | −12.9 |

(D here is the numerical moment-zero diagonal, 3.65. The rows up to 13 blocks come from `tower_n48.txt` and the 18-block row from `tower_n32.txt`, since the n48 run stops at 13 blocks.)

**Verdict: confirmed only in part.**

1. **What is confirmed.** At w = 1/32 the dyadic gaps hit only 2^k for k ≤ 6. From k = 7 on, other prime powers enter: 125 = 5³, 127 and 131. Any bound that sums absolute values, or norms gap by gap (V13-style Gershgorin), then fails: their mass grows like Σ_{q≈2^k} Λ(q)/√q.
2. **What is refuted (numerically, class (d)).** The resonances are **not** an obstruction to positivity in this discretised model. λ_min stays positive, at 0.82 for 18 blocks, and decreases slowly. The prime blocks cancel in phase: their operator norm stays at about 0.5–0.7 while their mass grows without bound. A *signed* treatment, which is the operator's 2026-11-17 direction, is the right kind of tool for gaps ≥ 7.
3. **What is missed.** In the Lean chain as it stands, resonances are **not** the binding constraint. The chain already fails at **4 blocks**, at gap 3, where only 2³ is in range. The cause is the diagonal: `103/100` against grid values of about **1.97 E without moments** and **3.65 E with moments**. V27 bounds the inner integral ∫₀^w (E − e^{u/2} Re C(u))/sinh u du from below by about −E/64; on the grids it is about +0.92 E. These grid values are minima over finite-dimensional step-function subspaces, so they are *upper* bounds on the infimum over all admissible packets, not lower bounds: class (d) observations only. The proved lower bound is the Lean S1/V1 result, 103/100 + e^{−1/32}·log 2 ≈ 1.7018 (§4.6).

[`budget.txt`](budget.txt) shows this with a Perron bound, using the cross ceilings c_k = log 2·2^{−k/2} + a_k:

| blocks | ρ(C) | margin with D = 1.0349 (Lean V27) | margin with D = 1.7018 (proved, §4.6) | margin with D = 1.7069 (proposed sharper transport, class (d)) |
|---|---|---|---|---|
| 3 | 0.908 | **+0.127** (the closed V31 result) | +0.794 | +0.799 |
| 4 | 1.243 | −0.208 | +0.459 | +0.464 |
| 5 | 1.522 | −0.487 | **+0.180** | +0.185 |
| 6 | 1.755 | −0.720 | −0.053 | −0.048 |

With the moment gain of §4.4 (D ≈ 3.16), the same bound gives 7 blocks, up to gap 6. That is exactly where the resonances begin. Only from that point are the operator's resonances the binding obstacle.

## 4. Key next step: the diagonal log-gain lemma

### 4.1 Statement

Let g ∈ `WeilCompactSmoothGV1` with `LogSupportIn g lo hi`, w = hi − lo ≤ 1/32, h = logLift g and E = energy g. Then

```
∫_{0}^{w} (E − Re C_g(u)) / u du  ≥  ∫ V_w(t) |h(t)|² dt  ≥  log 2 · E,
     V_w(t) = ½·log( w² / ((t − lo)(hi − t)) )      (on (lo, hi); V_w ≥ log 2)
```

Consequently, with no moment hypothesis:

```
−Re B(g,g) ≥ ( cothTail(w) − κ + e^{−w}·log 2 − ∫₀^w (e^{u/2} − 1)/sinh u du ) · E
```

At w = 1/32 this is **≥ 1.7068 E**, against 103/100 now.

### 4.2 Why it is plausible

These are my own computations:

* **Exact identity** on [0, 1]: `∫₀¹ (E − C(s))/s ds = Σ_n H_n·E_n + ∫ ½log(1/(x(1−x)))·h²`, where E_n is the energy of the Legendre-n component and H_n is the n-th harmonic number.
  * The kernel identity `∫_{−1}^{1} (P_n(x) − P_n(y))/|x − y| dy = 2H_n P_n(x)` holds exactly for n ≤ 8 (SymPy, [`legendre.txt`](legendre.txt)).
  * The full decomposition matches to 3.5·10⁻³⁰ on a random degree-6 h (mpmath, 30 digits, [`decomp.txt`](decomp.txt)).
  * Since H_n ≥ 0 and V ≥ log 2, the bound follows.
* **Numerical minimum** of the scale-free form: 0.9264 (n = 512) without moments, at least log 2 = 0.6931. It is 2.598 with the {1, s} constraints, at least 3/2 + log 2 = 2.193.

### 4.3 Smallest verifiable sub-lemma (Mathlib only, no Weil definitions)

> **S1.** Let h : ℝ → ℂ be continuous with support in [0, 1], E = ∫|h|² and C(s) = ∫ h(x+s)·conj h(x) dx. Then
> `∫₀¹ (E − Re C(s))/s ds ≥ log 2 · E`.

Proof in four elementary steps:

1. E − Re C(s) = ½∫|h(x+s) − h(x)|² dx, because h vanishes outside [0, 1].
2. This is ≥ ½∫_{1−s}^{1}|h|² + ½∫_{0}^{s}|h|², since on each of those sets one of the two terms vanishes.
3. Tonelli: ∫₀¹ (1/s)∫_{1−s}^{1}|h(x)|² dx ds = ∫|h(x)|²·log(1/(1−x)) dx, and the same for the other piece with log(1/x).
4. ½(log(1/x) + log(1/(1−x))) ≥ log 2 on (0, 1).

Then S1 is transported to the repository's `widthArchLogIntegrandV26` with three facts:

* translation and scaling of the support;
* 1/sinh u ≥ e^{−w}/u (the repository already has `sinh_le_self_mul_exp`);
* e^{u/2} ≤ 1 + (e^{u/2} − 1) together with ‖C‖ ≤ E (V25).

### 4.4 Second stage, after S1 is in place

With both moments, h is within O(w) of the span of {P₂, P₃, …}. The identity in 4.2 then gives a gain of at least (3/2 + log 2 − O(w))·E, and the diagonal rises to about 3.16 E. Window isolation is also needed for k = 5 and 6 at w = 1/32: the V13 condition 2r ≤ 2^{−(k+1)} fails there, but the hit sets are still {2^k}, since 31 < 32·e^{−1/32} = 31.015. This stage pushes the fixed-width comb to 7 blocks, which is the onset of resonance.

### 4.5 Success criteria

Status after 2026-11-22 (§4.6), against the criteria as first written below:

* **Criterion 1 is met in a corrected form.** The literal real-valued statement below is not what was proved, and it is false as written for merely continuous h (see §4.6). The proved theorem is the ℝ≥0∞ form, on any interval.
* **Criterion 2 is met with a slightly weaker constant.** It proves 103/100 + e^{−1/32}·log 2 ≈ 1.7018, not 1.70667, because it keeps V27's `diagonalSmallV21` for the (e^{u/2} − 1) part. Reaching 1.70667 needs the sharper pointwise bound with 1/63; that is not done.
* Criterion 3 is met as of 2026-11-23: `WeilFiveBlockE1V1.five_block_bound_of_moments` gives margin 17/100·E ≥ 1/10·E, with the gap-3 and gap-4 cross bounds compiled in `WeilFiveBlockCrossV1` (class (a), replayed here; see E1 in §5).
* Criterion 4 is met by the committed scripts.

1. **Lean, S1:** `theorem log_gain (h : ℝ → ℂ) (hc : Continuous h) (hs : support h ⊆ Icc 0 1) : Real.log 2 * ∫ x, ‖h x‖^2 ≤ ∫ s in Ioc 0 1, ((∫ x, ‖h x‖^2) - (∫ x, h (x+s) * conj (h x)).re) / s`. It must compile with `lean --trust=0`, `#print axioms` must list only `[propext, Classical.choice, Quot.sound]`, and it must contain no `sorry`.
2. **Lean, transport:** `diagonal_log_gain_v1 : (cothTail (1/32) − κ + exp(−1/32)·log 2 − 1/63)·E ≤ −Re B(g,g)` under `WidthOneThirtyTwoAt`. Here 1/63 is a rational upper bound for ∫₀^{1/32} (e^{u/2} − 1)/sinh u = 0.015685…; with it the constant is 1.70667. The same three axioms are required.
3. **Lean, use:** a five-block fixed-width comb theorem (gaps ≤ 4, so the V13 single-sample condition holds, since 1/32 ≤ 2^{−5}) with margin ≥ 1/10·E. This needs the gap-3 and gap-4 cross bounds compiled first: V13 is only a source snapshot today. With the proved constant 1.7018 the Perron margin is 0.180, using the 1/100 Archimedean bound.
4. **Checker:** `scripts/budget.py` reproduces the margins in §3 to within 10⁻⁴. `scripts/tower.py 1/32 96 10` keeps λ_min(5 blocks) ≥ 1.7066 − ρ(5) ≈ 0.185. The measured value is 2.17 (row N = 4), so the bound sits well below it.

### 4.6 Result (2026-11-22): S1 and the transport are proved

Files: [`lean/WeilDiagonalLogGainS1.lean`](lean/WeilDiagonalLogGainS1.lean) and [`lean/WeilDiagonalLogGainV1.lean`](lean/WeilDiagonalLogGainV1.lean), with sha256 in [`lean/SHA256SUMS`](lean/SHA256SUMS). Both were replayed with `lean --trust=0` (Lean 4.33.1, Mathlib `0df444a3`): exit 0, no warnings, no `sorry`. The logs are in `lean/*.trust0.txt`, and [`lean/build.sh`](lean/build.sh) reruns both on top of the 26-module closure from `scripts/replay.sh`.

**S1, as proved.** It is stated in `ℝ≥0∞`, so it needs no integrability hypothesis. That matters: for a merely continuous h, (E − Re C(s))/s need not be integrable, and a real-valued statement would be false through the zero default of the Bochner integral. It also holds on any interval:

```lean
theorem AEGIS.WeilDiagonalLogGainS1.log_gain (h : ℝ → ℂ) (hm : Measurable h) (lo L : ℝ)
    (hs : ∀ x, x ∉ Icc lo (lo + L) → h x = 0) :
    ENNReal.ofReal (Real.log 2) * ∫⁻ x, ENNReal.ofReal (‖h x‖ ^ 2) ≤
      ∫⁻ s in Ioc 0 L, ENNReal.ofReal (1 / (2 * s)) *
        ∫⁻ x, ENNReal.ofReal (‖h (x + s) - h x‖ ^ 2)
```

**Transport, as proved.** For every retained packet, with no moment hypothesis:

```lean
theorem AEGIS.WeilDiagonalLogGainV1.width_diagonal_log_gain_v1
    (g : WeilCompactSmoothGV1) (a : ℝ) (hw : WidthOneThirtyTwoAt g a) :
    (103 / 100 + Real.exp (-(1 / 32 : ℝ)) * Real.log 2) * energy g.1 ≤ -(B g g).re
theorem AEGIS.WeilDiagonalLogGainV1.log_gain_constant_gt :
    (17 / 10 : ℝ) < 103 / 100 + Real.exp (-(1 / 32 : ℝ)) * Real.log 2
```

The intermediate theorems are:

* `diff_sq_integral`: ∫‖h(v+u) − h(v)‖² = 2E − 2 Re C(u);
* `inner_pointwise`: integrand ≤ E·e^{1/64}/2 − e^{−1/32}·(E − Re C(u))/u on (0, 1/32];
* `weighted_gain`: ∫₀^{1/32} (E − Re C)/u ≥ log 2·E, which is S1 on [a − 1/64, a + 1/64];
* `inner_log_gain`: inner window ≤ E·diagonalSmallV21 − e^{−1/32}·log 2·E.

It reuses V21, V24, V25, V26, V27 and V31 unchanged, and modifies no existing module.

The new diagonal constant is 1.7018 (V27 has 1.03). It sits 0.005 below the numerical 1.7069 of §3, because it keeps V27's `diagonalSmallV21` for the (e^{u/2} − 1) part.

The lemma is useful because it is the cheapest edge with a measurable effect. Three blocks become five at the **same** width, with no new arithmetic input. It also separates the diagonal deficit from the resonance problem. It does not prove positivity on the whole class, it does not prove the windows L > 39/50, and it does not prove RH.

## 5. Dependency graph

The graph below is read bottom to top: arrows run from the finite certificates up to "Weil positivity on this class". ✗ marks a missing edge.

```
                          RiemannHypothesis (Mathlib)
                                   ▲  (a)ᴿ  final_sign_iff_rh_v13 (iff, both directions)
                        FinalSignResidualV1  ⇔  ∀L>0 WindowArithmeticNonpositive L   (a)ᴿ WeilWindowExhaustionV1
                                   ▲
         ✗ E4: windows L > 39/50, infinitely many; certificate cost grows doubly exponentially (Zhu barrier). OPEN.
                                   ▲
  ┌──────────────── window class, full test-function class inside [−L, L] ────────────────┐
  │ L ≤ 49/64, 31/40: (a)ᴿ    L ≤ 39/50: (b)ᴿ    8/5: in flight    13/8: —                  │
  │   ▲ CvS trace + τ boxes + row LDL (kernel decide) + Gram moment join                    │
  │ L = 9/10 (moment-zero class): (c) Feshbach N=400, NP=16000                              │
  │   ✗ E5: CvS = Weil form · Krein pairing · Feshbach ineq. · order-8 tail · reflection      │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
                                   ▲
         ✗ E3: comb class (translates of one packet) → full class. No density/approximation link.
                                   ▲
  ┌──────────────── fixed-width comb class, w = 1/32 ───────────────────────────────────────┐
  │ 3 blocks: (a), V31.three_block_bound_of_moments, margin −1/10·E                         │
  │   ▲ V22 moments/energy · V23 diag prime 0 · V25 ‖C‖≤E · V27 diag 103/100 · V28 transport │
  │   ▲ V29 isolation m=2,4 · V30 exact prime sums · V31 Arch ≤ E/100        (all (a))       │
  │ diagonal 1.7018·E without moments: (a), WeilDiagonalLogGainV1 (2026-11-22)                │
  │ 5 blocks: (a), WeilFiveBlockE1V1.five_block_bound_of_moments, margin −17/100·E (11-23)   │
  │   ▲ WeilFiveBlockCrossV1.translated_cross_bound gaps 1–4 · WeilFiveBlockPerronV1 (all (a))│
  │ ✗ E1': 6–7 blocks: moment gain of §4.4 and isolation for gaps 5 and 6                     │
  │ ✗ E2: ≥ 8 blocks: resonant prime powers (gap ≥ 7); needs signed bounds                    │
  │       (20261117 k=7,10,11 margins: (a)ᴿ algebra only; analytic producers (e))            │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
  Width-shrinking tower (V13 dyadic_tower, ∀N∃m): (e) — no fixed class; does not feed E1/E2.
```

| missing edge | what it lacks |
|---|---|
| **E1** | Closed for 5 blocks, class (a), replayed here at `--trust=0` (`lean/replay_e1.sh`, 2026-11-23): `WeilFiveBlockCrossV1.translated_cross_bound` bounds the cross terms for gaps 1–4, and `WeilFiveBlockE1V1.five_block_bound_of_moments` assembles five translates with arbitrary complex coefficients into Re W ≤ −17/100·energy, using the 1.7018 diagonal of §4.6 and the rational Perron rows of `WeilFiveBlockPerronV1`. Only propext, Classical.choice and Quot.sound are used. Still missing (E1′): 6–7 blocks. [`e1prime.txt`](e1prime.txt) (class (d) for the eigenvalues; the window lists are exact integer facts) shows that isolation is not the obstacle: with a ±1/32 window, gaps 5 and 6 see only 32 and 64. The obstacle is the diagonal. For a nonnegative symmetric ceiling matrix, no weighted-row (Perron) certificate beats D − ρ(C) (Collatz–Wielandt). With ceilings log 2·2^{−k/2} + a, six blocks need D > 1.7058 even at a = 0, and D > 1.7551 at a = 1/100. The proved D = 1.7018 falls short, and the sharper 1.70667 of criterion 2 would clear a = 0 by only 0.0009. So 6–7 blocks need the moment gain of §4.4, or cross ceilings sharper than the prime-sum term, not just more isolation lemmas. |
| **E2** | cross-term bounds for gaps k ≥ 7 that keep the phases of C_g at log q − k·log 2. In the class (d) model of §3, the absolute-sum and per-gap norm budgets go negative from 8 blocks on. That is a numerical observation for finitely many gaps and one discretisation (the per-gap norms are mesh-dependent), not a proof that every gap-by-gap norm approach must fail. |
| **E3** | any argument that a positive form on the comb class controls general packets of the same width. No such link exists in the repository. |
| **E4** | a uniform argument in L. Window-by-window certificates cannot supply one. |
| **E5** | Lean statements of the five unformalised Feshbach steps (`RECEIPT.json`). |

## 6. Feshbach L = 9/5 reproduction

* The first run stopped because `scipy` was missing from this container. That was an environment gap, not a certificate failure.
* In the second run ([`feshbach_reproduce.txt`](feshbach_reproduce.txt)), three block sets were regenerated: joint g0, and even and odd renormalised g0. Each matches its pinned sha256 byte for byte. The V9 set was not regenerated, so the script stopped at its missing file.
* I then ran the checks by hand ([`feshbach_checks.txt`](feshbach_checks.txt)):

| checker | even 4.23e-17 | odd 5e-17 | joint 4.21e-17 | even 4.24e-17 | joint 4.22e-17 |
|---|---|---|---|---|---|
| `schur_mid` (Rump) | PD | PD | PD | refused, pivot 368 | refused, pivot 632 |
| `cert_congr` (exact integer) | CERTIFIED | CERTIFIED | CERTIFIED | refused, 368 | refused, 632 |

`tests/test_certifiers.py`: ALL PASS. So the receipt's class (c) claim (μ = 4.23·10⁻¹⁷ split, 4.21·10⁻¹⁷ joint) reproduces here. This is still class (c), not Lean, and the five steps in E5 remain unformalised. (In the log, the `rc` lines of the passing cases are the exit code of `tail`; the verdict is the checker's own output line.)

## 7. Reproduce

```
# formal-conjectures checkout at ce4868fd, with the Mathlib cache from `lake exe cache get`
export FC=<fc> S=<scratch dir>; mkdir -p $S/w
python3 -I scripts/closure.py WeilSeparatedArchBridgeV31 <AEGIS-OMEGA>/sovereign-omega-v2/formal/bridges/lean \
    $FC/AegisRH/PR606/Source $FC/AegisRH/PR606/Compat $FC/AegisRH/PR606 > $S/w/order.tsv
bash scripts/replay.sh                      # 26 modules + audit at --trust=0; exits non-zero on any failure
OLEAN=$S/olean bash lean/build.sh           # the two new modules; rewrites lean/*.trust0.txt
OLEAN=$S/olean E1_LOGS=$S/e1 bash lean/replay_e1.sh   # the three five-block modules + exact arithmetic, with axiom audit
python3 -I scripts/tower.py 1/32 48 12; python3 -I scripts/budget.py; python3 -I scripts/e1prime.py
python3 -I scripts/legendre.py; python3 -I scripts/decomp.py      # needs sympy and mpmath
```
