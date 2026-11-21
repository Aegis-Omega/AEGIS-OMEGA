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
| `lean --trust=0` on the full import closure of `WeilSeparatedArchBridgeV31` (26 modules, `AegisRH/PR606/*.lean`) | formal-conjectures `ce4868fd`, Lean 4.33.1, Mathlib `v4.33.1` cache | **26/26 exit 0**, 0 errors ([`trust0_replay.tsv`](trust0_replay.tsv); source hashes in [`trust0_sources.sha256`](trust0_sources.sha256)) |
| `#print axioms` on 14 theorems of that chain, at `--trust=0` | [`scripts/Audit.lean`](scripts/Audit.lean) | every one is `[propext, Classical.choice, Quot.sound]` ([`trust0_axioms.log`](trust0_axioms.log)) |
| Feshbach L = 9/5: the integer τ layer (`tau80.py`, `diag80.py`) | copy of `research/rh/feshbach_arb_v3` | both input files match the pinned sha256 (`d5374e04…`, `efae4a0a…`) |
| Feshbach L = 9/5: block regeneration and both checkers | same | blocks byte-identical; both checkers certify and refuse as the receipt says (§6) |
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
| Q(G) ≥ μ‖G‖² for every moment-zero G in L²[0, 9/5]; prime powers 2, 3, 4, 5; μ = 4.23·10⁻¹⁷ (parity split, renormalised g0) and 4.21·10⁻¹⁷ (joint) | N = 400, NP = 16000, order-8 tail, c_∞ ≤ 0.97992 bound to `krein_slack.log` | (c) — checkers `schur_mid` (Rump) and `cert_congr` (exact T·S·Tᵀ, then Gershgorin) |
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
* g discretized as a step function on n cells (n = 32, 48, 96; results agree to about 1%);
* the exact Weil form evaluated: prime powers up to 2^{N+1}·e^w, the Archimedean kernel by quadrature;
* full output in [`tower_n48.txt`](tower_n48.txt), [`tower_n32.txt`](tower_n32.txt) and [`tower_n96.txt`](tower_n96.txt).

| gap k | prime powers in `[k log 2 ± 1/32]` | Σ Λ(q)/√q | ‖prime block‖ on moment-zero |
|---|---|---|---|
| 1–6 | only 2^k | log 2·2^{−k/2} | the same |
| 7 | 125, 127, 128, 131 | 1.061 | 0.541 |
| 10 | 11 | 2.186 | 0.690 |
| 12 | 30 | 3.780 | 0.679 |
| 17 | 696 | 22.57 | 0.511 |

| blocks N+1 | λ_min (true form) | absolute-sum budget D − 2Σ mass | norm budget D − 2Σ‖G_k‖ |
|---|---|---|---|
| 4 | 2.45 | 1.49 | 1.49 |
| 7 | 1.76 | 0.73 | 0.73 |
| 8 | 1.60 | **−1.39** | **−0.35** |
| 13 | 0.99 | −25.1 | −6.9 |
| 18 | 0.82 | −152 | −12.9 |

(D here is the numerical moment-zero diagonal, 3.65.)

**Verdict: confirmed only in part.**

1. **What is confirmed.** At w = 1/32 the dyadic gaps hit only 2^k for k ≤ 6. From k = 7 on, other prime powers enter: 125 = 5³, 127 and 131. Any bound that sums absolute values, or norms gap by gap (V13-style Gershgorin), then fails: their mass grows like Σ_{q≈2^k} Λ(q)/√q.
2. **What is refuted.** The resonances are **not** an obstruction to positivity in this model. λ_min stays positive, at 0.82 for 18 blocks, and decreases slowly. The prime blocks cancel in phase: their operator norm stays at about 0.5–0.7 while their mass grows without bound. A *signed* treatment, which is the operator's 2026-11-17 direction, is the right kind of tool for gaps ≥ 7.
3. **What is missed.** In the Lean chain as it stands, resonances are **not** the binding constraint. The chain already fails at **4 blocks**, at gap 3, where only 2³ is in range. The cause is the diagonal: `103/100` against a true value of about **1.97 E without moments** and **3.65 E with moments**. V27 bounds the inner integral ∫₀^w (E − e^{u/2} Re C(u))/sinh u du from below by about −E/64, while its true value is ≥ +0.92 E.

[`budget.txt`](budget.txt) shows this with a Perron bound, using the cross ceilings c_k = log 2·2^{−k/2} + a_k:

| blocks | ρ(C) | margin with D = 1.0349 (Lean V27) | margin with D = 1.7069 (§4 lemma, no moments) |
|---|---|---|---|
| 3 | 0.908 | **+0.127** (the closed V31 result) | +0.799 |
| 4 | 1.243 | −0.208 | +0.464 |
| 5 | 1.522 | −0.487 | **+0.185** |
| 6 | 1.755 | −0.720 | −0.048 |

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

1. **Lean, S1:** `theorem log_gain (h : ℝ → ℂ) (hc : Continuous h) (hs : support h ⊆ Icc 0 1) : Real.log 2 * ∫ x, ‖h x‖^2 ≤ ∫ s in Ioc 0 1, ((∫ x, ‖h x‖^2) - (∫ x, h (x+s) * conj (h x)).re) / s`. It must compile with `lean --trust=0`, `#print axioms` must list only `[propext, Classical.choice, Quot.sound]`, and it must contain no `sorry`.
2. **Lean, transport:** `diagonal_log_gain_v1 : (cothTail (1/32) − κ + exp(−1/32)·log 2 − 1/63)·E ≤ −Re B(g,g)` under `WidthOneThirtyTwoAt`. Here 1/63 is a rational upper bound for ∫₀^{1/32} (e^{u/2} − 1)/sinh u = 0.015685…; with it the constant is 1.70667. The same three axioms are required.
3. **Lean, use:** a five-block fixed-width comb theorem (gaps ≤ 4, so V13 single-sample isolation applies, since 1/32 ≤ 2^{−5}) with margin ≥ 1/10·E. The Perron margin is 0.185 with the 1/100 Archimedean bound.
4. **Checker:** `scripts/budget.py` reproduces the margins in §3 to within 10⁻⁴. `scripts/tower.py 1/32 96 10` keeps λ_min(5 blocks) ≥ 1.7066 − ρ(5) ≈ 0.185. The measured value is 2.17 (row N = 4), so the bound sits well below it.

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
  │ ✗ E1: 4–7 blocks: diagonal deficit (103/100 vs ≥1.707 / ~3.16). §4 lemma → 5, then 7      │
  │ ✗ E2: ≥ 8 blocks: resonant prime powers (gap ≥ 7); needs signed bounds                    │
  │       (20261117 k=7,10,11 margins: (a)ᴿ algebra only; analytic producers (e))            │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
  Width-shrinking tower (V13 dyadic_tower, ∀N∃m): (e) — no fixed class; does not feed E1/E2.
```

| missing edge | what it lacks |
|---|---|
| **E1** | a diagonal lower bound that keeps the E − Re C ≥ 0 structure (§4). Pure real analysis, no arithmetic. |
| **E2** | cross-term bounds for gaps k ≥ 7 that keep the phases of C_g at log q − k·log 2. Absolute and per-gap norm bounds provably fail (§3). |
| **E3** | any argument that a positive form on the comb class controls general packets of the same width. No such link exists in the repository. |
| **E4** | a uniform argument in L. Window-by-window certificates cannot supply one. |
| **E5** | Lean statements of the five unformalised Feshbach steps (`RECEIPT.json`). |

## 6. Feshbach L = 9/5 reproduction

* The first run stopped because `scipy` was missing from this container. That was an environment gap, not a certificate failure.
* In the second run ([`feshbach_reproduce.log`](feshbach_reproduce.log)), three block sets were regenerated: joint g0, and even and odd renormalised g0. Each matches its pinned sha256 byte for byte. The V9 set was not regenerated, so the script stopped at its missing file.
* I then ran the checks by hand ([`feshbach_checks.log`](feshbach_checks.log)):

| checker | even 4.23e-17 | odd 5e-17 | joint 4.21e-17 | even 4.24e-17 | joint 4.22e-17 |
|---|---|---|---|---|---|
| `schur_mid` (Rump) | PD | PD | PD | refused, pivot 368 | refused, pivot 632 |
| `cert_congr` (exact integer) | CERTIFIED | CERTIFIED | CERTIFIED | refused, 368 | refused, 632 |

`tests/test_certifiers.py`: ALL PASS. So the receipt's class (c) claim (μ = 4.23·10⁻¹⁷ split, 4.21·10⁻¹⁷ joint) reproduces here. This is still class (c), not Lean, and the five steps in E5 remain unformalised. (In the log, the `rc` lines of the passing cases are the exit code of `tail`; the verdict is the checker's own output line.)

## 7. Reproduce

```
# formal-conjectures checkout at ce4868fd, with the Mathlib cache from `lake exe cache get`
python3 -I scripts/closure.py WeilSeparatedArchBridgeV31 <AEGIS-OMEGA>/sovereign-omega-v2/formal/bridges/lean \
    <fc>/AegisRH/PR606/Source <fc>/AegisRH/PR606/Compat <fc>/AegisRH/PR606 > $S/w/order.tsv
cp scripts/Audit.lean $S/w/ && S=$S bash scripts/replay.sh        # one lean process at a time, about 6 min
python3 -I scripts/tower.py 1/32 48 12; python3 -I scripts/budget.py
python3 -I scripts/legendre.py; python3 -I scripts/decomp.py      # needs sympy and mpmath
```
