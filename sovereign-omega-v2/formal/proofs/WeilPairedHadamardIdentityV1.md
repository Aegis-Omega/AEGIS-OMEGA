# The normalized Weil identity from a paired Hadamard expansion

Status: **[MATH-PROVED] with the external dependencies explicitly listed below.**
This is a complete mathematical argument, not a Lean certificate for the whole
identity. PR #490 separately implements the Mellin-inversion and prime-line
part. Its exact-head kernel receipts belong in the accompanying evidence dossier.

The definitions in this note are those of `WeilCriterionCompactSmoothV1.lean`
and `ZeroHeightSummabilityBridgeV1.lean`, inherited from AEGIS commit
`9f0a2463c2f20ae3e4a931646027219ee6061ef3`.

## Statement and dependencies

Let (f\in C_c^\infty(0,\infty;\mathbb C)), extended by zero to the real line.
This is exactly the mathematical class encoded by `WeilCompactSmoothGV1`.
Set

\[
F(s)=\mathcal Mf(s)=\int_0^\infty f(x)x^{s-1}\,dx,
\quad Z(f)=\sum_\rho m_\rho F(\rho),
\]

where each distinct nontrivial zero occurs once and (m_\rho) is its analytic
multiplicity. Define

\[
P(f)=\sum_{n\ge1}\Lambda(n)[f(n)+n^{-1}f(n^{-1})],
\quad
A(f)=\int_1^\infty
\frac{xf(x)+f(x^{-1})-2f(1)}{x^2-1}\,dx.
\]

Then all displayed integrals and sums in the following identity converge
absolutely, and

\[
\boxed{Z(f)=F(0)+F(1)-P(f)
-[\log(4\pi)+\gamma_E]f(1)-A(f).}
\tag{EF}
\]

The prime sum agrees with `WeilPrimeSumV1`: its natural index is shifted by
one, and the (n=0) von Mangoldt term in the new prime-line theorem is zero.
Multiplying the repository's archimedean numerator and denominator by (x>1)
gives precisely (A(f)). In particular (EF) says

\[
Z(f)=F(0)+F(1)-\operatorname{WeilExplicitRightSideV1}(f).
\]

Inputs, with provenance kept separate:

1. **Repository-proved inputs:** the critical strip, local finiteness of the
   zero carrier, equality of zeta and xi multiplicities at nontrivial zeros,
   weighted inverse-square summability, uniform cubic Mellin decay in the
   closed strip, and the canonical symmetric-height limit. These were
   kernel-checked at parent `9f0a2463c2f20ae3e4a931646027219ee6061ef3`.
2. **Pinned provider source:** the entire completed function
   (\xi(s)=\tfrac12s(s-1)\pi^{-s/2}\Gamma(s/2)\zeta(s)), its functional
   equation, the multiplicity-preserving map (\rho\mapsto1-\rho), and its
   genus-one Hadamard factorization. Relevant source is the provider
   [HadamardBridge.lean](https://github.com/nicholasbulka/li-criterion-rh-equivalence-lean/blob/35df682f3b709ffe5fbcfdd452dfa964bd622b87/Lc/LiCriterion/HadamardBridge.lean),
   [XiGrowth.lean](https://github.com/nicholasbulka/li-criterion-rh-equivalence-lean/blob/35df682f3b709ffe5fbcfdd452dfa964bd622b87/Lc/LiCriterion/XiGrowth.lean),
   [Basic.lean](https://github.com/nicholasbulka/li-criterion-rh-equivalence-lean/blob/35df682f3b709ffe5fbcfdd452dfa964bd622b87/Lc/LiCriterion/Basic.lean),
   and [LogDerivMultiplicity.lean](https://github.com/nicholasbulka/li-criterion-rh-equivalence-lean/blob/35df682f3b709ffe5fbcfdd452dfa964bd622b87/Hadamard/OrderOne/LogDerivMultiplicity.lean).
   `xi_hadamard_factorization_with_multiplicity` requires finite order and
   order at most one; `XiGrowth` supplies those inputs. It does not require RH.
   These source declarations do not themselves constitute a new exact-head
   kernel receipt for the assembled identity in this note.
3. **[EXTERNAL-THEOREM]:** Gauss's digamma integral for \(\Re z>0\),
   [DLMF 5.9.16](https://dlmf.nist.gov/5.9#E16).
   The formula is used below with a full Fubini estimate. Its import into the
   pinned Lean library is a remaining formalization task.
4. Ordinary Fourier/Mellin inversion and the von Mangoldt Dirichlet-series
   identity on \(\Re s>1\). These have Mathlib proofs; PR #490 specializes
   them to the actual AEGIS class and proves the needed integral interchange.

No line localization, positivity, simplicity of zeros, or linear unit-shell
count is an input. Weighted inverse-square summability is stronger than a
bare cumulative quadratic count; this distinction is essential here.

## 1. Fixed-line decay and the involution

Define, for positive (x),

\[
f^\#(x)=x^{-1}f(x^{-1}),\quad q=f+f^\#,
\quad H(s)=\mathcal Mq(s)=F(s)+F(1-s).
\]

Extend (f^\#) by zero on (x\le0). Inversion takes a compact subset of
((0,\infty)) to another such subset. Hence (f^\#) and (q) are in the
same compact smooth class. The identity for their Mellin transforms follows
by (x=1/y), including its Jacobian.

For every fixed real \(\sigma\), the profile

\[
u\longmapsto e^{\sigma u}f(e^u)
\]

is smooth and compactly supported. Integrating its Fourier transform by
parts (j) times, with zero boundary terms, gives

\[
|F(\sigma+it)|\le D_{\sigma,j}(1+|t|)^{-j}.
\]

Thus at any chosen (c>1), there is (D\ge0) with

\[
|H(c+it)|\le D(1+|t|)^{-3},\quad
A_0=\int_{\mathbb R}|H(c+it)|\,dt<\infty,\quad
A_1=\int_{\mathbb R}|t|\,|H(c+it)|\,dt<\infty.
\]

This decay at (c) and (1-c) is proved from compact support; a theorem
restricted to the critical strip alone would not supply it.
For absolutely integrable expressions define

\[
I_c[G]=\frac1{2\pi}\int_{\mathbb R}G(c+it)\,dt.
\]

## 2. Pair before exchanging the zero sum and integral

Write (L=\xi'/\xi). The genus-one product, differentiated away from zeros,
gives

\[
L(s)=B+\sum_\rho m_\rho
\left(\frac1{s-\rho}+\frac1\rho\right).
\tag{H1}
\]

The summand equals (s/[\rho(s-\rho)]). On compact sets away from zeros,
its tail is bounded by a constant times \(|\rho|^{-2}\), so the indicated
series is absolutely and locally uniformly convergent. This justifies
differentiation of the canonical product's logarithm locally, without a
global choice of logarithm. The exponential prefactor contributes (B).

The functional equation implies (L(1-s)=-L(s)). Subtract (H1) at (1-s)
from (H1) at (s), keeping each convergent genus-one summand intact:

\[
2L(s)=\sum_\rho m_\rho K_\rho(s),\qquad
K_\rho(s)=\frac1{s-\rho}+\frac1{s-(1-\rho)}
=\frac{2s-1}{(s-\rho)(s-(1-\rho))}.
\tag{H2}
\]

The constant cancels. This does not split off the generally unjustified
series \(\sum m_\rho/\rho\).

Here is the absolute product-integral estimate needed to use (H2).
Put \(\delta=c-1>0\), (\rho=b+i\gamma), and (h=|\gamma|\ge1).
If \(|t|\le h/2\), both denominator norms in the last expression for
(K_\rho(c+it)) are at least (h/2). Therefore

\[
|K_\rho(c+it)|\le
\frac{4(2c+1+2|t|)}{h^2}.
\]

If \(|t|>h/2\), the real parts of both denominators exceed \(\delta\),
because (0<b<1). Hence \(|K_\rho(c+it)|\le2/\delta\). Also

\[
\int_{|t|>h/2}|H(c+it)|\,dt
\le\frac{D}{(1+h/2)^2}\le\frac{4D}{h^2}.
\]

Combining these two regions yields

\[
\int_{\mathbb R}|K_\rho(c+it)H(c+it)|\,dt
\le\frac{M}{h^2}\le\frac{2M}{|\rho|^2},
\quad M=4(2c+1)A_0+8A_1+8D/\delta.
\tag{FB}
\]

The last inequality uses \(|\rho|^2=b^2+h^2\le2h^2\).
There are only finitely many zeros with (h<1): they lie in the compact
rectangle (0\le b\le1, |\gamma|\le1), and the entire function xi is not
identically zero. Each has finite multiplicity and an integrable paired
term, by the bound (2|H|/\delta). Thus

\[
\sum_\rho m_\rho\int_{\mathbb R}|K_\rho H|\,dt<\infty.
\tag{FZ}
\]

Fubini now applies. Absolute convergence of (Z(f)) alone would not have
justified this exchange; (FZ) is the additional fact proved here.

## 3. Evaluate the paired zero integral

For any (a\in\mathbb C) with \(\Re a<c\),

\[
\frac1{s-a}=\int_0^\infty e^{-(s-a)v}\,dv,
\qquad
I_c\!\left[\frac{F(s)}{s-a}\right]
=\int_1^\infty f(x)x^{a-1}\,dx.
\tag{KI}
\]

For the second equality the double absolute integral is bounded by
\(\int|F(c+it)|dt/(c-\Re a)\). Consequently Fubini applies to the Laplace
representation. Mellin inversion at (x=e^v) evaluates the inner integral
as (f(e^v)); then (x=e^v) gives (KI). Both endpoint conventions at
(x=1) have the same Lebesgue integral.

Apply (KI) to (q) and to (a=\rho,1-\rho). The reciprocal substitution
in the (f^\#) terms gives

\[
I_c[K_\rho H]=F(\rho)+F(1-\rho).
\]

By (FZ), the strip, multiplicity-preserving reflection, and absolute
convergence of the Mellin zero sum,

\[
I_c[LH]=\frac12\sum_\rho m_\rho[F(\rho)+F(1-\rho)]
=Z(f).
\tag{ZL}
\]

For completeness, absolute convergence here follows from
\(W_2=\sum m_\rho/|\rho|^2<\infty\) and the quadratic consequence of
the uniform cubic strip bound:
\(|\rho|\le1+|\Im\rho|\) gives
\(m_\rho|F(\rho)|\le Dm_\rho/|\rho|^2\).

## 4. The prime and elementary pole terms

On \(\Re s=c>1\), the von Mangoldt identity is

\[
-\frac{\zeta'}{\zeta}(s)=\sum_{n\ge1}\Lambda(n)n^{-s}.
\]

The absolute product integral for (H) is at most

\[
\left(\sum_{n\ge1}\Lambda(n)n^{-c}\right)A_0<\infty.
\]

Fubini and Mellin inversion therefore give

\[
I_c[(\zeta'/\zeta)H]=-\sum_{n\ge1}\Lambda(n)q(n)=-P(f).
\tag{PL}
\]

This is the direct specialization implemented in `WeilPrimeLineIdentityV1`
when applied to (q). Closure of the reciprocal test function is proved in
prose above; it is not silently supplied as a compiled AEGIS theorem.

Using (KI) with (a=0,1) in exactly the same way as the paired zero kernel,

\[
I_c[(1/s+1/(s-1))H]=F(0)+F(1).
\tag{PO}
\]

## 5. The normalized gamma term, including its Fubini bound

Gauss's integral says, for \(\Re z>0\),

\[
\psi(z)+\gamma_E=\int_0^\infty
\frac{e^{-u}-e^{-zu}}{1-e^{-u}}\,du.
\tag{G}
\]

Use (z=s/2). This must be integrated with the numerator combined.
For (0<u\le1), the segment between (1) and (s/2) has positive real
part. The fundamental theorem of calculus along that segment gives
\(|e^{-u}-e^{-su/2}|\le u|1-s/2|\). Since \(1-e^{-u}\ge u/2\),
the quotient is bounded by (2|1-s/2|).
For (u\ge1), it is bounded by

\[
\frac{e^{-u}+e^{-cu/2}}{1-e^{-1}},
\]

an integrable function independent of (t). Hence its absolute (u)
integral is at most (C_c(1+|t|)). Multiplication by (|H(c+it)|) and
the finiteness of (A_0+A_1) prove absolute integrability on the product.
Fubini in (G) is therefore valid.

Mellin inversion gives (I_c[H]=q(1)=2f(1)) and
\(I_c[e^{-su/2}H]=q(e^{u/2})\). Substituting (x=e^{u/2}) yields

\[
I_c[\tfrac12\psi(s/2)H]
=-\gamma_E f(1)+
\int_1^\infty\frac{2f(1)/x-xq(x)}{x^2-1}\,dx.
\]

Compare the combined numerator with that of (A(f)):

\[
\frac{2f(1)/x-xq(x)}{x^2-1}
=-\frac{xq(x)-2f(1)}{x^2-1}
-\frac{2f(1)}{x(x+1)}.
\]

The first term has a removable endpoint and an integrable tail; the
second is independently integrable, with integral (-2\log2\,f(1)).
The constant (-\tfrac12\log\pi) contributes (-\log\pi\,f(1)).
Consequently

\[
I_c[(-\tfrac12\log\pi+\tfrac12\psi(s/2))H]
=-[\log(4\pi)+\gamma_E]f(1)-A(f).
\tag{GL}
\]

At no point were two divergent endpoint integrals subtracted after separate
integration.

## 6. Assemble the identity

The logarithmic derivative of the completed product on (c>1) is

\[
L(s)=\frac1s+\frac1{s-1}-\tfrac12\log\pi
+\tfrac12\psi(s/2)+\frac{\zeta'}{\zeta}(s).
\]

All its products with (H) are integrable by the estimates above. Apply
(I_c), then (ZL), (PO), (GL), and (PL). This proves (EF).

The proof works on any fixed (c>1); it needs no moving contour, no
selection of good heights, and no unproved estimate for horizontal contour
segments. It establishes an identity and provides no sign inequality.

## 7. Exact consequence for the current quadratic form

Let (g) be in the same class and

\[
f_g(x)=\int_0^\infty g(xy)\overline{g(y)}\,dy.
\]

If the support of (g) lies in ([a,b]\subset(0,\infty)), then the support
of (f_g) lies in ([a/b,b/a]). Differentiation under the integral is
valid to every order: (y\in[a,b]), and (y^j g^{(j)}(xy)\overline{g(y)})
has an integrable uniform bound on each compact (x)-interval. Thus (f_g)
belongs to the same compact smooth class. Fubini for its Mellin transform
is valid because (y) and (xy) range over compact positive intervals.
Writing (G=\mathcal Mg), the change of variables (u=xy) gives

\[
\mathcal M f_g(s)=G(s)\overline{G(1-\overline s)}.
\]

The repository moment conditions are (G(0)=G(1)=0), so (EF) becomes

\[
\operatorname{WeilExplicitRightSideV1}(f_g)
=-\sum_\rho m_\rho G(\rho)\overline{G(1-\overline\rho)}.
\tag{Q}
\]

The zero sum is absolute. On the critical line its summands are
(m_\rho|G(\rho)|^2); off that line they are cross terms. Equation (Q)
proves neither nonnegativity of the zero expression nor nonpositivity of
the arithmetic expression.

The next mathematical sign obligation is exactly

```lean
-- Proposed target, NOT a proved declaration in this note.
theorem weil_compact_smooth_arithmetic_nonpositive_v1
    (g : WeilCompactSmoothGV1) (hm : WeilMomentConditionsV1 g) :
    (WeilExplicitRightSideV1 (WeilAutocorrelationV1 g)).re ≤ 0
```

Together with the previously proved reality and the mathematical closure of
autocorrelations, this is the restricted negativity candidate. A formal
RH-equivalence for this exact restricted class remains a separate obligation.

## 8. Falsification of the shortcut from convergence to positivity

Even strip localization, multiplicity positivity, both zero symmetries,
and every counting/summability bound used here do not force the sign in (Q).
Choose (0<a<1/2), (\tau>0), and the four-point artificial spectrum

\[
\mathcal Z=\{a+i\tau,a-i\tau,1-a+i\tau,1-a-i\tau\},\qquad m=1.
\]

There exists a real compact smooth (g) on the positive half-line with

\[
G(0)=G(1)=0,\quad
G(a\pm i\tau)=1,\quad G(1-a\pm i\tau)=-1.
\]

Here is a proof of that interpolation assertion. On any open bounded
logarithmic interval, the six real functions (1,e^u,
e^{au}\cos(\tau u),e^{au}\sin(\tau u),
e^{(1-a)u}\cos(\tau u),e^{(1-a)u}\sin(\tau u)) are linearly independent.
Indeed a real dependence becomes a complex dependence among exponentials
with six distinct exponents; differentiating zero through order five at
an interior point gives an invertible Vandermonde system. If their six
integrals against real compact smooth test functions did not map onto
(\mathbb R^6), a nonzero linear combination would annihilate all tests.
The fundamental lemma of distributions would make that continuous
combination identically zero, contradicting independence. Choose the
prescribed six values and set (g(x)=h(\log x)), with zero extension.
This proves the assertion with genuine test functions, including both
moment constraints.

For this spectrum the zero quadratic expression equals (-4), not a
nonnegative number. This is **[REFUTED]** evidence against the proposed
generic implication from convergence and symmetry to positivity. It is
not a counterexample for the actual zeta zeros, and the artificial spectrum
is not claimed to satisfy the zeta explicit formula with its actual prime
terms. The arithmetic sign in (Q) still requires a new proof.

## Bounded disposition

Full normalized identity: MATH_PROVED with listed external dependencies.
Whole identity in the AEGIS Lean kernel: OPEN.
Prime-line part: determined by the exact-head PR #490 kernel receipt.
Original linear shell obligation: independently OPEN in this lane.
Global positivity and zero localization: OPEN.
RH = NOT_PROVEN. claim_promotion = NONE for RH or authority-bearing claims.
authority_effect = NONE. merge = NOT_PERFORMED.
