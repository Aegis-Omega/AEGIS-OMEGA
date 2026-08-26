# Perron decomposition of the finite prime-power multiplier

```
EPISTEMIC_STATUS : EXACT_DERIVATION + VERIFIED_NUMERICAL
SCOPE            : P ≤ 2·10⁶, six zero ordinates, six non-zero controls
NORMALIZATION    : λ_P(γ) = 2 Re Σ_{n≤P} Λ(n) n^{−1/2+iγ}
                   (the finite trigonometric symbol of T_P)
```

**Declared, not derived**

| symbol | status |
|---|---|
| `γ₁…γ₆` | standard tabulated ordinates; **inputs**, not measured here |
| `P` ladder | chosen grid; no claim of optimality |
| slope tolerances | chosen separation thresholds, **not bounds** |
| `σ` grid | chosen Gaussian widths |

**Not claimed**

- any statement about the Riemann Hypothesis
- a *rigorous* proof of the decomposition — see the caveat below
- positivity of the Weil quadratic form
- that `m(γ)` read off a slope constitutes a proof of multiplicity

---

## The decomposition

Write `w = ½ − iγ` so that `n^{−w} = n^{−1/2+iγ}`. Partial summation against
`ψ(x) = Σ_{n≤x} Λ(n)` with the explicit formula `ψ(x) = x − Σ_ρ x^ρ/ρ − …` gives

```
λ_P(γ) = 2 Re[ P^{½+iγ} / (½+iγ) ]  −  2·m(γ)·ln P  +  O_γ(1)          (*)
```

where `m(γ)` is the multiplicity of `½+iγ` as a zero of ζ, and `m = 0` when γ is
not a zero ordinate.

The `x` term contributes `P^{1−w}/(1−w) = P^{½+iγ}/(½+iγ)`. Each zero ρ enters with
exponent `ρ − 1 − w`. For `ρ = ½+ig′` that is `−1 + i(γ+g′)`, which equals `−1`
**exactly when `g′ = −γ`** — that is, for the *conjugate* zero `ρ̄ = ½−iγ`. Then
`∫₁^P x^{−1}dx = ln P`, real, and `2 Re` gives `−2 ln P`. Every other zero
contributes `P^{i(γ+g′)}/(i(γ+g′))`, a bounded oscillation.

> **Caveat, stated rather than buried.** The step above uses the heuristic
> differentiated explicit formula. The rigorous route is Perron plus a contour
> shift, where `ln P` appears as the residue of `−ζ′/ζ(s+w)` at the pole
> `s+w = ρ̄`. The mechanism is textbook analytic number theory; what is written
> here is a derivation sketch, **not machine-bound**, and sits at the same tier
> as the other hand-derived exact layers — not at the Coq tier.

`(*)` is **asserted** by the instrument, not assumed.

---

## What this separates

Two statements were previously compressed into one reading of `λ_P` at a zero:

| term | character |
|---|---|
| `2 Re[P^{½+iγ}/(½+iγ)]` | **truncation artifact**, present at *every* γ, zero or not |
| `−2 m(γ) ln P` | the **only** arithmetic content at a zero |

Measured, `P ≤ 2·10⁶`, 149 235 prime powers:

```
  label      slope d(resid)/d(lnP)    R²     implied m
  gamma_1      -1.993            0.980    0.996
  gamma_2      -2.027            0.980    1.013
  gamma_3      -2.006            0.972    1.003
  gamma_4      -2.065            0.931    1.032
  gamma_5      -1.871            0.878    0.935
  gamma_6      -1.810            0.892    0.905
  c_12.00      +0.214            0.171        -
  c_17.58      +0.163            0.083        -
  c_23.50      -0.217            0.067        -
  c_28.00      +0.001            0.000        -
  c_35.26      -0.270            0.109        -
  c_40.00      -0.314            0.077        -

  slope separation (min|zero| − max|control|): 1.496
```

The two populations do not overlap. The residual `λ_P − main` is the clean
discriminant; its slope reads `−2m`.

---

## Consequence for a single-P reading

At `P = 65 010`:

| γ | `λ_P` | main term | residual |
|---|---|---|---|
| `γ₁` (zero) | `−36.16` | `−14.01` | `−22.16` |
| `17.58` (gap) | `+2.01` | `+2.21` | `−0.20` |

A large negative value at a zero ordinate is **artifact-dominated**. A positive
value in a gap is **artifact only**. Reading the two against each other as a
contrast compares signal-plus-artifact against pure artifact.

The same applies to sign changes in `P`. Between `P = 10⁴` and `P = 2·10⁴` the
main term moves `−13.97 → +19.53`, i.e. `Δ = +33.50`, while the measured
increment in `λ_P(γ₁)` is `+32.31` — **96.4 % of the swing is the main term.**
The 1 033 primes in that band are phase-coherent (8.91× a random-phase null,
`cos > 0` on 0.639 of the weighted mass), but that coherence belongs to the
smooth factor `x^{½+iγ}` sweeping phase, not to resonance with the zero.

---

## Why the quadratic form is the stable object

`Q_P(σ) = ⟨T_P ψ, ψ⟩` for `ψ(u) = exp(−u²/2σ²)`, so `f = ψ*ψ` is Gaussian.

Measured at `σ = 0.8` across the whole ladder `P = 2·10⁴ … 2·10⁶`:

```
Q_P drift = 0.000e+00        (bit-identical)
λ_P over the same range: −31.69 → +0.62 → −185.75
```

The mechanism needs no qualitative language: `Σ Λ(n)n^{−1/2}` diverges like
`2√P`, while `Σ Λ(n)n^{−1/2}f(ln n)` converges absolutely for any `f` with
super-polynomial decay in `ln n`. For compactly supported ψ — the standard Weil
setup — the sum is **finite**, so truncation at `P > e^{sup supp f}` is exact
rather than approximate.

### One correction worth recording

The main term does **not** vanish under integration against the packet. It
converges to a constant, in closed form:

```
∫ λ_main(γ) |ψ̂(γ)|² dγ / 2π  =  4π σ² e^{σ²/4}                        (**)
```

`(**)` is asserted against quadrature, matching to `5.5·10⁻¹⁵` at `σ = 0.4` and
`4.1·10⁻¹⁵` at `σ = 0.8`. At `σ = 0.8` its value is `+9.4379`, **larger than
`Q_∞ = 4.9413` itself**. What the packet removes is the term's `P`-dependence,
not the term — which then plays the role of the archimedean constant.

### The price, measured

```
σ=0.4   γ-width 2.50   →  P_needed = 100
σ=0.8            1.25   →  P_needed = 3 000
σ=1.2            0.83   →  P_needed = 300 000
σ=1.6            0.62   →  P_needed > 2·10⁶

fit:  P_needed ~ exp(10.0 · σ)
```

Pointwise evaluation `λ_P(γ)` is the `σ → ∞` limit of this same dial, where
`P_needed` is infinite. Pointwise non-convergence and quadratic-form convergence
are not two objects — they are the two ends of one dial, and the dial is
exponential. Resolving zeros individually costs exponentially many primes.

---

## Reproduce

```bash
python3 research/rh/multiplier_decomposition.py
```

Deterministic: no RNG, no wall-clock. Receipt frozen at
`research/rh/receipts/multiplier_decomposition_p2e6.json`.

Not wired into blocking CI.
