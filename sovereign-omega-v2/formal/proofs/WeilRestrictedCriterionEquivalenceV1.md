# The exact restricted Weil criterion and a countable four-phase test family

Source definitions inspected at local AEGIS HEAD `ec6ce36278c99bbfb40c8200dbc09ec3c0b95faa`:
`WeilCriterionCompactSmoothV1.lean` and `WeilPairedHadamardIdentityV1.md`.
Status: **[MATH-PROVED]**, independently audited in this session. This document is a mathematical proof, not a kernel certificate or a claim of RH. The formal finite-dilation filter is a separate Lean implementation; its verified scope must be reported using its actual signatures and exact-head receipt.

The main new result is that the exact repository moment-zero compact-smooth class is sufficient for RH equivalence. A stronger corollary reduces its universal inequality to one explicitly specified countable family. Neither result proves those inequalities.

## The theorem

Let Z be a locally finite set of complex numbers z with |Re z| < 1/2, with positive integer multiplicities m(z). Assume Z and m are preserved by z -> -conj(z), and assume polynomial cumulative counting growth. For h in C_c^infinity(R;C), write

H_h(z) = integral_R h(u) exp(z u) du,
Q(h) = sum_(z in Z) m(z) H_h(z) conj(H_h(-conj z)).

Then the following are equivalent:

1. Re z = 0 for every z in Z.
2. Q(h) is real and nonnegative for every h with H_h(-1/2)=H_h(1/2)=0.
3. For every such h, Q(h)>=0 and Q(h+c h_t)>=0 for every t in R and |c|=1, where h_t(u)=h(u-t).

Every displayed zero sum converges absolutely. Hypothesis 3 is sufficient even though it tests only two translates at a time.

For the actual nontrivial zeta zeros, take z=rho-1/2. With g(x)=x^(-1/2)h(log x), extended by zero for x<=0, this is precisely the repository class and its two moments. Subject to the normalized explicit formula proved in prose in `WeilPairedHadamardIdentityV1.md`, this proves

    WeilCompactSmoothNegativityV1 <-> RiemannHypothesis.

The implication is mathematical at this point. It does not prove either equivalent statement.

## 1. Decay, summability, and normalization

If supp(h) is contained in a compact interval, integration by parts N times gives, uniformly for |Re z|<=1/2,

    |H_h(z)| <= C_(h,N) (1+|Im z|)^(-N).

For small |Im z| use the integral bound; for large |Im z| integrate the profile exp(Re(z)u)h(u) against exp(i Im(z)u). Compact support removes every boundary term and bounds each derivative uniformly over the compact real-part interval.

Polynomial cumulative counting and this decay imply sum m(z)|H_h(z)H_h(-conj z)|<infinity. In particular quadratic counting plus the existing uniform cubic decay suffices. Multiplicities are counted once per support point and included exactly once in each summand.

For g(x)=x^(-1/2)h(log x), substitution x=exp(u) gives

    M g(s) = H_h(s-1/2).

Thus H_h(+-1/2)=0 means M g(0)=M g(1)=0. Smoothness and support strictly inside the positive half-line are preserved in both directions. Translation becomes

    g_t(x) = exp(-t/2) g(exp(-t)x),
    M g_t(s) = exp((s-1/2)t) M g(s).

Both moments remain zero under translations and finite complex linear combinations.

## 2. The correlation function and its two-point bound

Fix a moment-zero h and set

    a_z = m(z) H_h(z) conj(H_h(-conj z)),
    k(t) = sum_z a_z exp(z t).

The series converges absolutely and locally uniformly in real t because sum|a_z|<infinity and |Re z|<1/2. Consequently k is continuous and |k(t)| <= exp(|t|/2) sum|a_z|.

The reflection assumption gives a_(-conj z)=conj(a_z). Reindexing the absolute series therefore gives

    k(-t) = conj(k(t)).

In particular k(0) is real. Direct finite expansion and the transform-of-translation identity give

    Q(h+c h_t) = k(0)(1+|c|^2) + 2 Re(c k(t)).       (1)

For completeness the cross terms are c k(t) and conj(c) k(-t); no conjugation or sign is suppressed.

If every Q is nonnegative, then k(0)=Q(h)>=0. For k(t)!=0 choose c=-conj(k(t))/|k(t)| in (1). For k(t)=0 the bound is automatic. Thus

    |k(t)| <= k(0) for every real t.                (2)

No Bochner theorem, distributional positivity theorem, or density of a larger test class has been used.

## 3. Bounded exponential sums cannot contain a positive-real pole

Suppose k is bounded for t>=0. Its Laplace transform

    L(w) = integral_0^infinity exp(-w t) k(t) dt

is holomorphic on Re w>0. On every closed sub-half-plane Re w>=epsilon>0 the integrand and each w derivative are bounded by a constant times t^n exp(-epsilon t); dominated differentiation proves holomorphy.

For Re w>1/2,

    sum_z integral_0^infinity |a_z exp((z-w)t)| dt
      = sum_z |a_z|/(Re w-Re z)
      <= sum_z |a_z|/(Re w-1/2) < infinity.

Fubini therefore gives

    L(w) = M(w) := sum_z a_z/(w-z).                 (3)

The right side is meromorphic on the whole complex plane, with residue a_z at z. Indeed on any compact set avoiding Z, all sufficiently large |Im z| make |w-z|>=1 uniformly, so the tail is uniformly dominated by sum|a_z|. The remaining terms form a finite rational sum by local finiteness. Near a particular z0, exclude that one summand and use the same argument to obtain a holomorphic remainder.

The domain {Re w>0}\Z is connected: polygonal paths between two points can be perturbed inside a compact region to avoid its finitely many deleted points. Since (3) holds on Re w>1/2, the identity theorem gives L=M throughout this punctured right half-plane. At a z0 with Re z0>0, L is holomorphic while M has residue a_z0. Thus

    boundedness of k on [0,infinity) implies a_z0=0
    for every z0 with Re z0>0.                     (4)

This argument is valid with infinitely many zeros, without assuming a rightmost zero or isolating a largest real part. Contributions from the remaining zeros cannot cancel the residue of an isolated, distinct support point.

More quantitatively, if Re z0=a>0 and a_z0!=0, then k cannot be O(exp(b t)) as t->infinity for any 0<=b<a: the same proof applies to Re w>b. In particular it is unbounded.

## 4. A finite-dilation moment filter detects an off-line point

Define, on the positive half-line and with zero extension,

    A f(x) = f(x) - 3 f(2x) + 2 f(4x),
    p(s) = (1-2^(-s))(1-2^(1-s)).

Here positive-real complex powers use the real logarithm. The substitution y=a x gives M[f(a x)](s)=a^(-s) M f(s), so

    M[A f](s) = (1-3*2^(-s)+2*4^(-s)) M f(s)
               = p(s) M f(s).

All substitutions are on compact positive intervals with absolutely convergent integrals. A preserves smoothness and compact support strictly inside the positive half-line. It kills both repository moments because p(0)=p(1)=0. For 0<Re s<1,

    |2^(-s)|=2^(-Re s)<1,
    |2^(1-s)|=2^(1-Re s)>1,

so p(s) is nonzero throughout the strict strip. This avoids differentiating the seed in the smallest formal implementation.

Fix z0 with Re z0>0 and put rho0=1/2+z0. Choose a real nonnegative eta in C_c^infinity((-1,1)) with integral eta=1, and set

    h_epsilon(u)=epsilon^(-1)eta(u/epsilon),
    f_epsilon(x)=x^(-1/2) h_epsilon(log x)   (x>0).

Its centered transform E_epsilon(z) satisfies

    M f_epsilon(1/2+z)=E_epsilon(z)
      =integral eta(v) exp(epsilon z v) dv -> 1

for each fixed z as epsilon->0. Hence for sufficiently small epsilon both E_epsilon(z0) and E_epsilon(-conj z0) are nonzero.

Take g=A f_epsilon and h(u)=exp(u/2)g(exp u). Then

    H_h(z)=p(1/2+z)E_epsilon(z).

Both moments vanish, and both values H_h(z0) and H_h(-conj z0) are nonzero because their shifted arguments lie in the strict strip. Consequently

    a_z0=m(z0)H_h(z0)conj(H_h(-conj z0)) != 0.

This contradicts (4) under positivity and its bound (2). Thus Z has no positive-real point. Reflection z -> -conj z excludes negative-real points as well, proving (2)->(1). The same proof uses only the two-point tests in statement 3.

Conversely if every z is imaginary, -conj z=z, and

    Q(h)=sum_z m(z)|H_h(z)|^2 >=0,

a real absolutely convergent sum. This proves (1)->(2)->(3), completing the equivalence.

## 5. A more concrete contrapositive witness

If an off-line point exists, reflection supplies z0 with Re z0>0. The seed h just constructed has unbounded k(t) on t>=0.

- If k(0)<0, h itself has negative Q.
- If k(0)>=0, choose t>=0 with |k(t)|>k(0), and c=-conj(k(t))/|k(t)|. Then h+c h_t is smooth, compactly supported, retains both vanishing moments, and has Q=2(k(0)-|k(t)|)<0.

Thus an off-line zero forces a negative witness in the exact class, using at most two dilates of a moment-zero bump. This is an existence theorem, not an algorithm with a numerical stopping bound: no off-line zeta zero is supplied or assumed to exist unconditionally.

## 6. Exact arithmetic criterion and nonvacuity

The prior normalized explicit formula says for f_g(x)=integral g(xy)conj(g(y))dy,

    WeilExplicitRightSideV1(f_g) = - Q(g)

when M g(0)=M g(1)=0. The minus sign is essential: RH corresponds to arithmetic NONPOSITIVITY, zero-side NONNEGATIVITY.

The repository predicate includes `WeilExplicitRightSideConvergentV1(f_g)` as an antecedent. It cannot be ignored. For every g in the class, f_g is again smooth with compact positive support: if supp(g) subset[a,b], then supp(f_g) subset[a/b,b/a], and differentiation under the y integral is uniformly dominated on compact x sets. The repository theorem `weil_compact_smooth_explicit_right_side_convergent_v1` then supplies the antecedent once this closure is encoded. In prose, this proves the antecedent for every g, so the predicate is not vacuously true on the witnesses used above.

Consequently the exact compact-smooth, two-moment repository predicate is RH-equivalent under the stated explicit-formula transport. No enlargement to Bombieri's full W is mathematically required for this direction.

## 7. A single countable family is already RH-equivalent

Fix eta once and for all as above. For a completely specified choice, take eta(u) to be the normalization to integral one of exp(-1/(1-u^2)) on |u|<1, extended by zero. For each integer n>=1 define

    f_n(x)=x^(-1/2) n eta(n log x)      (x>0),
    g_n=A f_n,
    (D_q g)(x)=exp(-q/2) g(exp(-q)x),
    v_(n,q,c)=g_n+c D_q g_n,

with q rational and c in {1,-1,i,-i}. Every v is in the exact repository class and satisfies both moments automatically. The family is countable; no member depends on knowing a zeta zero.

For the actual zeta spectrum, RH is equivalent to

    Q(v_(n,q,c)) >= 0
    for every n>=1, q in Q, c in {1,-1,i,-i}.       (CF)

Subject to the normalized explicit formula, this is equivalently

    Re(WeilExplicitRightSideV1(
        WeilAutocorrelationV1(v_(n,q,c)))) <= 0
    for every n>=1, q in Q, c in {1,-1,i,-i}.       (ACF)

Reality and convergence hold for all these tests by the preceding arguments. The arithmetic sign is nonpositive; reversing it would invalidate the criterion.

Proof of sufficiency: fix n and form k_n from g_n as in Section 2. The test q=0,c=1 has Q(2g_n)=4k_n(0), so (CF) gives k_n(0)>=0. At each rational q, the two phases +/-1 imply

    |Re k_n(q)| <= k_n(0),

while the phases +/-i imply

    |Im k_n(q)| <= k_n(0).

Hence |k_n(q)|<=sqrt(2)k_n(0), or the slightly weaker bound 2k_n(0) if one wants to avoid a square root. These four phases do not in general give the sharper |k_n(q)|<=k_n(0); that sharper inequality used every unit phase in Section 2. Continuity and density of Q extend the displayed component bounds to all real t. Thus every k_n is bounded.

If z0 were an off-line zero with positive real part, choose n sufficiently large. The approximate-identity calculation in Section 4 with epsilon=1/n gives E_(1/n)(z0)->1 and E_(1/n)(-conj z0)->1. The nonvanishing filter therefore ensures a_(z0,n)!=0 for all sufficiently large n. The Laplace-pole obstruction then says k_n cannot be bounded, contradiction. Reflection excludes the other half-strip. Necessity follows because on RH each zero summand in every Q is a nonnegative squared modulus.

In contrapositive form: an off-line zero forces **one positive arithmetic value** for some finite triple (n,q,c) in this fixed family. Indeed choose n as above; unbounded k_n violates one of its two component bounds at a real t, and continuity gives a rational q with a strict violation. One of the four phases then makes Q negative. This is an existence theorem, not a numerical bound on the necessary n or q.

This countable criterion reduces the test family while retaining full RH equivalence. It does not establish (CF) or (ACF), and finite checking of family members would be numerical evidence only.

## Remaining theorem, now with one fewer mathematical bridge

    For every g : WeilCompactSmoothGV1 with WeilMomentConditionsV1 g,
    (WeilExplicitRightSideV1 (WeilAutocorrelationV1 g)).re <= 0.

Equivalently, it suffices to prove the single universal countable-family assertion (ACF). The proof above establishes the criterion's sufficiency. It supplies no proof of either version of the sign inequality. The full identity and criterion equivalence remain separate formalization targets; current compiled local definitions alone prove neither.

Dependencies: the existing strip, local finiteness, multiplicity-preserving reflection, and Mellin-decay/counting facts; standard elementary integration by parts, dominated holomorphic differentiation, Fubini under the displayed bound, and the identity theorem. Arithmetic transport additionally inherits the explicit external digamma/Hadamard dependencies declared in `WeilPairedHadamardIdentityV1.md`. No assumption of RH, Weil positivity, or zero simplicity enters the converse proof.

## Claim disposition

| Claim | Status | Evidence scope | Remaining obligation | Authority effect |
|---|---|---|---|---|
| Moment-zero compact-smooth zero criterion iff vertical localization | MATH-PROVED | Full Sections 1-5; independent mathematical audit | Kernel formalization | NONE |
| Countable four-phase family iff the same localization | MATH-PROVED | Section 7, including rational-density and nonvanishing seed proofs | Kernel formalization | NONE |
| Actual arithmetic predicate iff RH | MATH-PROVED with declared transport dependencies | Section 6 plus prior normalized explicit formula | Full exact-head kernel transport and equivalence | NONE |
| Arithmetic nonpositivity for the family | OPEN | Not established by this proof | Prove (ACF) for every family member | NONE |
| RH | NOT_PROVEN | No proof of (CF)/(ACF) supplied | Universal sign inequality | NONE |

The inspected SHA identifies the source definitions. This newly written proof document is not a theorem machine-checked at that SHA. A later commit or CI run must not inherit an earlier receipt merely because the mathematical statement is unchanged.
