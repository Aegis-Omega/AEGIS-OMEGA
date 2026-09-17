import WeilCauchyRankTwoV1

set_option autoImplicit false

/-!
Preregistered contract for the exact finite source-calculus bridge used in the
Guinand--Weil dictionary.

The production theorem must identify the quadratic contraction of the
single-frequency divided-difference matrix with the Volterra sine-chord kernel
for a finite real even coefficient family.  This is a finite basis-evaluation
identity only.  It does not assert global Weil positivity or RH.

The next bounded strengthening is the finite-source-measure extension: a
finite real family of single-frequency source atoms must compose linearly at
the entry, quadratic-contraction, and chord-kernel levels.  This remains a
finite identity only and does not import finite PSD, global Weil positivity,
or RH.

After that extension, full entry identification requires the single matrix
obtained by summing the atomic entries to have exactly the same finite
quadratic contraction as the sum of the atomic quadratic values.

The canonical-prime evaluator bridge specializes one atom to
`alpha = -beta`, `omega = 1-r`, and identifies its integer Galerkin entry with
the prime kernel evaluated by `guinand_weil_arb.py`.

The next Archimedean algebra boundary is the rank-two Cauchy factorization:
the divided difference of `x/(a^2-x^2)` and its diagonal value must equal the
sum of the two Cauchy feature products used by the #322 Gram infrastructure.
These are algebraic identities only; they do not yet identify the actual
Archimedean source with this core or import PSD.
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
#check WeilCauchyCoreV1
#check WeilCauchyRankTwoKernelV1
#check weil_cauchy_divided_difference_rank_two_v1
#check weil_cauchy_diagonal_rank_two_v1
