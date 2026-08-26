# Observable Contraction Freeze

Status: **THEOREM-SAFE FINITE-DIMENSIONAL FREEZE**

This file is the canonical theorem boundary for the Douglas/conditioning layer.
`CONDITIONING.md` remains the numerical evidence report for the tested RH finite
model; where a general statement about a prescribed `T` would exceed what
`A_-` observes, this freeze governs.

## Layer 1 — generalized PSD threshold

For symmetric `X` and `Y >= 0`, the primary definition is extended-real:

\[
\lambda_\star
=
\sup\{\lambda\in\mathbb R: X-\lambda Y\succeq0\}.
\]

When the feasible set is nonempty and the threshold is finite,

\[
\lambda_\star
=
\inf_{v:\,v^T Yv>0}
\frac{v^T Xv}{v^T Yv}.
\]

The condition

\[
v^T Xv\ge0\qquad\forall v\in\ker Y
\]

is necessary but is not by itself sufficient for a finite feasible PSD
threshold.  Cross-coupling can destroy feasibility.  The canonical fixture is

\[
Y=\begin{pmatrix}1&0\\0&0\end{pmatrix},\qquad
X=\begin{pmatrix}0&1\\1&0\end{pmatrix}.
\]

The kernel condition holds on `ker(Y)=span(e_2)`, while

\[
X-\lambda Y
=\begin{pmatrix}-\lambda&1\\1&0\end{pmatrix}
\]

is not PSD for any finite `lambda`; equivalently the Rayleigh quotient
`2ab/a^2 = 2b/a` is unbounded below.

## Layer 2 — Observable Contraction Theorem

Assume

\[
A_+=A_-T,
\qquad
D:=A_-A_-^T-A_+A_+^T
=A_-(I-TT^T)A_-^T.
\]

Define the observable subspace and its orthogonal projector

\[
\mathcal R_-:=\operatorname{Ran}(A_-^T),
\qquad
P_-:=P_{\mathcal R_-}.
\]

The operator certified by `D` is the compression

\[
C_-:=P_-TT^T\big|_{\mathcal R_-},
\]

not the unrestricted global operator `TT^T`.

For every `z in R_-`,

\[
\langle z,C_-z\rangle
=
\langle z,TT^Tz\rangle
=
\|T^Tz\|^2.
\]

Therefore

\[
\boxed{
D\succeq0
\iff
I_{\mathcal R_-}-C_-\succeq0
}
\]

and equivalently

\[
\boxed{\lambda_{\max}(C_-)\le1.}
\]

Define the effective observable defect

\[
\boxed{
\kappa_{\rm eff}
:=
\sqrt{\lambda_{\max}(C_-)}-1
=
\|T^T|_{\mathcal R_-}\|_2-1.
}
\]

Then, without any rank assumption,

\[
\boxed{D\succeq0\iff\kappa_{\rm eff}\le0.}
\]

### Critical observable direction

The critical surface is

\[
\kappa_{\rm eff}=0
\iff
\lambda_{\max}(C_-)=1.
\]

Because `R_-` is finite-dimensional, the maximum is attained.  Hence

\[
\boxed{
\kappa_{\rm eff}=0
\Longrightarrow
\exists\,0\ne z\in\mathcal R_-:
P_-TT^Tz=z.
}
\]

This is the zero-defect **observable** direction.  In general it does **not**
imply

\[
TT^Tz=z,
\]

because `TT^T z` may contain a component in `R_-^perp` that `A_-` does not
observe.

Thus:

| level | object | authority |
|---|---|---|
| Global | `TT^T` | requires full access |
| Observable | `P_- TT^T |_{R_-}` | certified by `D` |
| Null | `R_-^perp` | not observable through `A_-` |

### Full-column-rank corollary

If

\[
\operatorname{rank}(A_-)=n,
\]

then `R_-=R^n` and `P_-=I`.  Only in this case does the general theorem reduce
to

\[
\boxed{
D\succeq0
\iff
\|T\|_2\le1
}
\]

and

\[
\kappa_{\rm eff}=\|T\|_2-1.
\]

The numerical `CONDITIONING.md` report measured `s_min(A_-)>0` on all 300
reported finite-model cases; the global-norm specialization in that measured
scope is therefore a full-column-rank corollary, not the rank-deficient general
theorem.

### Douglas factorisation boundary

Douglas remains

\[
\boxed{
A_+A_+^T\preceq A_-A_-^T
\iff
\exists C:\ A_+=A_-C,\ \|C\|_2\le1.
}
\]

This is an existence statement for a contractive factor `C`.  If a particular
`T` has already been prescribed by `A_+=A_-T`, the PSD inequality certifies only

\[
\boxed{
\|T^T|_{\mathcal R_-}\|_2\le1,
}
\]

unless full-column-rank makes `R_-` the whole ambient space.

## HOS authority law

\[
\boxed{
\text{A measurement operator may certify contraction only on the subspace it actually observes.}
}
\]

The compression

\[
TT^T\longmapsto P_-TT^T|_{\mathcal R_-}
\]

is an authority boundary: global instability modes living entirely outside the
observable subspace cannot be promoted to observed instability from `A_-`
evidence alone.

## Layer 3 — semantic boundary remains open

For an optimization residual

\[
r_\theta=c-B\theta\in K,
\]

a maximizer/minimizer supplied by the optimization geometry is not thereby a
semantic truth theorem.  Until a separate semantic bridge is proved, the
allowed label is

\[
\boxed{
r_{\theta_\star}=\texttt{MAXIMAL_ADMISSIBLE_RESIDUAL}
}
\]

and the truth identification remains

`NOT_ESTABLISHED`.

## Exact falsification kernel

The dependency-free exact kernel uses `fractions.Fraction`; no floating-point
tolerance is involved.  Four committed fixtures are mandatory:

1. rank-deficient prescribed-`T` counterexample;
2. full-column-rank global-norm equivalence;
3. observable compression contracts while global `||T|| > 1`;
4. zero-defect fixture with `P_-TT^T z = z` but `TT^T z != z`.

Run:

```bash
cd research/rh
python -m unittest -v test_observable_contraction_exact.py
```

Hosted gate: `RH Observable Contraction Exact`.
