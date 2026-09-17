import WeilFiniteSourceCalculusV1

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

After that extension, the next isolated boundary is full entry identification:
the single matrix obtained by summing the atomic entries must have exactly the
same finite quadratic contraction as the sum of the atomic quadratic values.
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
