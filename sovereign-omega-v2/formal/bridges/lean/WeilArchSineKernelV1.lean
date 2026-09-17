import WeilFiniteSourceCalculusV1
import Mathlib.Analysis.Calculus.ParametricIntervalIntegral
import Mathlib.Tactic

/-!
AEGIS Ω — true Archimedean sine-source kernel v1.

This module starts the analytic identification between the actual truncated
Archimedean source and the rational Cauchy core already isolated in
`WeilFiniteSourceCalculusV1`.

It proves differentiation of the true parameter-dependent source integral with
respect to the Galerkin coordinate and the exact nonresonant integer-node
closed forms. No Cauchy--Stieltjes integration, PSD import, operator order,
global Weil positivity, formula-to-Weil identity, or RH claim is made.
-/

open scoped BigOperators
open intervalIntegral

set_option autoImplicit false

noncomputable section

/-- `rho = 2π/L`, the Galerkin frequency scale. -/
def WeilArchRhoV1 (L : ℝ) : ℝ :=
  2 * Real.pi / L

/-- True truncated Archimedean sine source before the outer `h₊(T)` weight. -/
def WeilArchSineKernelV1 (L T x : ℝ) : ℝ :=
  ∫ y in (0 : ℝ)..L,
    Real.sin (2 * Real.pi * x * (1 - y / L)) * Real.cos (T * y)

/-- Pointwise x-derivative integrated over the true Archimedean source. -/
def WeilArchSineKernelDxV1 (L T x : ℝ) : ℝ :=
  ∫ y in (0 : ℝ)..L,
    (2 * Real.pi * (1 - y / L) *
      Real.cos (2 * Real.pi * x * (1 - y / L))) *
      Real.cos (T * y)

/-- Differentiation under the finite interval integral for the actual source.
This is the load-bearing diagonal bridge: the diagonal Galerkin entry is the
x-derivative of the true source, not of a node-only surrogate. -/
theorem weil_arch_sine_kernel_hasDerivAt_v1
    (L T x : ℝ) :
    HasDerivAt (WeilArchSineKernelV1 L T)
      (WeilArchSineKernelDxV1 L T x) x := by
  unfold WeilArchSineKernelV1 WeilArchSineKernelDxV1
  let F : ℝ → ℝ → ℝ := fun z y =>
    Real.sin (2 * Real.pi * z * (1 - y / L)) * Real.cos (T * y)
  let F' : ℝ → ℝ → ℝ := fun z y =>
    (2 * Real.pi * (1 - y / L) *
      Real.cos (2 * Real.pi * z * (1 - y / L))) * Real.cos (T * y)
  let bound : ℝ → ℝ := fun y => |2 * Real.pi * (1 - y / L)|
  refine (intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le
    (F := F) (F' := F') (bound := bound) (s := Set.univ) (x₀ := x)
    Filter.univ_mem ?_ ?_ ?_ ?_ ?_ ?_).2
  · filter_upwards with z
    dsimp [F]
    fun_prop
  · dsimp [F]
    exact (by fun_prop : Continuous (fun y : ℝ =>
      Real.sin (2 * Real.pi * x * (1 - y / L)) * Real.cos (T * y))).intervalIntegrable 0 L
  · dsimp [F']
    fun_prop
  · filter_upwards with y hy z hz
    dsimp [F', bound]
    change
      ‖(2 * Real.pi * (1 - y / L) *
          Real.cos (2 * Real.pi * z * (1 - y / L))) * Real.cos (T * y)‖ ≤
        ‖2 * Real.pi * (1 - y / L)‖
    calc
      ‖(2 * Real.pi * (1 - y / L) *
          Real.cos (2 * Real.pi * z * (1 - y / L))) * Real.cos (T * y)‖ =
          ‖2 * Real.pi * (1 - y / L)‖ *
            ‖Real.cos (2 * Real.pi * z * (1 - y / L))‖ * ‖Real.cos (T * y)‖ := by
              rw [norm_mul, norm_mul]
      _ ≤ ‖2 * Real.pi * (1 - y / L)‖ * 1 * 1 := by
        gcongr
        · simpa [Real.norm_eq_abs] using Real.abs_cos_le_one
            (2 * Real.pi * z * (1 - y / L))
        · simpa [Real.norm_eq_abs] using Real.abs_cos_le_one (T * y)
      _ = ‖2 * Real.pi * (1 - y / L)‖ := by ring
  · dsimp [bound]
    exact (by fun_prop : Continuous (fun y : ℝ =>
      |2 * Real.pi * (1 - y / L)|)).intervalIntegrable 0 L
  · filter_upwards with y hy z hz
    dsimp [F, F']
    have harg : HasDerivAt
        (fun w : ℝ => 2 * Real.pi * w * (1 - y / L))
        (2 * Real.pi * (1 - y / L)) z := by
      simpa [mul_assoc] using
        (((hasDerivAt_id z).const_mul (2 * Real.pi)).mul_const (1 - y / L))
    have hsin := (Real.hasDerivAt_sin
      (2 * Real.pi * z * (1 - y / L))).comp z harg
    simpa [mul_assoc, mul_comm, mul_left_comm] using
      hsin.mul_const (Real.cos (T * y))

private theorem integral_sin_linear_v1 (k L : ℝ) (hk : k ≠ 0) :
    (∫ y in (0 : ℝ)..L, Real.sin (k * y)) =
      (1 - Real.cos (k * L)) / k := by
  have hscale :
      k * (∫ y in (0 : ℝ)..L, Real.sin (k * y)) =
        1 - Real.cos (k * L) := by
    calc
      k * (∫ y in (0 : ℝ)..L, Real.sin (k * y)) =
          ∫ y in k * 0..k * L, Real.sin y := by
            simpa using
              (intervalIntegral.mul_integral_comp_mul_left
                (a := (0 : ℝ)) (b := L) (f := Real.sin) k)
      _ = 1 - Real.cos (k * L) := by simp
  apply (eq_div_iff hk).2
  simpa [mul_comm] using hscale

private theorem integral_sin_mul_cos_linear_v1
    (A T L : ℝ) (hsub : A - T ≠ 0) (hadd : A + T ≠ 0) :
    (∫ y in (0 : ℝ)..L, Real.sin (A * y) * Real.cos (T * y)) =
      (1 / 2 : ℝ) *
        ((1 - Real.cos ((A - T) * L)) / (A - T) +
          (1 - Real.cos ((A + T) * L)) / (A + T)) := by
  have hfun :
      (fun y : ℝ => Real.sin (A * y) * Real.cos (T * y)) =
        fun y : ℝ => (1 / 2 : ℝ) *
          (Real.sin ((A - T) * y) + Real.sin ((A + T) * y)) := by
    funext y
    have htrig := Real.two_mul_sin_mul_cos (A * y) (T * y)
    rw [show A * y - T * y = (A - T) * y by ring,
      show A * y + T * y = (A + T) * y by ring] at htrig
    linarith
  rw [hfun, intervalIntegral.integral_const_mul]
  rw [intervalIntegral.integral_add (by fun_prop) (by fun_prop)]
  rw [integral_sin_linear_v1 (A - T) L hsub,
    integral_sin_linear_v1 (A + T) L hadd]

private theorem integral_weighted_cos_linear_v1
    (L k : ℝ) (hL : L ≠ 0) (hk : k ≠ 0) :
    (∫ y in (0 : ℝ)..L, (1 - y / L) * Real.cos (k * y)) =
      (1 - Real.cos (k * L)) / (L * k ^ 2) := by
  let F : ℝ → ℝ := fun y =>
    (1 - y / L) * Real.sin (k * y) / k -
      Real.cos (k * y) / (L * k ^ 2)
  have hF : ∀ y : ℝ,
      HasDerivAt F ((1 - y / L) * Real.cos (k * y)) y := by
    intro y
    have hone : HasDerivAt (fun z : ℝ => 1 - z / L) (-1 / L) y := by
      convert (hasDerivAt_const y 1).sub ((hasDerivAt_id y).div_const L) using 1 <;>
        field_simp [hL] <;> ring
    have hlin : HasDerivAt (fun z : ℝ => k * z) k y :=
      (hasDerivAt_id y).const_mul k
    have hsin0 := (Real.hasDerivAt_sin (k * y)).comp y hlin
    have hsin :
        HasDerivAt (fun z : ℝ => Real.sin (k * z) / k)
          (Real.cos (k * y)) y := by
      convert hsin0.div_const k using 1 <;> field_simp [hk] <;> ring
    have hprod := hone.mul hsin
    have hcos0 := (Real.hasDerivAt_cos (k * y)).comp y hlin
    have hcos :
        HasDerivAt (fun z : ℝ => Real.cos (k * z) / (L * k ^ 2))
          (-Real.sin (k * y) / (L * k)) y := by
      convert hcos0.div_const (L * k ^ 2) using 1 <;>
        field_simp [hL, hk] <;> ring
    have htot := hprod.sub hcos
    dsimp [F]
    convert htot using 1 <;> field_simp [hL, hk] <;> ring
  calc
    (∫ y in (0 : ℝ)..L, (1 - y / L) * Real.cos (k * y)) = F L - F 0 := by
      apply integral_eq_sub_of_hasDerivAt
      · intro y hy
        exact hF y
      · apply Continuous.intervalIntegrable
        fun_prop
    _ = (1 - Real.cos (k * L)) / (L * k ^ 2) := by
      dsimp [F]
      field_simp [hL, hk]
      ring

private theorem integral_weighted_cos_mul_cos_linear_v1
    (L A T : ℝ) (hL : L ≠ 0)
    (hsub : A - T ≠ 0) (hadd : A + T ≠ 0) :
    (∫ y in (0 : ℝ)..L,
      (1 - y / L) * Real.cos (A * y) * Real.cos (T * y)) =
      (1 / 2 : ℝ) *
        ((1 - Real.cos ((A - T) * L)) / (L * (A - T) ^ 2) +
          (1 - Real.cos ((A + T) * L)) / (L * (A + T) ^ 2)) := by
  have hfun :
      (fun y : ℝ => (1 - y / L) * Real.cos (A * y) * Real.cos (T * y)) =
        fun y : ℝ => (1 / 2 : ℝ) *
          ((1 - y / L) * Real.cos ((A - T) * y) +
            (1 - y / L) * Real.cos ((A + T) * y)) := by
    funext y
    have htrig := Real.two_mul_cos_mul_cos (A * y) (T * y)
    rw [show A * y - T * y = (A - T) * y by ring,
      show A * y + T * y = (A + T) * y by ring] at htrig
    nlinarith
  rw [hfun, intervalIntegral.integral_const_mul]
  rw [intervalIntegral.integral_add (by fun_prop) (by fun_prop)]
  rw [integral_weighted_cos_linear_v1 L (A - T) hL hsub,
    integral_weighted_cos_linear_v1 L (A + T) hL hadd]

private theorem arch_sin_phase_integer_v1 (L y : ℝ) (n : ℤ) :
    Real.sin (2 * Real.pi * (n : ℝ) * (1 - y / L)) =
      -Real.sin (WeilArchRhoV1 L * (n : ℝ) * y) := by
  calc
    Real.sin (2 * Real.pi * (n : ℝ) * (1 - y / L)) =
        Real.sin ((n : ℝ) * (2 * Real.pi) -
          2 * Real.pi * (y / L) * (n : ℝ)) := by
            congr 1
            ring
    _ = -Real.sin (2 * Real.pi * (y / L) * (n : ℝ)) := by
          simpa [mul_assoc, mul_comm, mul_left_comm] using
            Real.sin_int_mul_two_pi_sub
              (2 * Real.pi * (y / L) * (n : ℝ)) n
    _ = -Real.sin (WeilArchRhoV1 L * (n : ℝ) * y) := by
          congr 1
          simp [WeilArchRhoV1]
          ring

private theorem arch_cos_phase_integer_v1 (L y : ℝ) (n : ℤ) :
    Real.cos (2 * Real.pi * (n : ℝ) * (1 - y / L)) =
      Real.cos (WeilArchRhoV1 L * (n : ℝ) * y) := by
  calc
    Real.cos (2 * Real.pi * (n : ℝ) * (1 - y / L)) =
        Real.cos ((n : ℝ) * (2 * Real.pi) -
          2 * Real.pi * (y / L) * (n : ℝ)) := by
            congr 1
            ring
    _ = Real.cos (2 * Real.pi * (y / L) * (n : ℝ)) := by
          simpa [mul_assoc, mul_comm, mul_left_comm] using
            Real.cos_int_mul_two_pi_sub
              (2 * Real.pi * (y / L) * (n : ℝ)) n
    _ = Real.cos (WeilArchRhoV1 L * (n : ℝ) * y) := by
          congr 1
          simp [WeilArchRhoV1]
          ring

private theorem one_sub_cos_eq_two_sin_sq_half_v1 (z : ℝ) :
    1 - Real.cos z = 2 * Real.sin (z / 2) ^ 2 := by
  have hcos := Real.cos_two_mul' (z / 2)
  have hpyth := Real.sin_sq_add_cos_sq (z / 2)
  rw [show z = 2 * (z / 2) by ring, hcos]
  nlinarith

/-- Exact integer-node evaluation of the Archimedean sine kernel away from
its two resonant denominators. -/
theorem weil_arch_sine_kernel_integer_v1
    (L T : ℝ) (n : ℤ) (hL : L ≠ 0)
    (hden : T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2 ≠ 0) :
    WeilArchSineKernelV1 L T (n : ℝ) =
      2 * WeilArchRhoV1 L * (n : ℝ) * Real.sin (L * T / 2) ^ 2 /
        (T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2) := by
  let A : ℝ := WeilArchRhoV1 L * (n : ℝ)
  have hsub : A - T ≠ 0 := by
    intro h
    apply hden
    have hAT : A = T := sub_eq_zero.mp h
    rw [hAT]
    ring
  have hadd : A + T ≠ 0 := by
    intro h
    apply hden
    have hAT : A = -T := by linarith
    rw [hAT]
    ring
  have hAL : A * L = (n : ℝ) * (2 * Real.pi) := by
    dsimp [A, WeilArchRhoV1]
    field_simp [hL]
    ring
  have hcos_sub : Real.cos ((A - T) * L) = Real.cos (T * L) := by
    rw [show (A - T) * L = (n : ℝ) * (2 * Real.pi) - T * L by rw [hAL]; ring]
    simpa [mul_assoc, mul_comm, mul_left_comm] using
      Real.cos_int_mul_two_pi_sub (T * L) n
  have hcos_add : Real.cos ((A + T) * L) = Real.cos (T * L) := by
    rw [show (A + T) * L = T * L + (n : ℝ) * (2 * Real.pi) by rw [hAL]; ring]
    simpa [mul_assoc, mul_comm, mul_left_comm] using
      Real.cos_add_int_mul_two_pi (T * L) n
  have hhalf : 1 - Real.cos (T * L) = 2 * Real.sin (L * T / 2) ^ 2 := by
    rw [show T * L = L * T by ring]
    exact one_sub_cos_eq_two_sin_sq_half_v1 (L * T)
  unfold WeilArchSineKernelV1
  have hfun :
      (fun y : ℝ =>
        Real.sin (2 * Real.pi * (n : ℝ) * (1 - y / L)) * Real.cos (T * y)) =
      (fun y : ℝ => -(Real.sin (A * y) * Real.cos (T * y))) := by
    funext y
    rw [arch_sin_phase_integer_v1]
    dsimp [A]
    ring
  rw [hfun, intervalIntegral.integral_neg]
  rw [integral_sin_mul_cos_linear_v1 A T L hsub hadd]
  rw [hcos_sub, hcos_add, hhalf]
  change
    -(1 / 2 *
      ((2 * Real.sin (L * T / 2) ^ 2) / (A - T) +
        (2 * Real.sin (L * T / 2) ^ 2) / (A + T))) =
      2 * A * Real.sin (L * T / 2) ^ 2 / (T ^ 2 - A ^ 2)
  field_simp [hsub, hadd, hden]
  ring

/-- Exact integer-node value of the true x-derivative of the Archimedean sine
kernel, again away from the resonant denominators. -/
theorem weil_arch_sine_kernel_dx_integer_v1
    (L T : ℝ) (n : ℤ) (hL : L ≠ 0)
    (hden : T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2 ≠ 0) :
    WeilArchSineKernelDxV1 L T (n : ℝ) =
      2 * WeilArchRhoV1 L * Real.sin (L * T / 2) ^ 2 *
        (T ^ 2 + (WeilArchRhoV1 L * (n : ℝ)) ^ 2) /
        (T ^ 2 - (WeilArchRhoV1 L * (n : ℝ)) ^ 2) ^ 2 := by
  let A : ℝ := WeilArchRhoV1 L * (n : ℝ)
  have hsub : A - T ≠ 0 := by
    intro h
    apply hden
    have hAT : A = T := sub_eq_zero.mp h
    rw [hAT]
    ring
  have hadd : A + T ≠ 0 := by
    intro h
    apply hden
    have hAT : A = -T := by linarith
    rw [hAT]
    ring
  have hAL : A * L = (n : ℝ) * (2 * Real.pi) := by
    dsimp [A, WeilArchRhoV1]
    field_simp [hL]
    ring
  have hcos_sub : Real.cos ((A - T) * L) = Real.cos (T * L) := by
    rw [show (A - T) * L = (n : ℝ) * (2 * Real.pi) - T * L by rw [hAL]; ring]
    simpa [mul_assoc, mul_comm, mul_left_comm] using
      Real.cos_int_mul_two_pi_sub (T * L) n
  have hcos_add : Real.cos ((A + T) * L) = Real.cos (T * L) := by
    rw [show (A + T) * L = T * L + (n : ℝ) * (2 * Real.pi) by rw [hAL]; ring]
    simpa [mul_assoc, mul_comm, mul_left_comm] using
      Real.cos_add_int_mul_two_pi (T * L) n
  have hhalf : 1 - Real.cos (T * L) = 2 * Real.sin (L * T / 2) ^ 2 := by
    rw [show T * L = L * T by ring]
    exact one_sub_cos_eq_two_sin_sq_half_v1 (L * T)
  unfold WeilArchSineKernelDxV1
  have hfun :
      (fun y : ℝ =>
        (2 * Real.pi * (1 - y / L) *
          Real.cos (2 * Real.pi * (n : ℝ) * (1 - y / L))) * Real.cos (T * y)) =
      (fun y : ℝ =>
        (2 * Real.pi) * ((1 - y / L) * Real.cos (A * y) * Real.cos (T * y))) := by
    funext y
    rw [arch_cos_phase_integer_v1]
    dsimp [A]
    ring
  rw [hfun, intervalIntegral.integral_const_mul]
  rw [integral_weighted_cos_mul_cos_linear_v1 L A T hL hsub hadd]
  rw [hcos_sub, hcos_add, hhalf]
  change
    (2 * Real.pi) *
      (1 / 2 *
        ((2 * Real.sin (L * T / 2) ^ 2) / (L * (A - T) ^ 2) +
          (2 * Real.sin (L * T / 2) ^ 2) / (L * (A + T) ^ 2))) =
      2 * (2 * Real.pi / L) * Real.sin (L * T / 2) ^ 2 *
        (T ^ 2 + A ^ 2) / (T ^ 2 - A ^ 2) ^ 2
  field_simp [hL, hsub, hadd, hden]
  ring

#print axioms weil_arch_sine_kernel_hasDerivAt_v1
#print axioms weil_arch_sine_kernel_integer_v1
#print axioms weil_arch_sine_kernel_dx_integer_v1
