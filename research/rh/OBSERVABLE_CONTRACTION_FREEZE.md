# Observable Contraction Freeze v1

```text
MATHEMATICAL_STATUS      = PROVED_FINITE_DIMENSIONAL
MACHINE_STATUS           = EXACT_REGRESSION_VERIFIED
FIXTURES                 = 7/7 PASS
FORMAL_PROOF_ASSISTANT   = NOT_MACHINE_BOUND
SEMANTIC_TRUTH_BRIDGE    = NOT_ESTABLISHED
```

`PROVED_FINITE_DIMENSIONAL` means the finite-dimensional theorem below has a
complete ordinary mathematical derivation. It does **not** mean that Lean,
Coq, Isabelle, or another proof assistant has checked the theorem. The machine
layer in this repository is narrower: exact `Fraction` regression and
falsification witnesses preserve the stated boundaries and canonical
counterexamples.

This file is the canonical theorem boundary for the Douglas/conditioning
layer. `CONDITIONING.md` remains the numerical evidence report for the tested
RH finite model. Where a general statement about a prescribed `T` would exceed
what `A_-` observes, this freeze governs.

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
threshold. Cross-coupling can destroy feasibility. The canonical fixture is

\[
Y=\begin{pmatrix}1&0\\0&0\end{pmatrix},\qquad
X=\begin{pmatrix}0&1\\1&0\end{pmatrix}.
\]

On `ker(Y)=span(e_2)`, `e_2^T X e_2 = 0`, so the kernel condition holds. But

\[
X-\lambda Y
=\begin{pmatrix}-\lambda&1\\1&0\end{pmatrix},
\qquad
\det(X-\lambda Y)=-1
\]

for every finite real `lambda`; hence no member of the affine family is PSD.
The exact kernel locks this as a symbolic 2x2 determinant-polynomial witness,
not as a sample over selected `lambda` values.

## Exact PSD decision boundary

For a real symmetric matrix, positive semidefiniteness is equivalent to
non-negativity of **all principal minors**. Non-negative leading principal
minors alone are insufficient for PSD. Symmetry is also mandatory.

Two permanent regression guards are canonical:

\[
A=\begin{pmatrix}0&0\\0&-1\end{pmatrix}.
\]

Its leading principal minors are `0, 0`, yet `A` is not PSD because the
principal minor indexed by the second coordinate is `-1`.

And

\[
B=\begin{pmatrix}1&1\\0&1\end{pmatrix}
\]

must be rejected because it is not symmetric.

The exact `is_psd` implementation therefore checks symmetry first and then
enumerates every principal minor using `Fraction` arithmetic.

## Layer 2 — Observable Contraction Theorem

Assume

\[
A_+=A_-T,
\qquad
Q:=I-TT^T,
\qquad
D:=A_-A_-^T-A_+A_+^T=A_-QA_-^T.
\]

Define

\[
\mathcal R_-:=\operatorname{Ran}(A_-^T),
\qquad
P_-:=P_{\mathcal R_-},
\qquad
C_-:=P_-TT^T\big|_{\mathcal R_-}.
\]

For every vector `y`,

\[
y^TDy
=
(A_-^Ty)^TQ(A_-^Ty).
\]

Since `Ran(A_-^T)=R_-`, this gives

\[
D\succeq0
\iff
z^TQz\ge0\qquad\forall z\in\mathcal R_-.
\]

For `z in R_-`,

\[
z^TQz
=
\|z\|^2-\|T^Tz\|^2
=
\left\langle
z,
\left(I_{\mathcal R_-}-P_-TT^T\big|_{\mathcal R_-}\right)z
\right\rangle.
\]

Therefore, without any rank assumption,

\[
\boxed{
D\succeq0
\iff
I_{\mathcal R_-}-C_-\succeq0
\iff
\lambda_{\max}(C_-)\le1.
}
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

Then

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

Because `R_-` is finite-dimensional, the maximum is attained. Hence

\[
\boxed{
\kappa_{\rm eff}=0
\Longrightarrow
\exists\,0\ne z\in\mathcal R_-:
P_-TT^Tz=z.
}
\]

This is the zero-defect **observable** direction. In general it does **not**
imply

\[
TT^Tz=z,
\]

because `TT^Tz` may contain a component in `R_-^perp` that `A_-` does not
observe.

Thus:

| level | object | authority |
|---|---|---|
| Global | `TT^T` | requires full access |
| Observable | `P_- TT^T |_{R_-}` | certified by `D` |
| Null | `R_-^perp` | not observable through `A_-` |

### Full-column-rank corollary

If `A_-` has `n` columns and

\[
\operatorname{rank}(A_-)=n,
\]

then `R_-=R^n` and `P_-=I`. Only under that rank fact does the theorem reduce
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

The 300 instances in `CONDITIONING.md` were **numerically classified** as
full-column-rank because their floating-point SVD returned positive measured
`s_min(A_-)`. Conditional on that numerical rank classification, the
global-norm statement is the full-rank corollary for those tested instances.
This numerical observation is **not** an exact algebraic rank receipt and is
not a rigorous interval lower bound for `s_min(A_-)`.

Promotion of `ker(A_-)=0` to exact/formal authority requires a separate exact
rank certificate or a rigorous interval certificate proving `s_min(A_-)>0`.

### Douglas factorisation boundary

Douglas remains

\[
\boxed{
A_+A_+^T\preceq A_-A_-^T
\iff
\exists C:\ A_+=A_-C,\ \|C\|_2\le1.
}
\]

This is an existence statement for a contractive factor `C`. If a particular
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
semantic truth theorem. Until a separate semantic bridge is proved, the
allowed label is

\[
\boxed{
r_{\theta_\star}=\texttt{MAXIMAL_ADMISSIBLE_RESIDUAL}
}
\]

and the truth identification remains

`NOT_ESTABLISHED`.

## Exact regression kernel

The dependency-free exact kernel uses `fractions.Fraction`; no floating-point
tolerance is involved. Seven committed regressions are mandatory:

1. PSD rejects the leading-principal-minors-only counterexample;
2. PSD rejects a non-symmetric matrix;
3. singular-`Y` Layer-1 cross-coupling has `det(X-lambda Y) == -1` identically;
4. rank-deficient prescribed-`T` need not be a global contraction;
5. full-column-rank recovers the global-norm equivalence;
6. observable compression can contract while global `||T|| > 1`;
7. zero-defect fixture has `P_-TT^T z = z` but `TT^T z != z`.

These are regression/falsification witnesses. They are **not** a universal
machine proof of the Observable Contraction Theorem.

Run:

```bash
cd research/rh
python -m unittest -v test_observable_contraction_exact.py
```

Hosted gate: `RH Observable Contraction Exact`.

The workflow path filter includes this canonical freeze file itself, so an
isolated future edit to the theorem boundary must rerun the exact regression
kernel.
