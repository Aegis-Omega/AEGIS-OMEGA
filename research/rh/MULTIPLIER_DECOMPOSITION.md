# Perron decomposition of the finite prime-power multiplier

```
EPISTEMIC_STATUS : NUMERICAL_EVIDENCE + UNPROVED_ASYMPTOTIC_SKETCH
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

Write `w = ½ − iγ` so that `n^{−w} = n^{−1/2+iγ}`. The historical sketch proposed the following asymptotic by partial summation
against `ψ(x) = Σ_{n≤x} Λ(n)`. It is not established by the argument below:

```
λ_P(γ) = 2 Re[ P^{½+iγ} / (½+iγ) ]  −  2·m(γ)·ln P  +  O_γ(1)          (*)
```

where `m(γ)` is the multiplicity of `½+iγ` as a zero of ζ, and `m = 0` when γ is
not a zero ordinate.

The smooth `x` term gives `P^{1-w}/(1-w)`. The resonant zero
`rho = w = 1/2 - i gamma`, if present, produces the logarithmic term.
However, the previous derivation wrote **every other zero** as
`rho = 1/2 + i gamma'`. That is not available without RH. A general
zero has a contribution of the shape

```
-m_rho P^{rho-w}/(rho-w),   rho != w,
```

in a properly truncated Perron residue calculation. Its magnitude involves
`P^{Re rho - 1/2}`. Thus an off-line zero to the right cannot be discarded
as a bounded oscillation. Even assuming RH, boundedness of each individual
oscillation does not prove a uniform bound for their infinite sum. A valid
contour calculation must retain its zero cutoff, boundary terms and error
estimates before any limiting claim is made.

**[OPEN]** The unconditional `O_gamma(1)` remainder in `(*)` is not proved
here. This identifies a failure of the supplied derivation; it does not
prove that `(*)` itself is false. The finite numerical slope checks below
remain **[NUMERICAL-EVIDENCE]**. A passing assertion over the chosen ladder
cannot establish this asymptotic or determine an analytic multiplicity.


---

## What this separates

Two statements were previously compressed into one reading of `λ_P` at a zero:

| term | character |
|---|---|
| `2 Re[P^{½+iγ}/(½+iγ)]` | **truncation artifact**, present at *every* γ, zero or not |
| `−2 m(γ) ln P` | resonant term in the proposed sketch; remainder unproved |

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

The two populations do not overlap on this finite grid. The observed residual
slopes are consistent with the proposed resonant coefficient; they do not
prove an asymptotic or an analytic multiplicity.

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

For the Gaussian packet used here, the prime sum converges absolutely.
For compactly supported log-coordinate `f`, it is finite: truncation above
`exp(sup supp f)` is exact. Both statements have elementary sufficient
bounds and do not require the unproved pointwise asymptotic `(*)`.

**[REFUTED] Historical decay shortcut.** The previous statement that
super-polynomial decay in `log n` suffices for

```
Sum_n Lambda(n) n^(-1/2) |f(log n)| < infinity
```

is false, even for a nonnegative Schwartz function. Set

```
f(u) = exp(-(1+u^2)^(1/4)).
```

This is smooth; each derivative is its exponential factor times a function
of at most polynomial growth. Since the factor decays like
`exp(-sqrt(|u|))`, every derivative decays faster than every inverse power,
so `f` is Schwartz. For `u >= 8`, `(1+u^2)^(1/4) <= u/2`, and therefore
`f(log p) >= p^(-1/2)` for sufficiently large primes. Consequently

```
Lambda(p) p^(-1/2) f(log p) >= log(p)/p >= log(2)/p.
```

The sum of prime reciprocals diverges, so the displayed prime subseries
and hence the nonnegative full series diverge. This last dependency is
Euler's prime-reciprocal theorem; a formal version is
`not_summable_one_div_on_primes` in pinned Mathlib
`0df444a360eaa60ab8c11dca51a86af692955474`,
`Mathlib/NumberTheory/SumPrimeReciprocals.lean`. The counterexample itself
is a mathematical derivation, not a newly compiled AEGIS theorem.

A correct convenient sufficient condition is

```
|f(u)| <= C exp(-(1/2 + epsilon) u) for large u, epsilon > 0.
```

It bounds the series by a finite exception plus
`C Sum_n log(n)/n^(1+epsilon)`, which converges by the integral test.
Gaussian decay satisfies this condition for every fixed positive epsilon.
The condition is sufficient; no necessity claim is made for individual
functions. Super-polynomial decay in log height must not be confused with
power decay in the integer variable or with Mellin decay on a vertical line.


### One correction worth recording

The main term does **not** vanish under integration against the packet. It
converges to a constant, in closed form:

```
lim_{P -> infinity} ∫ λ_main,P(γ) |ψ̂(γ)|² dγ / 2π
    = 4π σ² e^{σ²/4}.                                                (**)
```

For the stated Fourier convention
`psi_hat(gamma) = sqrt(2 pi) sigma exp(-sigma^2 gamma^2/2)`, the finite-cutoff
expression is instead

```
2 pi sigma^2 exp(sigma^2/4)
  * (1 + erf((log P - sigma^2)/(2 sigma))),   sigma > 0.
```

Indeed write `(1/2+i gamma)^(-1)` as
`integral_0^infinity exp(-(1/2+i gamma)t) dt`. The Gaussian factor makes the
two-variable integrand absolutely integrable for fixed `P`. Fubini and the
Gaussian Fourier integral reduce the expression to
`2 sigma sqrt(pi) integral_{-infinity}^{log P} exp(u/2-u^2/(4 sigma^2)) du`.
Completing the square yields the formula and then `(**)`. This elementary
derivation is not a compiled repository theorem.

The historical limiting-value comparison against quadrature reported agreement to `5.5·10⁻¹⁵` at `σ = 0.4` and
`4.1·10⁻¹⁵` at `σ = 0.8`. At `σ = 0.8` its value is `+9.4379`, **larger than
`Q_∞ = 4.9413` itself**. What the packet removes is the term's `P`-dependence,
not the term. This smooth-density contribution originates from the zeta
pole. Identifying it with an archimedean gamma-factor constant requires
a separate normalized explicit-formula identity and is not justified here.

### The price, measured

```
σ=0.4   γ-width 2.50   →  P_needed = 100
σ=0.8            1.25   →  P_needed = 3 000
σ=1.2            0.83   →  P_needed = 300 000
σ=1.6            0.62   →  P_needed > 2·10⁶

fit:  P_needed ~ exp(10.0 · σ)
```

The fitted exponential describes this finite width grid. It is not an
asymptotic lower bound for resolving zeros and does not justify exchanging
`P -> infinity` with `sigma -> infinity`. Pointwise evaluation also requires
normalizing the Fourier packet to an approximate identity before taking a
concentration limit. No such two-limit theorem is proved here.

---

## Reproduce

```bash
python3 research/rh/multiplier_decomposition.py
```

Deterministic: no RNG, no wall-clock. Receipt frozen at
`research/rh/receipts/multiplier_decomposition_p2e6.json`.

Not wired into blocking CI.

## Bounded correction — 2026-09-12

The correction was prepared against repository head
`11355fc6816d9e767b33888205b0ad4fc26b5df1`, source blob
`198ff4d19bd389effdb768285f7fb3762054bc33`. It changes the mathematical
interpretation of this note. Numerical scripts, inputs and receipts were
not changed or rerun; their historical hashes and execution dates remain
historical evidence. No new formal proof, sign theorem, merge or authority
is granted. `RH = NOT_PROVEN`; `authority_effect = NONE`.
