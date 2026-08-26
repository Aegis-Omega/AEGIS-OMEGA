# Finite-conditioning report — Douglas factorisation critical surface

```
EPISTEMIC_STATUS : VERIFIED_NUMERICAL
SCOPE            : first 300 tested zeros
SEED             : 20260825
NORMALIZATION    : current RH finite-model normalization (H=3.5, NF=720, panel=0.01)
```

**Declared, not derived**

| symbol | status |
|---|---|
| `C = 1e3` | chosen safety multiplier; **convention, not a derived bound** |
| `ε` | target norm violation to be detected |
| `‖A₋A₋ᵀ‖ = 0.2772` | **measured** at the worst-conditioned tested zero under this normalization; **not invariant** under rescaling |
| `s_min(A₋)` | measured quantity |

**Not claimed**

- asymptotic validity
- universal conditioning floor
- theorem `dim(P(V)) = 2`
- derived backward-error constant `C`

---

## What this separates

Three statements were previously compressed into one. They are not the same statement:

```
κ = 0                 algebraic boundary
ker(A₋) = {0}         identifiability
s_min(A₋) > τ(C)      numerical resolvability
```

## Error budget

```
signal(ε) = |λ_min(A₋A₋ᵀ − A₊A₊ᵀ)| = s_min² · ((1+ε)² − 1)        exact
floor(C)  = C · ε_mach · ‖A₋A₋ᵀ‖                                  convention
τ(C,ε)    = sqrt( C · ε_mach · ‖A₋A₋ᵀ‖ / ((1+ε)² − 1) )
M(C,ε)    = s_min(A₋) / τ(C,ε)
C_crit    = sup{C : M(C) > 1} = s_min²((1+ε)²−1) / (ε_mach‖A₋A₋ᵀ‖)
```

The exact `signal` law was checked against measurement on 6 zeros spanning
γ = 14 … 542 at ε ∈ {1e−3, 1e−2, 1e−1}; measured/predicted = `1 + ε/2` to the digit,
which is the `ε²` term.

## Read this before quoting a margin

Because `τ ∝ sqrt(C)`,

```
M(C) = sqrt( C_crit / C )
```

This identity is **asserted in the harness at every reported row**, not assumed.
It is why two apparently different figures describe the same fact:

```
C_crit / C   at C = 1e3   =  143.29
M(1e3)                    =   11.9705  =  sqrt(143.29)
```

**143× is the C-ratio; 12× is its square root.** Quoting one against the other as
a discrepancy is a misreading.

The exponent is fitted, not assumed: `M ∝ C^(−0.500000)`, max log-residual `2.66e-15`.
Inverse square root — neither linear nor quadratic in `C`.

## Results — worst-conditioned zero (k=204, γ=402.86192)

`s_min(A₋) = 6.6396e−05`, `‖A₋A₋ᵀ‖ = 0.2772`, `ε = 1e−3`:

| C | τ(C) | M(C) | |
|---:|---:|---:|---|
| 1e0 | 1.7540e−07 | 378.54 | resolvable |
| 1e2 | 1.7540e−06 | 37.85 | resolvable |
| **1e3** | 5.5467e−06 | **11.97** | resolvable |
| 1e5 | 5.5467e−05 | 1.20 | resolvable |
| **1.4329e5** | 6.6396e−05 | **1.0000** | ← `C_crit` |
| 1e6 | 1.7540e−04 | 0.38 | NOT resolvable |

`C_crit` carries `ε` as well:

| ε | M(1e3) | C_crit |
|---:|---:|---:|
| 1e−1 | 122.63 | 1.5038e+07 |
| 1e−3 | 11.97 | 1.4329e+05 |
| 1e−5 | **1.20** | **1.4322e+03** |

At `ε = 1e−5` the declared `C = 1e3` sits only **1.43× below its own critical value**.

## Distribution over all 300 zeros (ε = 1e−3)

```
C_crit :  min=1.4329e+05   median=1.0009e+11   max=6.0729e+12
M(1e3) :  min=11.9705      median=10004.37     max=77929.05
M(1e3) < 10 : 0/300        M(1e3) < 100 : 2/300
```

The worst zero is a **~6-order outlier**, not the typical case.

## Identifiability holds, and more narrowly than the general theorem needs

`s_min(A₋) > 0` on all 300 tested zeros, so `ker(A₋) = {0}` throughout.

This matters because the Douglas converse — *difference ⪰ 0 ⟹ ‖T‖ ≤ 1* — is **false in
general**: with `A₋ = 0`, any `T` satisfies it. The condition constrains `I − TTᵀ`
only on `range(A₋ᵀ)`.

In this pipeline that failure mode is structurally excluded: `T` is obtained as
`A₋⁺A₊` via `lstsq`, i.e. minimum norm, so its columns lie in `range(A₋ᵀ)` and carry
no component in `ker(A₋)` (verified: `‖KᵀT‖ = 0` over 500 rank-deficient draws).

What remains is not a logical gap but amplification: `‖A₋⁺‖ = 1/s_min = 1.5061e+04`
at the worst zero. That is what the margin above measures.

## Observed floor — measured, still not a bound

400 exact-contraction draws (`‖T‖ = 1`, i.e. `κ = 0`; exact arithmetic gives 0):

```
|λ|_max :  median=6.2860e-17   max=2.8166e-16
C_obs   =  4.575
```

The declared `C = 1e3` is **218.6× above the observed floor**; under `C_obs` the
worst-zero margin would be `M = 176.97` rather than `11.97`.

`C_obs` is measured at **one** zero under **one** perturbation family, and covers only
floating-point evaluation of the residual at **exact inputs**. It does not cover input
perturbation. **It bounds nothing** — it only shows the declared `C` is conservative
rather than arbitrary.

## Status of the layer this supports

```
Layer 1   dim P(V) = 2  for all 300 tested zeros
          VERIFIED_NUMERICAL — not a theorem, and stated without an arrow to
          η ≡ 0 unless the hypotheses that implication needs are separately
          stated and proved.

Layer 2   A₊ = A₋T ,  κ = ‖T‖₂ − 1 ,  A₋(I − TTᵀ)A₋ᵀ ⪰ 0
          exact structural reduction + the finite conditioning envelope above.
          Sign: the PSD residual is A₋(I − TTᵀ)A₋ᵀ. Its negative is NOT PSD.

Layer 3   "maximal non-destructive subtraction"
          NOT_ESTABLISHED — interpretive analogy only, unboxed.
          Formalising it as ‖(I−P)c‖ > 0 yields orthogonal projection, which has
          no contractive factor, no operator-order statement, and no positivity
          cone — i.e. none of the Douglas content the phrasing borrowed. And
          ‖(I−P)c‖ > 0 proves non-membership in the chosen subspace, not novelty.
```

## Position in the verification stack

This is a **research evidence producer → deterministic receipt →
non-authoritative numerical checkpoint**. It is deliberately **not** in blocking CI.

Promotion to a stronger verification layer requires deriving `C` from the
`QR → SVD → P_Qg` backward-error chain. Until then `C` is a convention and the
margin is reported as a function of it, never as a single number.

## Reproduce

```bash
cd research/rh
python conditioning.py receipts/conditioning_n300_seed20260825.json
```

Requires `numpy`, `scipy`, `mpmath`. Deterministic: seed `20260825`, and zeros come
from `mpmath.zetazero` at `dps=25`. `A₋` is read from the live `Kappa.at()` pipeline
in `kappa.py` rather than reimplemented, so the report describes the conditioning of
the actual `κ` computation.
