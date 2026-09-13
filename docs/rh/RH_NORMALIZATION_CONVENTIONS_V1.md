# RH normalization conventions V1

**Status:** frozen specification only; no explicit-formula theorem is present or
proved in this repository.  **Audit base:**
`495bfd85d79abcb2b4f6898fe9c156488492426a`.

All future RH-path artifacts must cite this file and must not silently change
these conventions.

## Analytic objects

* `zeta(s)` means the meromorphic continuation of
  \(\sum_{n\ge1}n^{-s}\), initially defined for \(\Re s>1\), with its single
  simple pole at `s = 1`.
* \(\xi(s)=\tfrac12s(s-1)\pi^{-s/2}\Gamma(s/2)\zeta(s)\).  A
  **nontrivial zero** is a zero of `zeta` with \(0<\Re s<1\), counted with its
  analytic multiplicity. Trivial zeros are the zeros at negative even integers
  and are not members of the nontrivial-zero multiset.
* Complex conjugation is written \(\bar z\). Zero sums count multiplicity and,
  unless an ordering is proved harmless, use the symmetric height limit
  \(\lim_{T\to\infty}\sum_{|\Im\rho|\le T}\).

## Transforms and test functions

For \(f:\mathbb R\to\mathbb C\),

\[
  \widehat f(t)=\int_{-\infty}^{\infty}f(x)e^{-itx}\,dx,
  \qquad
  f(x)=\frac1{2\pi}\int_{-\infty}^{\infty}\widehat f(t)e^{itx}\,dt.
\]

For \(g:(0,\infty)\to\mathbb C\),
\(\mathcal M g(s)=\int_0^\infty g(x)x^{s-1}\,dx\).

Until a larger class and all limiting operations are proved, the canonical
discovery class is the even, real-valued Schwartz functions whose Fourier
transform is compactly supported. This class is **not** asserted here to be the
exact class of any Weil equivalence theorem.

## Explicit-formula bookkeeping

Any proposed explicit formula must display, rather than absorb into notation:

1. the pole terms from `s = 0,1` in the completed normalization;
2. the complete gamma-factor integral and its contour/domain;
3. the prime-power term with \(\Lambda(p^k)=\log p\) and zero otherwise;
4. the nontrivial-zero sum, its multiplicities, and its summation order;
5. every boundary/residue term and every support or symmetry hypothesis; and
6. whether equality is pointwise, in an `L²` space, or distributional.

No positivity functional `W` is canonically defined yet. Defining `W`, proving
convergence, proving the explicit formula, and proving both directions of the
criterion remain separate obligations.
