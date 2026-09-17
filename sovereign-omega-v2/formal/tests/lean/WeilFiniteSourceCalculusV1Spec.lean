import WeilArchSineKernelIntegerV1

set_option autoImplicit false

/-!
Preregistered contract for the exact finite source-calculus bridge used in the
Guinand--Weil dictionary.

The production theorem must identify the quadratic contraction of the
single-frequency divided-difference matrix with the Volterra sine-chord kernel
for a finite real even coefficient family. This is a finite basis-evaluation
identity only. It does not assert global Weil positivity or RH.

The finite-source extension and full entry identification compose finitely many
single-frequency atoms without importing finite PSD. The canonical-prime bridge
then identifies the integer entry for `alpha = -beta`, `omega = 1-r` with the
prime kernel evaluated by `guinand_weil_arb.py`.

The rank-two Cauchy algebra boundary identifies the divided difference of
`x/(a^2-x^2)` and its diagonal value with the two Cauchy feature products used
by the #322 Gram infrastructure. These are algebraic identities only.

The next Archimedean analytic boundary is narrower than the full tail theorem.
For

  S(L,T,x) = ∫_0^L sin(2π x (1-y/L)) cos(T y) dy,

freeze the true x-derivative bridge and the exact integer-node value and
x-derivative formulas with `rho = 2π/L`:

  d/dx S(L,T,x) = Sx(L,T,x),

  S(L,T,n)
    = 2 rho n sin(LT/2)^2 / (T^2 - (rho n)^2),

  Sx(L,T,n)
    = 2 rho sin(LT/2)^2 (T^2 + (rho n)^2)
        / (T^2 - (rho n)^2)^2.

The derivative bridge is mandatory: the diagonal divided-difference entry is
the derivative of the true source, not of an integer-node surrogate.
Only these source-to-rational-core identities are targeted. The subsequent
continuous Cauchy--Stieltjes integration, finite PSD import, operator order,
global Weil positivity, formula-to-Weil identity, and RH remain outside this
slice.
-/

#check WeilSingleFrequencySourceV1
#check WeilSingleFrequencyEntryV1
#check WeilTrigPolynomialV1
#check WeilChordKernelV1
#check weil_single_frequency_source_offdiag_v1
#check weil_single_frequency_source_diagonal_v1
#check weil_single_frequency_source_calculus_v1
#check weil_finite_source_measure_extension_v1
#check weil_finite_source_full_entry_identification_v1
#check weil_prime_atom_entry_matches_evaluator_v1
#check WeilCauchySourceCoreV1
#check WeilCauchyRankTwoEntryV1
#check WeilCauchyDiagonalV1
#check weil_cauchy_divided_difference_rank_two_v1
#check weil_cauchy_diagonal_rank_two_v1
#check WeilArchSineKernelV1
#check WeilArchSineKernelDxV1
#check weil_arch_sine_kernel_hasDerivAt_v1
#check weil_arch_sine_kernel_integer_v1
#check weil_arch_sine_kernel_dx_integer_v1
