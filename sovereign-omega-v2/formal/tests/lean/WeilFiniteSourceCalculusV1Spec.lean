import WeilArchTailIntegralV1

set_option autoImplicit false

/-!
Preregistered contract for the exact finite source-calculus bridge used in the
Guinand--Weil dictionary.

The production theorem identifies the single-frequency divided-difference
quadratic contraction with the Volterra sine-chord kernel, then extends by
finite source superposition, full entry contraction, and the canonical prime
evaluator specialization.

The Archimedean lane now machine-binds the true source derivative, exact
nonresonant integer-node source/derivative formulas, the exact pointwise entry
identity

  true Arch source entry = scale(L,T) * rank-two Cauchy entry,

and the finite real Cauchy Gram identity

  Cauchy quadratic = 1/2 * (minusMoment^2 + plusMoment^2) >= 0.

The next bounded target composes only those already-closed results. On a finite
Galerkin band with `0 < L` and nonresonance at every band index, the true Arch
sine-source quadratic equals `WeilArchScaleV1 L T` times the finite Cauchy
quadratic, the scale is nonnegative, and hence that pointwise source quadratic
is nonnegative.

This remains pointwise in T and only for the true sine-source kernel.
Continuous T-integration, the full Archimedean weight, tail operator order,
finite Galerkin PSD promotion, formula-to-Weil operator identity, global Weil
positivity, RH, repository admission, merge, and authority effects remain
outside this slice.
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
#check WeilArchFiniteQuadraticV1
#check weil_arch_finite_quadratic_scaled_cauchy_v1
#check weil_arch_scale_nonnegative_v1
#check weil_arch_finite_quadratic_nonnegative_v1
#check weil_arch_sine_finite_quadratic_nonnegative_v1

#check WeilArchWeightedTailQuadraticV1
#check weil_arch_weighted_tail_quadratic_nonnegative_v1
