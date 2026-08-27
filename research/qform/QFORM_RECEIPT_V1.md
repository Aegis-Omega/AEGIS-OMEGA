# QFormReceiptV1 authority contract

`QFormReceiptV1` is a proof-carrying numerical receipt for the finite Weil quadratic-form computation. It is **not** a proof of RH and must never be interpreted as one.

## Authority lattice

- `EXACT`: discrete combinatorial facts evaluated without transcendental approximation, e.g. the `(p,k)` census and canonical ordering.
- `CERTIFIED_INTERVAL`: a real-valued quantity enclosed by a rigorously justified outward-rounded interval.
- `NUMERICALLY_VERIFIED`: independently cross-checked numerical computation with stated tolerance, but without a rigorous enclosure proof.
- `EMPIRICAL_FIXTURE`: regression/falsification datum only; it carries no theorem authority.

Authority may only decrease across a derived field unless a separately verified theorem justifies promotion.

## Required provenance

Every receipt must bind:

1. repository commit SHA and tree SHA;
2. implementation digest and parameter digest;
3. exact prime-power census digest;
4. numerical backend and precision/rounding mode;
5. truncation and discretization error budgets;
6. test/CI run identity;
7. theorem/lemma identifiers used to justify any certified bound.

## Error budget

A receipt must keep at least these terms separate:

- arithmetic cutoff error;
- finite-domain (`U_max`) truncation error;
- grid/quadrature (`du`) discretization error;
- transcendental evaluation/rounding error;
- any model/operator projection error.

A symbolic `O(du^2)` convergence statement is insufficient for `CERTIFIED_INTERVAL`; certification requires a computable constant or another rigorous enclosure method.

## Gaussian cutoff obligation

For a Gaussian autocorrelation tail with bound of the form

`tail(u_cut, sigma) <= exp(-u_cut^2 / (4 sigma^2))`,

requiring `tail <= epsilon` yields

`u_cut >= 2 sigma sqrt(log(1/epsilon))`,

hence with `u_cut = log(P_needed)`:

`P_needed >= exp(C(epsilon) sigma)`, where `C(epsilon) = 2 sqrt(log(1/epsilon))`.

This implication is valid only when the stated tail inequality has been proved for the exact normalized quantity being truncated. The arithmetic Weil sum may require an additional envelope/counting factor; the receipt must reference the precise theorem used.

## Globalization boundary

The finite chain

`prime-power census -> finite Q_P -> lambda_P(gamma) -> finite T_P -> <T_P psi, psi>`

is computational evidence. Connecting it to an infinite-dimensional Weil positivity statement requires explicit domain, projection, convergence, and limit theorems. Numerical fixtures must not be imported into Coq as axioms for a global theorem.
