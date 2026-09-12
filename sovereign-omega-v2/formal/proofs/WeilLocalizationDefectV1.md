# Weil localization: exact defect and the failure of the narrow-packet limit

This source-bound mathematical note consolidates the exact localization identity and two quantitative obstructions to promoting local packet positivity to the full Weil criterion. All reference definitions are those of `WeilCriterionCompactSmoothV1.lean` at parent `dcfa2a51f52d941937a7cb72996d58b2d0ec0f43`.

The companion `WeilLocalizationAlgebraV1.lean` proves six finite-frame algebra statements only. Hosted compilation and its exact SHA receipts are reported separately. The integrated identities and limit theorems below have complete mathematical proofs and an independent adversarial audit; no whole-argument kernel claim is made.

The appendix reproduces the prior mathematical derivation of the arithmetic energy normalization and local bound, so these are not hidden repository-proof assumptions. No new axiom, RH assumption or global positivity assumption is introduced.

RH = NOT_PROVEN. Authority effect = NONE.

---

# Exact localization and the cancellation of narrow-support coercivity

Status: **[MATH-PROVED]**, a complete mathematical derivation using the repository normalization at reference head `dcfa2a51f52d941937a7cb72996d58b2d0ec0f43`. The integrated identity, error bounds and limit obstruction are not kernel-checked here. The companion Lean module proves only its finite-frame pointwise algebra. No global positivity or RH is asserted.

## 1. Form and hypotheses

Let h be complex, smooth and compactly supported on R. Set

    C_h(t) = integral h(u+t) conjugate(h(u)) du,
    H = ||h||_2^2,
    kappa(t) = exp(t/2)/sinh(t),
    w_n = Lambda(n)/sqrt(n),
    c_* = log(8*pi) + gamma_E + pi/2,

and use the existing arithmetic quadratic form

    q(h) = (1/2) integral_0^infinity kappa(t)||h(.+t)-h||_2^2 dt
           - c_* H - 2 sum_(n>=2) w_n Re C_h(log n).

The prime sum is finite for compact support. Let chi_1,...,chi_m be real smooth functions with

    sum_j chi_j(u)^2 = 1  for every u in supp(h).

No normalization is needed outside supp(h). For a finite family all products chi_j h remain compact smooth. For the uniform estimates below assume sum_j |chi_j'(u)|^2 <= A^2 on the convex hull of supp(h), or globally. Write

    Delta_chi(u,t) = sum_j (chi_j(u+t)-chi_j(u))^2.

The norm-one identity at both endpoints is invoked only when h(u+t)conjugate(h(u)) is nonzero. At other pairs the cross product is zero.

## 2. Exact localization identity

Pointwise expansion proves

    sum_j |chi_j(u+t)h(u+t)-chi_j(u)h(u)|^2
      - |h(u+t)-h(u)|^2
    = Delta_chi(u,t) Re(h(u+t)conjugate(h(u))).

Indeed the two diagonal terms cancel by the squared-partition identity and the remaining cross term is twice (1 - sum_j chi_j(u+t)chi_j(u)) times the real product. On its active set this coefficient equals Delta_chi. Similarly,

    sum_j Re C_(chi_j h)(t) - Re C_h(t)
    = -(1/2) integral Delta_chi(u,t) Re(h(u+t)conjugate(h(u))) du.

Also sum_j ||chi_j h||_2^2 = H. Hence

    sum_j q(chi_j h) - q(h) = D_arch(h,chi) + D_prime(h,chi),

where

    D_arch = (1/2) integral_0^infinity kappa(t)
               integral Delta_chi(u,t) Re(h(u+t)conjugate(h(u))) du dt,

    D_prime = sum_(n>=2) w_n
               integral Delta_chi(u,log n)
                 Re(h(u+log n)conjugate(h(u))) du.

Both coefficients matter: one half for the continuous energy defect, one for the discrete defect. The scalar potential cancels exactly. Each defect is signed: Delta_chi >= 0 does not imply its product with the real correlation is nonnegative.

All integrations are legitimate. On active pairs, 0 <= Delta_chi <= 4. The derivative bound and vector-valued Cauchy--Schwarz also give Delta_chi <= A^2 t^2. Thus the continuous defect is absolutely integrable near zero (kappa(t) = O(1/t)); away from zero, active cross products have t bounded by the compact support diameter and the kernel is continuous. The pointwise identity can first be integrated on epsilon <= t <= M and then passed to its absolutely convergent limit. No separate integral of the divergent diagonal expression integral_0 kappa(t)H dt is used.

## 3. Explicit localization-error estimate

Let supp(h) have diameter D > 0 and define

    b(t) = min(4, A^2 t^2).

Cauchy--Schwarz and translation invariance yield

    |integral Delta_chi(u,t) Re(h(u+t)conjugate(h(u))) du|
      <= b(t) H.

Therefore

    |sum_j q(chi_j h) - q(h)| <= E_chi(D) H,

    E_chi(D) = (1/2) integral_0^D kappa(t)b(t) dt
               + sum_(2 <= n <= exp(D)) w_n b(log n).

The integer endpoint can be included harmlessly. If all chi_j are nonnegative, Delta_chi <= 2 on the active pairs and b(t) can be replaced by min(2,A^2 t^2). More accurate bounds may keep Delta_chi inside its weighted spatial integral instead of taking the supremum. None of these estimates deletes prime correlations.

Consequently, if every localized packet satisfies q(chi_j h) >= delta ||chi_j h||_2^2, then

    q(h) >= (delta - E_chi(D)) H.

This is a proved sufficient criterion, not a proof that delta > E_chi(D) holds for arbitrary h or fine partitions.

## 4. What narrow localization actually does

Suppose every packet chi_j h has support diameter at most L, where 0 < L < log 2. Then every localized prime correlation vanishes. Moreover, for t >= L, almost every active pair satisfies

    sum_j chi_j(u+t)chi_j(u) = 0,
    Delta_chi(u,t) = 2.

At t = L, possible contacts have measure zero; alternatively retain strict t > L, which gives the same t-integral. Therefore

    D_prime = 2 sum_(n>=2) w_n Re C_h(log n),

and

    D_arch = D_arch,<L + integral_L^infinity kappa(t) Re C_h(t) dt.

The prime interaction is thus restored exactly in the assembly defect. Its disappearance from every individual localized packet is not a global bound on it.

Let

    K(L) = integral_L^infinity kappa(t) dt,
    E(h) = integral_0^infinity kappa(t)(H - Re C_h(t)) dt,
    E_<L(h) = integral_0^L kappa(t)(H - Re C_h(t)) dt.

All integrals here are finite for each fixed L > 0. Exact algebra gives

    integral_L^infinity kappa(t) Re C_h(t) dt
      = H K(L) - E(h) + E_<L(h).

The local support theorem uses the positive term H K(L), and the assembly defect contains exactly the same term H K(L). As L tends to zero,

    K(L) = log(1/L) + O(1),
    0 <= E_<L(h) <= (||h'||_2^2/2) integral_0^L kappa(t)t^2 dt = O_h(L^2).

Thus the explicit tail term H K(L) occurs with the same coefficient in the local coercivity and the assembly subtraction. Without additional derivative control, this does not assert an exact asymptotic for the entire defect: its short-scale part can grow faster. The unconditional lower bound below is sufficient for the obstruction.

For clarity, there is also an exact identity for the remaining short-scale part:

    sum_j E_<L(chi_j h) - D_arch,<L = E_<L(h).

Because every localized short-scale energy is nonnegative, the same identity proves the partition-independent lower bound

    D_arch >= H K(L) - E(h).

For each fixed nonzero h, this tends to positive infinity at least as H log(1/L) as the packet width tends to zero. Hence no family of such fine square partitions can have an archimedean assembly defect tending to zero for that h. Combining the short-scale identity with the displayed tail identity reconstructs E(h) and then the original q(h) exactly. A proof which discards D_arch or D_prime after summing the local inequalities discards the terms responsible for the global question.

## 5. Moment conditions

The arithmetic localization identity and the existing local arithmetic sign theorem require no exponential moment conditions. The original h may satisfy both integrals integral exp(+-u/2)h(u)du = 0; its products chi_j h generally do not. This does not obstruct the arithmetic argument, but it forbids applying a moment-zero zero-functional identity separately to chi_j h without an additional correction.

A moment-preserving decomposition obtained by writing h = (d^2/du^2 - 1/4)phi and then summing (d^2/du^2 - 1/4)(theta_j phi) has a different product-rule expansion. It cannot silently be substituted for a square partition: derivatives of theta_j enter and its squared norms do not sum to H automatically.

## 6. Bounded conclusion

The exact IMS-type identity and its quantitative error bound are proved. They locate the cancellation that prevents local-support positivity, by itself, from settling arbitrary-support positivity. This does not refute global positivity or every possible localization method. Any successful continuation through this route must prove a new estimate on the combined signed defect strong enough to imply

    D_arch(h,chi) + D_prime(h,chi) <= sum_j q(chi_j h)

for every admissible original h and an appropriate admissible partition, or find a genuinely different positive representation. The displayed inequality is precisely what is still missing; it is not supplied by the fact that each localized term is positive.


---

# A quantitative obstruction to passing narrow-packet positivity to arbitrary supports

Status: [MATH-PROVED], complete elementary proof relative to the already derived arithmetic energy identity. This is a limit theorem for the packet method, not a counterexample to Weil positivity. Its proof is mathematical; no kernel verification of this integrated result is claimed.

Write
\[
k(t)=\frac{e^{t/2}}{\sinh t},\quad K(L)=\int_L^\infty k(t)\,dt,
\quad c_*=\log(8\pi)+\gamma_E+\pi/2,
\]
\[
E(h)=\frac12\int_0^\infty k(t)\|h(\cdot+t)-h\|_2^2\,dt,
\quad q(h)=E(h)-c_*\|h\|_2^2-2\sum_{n\ge2}\frac{\Lambda(n)}{\sqrt n}\Re C_h(\log n).
\]
The inherited packet certificate uses local coefficient \(\kappa(L)=K(L)-c_*\), off-diagonal matrix
\[
M_{ij}=\frac L2k(|a_i-a_j|-L)+P_{ij},\qquad P_{ij}\ge0,
\]
and row maximum \(S=\max_i\sum_{j\ne i}M_{ij}\). A successful certificate means \(\kappa(L)-S\ge0\).

## 1. Exact grid theorem

Let \(N\ge4\) be an integer, \(0<\varepsilon\le1/2\), \(\theta=1-\varepsilon\), \(d=1/N\), and \(L=\theta/N\). Put
\[
a_i=i/N\ (0\le i<N),\qquad I_i=[a_i-L/2,a_i+L/2],\qquad \mathcal S_N=\bigcup_{i=0}^{N-1}I_i.
\]
The packet certificate has the following necessary condition:
\[
\boxed{\kappa(L)-S\le\varepsilon\log N-\frac{\theta}{\varepsilon}+4.}\tag{1}
\]
Independently of any certificate, every smooth compactly supported \(h\) supported in \(\mathcal S_N\) satisfies
\[
\boxed{E(h)\ge\varepsilon(H_N-1/2)\|h\|_2^2
       \ge\varepsilon(\log N-1/2)\|h\|_2^2,}\tag{2}
\]
where \(H_N=\sum_{j=1}^N1/j\). Consequently, if the packet certificate succeeds,
\[
\boxed{E(h)\ge\left(\frac{1-\varepsilon}{\varepsilon}-4-\frac\varepsilon2\right)\|h\|_2^2.}\tag{3}
\]
These are lower bounds; when a displayed coefficient is negative the inequality is still valid but uninformative.

### Proof of the necessary certificate condition

The identity
\[
k(t)=\frac{2e^{-t/2}}{1-e^{-2t}}
\]
and \(1-e^{-2t}\le2t\), \(e^{-t/2}\ge1-t/2\), imply the global elementary bound
\[
k(t)\ge\frac1t-\frac12\qquad(t>0).\tag{4}
\]
Let \(m=\lfloor(N-1)/2\rfloor\ge1\). The middle grid point has at least \(m\) neighbors on each side. Drop the nonnegative prime weights. Each pair of neighbors at distance \(jd\) contributes \(Lk(jd-L)\) to this row. Hence
\[
\begin{aligned}
S&\ge\theta\sum_{j=1}^m\frac1{j-\theta}-\frac{Lm}{2}\\
 &\ge\frac\theta\varepsilon+\theta(H_m-1)-\frac14\\
 &\ge\frac\theta\varepsilon+\theta\log m-\theta-\frac14.
\end{aligned}\tag{5}
\]
Here \(Lm\le1/2\) and, for \(j\ge2\), \(1/(j-\theta)\ge1/j\).

The known exact formula
\[
K(L)=\log\coth(L/4)+2\arctan(e^{-L/2})
\]
with \(\coth x=1+2/(e^{2x}-1)\le1+1/x\) gives, since \(L\le1\),
\[
\kappa(L)\le\log(5/L)-\log(8\pi)-\gamma_E\le\log(1/L).
\tag{6}
\]
The last inequality uses only \(\pi>1\) and \(\gamma_E\ge0\).
Since \(N/m\le4\), \(\theta\ge1/2\), and \(\theta\le1\), subtraction of (5) from (6) gives
\[
\begin{aligned}
\kappa(L)-S
 &\le\varepsilon\log N-\frac\theta\varepsilon
  +\theta\log(N/m)-\log\theta+\theta+\frac14\\
 &\le\varepsilon\log N-\frac\theta\varepsilon+\log8+\frac54\\
 &<\varepsilon\log N-\frac\theta\varepsilon+4.
\end{aligned}
\]
This proves (1), with a deliberately simple constant 4. For the last numerical inequality one may use log(2) <= 3/4, obtained from log(x) <= (x - 1/x)/2 for x >= 1 by differentiation; then log(8) + 5/4 <= 7/2 < 4.

### Proof of the forced gap energy

Extend the grid periodically to all integer centers \(id\). The complement between successive intervals contains gaps
\[
G_i=(id+\theta d/2,(i+1)d-\theta d/2),\qquad |G_i|=\varepsilon d.
\]
Every such gap is outside \(\mathcal S_N\), and therefore \(h=0\) there. Symmetrization of the energy gives
\[
E(h)=\frac14\int_{\mathbb R}\int_{\mathbb R}
k(|v-u|)|h(v)-h(u)|^2\,dv\,du.
\]
The integrand is nonnegative, so Tonelli permits restriction to pairs with one point in \(\mathcal S_N\) and the other in the periodic gaps. Consequently
\[
E(h)\ge\frac12\int_{\mathcal S_N}|h(u)|^2
       \int_{\bigcup_iG_i}k(|v-u|)\,dv\,du.\tag{7}
\]
For \(u\in I_i\), the \(j\)-th whole gap to the right and the \(j\)-th whole gap to the left each have length \(\varepsilon d\) and all their points have distance at most \(jd\) from \(u\). The kernel is decreasing, since \(k'/k=1/2-\coth t<0\). Using the first \(N\) gaps on each side in (7), then (4), yields
\[
\begin{aligned}
E(h)&\ge\varepsilon d\sum_{j=1}^Nk(jd)\|h\|_2^2\\
&\ge\varepsilon d\sum_{j=1}^N\left(\frac1{jd}-\frac12\right)\|h\|_2^2
=\varepsilon(H_N-1/2)\|h\|_2^2.
\end{aligned}
\]
This proves (2). When \(\kappa(L)-S\ge0\), (1) gives \(\varepsilon\log N\ge\theta/\varepsilon-4\). Substitution into (2) proves (3).

## 2. The dense-limit implication that is refuted

Let \(N_j\to\infty\) and \(\varepsilon_j\to0\), and assume each corresponding grid is certified by the inherited sufficient row condition. If \(h_j\) is supported on that grid and
\[
\liminf_j\|h_j\|_2>0,
\]
then (3) proves
\[
\boxed{E(h_j)\longrightarrow+\infty.}\tag{8}
\]
In particular such a sequence cannot converge to a nonzero smooth test in the energy norm
\[
\|h\|_{\mathcal E}^2=\|h\|_2^2+E(h).
\]
Indeed the square root of \(E\) is a seminorm, as is immediate from its Hilbert-space difference representation; energy-norm convergence would imply bounded \(E(h_j)\).

For this grid the entire support diameter is less than 1, so only the prime-power correlation at \(n=2\) can survive (\(e<3\)). Thus Cauchy--Schwarz also gives
\[
q(h_j)\ge E(h_j)-\left(c_*+2\log2/\sqrt2\right)\|h_j\|_2^2.
\]
If additionally \(h_j\to h\ne0\) in \(L^2\), this implies \(q(h_j)\to+\infty\), whereas \(q(h)\) is finite for smooth compactly supported \(h\). Hence the positive values on the certified approximants do not pass to \(q(h)\) by \(L^2\) convergence.

The condition \(\varepsilon_j\to0\) is necessary for these support sets to approximate a fixed nonzero smooth function in \(L^2\). For example choose a compact interval inside \((0,1)\) on which \(|h|\ge c>0\). On this interval the total gap length is \(\varepsilon_j\) times its length, up to an error \(O(1/N_j)\). Thus \(\|h_j-h\|_2^2\) is bounded below by \(c^2\) times that gap length.

Conversely, for a fixed h in C_c^infinity((0,1)), smooth periodic masks which vanish on the gaps and equal one away from slightly larger gaps do produce \(L^2\) approximants when \(\varepsilon_j\to0\). Therefore the topology distinction is concrete: shrinking gaps can give \(L^2\) approximation, while successful use of this specific positivity certificate forces divergence in the very energy governing the arithmetic form.

**What is refuted:** the inference that the previously proved finite-packet sufficient inequality extends to arbitrary smooth support by a dense regular-grid limit and continuity of the form in \(L^2\).

**What is not refuted:** global Weil positivity, an alternative certificate using actual signed cross correlations, a different family of approximants, or a genuinely proved global arithmetic inequality.

## 3. A universal square-partition defect theorem

For completeness the overlapping-partition route has an even more direct obstruction. Fix a nonzero \(h\in C_c^\infty(\mathbb R)\). Suppose real smooth functions \(\chi_1,\ldots,\chi_r\) satisfy \(\sum_j\chi_j^2=1\) on \(\operatorname{supp}h\), and each \(\chi_jh\) has support diameter at most \(L<\log2\). No individual moment conditions are needed by the local arithmetic theorem. Then
\[
\sum_jq(\chi_jh)-q(h)
\ge [K(L)-c_*]\|h\|_2^2-q(h).
\]
Using the inherited bound \(K(L)-c_*\ge-\log(8L)-1-L\) proves that this exact localization defect tends to \(+\infty\) as \(L\downarrow0\). It cannot be replaced by a scalar error tending to zero. The conclusion remains nonvacuous in the actual two-moment class: take any nonzero compact smooth \(\phi\) and \(h=\phi''-\phi/4\); integration by parts gives both exponential moments zero, and the compactly supported solution of \(h=0\) would force \(\phi=0\).

This theorem does not assume a uniform bound on the number of cutoffs or their derivatives; neither can rescue the proposed vanishing-defect argument.


---

# Appendix: arithmetic normalization and local sign

# A strict local Weil sign theorem in the existing repository normalization

Status: **[MATH-PROVED]**, independently derived from the definitions at
`dcfa2a51f52d941937a7cb72996d58b2d0ec0f43`. No new kernel theorem is claimed here.
The arithmetic theorem is unconditional and does not use zeros of zeta. Its
zero-sum corollary uses the previously established mathematical explicit-formula
transport, with that transport's separately declared external dependencies.

## Exact hypotheses and notation

Let `g : WeilCompactSmoothGV1`; explicitly, extend a complex smooth function
compactly supported in `(0,infinity)` to the real line by zero. Write

\[
h(u)=e^{u/2}g(e^u),\qquad H=\int_{\mathbb R}|h(u)|^2\,du,
\qquad C(t)=\int_{\mathbb R}h(u+t)\overline{h(u)}\,du.
\]

Then `h` is a complex compactly supported smooth function on the real line.
Let `f = WeilAutocorrelationV1 g`, exactly as defined by the repository,
with measure `dy`, not `dy/y`. Let

\[
\mathscr R(g)=\Re\operatorname{WeilExplicitRightSideV1}(f),\quad
c_0=\log(4\pi)+\gamma_E,\quad
c_*=\log(8\pi)+\gamma_E+\frac\pi2.
\]

The centered change of variables also gives the useful exact normalization

\[H=\int_0^\infty |g(x)|^2\,dx.\]

No moment conditions are imposed until the final corollary.

## 1. Exact arithmetic energy identity

The substitution `y = exp(u)` in the repository autocorrelation gives

\[
f(e^t)=e^{-t/2}C(t),\qquad f(1)=H,\qquad C(-t)=\overline{C(t)}.
\]

Consequently its prime term at the positive integer `n` is

\[
\Lambda(n)\bigl(f(n)+n^{-1}f(n^{-1})\bigr)
=2\Lambda(n)n^{-1/2}\Re C(\log n).
\]

Only finitely many terms are nonzero because `C` is compactly supported, and
`Lambda(1)=0`. The substitution `x=exp(t)` in the archimedean integral gives

\[
A(g)=\int_0^\infty
  \frac{e^{t/2}\Re C(t)-H}{\sinh t}\,dt.                 \tag{1}
\]

Define the nonnegative energy

\[
\mathcal E(h)=\frac12\int_0^\infty
  \frac{e^{t/2}}{\sinh t}\|h(\cdot+t)-h\|_2^2\,dt.
\]

Translation invariance of the real-line integral yields

\[
\|h(\cdot+t)-h\|_2^2=2H-2\Re C(t).
\]

The energy is finite. At zero,
`||h(.+t)-h||_2 <= t ||h'||_2` follows by integrating the derivative and
Minkowski's inequality; hence the energy integrand is `O(t)` there. For
`t >= 1`, the squared difference is at most `4H` and
`exp(t/2)/sinh(t) = O(exp(-t/2))`. The scalar integral below is finite as well:
its integrand has limit `1/2` at zero and decays exponentially at infinity.
Thus subtracting its integrable term and the energy term is legitimate:

\[
A(g)=H\int_0^\infty\frac{e^{t/2}-1}{\sinh t}\,dt-\mathcal E(h).
\]

For completeness, put `y=exp(-t/2)` to evaluate the scalar integral:

\[
\begin{aligned}
\int_0^\infty\frac{e^{t/2}-1}{\sinh t}\,dt
 &=4\int_0^1\frac{dy}{(1+y)(1+y^2)}\\
 &=\log2+\frac\pi2.
\end{aligned}
\]

(The partial fraction decomposition is
`1/((1+y)(1+y^2)) = 1/(2(1+y)) + (1-y)/(2(1+y^2))`.) Therefore

\[
\boxed{\mathscr R(g)=c_*H+
  2\sum_{n\ge2}\frac{\Lambda(n)}{\sqrt n}\Re C(\log n)
  -\mathcal E(h).}                                      \tag{2}
\]

Every term in this formula is real. In particular it also identifies directly
the real value of the repository RHS. Equation (2) is an identity, not an
inequality proving the global sign: nonnegativity of `E` alone gives an upper
bound by its positive constant and prime terms.

## 2. Exact local-support bound

Assume `supp(h)` is contained in a closed interval `[a,b]`, and choose
`L > 0` with `b-a <= L`. Then `C(t)=0` for `t >= L`: beyond that distance the
two support intervals are disjoint; at equality their intersection has
measure zero. On `0 <= t < L`, Cauchy--Schwarz gives `Re C(t) <= H`.

If additionally `L < log 2`, all prime terms vanish. Applying these bounds
to (1), and using positivity of `exp(t/2)/sinh(t)` for `t>0`, gives

\[
\mathscr R(g)\le B(L)H,
\]

where the exact coefficient justified by this argument is

\[
\begin{aligned}
B(L)
 &=c_0+\int_0^L\frac{e^{t/2}-1}{\sinh t}\,dt
      +\log\tanh(L/2)\\
 &=c_* - K(L),\\
K(L)
 &=\int_L^\infty\frac{e^{t/2}}{\sinh t}\,dt\\
 &=\log\frac{1+e^{-L/2}}{1-e^{-L/2}}
       +2\arctan(e^{-L/2}).                              \tag{3}
\end{aligned}
\]

To verify the first line, an antiderivative of `1/sinh(t)` is
`log(tanh(t/2))`, with limit zero at infinity. To verify the final line,
put `y=exp(-t/2)` and integrate
`4/(1-y^4) = 2/(1-y^2) + 2/(1+y^2)` from zero to `exp(-L/2)`.

Thus **any `0<L<log 2` satisfying `K(L)>c_*` gives a strict negative
arithmetic form on every nonzero test with that support diameter**. This
criterion is stronger than the simple rational sufficient bound below. No
claim that (3) is the optimal support inequality is made: it discards the
additional nonnegative energy from translations `0<t<L`.

## 3. A fully explicit rational coercivity margin

For every `t>0`, the elementary inequalities

\[
e^{t/2}-1\le\frac{e^t-1}{2}\le\sinh t
\]

follow respectively from `(exp(t/2)-1)^2>=0` and `exp(-t)<=1`. Hence

\[
0\le\int_0^L\frac{e^{t/2}-1}{\sinh t}\,dt\le L
\quad(L>0).
\]

Also `tanh(L/2)<=L/2`. Consequently

\[
B(L)\le\log(2\pi L)+\gamma_E+L.
\]

Use only the elementary bounds `pi < 4`, `gamma_E <= 1`, and
`log 4 >= 4/3`. The last follows from
`log x >= 2(x-1)/(x+1)` at `x=2`; differentiating the difference verifies
that inequality for `x>=1`. If `0<L<=1/32`, then

\[
\begin{aligned}
B(L)
 &\le\log(1/4)+1+1/32\\
 &\le-4/3+33/32=-29/96.
\end{aligned}
\]

The elementary constant bounds need no numerical oracle: `pi<4` follows
from `pi=4 integral_0^1 (1+x^2)^(-1) dx`; and `gamma_E<=1` follows by
taking the limit of `H_n-log n<=1`, using
`sum_{k=2}^n 1/k <= integral_1^n dx/x`.

Here `L<log2` is automatic from `log2>=2/3`.
We have therefore proved the following unconditional theorem directly from
the repository arithmetic definition:

\[
\boxed{\operatorname{diam}(\operatorname{supp}h)\le\frac1{32}
\quad\Longrightarrow\quad
\mathscr R(g)\le-\frac{29}{96}\|h\|_2^2.}               \tag{4}
\]

For a nonzero smooth `g`, its corresponding `h` is nonzero and continuous,
so `||h||_2^2>0`, making the sign strict.

## 4. A support-preserving moment filter and nontrivial positive subspace

Fix an interval `[a,b]` with positive length at most `1/32`, and take any
nonzero `phi` in `C_c^infinity(R;C)` supported in `[a,b]`. Define

\[
h=\phi''-\tfrac14\phi,\qquad
g(x)=\begin{cases}x^{-1/2}h(\log x),&x>0,\\0,&x\le0.\end{cases}
\]

Derivatives do not enlarge support, so `supp(h) subset [a,b]`. The support
of `g` is contained in `[exp(a),exp(b)]`, separated from zero. Therefore
its extension by zero is globally smooth and belongs to the existing
`WeilCompactSmoothGV1` carrier.

For either `r=1/2` or `r=-1/2`, two integrations by parts, with no boundary
terms because `phi` has compact support, yield

\[
\int_{\mathbb R}e^{ru}h(u)\,du
  =(r^2-1/4)\int_{\mathbb R}e^{ru}\phi(u)\,du=0.
\]

Under `x=exp(u)`, these are exactly the repository moments:

\[
\int_0^\infty g(x)\,dx=\int e^{u/2}h(u)\,du=0,
\qquad
\int_0^\infty\frac{g(x)}x\,dx=\int e^{-u/2}h(u)\,du=0.
\]

The filter is injective on compactly supported smooth functions. Indeed,
if `h=0`, integration by parts gives

\[
0=\int h\overline\phi
=-\int|\phi'|^2-\frac14\int|\phi|^2,
\]

forcing `phi=0`. Hence every nonzero `phi` produces a nonzero admissible
moment-zero `g`, and (4) proves the strict arithmetic inequality for it.
Because the map is linear and injective, this supplies an
**infinite-dimensional linear subspace** of the actual repository
moment-zero class on which the arithmetic form is strictly negative.

Under the previously proved mathematical explicit-formula transport and
absolute-convergence bridge, the zero functional for these exact tests is

\[
Q(g)=\sum_\rho m_\rho G(\rho)\overline{G(1-\overline\rho)}
      =-\mathscr R(g),\qquad G=\mathcal M g.
\]

Thus its quantitative consequence is

\[
\boxed{Q(g)\ge\frac{29}{96}\|\phi''-\phi/4\|_2^2>0
\qquad(\phi\ne0).}                                    \tag{5}
\]

This is a genuine positive-subspace result, not merely convergence or a
reality statement. Its proof does not localize any zero and does not use RH.

## 5. Exact parametrization and assembly of the whole moment-zero class

In fact the differential filter above parametrizes the **entire** admissible
centered moment-zero class, not merely a subclass. If `h` is compactly
supported and smooth with

\[
\int e^{-u/2}h(u)\,du=\int e^{u/2}h(u)\,du=0,
\]

set

\[
\phi(u)=2\int_{-\infty}^u
       \sinh\bigl((u-v)/2\bigr)h(v)\,dv.                  \tag{6}
\]

If `supp(h) subset [a,b]`, the integral is zero for `u<a`. For `u>b`,
expanding the hyperbolic sine gives

\[
\phi(u)=e^{u/2}\int e^{-v/2}h(v)\,dv
       -e^{-u/2}\int e^{v/2}h(v)\,dv=0.
\]

Differentiation of the integral is justified on every compact `u` interval
by smoothness and finite integration support. The boundary term in its
first derivative vanishes, and

\[
\phi'(u)=\int_{-\infty}^u\cosh\bigl((u-v)/2\bigr)h(v)\,dv,
\qquad \phi''(u)=h(u)+\tfrac14\phi(u).
\]

These identities give smoothness of all orders and show that
`phi''-phi/4=h`. Its support stays inside `[a,b]`, and injectivity from
Section 4 proves uniqueness. Thus

\[
\boxed{\{h\in C_c^\infty(\mathbb R):\int e^{\pm u/2}h=0\}
       =(D^2-\tfrac14)C_c^\infty(\mathbb R),}             \tag{7}
\]

with a unique support-preserving inverse given by (6).

Choose a finite smooth partition of unity `chi_j` equal in sum to one on
a neighborhood of the compact support of this `phi`, each `chi_j`
supported in an interval of length at most `1/32`. Such a partition is
obtained from a finite cover by shorter open intervals and subordinate
smooth bumps. Define

\[
\phi_j=\chi_j\phi,\quad h_j=\phi_j''-\tfrac14\phi_j,
\quad g_j(x)=x^{-1/2}h_j(\log x)\quad(x>0).
\]

Then, exactly,

\[
h=\sum_j h_j,\qquad g=\sum_j g_j,
\]

and **every piece has both vanishing moments**, compact support of logarithmic
diameter at most `1/32`, and the proved quantitative sign
`Q(g_j)>=29/96 ||h_j||_2^2`. Partitioning `phi`, rather than `h`, is
necessary here: an arbitrary partition of `h` need not preserve the moments.
This is a constructive decomposition of every admissible test into finitely
many members of the proven positive subspace for short intervals.

## 6. Exact boundary of the assembled result

For admissible `g_j`, let `B(g_i,g_j)` be the Hermitian polarization of the
zero quadratic form `Q`; absolute convergence legitimizes the finite
expansion. Then

\[
Q\!\left(\sum_jg_j\right)=
 \sum_j Q(g_j)+2\Re\sum_{i<j}B(g_i,g_j).                 \tag{8}
\]

The positive diagonal terms in (8) are proved by the local-support theorem.
Their sum does not control the off-diagonal terms. For separated pieces,
the union has large support diameter and its prime sum need not vanish.
Thus the proof cannot infer universal positivity by adding the local
inequalities. Even positivity of all individual two-by-two principal
matrices would be insufficient to establish positive semidefiniteness of
every larger Gram matrix; a matrix inequality for all finite families, or
a stronger direct energy estimate, is needed.

The exact unresolved global inequality in the energy representation is

\[
\mathcal E(h)\ge c_*\|h\|_2^2+
  2\sum_{n\ge2}\frac{\Lambda(n)}{\sqrt n}\Re C(\log n)
\]

for every compactly supported smooth `h` whose two exponential moments
vanish. Equations (6)--(8) expose where the assembled existing results do
and do not establish it. The local-support theorem proves this inequality
with a strict gap on an infinite-dimensional subspace, while the inverse
filter proves that finite linear sums of such local pieces span the entire
admissible class. The signs of the cross terms remain unproved.

`RH = NOT_PROVEN`; `authority_effect = NONE`.
