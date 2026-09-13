# WEIL_CROSS_TERM_KERNEL_V1

Disposition: mathematical derivation for review; NOT Lean-kernel verified.
Source anchor: PR #493, head f10d066152dd07fcbe6497566213d91f29e68c5a,
rechecked 2026-09-13. This document adds no axiom, theorem declaration, or
authority promotion. The underlying Lean sources and their normalization are unchanged.

The existing registry entry used is GitHub PR/CI, together with
sovereign-omega-v2/formal/bridges/lean/WeilCriterionCompactSmoothV1.lean,
WeilAutocorrelationClosureV1.lean, WeilAutocorrelationRealityV1.lean, and
WeilArchimedeanConvergenceV1.lean. At this anchor the searched formal sources and
docs/rh do not establish the asserted 29/96 local bound, moment parameterization,
or moment-preserving localization theorem. Those remain supplied hypotheses
unless separately bound to verified declarations and a source head.

## 1. Exact mixed form in the existing definitions

For a,b in WeilCompactSmoothGV1, write

F_ab(x) = integral_(y>0) a(xy) conjugate(b(y)) dy,
L(f) = WeilExplicitRightSideV1(f),
B(a,b) = L(F_ab), and Q(a) = Re L(F_aa).

The measure is dy, not dy/y. F_ab has compact support inside
{u/v : u in tsupport(a), v in tsupport(b)}, a compact subset of (0,infinity).
Its integrand has fixed compact support in y, and the smooth parameter-integral
argument used for autocorrelation applies with the second factor b. Thus F_ab
belongs to the same compact-smooth class, and the existing general RHS
convergence theorem applies mathematically. This mixed-class application is
not yet a new checked Lean theorem.

Alternatively, on the underlying vector space of these test functions,

F_ab = (F_(a+b,a+b) - F_(a-b,a-b)
        + i F_(a+ib,a+ib) - i F_(a-ib,a-ib))/4.

This is the polarization identity for the convention linear in the first
argument. It also reduces mixed closure to closure under finite linear
combinations and the checked diagonal result. Linearity of L is used only on
convergent expressions; totalized Lean integrals/tsums are not a substitute
for these convergence facts.

A positive scaling change of variable gives
F_ab(x^-1) = x conjugate(F_ba(x)) for x>0.
The real coefficients of L then give B(b,a)=conjugate(B(a,b)).
For any FINITE family, integral and sum linearity now give exactly

Q(sum_j g_j) = sum_j Q(g_j) + 2 Re sum_(i<j) B(g_i,g_j).

Countably infinite localization requires separate convergence and limit
interchange theorems. None is assumed here.

## 2. Logarithmic coordinates and the exact kernel

Define h_a(t)=exp(t/2) a(exp t), and

R_ab(u) = integral_R h_a(t+u) conjugate(h_b(t)) dt.

The substitutions y=exp(t), x=exp(u) give

F_ab(exp u) = exp(-u/2) R_ab(u),
||h_a||_2^2 = integral_(x>0) |a(x)|^2 dx.

The two existing moments become precisely

integral_R exp(-t/2) h_a(t) dt = 0,
integral_R exp( t/2) h_a(t) dt = 0.

This fixes the h normalization for this document. A differently defined h in
a local theorem needs an explicit correspondence before importing its constant.

Let kappa = log(4*pi) + EulerMascheroniConstant, and Lambda be von Mangoldt.
The repository indexes n+1; below the identical sum is indexed by m>=2,
since Lambda(1)=0. Direct substitution in its RHS gives

$$
B_{\mathrm{prime}}(a,b)=\sum_{m\ge2}\frac{\Lambda(m)}{\sqrt m}
\bigl(R_{ab}(\log m)+R_{ab}(-\log m)\bigr).
$$

$$
B_\infty(a,b)=\kappa R_{ab}(0)+
\int_0^\infty
\frac{e^{u/2}\bigl(R_{ab}(u)+R_{ab}(-u)\bigr)-2R_{ab}(0)}
{e^u-e^{-u}}\,du.
$$

B(a,b) = B_infinity(a,b) + B_prime(a,b).

These are formulas for the defined arithmetic RHS, not a proved
explicit-formula identification with a zeta-zero sum.

The prime sum is finite for each pair because R_ab has compact support.
At u=0 the combined numerator is u R_ab(0)+O(u^2), so its quotient tends
to R_ab(0)/2. At infinity the remaining counterterm is integrable.
Do not split this integral into separately divergent terms at zero.

If K_a and K_b are the log supports, then

tsupport(R_ab) is contained in K_a-K_b.

In the original positive coordinate the corresponding envelope is a RATIO,
not a difference. The difference assertion belongs to log coordinates.
It is an inclusion, not an equality.

## 3. Separated blocks: archimedean decay and moment improvement

Suppose K_a lies in I_a and K_b in I_b, finite intervals with I_a strictly
to the right of I_b, and delta=inf(I_a)-sup(I_b)>0.
Then R_ab(0)=0 and R_ab(-u)=0 for u>0. Set

k(v)=exp(-v/2)/(1-exp(-2v)), v>0.

The exact double-integral form is

$$
B_\infty(a,b)=\int_{I_a}\int_{I_b}
h_a(s)\overline{h_b(t)}k(s-t)\,dt\,ds.
$$

Without moments this gives
|B_infinity| <= k(delta) ||h_a||_1 ||h_b||_1.

More sharply, k(v)=sum_(r>=0) exp(-(2r+1/2)v), uniformly on v>=delta.
Absolute domination by k(delta)|h_a(s)||h_b(t)| justifies interchange.
Writing alpha_r=2r+1/2 gives the exact factorization

$$
B_\infty(a,b)=\sum_{r\ge0}
\left(\int_{\mathbb R}e^{-\alpha_rs}h_a(s)\,ds\right)
\overline{\left(\int_{\mathbb R}e^{\alpha_rt}h_b(t)\,dt\right)},
\qquad \alpha_r=2r+\tfrac12.
$$

If the existing moment conditions hold, the r=0 term vanishes. Therefore

$$
|B_\infty(a,b)|\le
\frac{e^{-5\delta/2}}{1-e^{-2\delta}}\|h_a\|_1\|h_b\|_1
\le
\sqrt{|I_a||I_b|}\,
\frac{e^{-5\delta/2}}{1-e^{-2\delta}}\|h_a\|_2\|h_b\|_2.
$$

Reverse interval order follows by Hermitian symmetry.
This is a written proof, not yet a kernel-certified declaration.
It does not cover overlapping blocks or a zero separation gap.

## 4. Prime re-entry: an exact moment-zero two-block witness

Choose 0<w<log(3/2), a nonzero real nonnegative smooth bump phi supported
in [-w/2,w/2], and h_0=phi''-phi/4. Integration by parts gives

integral exp(+-t/2) h_0(t) dt = 0.

Let d=log 2, h_b(t)=h_0(t), h_a(t)=h_0(t-d), and recover each original
g by g(x)=x^(-1/2)h(log x) for x>0, extended by zero for x<=0.
These are genuine members of the existing test-function class. Both obey
the original moments, since translation only rescales the two zero moments.

Both diagonal correlations have support in [-w,w]; hence their prime
terms vanish because w<log 2. The mixed correlation has support in
[d-w,d+w]. This contains only log 2 among log m for integers m>=2 and
contains no negative log m. At its center R_ab(d)=||h_0||_2^2. Thus EXACTLY

$$
B_{\mathrm{prime}}(a,b)=\frac{\log 2}{\sqrt2}\|h_0\|_2^2>0.
$$

The strict inequality holds because h_0 is nonzero: a compactly supported
solution of phi''=phi/4 is zero. This is an explicit prime resonance between
disjoint moment-zero blocks, even though both diagonal prime sums are zero.

The archimedean part is also explicit:

$$
B_\infty(a,b)=\sum_{r\ge1}e^{-\alpha_rd}(\alpha_r^2-\tfrac14)^2
\left(\int_{\mathbb R}e^{-\alpha_rt}\phi(t)\,dt\right)
\left(\int_{\mathbb R}e^{\alpha_rt}\phi(t)\,dt\right),
\quad \alpha_r=2r+\tfrac12.
$$

Every displayed term is positive. This does NOT prove Q(a+b)>0:
the diagonal negative budget has not been compared with this cross term.
It falsifies only the claim that disjoint support or zero moments eliminate
the off-diagonal prime contribution.

## 5. A computable sufficient majorant and its limitation

For any pair let J_ab=(I_a-I_b) union (I_b-I_a), and define

P_ab = sum_(m>=2, log m in J_ab) Lambda(m)/sqrt(m).

Cauchy-Schwarz yields |R_ab(u)|<=||h_a||_2||h_b||_2. If the intervals are
strictly separated, only one of +-log m can occur, and consequently

|B_prime(a,b)| <= P_ab ||h_a||_2 ||h_b||_2.

For separated moment-zero blocks put

K_ab = sqrt(length(I_a) length(I_b))
       exp(-5 delta_ab/2)/(1-exp(-2 delta_ab)),
a_ab = (96/29) (K_ab + P_ab), a_aa=0.

Then a_ab=a_ba>=0 and
|B(a,b)| <= (29/96) a_ab ||h_a||_2||h_b||_2.

This is a valid explicit finite-pair majorant. No uniform row-sum bound
is proved. P_ab depends on prime-power resonance, not just |a-b|.
If its row sum is too large, only this sufficient majorant has failed;
that does not imply the true Gram matrix fails. Establishing actual
failure requires an exact/certified lower bound or a Rayleigh witness.

For translated test blocks h_j(t)=h_0(t-t_j), the entire test is reproducible:
R_ij(u)=R_00(u-(t_i-t_j)). Enumerate the finite integer samples intersecting
each support-difference interval, retain the actual signed/complex values,
and evaluate the regularized archimedean expression above. A numerical
study needs error enclosures before any strict sign or spectral conclusion.

## 6. Correct closure statement and proof boundary

For a finite family, put D_j=-Q(g_j). The exact equivalence is

Q(sum_j g_j)<=0 iff 2 Re sum_(i<j) B(g_i,g_j) <= sum_j D_j.

If D_j >= c||h_j||_2^2 with c=29/96, replacing the right side by
c sum_j ||h_j||_2^2 is SUFFICIENT, not equivalent in general.

Discard zero blocks. Under that local inequality the remaining D_j>0.
The matrix C_ij=B(g_i,g_j)/sqrt(D_i D_j), with C_ii=0, is Hermitian.
For v_j=sqrt(D_j), the exact scalar condition for the specified sum is
v* C v <= v* v. The stronger lambda_max(C)<=1 controls every vector;
it is sufficient for this sum, not necessary for this one vector.
A strict operator norm bound is stronger still.

For symmetric a_ij>=0 with maximum row sum rho<1, put r_i=||h_i||_2.
The elementary proof needs no spectral theorem:

$$
\begin{aligned}
2\Re\sum_{i<j}B_{ij}
&\le 2c\sum_{i<j}a_{ij}r_ir_j\\
&\le c\sum_{i<j}a_{ij}(r_i^2+r_j^2)\\
&=c\sum_i r_i^2\sum_{j\ne i}a_{ij}
\le c\rho\sum_i r_i^2.
\end{aligned}
$$

Hence Q(sum_j g_j)<=-c(1-rho) sum_j r_j^2.
For a nonzero sum the final sum of squared norms is positive.
The infinite-family version additionally needs a justified decomposition,
bounded operator/convergent form, and passage to the limit.

| Obligation | Disposition at this source anchor |
| --- | --- |
| Diagonal compact-smooth closure and arithmetic convergence | Existing exact-head Lean evidence in PR #493 |
| Local negativity with constant 29/96 | User-supplied hypothesis; no bound verified here |
| Moment-zero parameterization theorem in the ledger | No checked declaration identified here |
| Localization preserving both moments and full coverage | No checked declaration identified here |
| Generic finite Gram/Schur closure | Written proof above; Lean formalization open |
| Mixed kernel formula and separated moment decay | Derived above; Lean formalization open |
| Prime re-entry for two moment-zero blocks | Exact written witness above; Lean formalization open |
| Uniform summable off-diagonal bound | OPEN |
| Global Weil sign | OPEN |
| Explicit formula / zero-side and full-class correspondence | OPEN |
| RH | NOT_PROVEN |
| RH claim promotion | BLOCKED |
| authority_effect | NONE |

Next formal target: certify the mixed form, its convergent linearity and the
logarithmic kernel identity against the existing definitions. Next arithmetic
target: bound the actual resonant prime samples on an explicitly specified
moment-preserving decomposition. Neither is discharged by this document.
