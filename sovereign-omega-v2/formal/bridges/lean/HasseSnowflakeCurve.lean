/-
Hasse–Weil bound for the affine curve  y² = x³ + 1  over 𝔽_p  (p prime, p ≥ 5).

  N := #{(x, y) ∈ (ZMod p)² | y² = x³ + 1},   (N - p)² ≤ 4p.

Proof outline.
* `card_sub_eq`: N - p = ∑ₓ χ₂(x³ + 1), χ₂ = quadratic character (`quadraticChar_card_sqrts`).
* p ≡ 2 (mod 3): cubing is a bijection of ZMod p (`cube_injective`), so the sum is
  ∑ᵤ χ₂(u + 1) = 0 (`sum_eq_zero_of_two`); hence N = p.
* p ≡ 1 (mod 3): take χ : MulChar (ZMod p) ℂ of order 3 (`MulChar.exists_mulChar_orderOf`).
  #{x | x³ = w} = 1 + χ w + χ(w)² for every w (`card_cube_roots`), so the sum equals
  J(χ, q) + J(χ⁻¹, q) with q = χ₂ viewed in ℂ (`sum_eq_jacobi_add`, using χ(-1) = 1).
  J(χ⁻¹, q) = conj J(χ, q) (`jacobi_inv_eq_star`) and J(χ, q)·J(χ⁻¹, q) = p (`jacobi_mul`,
  from Mathlib's `jacobiSum_mul_jacobiSum_inv`). So N - p = 2 Re J with |J|² = p, and
  (N - p)² = 4 (Re J)² ≤ 4 |J|² = 4p (`sq_le_of_eq_add_star`).
-/
import Mathlib

open Finset

namespace HasseSnowflake

lemma card_eq_sum (p : ℕ) [Fact p.Prime] :
    (Fintype.card {xy : ZMod p × ZMod p // xy.2 ^ 2 = xy.1 ^ 3 + 1} : ℤ)
      = ∑ x : ZMod p, ((#{y : ZMod p | y ^ 2 = x ^ 3 + 1} : ℕ) : ℤ) := by
  rw [Fintype.card_subtype, Finset.card_filter, Fintype.sum_prod_type]
  push_cast
  refine Finset.sum_congr rfl fun x _ => ?_
  rw [Finset.card_filter]
  push_cast
  rfl

lemma ringChar_ne_two (p : ℕ) [Fact p.Prime] (hp : 5 ≤ p) : ringChar (ZMod p) ≠ 2 := by
  rw [ZMod.ringChar_zmod_n]; omega

/-- `N - p` is the quadratic character sum. -/
lemma card_sub_eq (p : ℕ) [Fact p.Prime] (hp : 5 ≤ p) :
    (Fintype.card {xy : ZMod p × ZMod p // xy.2 ^ 2 = xy.1 ^ 3 + 1} : ℤ) - p
      = ∑ x : ZMod p, quadraticChar (ZMod p) (x ^ 3 + 1) := by
  rw [card_eq_sum]
  have h : ∀ x : ZMod p, ((#{y : ZMod p | y ^ 2 = x ^ 3 + 1} : ℕ) : ℤ)
      = quadraticChar (ZMod p) (x ^ 3 + 1) + 1 := by
    intro x
    rw [← quadraticChar_card_sqrts (ringChar_ne_two p hp), Set.toFinset_ofPred]
  simp only [h, Finset.sum_add_distrib, Finset.sum_const, Finset.card_univ, ZMod.card,
    nsmul_eq_mul, mul_one]
  ring

/-- For `p ≡ 2 mod 3` cubing is injective on `ZMod p`. -/
lemma cube_injective (p : ℕ) [Fact p.Prime] (h2 : p % 3 = 2) :
    Function.Injective (fun x : ZMod p => x ^ 3) := by
  have key : ∀ x : ZMod p, (x ^ 3) ^ (2 * (p / 3) + 1) = x := by
    intro x
    have hp3 : 3 * (2 * (p / 3) + 1) = p + (p - 1) := by omega
    rw [← pow_mul, hp3, pow_add, ZMod.pow_card]
    rcases eq_or_ne x 0 with rfl | hx
    · simp
    · rw [ZMod.pow_card_sub_one_eq_one hx, mul_one]
  intro x y hxy
  have := congrArg (fun z : ZMod p => z ^ (2 * (p / 3) + 1)) hxy
  simpa only [key] using this

lemma sum_eq_zero_of_two (p : ℕ) [Fact p.Prime] (hp : 5 ≤ p) (h2 : p % 3 = 2) :
    ∑ x : ZMod p, quadraticChar (ZMod p) (x ^ 3 + 1) = 0 := by
  have hbij : Function.Bijective (fun x : ZMod p => x ^ 3) :=
    (cube_injective p h2).bijective_of_finite
  rw [hbij.sum_comp (fun w => quadraticChar (ZMod p) (w + 1))]
  exact (Equiv.sum_comp (Equiv.addRight (1 : ZMod p)) (fun w => quadraticChar (ZMod p) w)).trans
    (quadraticChar_sum_zero (ringChar_ne_two p hp))


/-! ### The case `p ≡ 1 mod 3` -/

/-- A primitive cube root of unity in `ZMod p` when `p ≡ 1 mod 3`. -/
lemma exists_cube_root_unity (p : ℕ) [Fact p.Prime] (h1 : p % 3 = 1) :
    ∃ h : ZMod p, h ^ 2 + h + 1 = 0 ∧ h ≠ 1 ∧ h ^ 2 ≠ 1 := by
  have : Fact (Nat.Prime 3) := ⟨Nat.prime_three⟩
  have hdvd : 3 ∣ Fintype.card (ZMod p)ˣ := by rw [ZMod.card_units]; omega
  obtain ⟨u, hu⟩ := exists_prime_orderOf_dvd_card 3 hdvd
  have hu3 : u ^ 3 = 1 := hu ▸ pow_orderOf_eq_one u
  have hu1 : u ≠ 1 := by intro h; rw [h, orderOf_one] at hu; norm_num at hu
  have hu2 : u ^ 2 ≠ 1 := pow_ne_one_of_lt_orderOf (by norm_num) (by omega)
  refine ⟨(u : ZMod p), ?_, ?_, ?_⟩
  · have h3 : (u : ZMod p) ^ 3 = 1 := by rw [← Units.val_pow_eq_pow_val, hu3, Units.val_one]
    have hne : (u : ZMod p) - 1 ≠ 0 := sub_ne_zero.mpr (fun h => hu1 (Units.ext h))
    have : ((u : ZMod p) - 1) * ((u : ZMod p) ^ 2 + u + 1) = 0 := by linear_combination h3
    exact (mul_eq_zero.mp this).resolve_left hne
  · exact fun h => hu1 (Units.ext h)
  · intro h; apply hu2; ext; push_cast; exact h

/-- A nonzero cube has exactly three cube roots when `p ≡ 1 mod 3`. -/
lemma card_cube_roots_of_cube (p : ℕ) [Fact p.Prime] (h1 : p % 3 = 1) {a : ZMod p}
    (ha : a ≠ 0) : #{x : ZMod p | x ^ 3 = a ^ 3} = 3 := by
  obtain ⟨h, hh, hh1, hh2⟩ := exists_cube_root_unity p h1
  have hmem : ∀ x : ZMod p, x ^ 3 = a ^ 3 ↔ x = a ∨ x = a * h ∨ x = a * h ^ 2 := by
    intro x
    constructor
    · intro hx
      have : (x - a) * (x - a * h) * (x - a * h ^ 2) = 0 := by
        linear_combination hx + (-a * x ^ 2 + a ^ 2 * h * x - a ^ 3 * (h - 1)) * hh
      rcases mul_eq_zero.mp this with h' | h'
      · rcases mul_eq_zero.mp h' with h'' | h''
        · exact Or.inl (sub_eq_zero.mp h'')
        · exact Or.inr (Or.inl (sub_eq_zero.mp h''))
      · exact Or.inr (Or.inr (sub_eq_zero.mp h'))
    · rintro (rfl | rfl | rfl)
      · rfl
      · linear_combination a ^ 3 * (h - 1) * hh
      · linear_combination a ^ 3 * (h - 1) * (h ^ 3 + 1) * hh
  rw [Finset.card_eq_three]
  refine ⟨a, a * h, a * h ^ 2, ?_, ?_, ?_, ?_⟩
  · intro H; apply hh1; exact (mul_left_cancel₀ ha (H.symm.trans (mul_one a).symm))
  · intro H; apply hh2; exact (mul_left_cancel₀ ha (H.symm.trans (mul_one a).symm))
  · intro H
    apply hh1
    have E : h = h ^ 2 := mul_left_cancel₀ ha H
    have h3 : h ^ 3 = 1 := by linear_combination (h - 1) * hh
    linear_combination h3 + (1 + h) * E
  · ext x
    simp only [Finset.mem_filter, Finset.mem_univ, true_and, Finset.mem_insert,
      Finset.mem_singleton, hmem]

/-- If a character of order `3` is trivial at `w ≠ 0`, then `w` is a cube. -/
lemma cube_of_chi_eq_one (p : ℕ) [Fact p.Prime] {χ : MulChar (ZMod p) ℂ} (hχ : orderOf χ = 3)
    {w : ZMod p} (hw : w ≠ 0) (h : χ w = 1) : ∃ a : ZMod p, a ^ 3 = w := by
  obtain ⟨g, hg⟩ := IsCyclic.exists_generator (α := (ZMod p)ˣ)
  have hχ3 : χ ^ 3 = 1 := hχ ▸ pow_orderOf_eq_one χ
  set η := χ.toUnitHom g with hηdef
  have hη3 : η ^ 3 = 1 := by
    ext
    rw [Units.val_pow_eq_pow_val, hηdef, MulChar.coe_toUnitHom,
      ← MulChar.pow_apply' χ (by norm_num), hχ3, MulChar.one_apply_coe, Units.val_one]
  have hη1 : η ≠ 1 := by
    intro h1
    have hc : χ = 1 := by
      rw [MulChar.eq_iff hg, MulChar.one_apply_coe]
      have := congrArg Units.val h1
      rwa [hηdef, MulChar.coe_toUnitHom, Units.val_one] at this
    rw [hc, orderOf_one] at hχ
    norm_num at hχ
  have : Fact (Nat.Prime 3) := ⟨Nat.prime_three⟩
  have hord : orderOf η = 3 := orderOf_eq_prime hη3 hη1
  obtain ⟨k, hk⟩ := Subgroup.mem_zpowers_iff.mp (hg (Units.mk0 w hw))
  have hk1 : η ^ k = 1 := by
    rw [hηdef, ← map_zpow, hk]
    ext
    rw [MulChar.coe_toUnitHom, Units.val_mk0, h, Units.val_one]
  have hdvd : ((orderOf η : ℕ) : ℤ) ∣ k := orderOf_dvd_iff_zpow_eq_one.mpr hk1
  rw [hord] at hdvd
  obtain ⟨m, rfl⟩ := hdvd
  refine ⟨((g ^ m : (ZMod p)ˣ) : ZMod p), ?_⟩
  have hu : (g ^ m) ^ 3 = Units.mk0 w hw := by
    rw [← hk, ← zpow_natCast, ← zpow_mul, mul_comm]
  have := congrArg Units.val hu
  rwa [Units.val_pow_eq_pow_val, Units.val_mk0] at this

/-- Number of cube roots via a cubic character (valid for all `w`, including `0`). -/
lemma card_cube_roots (p : ℕ) [Fact p.Prime] (h1 : p % 3 = 1) {χ : MulChar (ZMod p) ℂ}
    (hχ : orderOf χ = 3) (w : ZMod p) :
    ((#{x : ZMod p | x ^ 3 = w} : ℕ) : ℂ) = 1 + χ w + χ w ^ 2 := by
  have hχ3 : χ ^ 3 = 1 := hχ ▸ pow_orderOf_eq_one χ
  rcases eq_or_ne w 0 with rfl | hw
  · have : #{x : ZMod p | x ^ 3 = 0} = 1 := by
      rw [Finset.card_eq_one]
      exact ⟨0, by ext x; simp⟩
    rw [this, MulChar.map_zero]
    simp
  · have hw3 : χ w ^ 3 = 1 := by
      rw [← MulChar.pow_apply' χ (by norm_num), hχ3, MulChar.one_apply hw.isUnit]
    by_cases hc : ∃ a : ZMod p, a ^ 3 = w
    · obtain ⟨a, rfl⟩ := hc
      have ha : a ≠ 0 := by rintro rfl; simp at hw
      rw [card_cube_roots_of_cube p h1 ha]
      have : χ (a ^ 3) = 1 := by
        rw [map_pow, ← MulChar.pow_apply' χ (by norm_num), hχ3, MulChar.one_apply ha.isUnit]
      rw [this]
      norm_num
    · have hempty : #{x : ZMod p | x ^ 3 = w} = 0 := by
        rw [Finset.card_eq_zero, Finset.filter_eq_empty_iff]
        intro x _ hx
        exact hc ⟨x, hx⟩
      have hne : χ w ≠ 1 := fun h => hc (cube_of_chi_eq_one p hχ hw h)
      rw [hempty]
      have : (χ w - 1) * (1 + χ w + χ w ^ 2) = 0 := by linear_combination hw3
      rw [Nat.cast_zero]
      exact ((mul_eq_zero.mp this).resolve_left (sub_ne_zero.mpr hne)).symm


/-- Summing over cubes, weighted by the number of cube roots. -/
lemma sum_cube_eq (p : ℕ) [Fact p.Prime] (h1 : p % 3 = 1) {χ : MulChar (ZMod p) ℂ}
    (hχ : orderOf χ = 3) (f : ZMod p → ℂ) :
    ∑ x : ZMod p, f (x ^ 3) = ∑ w : ZMod p, (1 + χ w + χ w ^ 2) * f w := by
  rw [← Fintype.sum_fiberwise' (fun x : ZMod p => x ^ 3) f]
  refine Finset.sum_congr rfl fun w _ => ?_
  rw [Finset.sum_const, Finset.card_univ, nsmul_eq_mul, ← card_cube_roots p h1 hχ w,
    Fintype.card_subtype]

/-- The quadratic character of `ZMod p`, viewed with complex values. -/
noncomputable abbrev qC (p : ℕ) [Fact p.Prime] : MulChar (ZMod p) ℂ :=
  (quadraticChar (ZMod p)).ringHomComp (Int.castRingHom ℂ)

lemma qC_isQuadratic (p : ℕ) [Fact p.Prime] : (qC p).IsQuadratic :=
  (quadraticChar_isQuadratic (ZMod p)).comp _

lemma qC_ne_one (p : ℕ) [Fact p.Prime] (hp : 5 ≤ p) : qC p ≠ 1 :=
  (MulChar.ringHomComp_ne_one_iff (Int.castRingHom ℂ).injective_int).mpr
    (quadraticChar_ne_one (ringChar_ne_two p hp))

lemma apply_neg_one_eq_one (p : ℕ) [Fact p.Prime] {φ : MulChar (ZMod p) ℂ} (hφ : φ ^ 3 = 1) :
    φ (-1) = 1 := by
  have h2 : φ (-1) ^ 2 = 1 := by rw [← map_pow, neg_one_sq, map_one]
  have h3 : φ (-1) ^ 3 = 1 := by
    rw [← MulChar.pow_apply' φ (by norm_num), hφ, MulChar.one_apply isUnit_one.neg]
  linear_combination h3 - φ (-1) * h2

/-- Substitution `x = -w` turns the twisted sum into a Jacobi sum. -/
lemma sum_eq_jacobiSum (p : ℕ) [Fact p.Prime] (φ ψ : MulChar (ZMod p) ℂ) (hφ : φ (-1) = 1) :
    ∑ w : ZMod p, φ w * ψ (w + 1) = jacobiSum φ ψ := by
  rw [jacobiSum]
  refine Fintype.sum_equiv (Equiv.neg (ZMod p)) _ _ fun w => ?_
  simp only [Equiv.neg_apply, sub_neg_eq_add]
  rw [neg_eq_neg_one_mul w, map_mul, hφ, one_mul, add_comm]

/-- For `p ≡ 1 mod 3`: the character sum is `J(χ, q) + J(χ⁻¹, q)`. -/
lemma sum_eq_jacobi_add (p : ℕ) [Fact p.Prime] (hp : 5 ≤ p) (h1 : p % 3 = 1)
    {χ : MulChar (ZMod p) ℂ} (hχ : orderOf χ = 3) :
    ((∑ x : ZMod p, quadraticChar (ZMod p) (x ^ 3 + 1) : ℤ) : ℂ)
      = jacobiSum χ (qC p) + jacobiSum χ⁻¹ (qC p) := by
  have hχ3 : χ ^ 3 = 1 := hχ ▸ pow_orderOf_eq_one χ
  have hχi3 : χ⁻¹ ^ 3 = 1 := by rw [inv_pow, hχ3, inv_one]
  have hsq : ∀ w, χ w ^ 2 = χ⁻¹ w := by
    intro w
    rw [← MulChar.pow_apply' χ (by norm_num)]
    congr 1
    exact eq_inv_of_mul_eq_one_left (by rw [← pow_succ, hχ3])
  have hL : ((∑ x : ZMod p, quadraticChar (ZMod p) (x ^ 3 + 1) : ℤ) : ℂ)
      = ∑ x : ZMod p, qC p (x ^ 3 + 1) := by
    push_cast
    rfl
  rw [hL, sum_cube_eq p h1 hχ (fun w => qC p (w + 1))]
  simp only [add_mul, one_mul, Finset.sum_add_distrib, hsq]
  have h0 : ∑ w : ZMod p, qC p (w + 1) = 0 :=
    (Equiv.sum_comp (Equiv.addRight (1 : ZMod p)) (fun w => qC p w)).trans
      (MulChar.sum_eq_zero_of_ne_one (qC_ne_one p hp))
  rw [h0, zero_add, sum_eq_jacobiSum p χ _ (apply_neg_one_eq_one p hχ3),
    sum_eq_jacobiSum p χ⁻¹ _ (apply_neg_one_eq_one p hχi3)]

/-- `J(χ⁻¹, q)` is the complex conjugate of `J(χ, q)`. -/
lemma jacobi_inv_eq_star (p : ℕ) [Fact p.Prime] (χ : MulChar (ZMod p) ℂ) :
    jacobiSum χ⁻¹ (qC p) = star (jacobiSum χ (qC p)) := by
  simp only [jacobiSum, star_sum, star_mul', MulChar.star_apply', (qC_isQuadratic p).inv]

/-- `J(χ, q) · J(χ⁻¹, q) = p`. -/
lemma jacobi_mul (p : ℕ) [Fact p.Prime] (hp : 5 ≤ p) {χ : MulChar (ZMod p) ℂ}
    (hχ : orderOf χ = 3) :
    jacobiSum χ (qC p) * jacobiSum χ⁻¹ (qC p) = p := by
  have hqq := qC_isQuadratic p
  have hχ1 : χ ≠ 1 := by
    rintro rfl
    rw [orderOf_one] at hχ
    norm_num at hχ
  have hχq : χ * qC p ≠ 1 := by
    intro h
    have h' : χ = (qC p)⁻¹ := eq_inv_of_mul_eq_one_left h
    rw [hqq.inv] at h'
    have h2 : χ ^ 2 = 1 := h' ▸ hqq.sq_eq_one
    have := orderOf_dvd_of_pow_eq_one h2
    rw [hχ] at this
    norm_num at this
  have hchar : ringChar ℂ ≠ ringChar (ZMod p) := by
    rw [ringChar.eq_zero, ZMod.ringChar_zmod_n]
    exact (Fact.out : p.Prime).ne_zero.symm
  have := jacobiSum_mul_jacobiSum_inv hchar hχ1 (qC_ne_one p hp) hχq
  rwa [hqq.inv, ZMod.card] at this

/-- The final real-variable estimate: if `S = J + J̄` and `J J̄ = p` then `S² ≤ 4p`. -/
lemma sq_le_of_eq_add_star (S : ℤ) (J : ℂ) (p : ℕ) (hS : (S : ℂ) = J + star J)
    (hJ : J * star J = p) : S ^ 2 ≤ 4 * p := by
  have h1 : (S : ℝ) = 2 * J.re := by
    have := congrArg Complex.re hS
    simp only [Complex.intCast_re, Complex.add_re, Complex.star_def, Complex.conj_re] at this
    rw [this]
    ring
  have h2 : J.re ^ 2 + J.im ^ 2 = p := by
    have := congrArg Complex.re hJ
    simp only [Complex.mul_re, Complex.star_def, Complex.conj_re, Complex.conj_im,
      Complex.natCast_re] at this
    linear_combination this
  have : (S : ℝ) ^ 2 ≤ 4 * p := by
    rw [h1]
    nlinarith [sq_nonneg J.im]
  exact_mod_cast this

end HasseSnowflake

open HasseSnowflake in
/-- **Hasse–Weil bound** for the affine curve `y² = x³ + 1` over `𝔽_p`, `p ≥ 5`:
`(N - p)² ≤ 4p`, where `N` is the number of affine solutions in `ZMod p`. -/
theorem hasse_snowflake (p : ℕ) [Fact p.Prime] (hp : 5 ≤ p) :
    ((Fintype.card {xy : ZMod p × ZMod p // xy.2 ^ 2 = xy.1 ^ 3 + 1} : ℤ) - p) ^ 2 ≤ 4 * p := by
  rw [card_sub_eq p hp]
  have hp3 : p % 3 = 1 ∨ p % 3 = 2 := by
    have : p % 3 ≠ 0 := by
      intro h
      rcases (Fact.out : p.Prime).eq_one_or_self_of_dvd 3 (Nat.dvd_of_mod_eq_zero h) with h' | h'
      <;> omega
    omega
  rcases hp3 with h1 | h2
  · obtain ⟨χ, hχ⟩ := MulChar.exists_mulChar_orderOf (ZMod p) (R := ℂ) (n := 3)
      (by rw [ZMod.card]; omega) (Complex.isPrimitiveRoot_exp 3 (by norm_num))
    apply sq_le_of_eq_add_star _ (jacobiSum χ (qC p)) p
    · rw [sum_eq_jacobi_add p hp h1 hχ, jacobi_inv_eq_star]
    · rw [← jacobi_inv_eq_star]
      exact jacobi_mul p hp hχ
  · rw [sum_eq_zero_of_two p hp h2]
    positivity

#print axioms hasse_snowflake
#print axioms HasseSnowflake.card_sub_eq
#print axioms HasseSnowflake.sum_eq_zero_of_two
#print axioms HasseSnowflake.card_cube_roots
#print axioms HasseSnowflake.sum_eq_jacobi_add
#print axioms HasseSnowflake.jacobi_inv_eq_star
#print axioms HasseSnowflake.jacobi_mul
#print axioms HasseSnowflake.sq_le_of_eq_add_star
