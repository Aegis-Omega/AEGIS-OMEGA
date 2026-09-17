import WeilArchSineKernelIntegerV1

set_option autoImplicit false

/-!
Preregistered contract for the exact finite source-calculus bridge used in the
Guinand--Weil dictionary.

The production theorem identifies the single-frequency divided-difference
quadratic contraction with the Volterra sine-chord kernel, then extends by
finite source superposition, full entry contraction, and the canonical prime
evaluator specialization.

The Archimedean lane now machine-binds the true source derivative, the exact
nonresonant integer-node source/derivative formulas, and the exact pointwise
entry identity

  true Arch source entry = scale(L,T) * rank-two Cauchy entry.

The next bounded target is finite real Cauchy Gram algebra only. For the finite
Galerkin band, the quadratic contraction of `WeilCauchyRankTwoEntryV1` must be
exactly one half of the sum of the squares of the two finite Cauchy feature
moments, and hence nonnegative. This is the real-carrier analogue of the
abstract #322 rank-two Gram core; it is NOT yet the actual Archimedean tail
integral and does not promote finite Galerkin PSD.

Continuous T-integration, positivity of the full Archimedean weight, tail
operator order, formula-to-Weil operator identity, global Weil positivity, RH,
repository admission, merge, and authority effects remain outside this slice.
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
#check weil_cauchy_rank_two_quadratic_nonnegative_v1
#check WeilArchSineKernelV1
#check WeilArchSineKernelDxV1
#check weil_arch_sine_kernel_hasDerivAt_v1
#check weil_arch_sine_kernel_integer_v1
#check weil_arch_sine_kernel_dx_integer_v1
#check weil_arch_sine_entry_cauchy_rank_two_v1
#check WeilCauchyFiniteQuadraticV1
#check WeilCauchyMinusMomentV1
#check WeilCauchyPlusMomentV1
#check weil_cauchy_finite_quadratic_sum_squares_v1
#check weil_cauchy_finite_quadratic_nonnegative_v1
