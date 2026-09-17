import WeilPairedHadamardTsumFusionV1

/-!
AEGIS Ω — preregistered theorem surface for the single paired-kernel `tsum` fusion.

This spec intentionally requires only summability/fusion on the existing
`LiCriterion.NontrivialZero` carrier.  It does not require transport to the
AEGIS zeta-zero carrier, Mellin-test evaluation, the whole explicit formula,
any sign inequality, or RH.
-/

#check riemannXi_weighted_hadamard_term_summable_v1
#check riemannXi_paired_kernel_summable_v1
#check riemannXi_paired_hadamard_tsum_v1

#print axioms riemannXi_weighted_hadamard_term_summable_v1
#print axioms riemannXi_paired_kernel_summable_v1
#print axioms riemannXi_paired_hadamard_tsum_v1
