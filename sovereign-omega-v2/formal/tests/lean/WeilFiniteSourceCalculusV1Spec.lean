import WeilFiniteSourceCalculusV1

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

The current Archimedean algebra boundary is the rank-two Cauchy factorization:
the divided difference of `x/(a^2-x^2)` and its diagonal value equal the two
Cauchy feature products used by the #322 Gram infrastructure. These are
algebraic identities only; the actual Archimedean source-to-core identity and
operator-order theorem remain separate.
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
