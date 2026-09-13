# Weil autocorrelation closure V1

Source base: PR #489 at `9f0a2463c2f20ae3e4a931646027219ee6061ef3`.
Audit context: PR #487 at `6f828a4515a66497007f7c8b5318e13c764c6e0a`.
Mathlib: `0df444a360eaa60ab8c11dca51a86af692955474`; Lean 4.33.1.

The historical `RH_D0_ANALYTIC_FOUNDATIONS` prescription in #487 has been
superseded by its September 12 scope correction. This change addresses the
existing `AUTOCORRELATION_COMPACT_SMOOTH_BRIDGE` using the existing definitions.
It does not modify the historical census or any cognitive manifest.

## Exact mathematical statement

For `g : WeilCompactSmoothGV1`, let

\[
A_g(x)=\int_0^\infty g(xy)\overline{g(y)}\,dy.
\]

The measure is Lebesgue `dy`, exactly as in `WeilAutocorrelationV1`.
Then `A_g` is smooth on all of the real line, has compact support, and
its topological support is contained in the strictly positive half-line.
Consequently `A_g` belongs to the existing `WeilCompactSmoothGV1` class.
No moment conditions, RH assumption, or sign inequality are needed.

## Mathematical proof

Let `K = tsupport g`. This is compact and contained in `(0,infinity)`.
The ratio map `(u,v) -> u/v` is continuous on `K × K`, since `v` never
vanishes there. Its image `E` is therefore compact and strictly positive.
If `x` is outside `E`, then for every `y` either `g(y)=0` or `g(xy)=0`:
otherwise `(xy,y)` belongs to `K × K` and `x=(xy)/y` belongs to `E`.
Thus `A_g(x)=0`. Since `E` is closed, `tsupport A_g` is a subset of `E`.
This argument also covers `g=0`, for which `K` and `E` are empty.

For every fixed `x`, the integrand is continuous in `y` and vanishes outside
`K`. It is therefore integrable. This separately establishes that the
integral exists; the support argument alone would not justify treating a
totalized Lean integral as a convergent integral.

For smoothness, choose `0<a<b` with `K` contained in `[a,b]`. Such a pair
exists by compactness, with any positive interval usable if `K` is empty.
For each nonnegative integer `n`, the parameter derivative of the integrand is

\[
\partial_x^n\bigl(g(xy)\overline{g(y)}\bigr)
 = y^n g^{(n)}(xy)\overline{g(y)}.
\]

Fix any compact parameter interval `J`. The image of `J × [a,b]` under
multiplication is compact, so every derivative `g^(n)` is bounded there
by some finite `M_n(J)`. Let `G` bound `|g|` on `[a,b]`. The displayed
derivative is bounded in modulus, uniformly for `x` in `J`, by
`b^n M_n(J) G 1_[a,b](y)`, an integrable function. Applying dominated
convergence and differentiation under the integral at each order gives

\[
A_g^{(n)}(x)=\int_0^\infty y^n g^{(n)}(xy)\overline{g(y)}\,dy,
\qquad A_g\in C^\infty(\mathbb R).
\]

The Lean implementation uses Mathlib's
`contDiffOn_convolution_right_with_param_comp` to obtain smoothness directly.
Set `F(p,z)=g(p*(-z))*conj(g(-z))`, supported in `-K` in its second variable,
and convolve it with the constant scalar function `1`, using the measure
`volume.restrict (Ioi 0)`. Evaluation at zero is exactly `A_g(p)`.
This is an identity of integrands, not a change of variables or of measure.
The explicit derivative formula above is explanatory; this patch does not
export it as a separate Lean theorem.

## Connection to existing convergence

`WeilAutocorrelationCompactSmoothV1 g` packages the very same function with
the three closure proofs. Its underlying-function equality is reflexive.
Applying `weil_compact_smooth_explicit_right_side_convergent_v1` to this
packaged function yields both actual prime-series summability and actual
archimedean-integrand integrability for `WeilAutocorrelationV1 g`.

Together with the previously established reality theorem, the original
`WeilCompactSmoothNegativityV1` is equivalent to

\[
\forall g,\quad \operatorname{WeilMomentConditionsV1}(g)
\Longrightarrow \Re\operatorname{WeilExplicitRightSideV1}(A_g)\le0.
\]

This equivalence does not prove the remaining inequality.

## Verification and authority boundary

The new source contains ten public theorem declarations and corresponding
`#print axioms` commands. The extended existing workflow compiles the
definition and four proof modules at the exact PR source head, then audits
all 29 public theorem closures (19 inherited, ten new). Only `propext`,
`Classical.choice`, and `Quot.sound`, or an empty axiom set, are accepted.
Missing closures and `sorryAx` are rejected.

At preparation, the local Lean runtime could not launch. A written proof,
source inspection, and passing TypeScript tests are not kernel verification.
The hosted run and logs must be checked at the resulting candidate SHA before
the formal obligation is marked closed. A subsequent writer commit requires
new exact-head verification; inherited successful runs do not certify this file.

The explicit formula, arithmetic sign inequality, full-class coverage,
cross-carrier semantic correspondence, and RH equivalence remain open.

`RH = NOT_PROVEN`; `RH_CLAIM_PROMOTION = BLOCKED`; `AUTHORITY_EFFECT = NONE`.
No merge, release, or admission follows from this local analytic closure.
