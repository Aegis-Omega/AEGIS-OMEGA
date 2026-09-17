/-
Control for the `WeilDiagonalPrimeWindowV22` build fix.

The module previously reached `WeilPrimeSumV1 f = 0` through
`tsum_eq_zero_of_not_summable`, i.e. from DIVERGENCE of the prime-term family.
That is recorded here as unreachable rather than asserted in prose: under the
very hypothesis the module assumes, the family is summable, so the `False`
branch of that proof had no inhabitant and no amount of `absurd` or explicit
`have` plumbing could have closed it.
-/
import WeilDiagonalPrimeWindowV22

open Set Complex
open AEGIS.WeilDiagonalPrimeWindowV22

/-- Under the module's own support hypothesis the prime-term family is
summable, because every term is zero. -/
theorem prime_terms_summable_under_window
    (f : ℝ → ℂ)
    (hsupp :
      tsupport f ⊆
        Ioo (Real.exp (-(1 : ℝ) / 32)) (Real.exp ((1 : ℝ) / 32))) :
    Summable (WeilPrimeTermV1 f) := by
  have hzero : WeilPrimeTermV1 f = fun _ : ℕ => (0 : ℂ) :=
    funext (weil_prime_term_zero_of_tsupport_exp_window f hsupp)
  rw [hzero]
  exact summable_zero

/-- Hence the divergence route was vacuous: `¬ Summable` is unprovable here. -/
theorem not_summable_route_is_vacuous
    (f : ℝ → ℂ)
    (hsupp :
      tsupport f ⊆
        Ioo (Real.exp (-(1 : ℝ) / 32)) (Real.exp ((1 : ℝ) / 32))) :
    ¬ ¬ Summable (WeilPrimeTermV1 f) :=
  not_not_intro (prime_terms_summable_under_window f hsupp)

#print axioms weil_prime_term_zero_of_tsupport_exp_window
#print axioms weil_prime_sum_zero_of_tsupport_exp_window
#print axioms diagonal_autocorrelation_prime_sum_zero
#print axioms prime_terms_summable_under_window
#print axioms not_summable_route_is_vacuous
