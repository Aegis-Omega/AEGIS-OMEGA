import Mathlib

open Finset

namespace EulerProductSupport

/-- `L` is a logarithmic derivative of `f`: `f(n) log n = Σ_{d ∣ n} L(d) f(n/d)`. -/
def IsLogDeriv (f L : ℕ → ℝ) : Prop :=
  ∀ n, f n * Real.log n = ∑ d ∈ n.divisors, L d * f (n / d)

lemma sum_divisors_coprime {a b : ℕ} (h : a.Coprime b) (F : ℕ → ℝ) :
    ∑ d ∈ (a * b).divisors, F d = ∑ d₁ ∈ a.divisors, ∑ d₂ ∈ b.divisors, F (d₁ * d₂) := by
  rw [Nat.divisors_mul, Finset.mul_def, Finset.sum_image h.mul_injOn_divisors,
    Finset.sum_product]

lemma L_one {f L : ℕ → ℝ} (hf1 : f 1 = 1) (hL : IsLogDeriv f L) : L 1 = 0 := by
  have := hL 1
  simp [hf1] at this
  linarith

/-- A product of two coprime numbers, both `> 1`, is not a prime power. -/
lemma not_isPrimePow_mul {a b : ℕ} (h : a.Coprime b) (ha : 1 < a) (hb : 1 < b) :
    ¬ IsPrimePow (a * b) := by
  rintro ⟨p, k, hp, hk, hpk⟩
  have hp' := hp.nat_prime
  obtain ⟨i, -, hi⟩ := (Nat.dvd_prime_pow hp').1 (hpk ▸ dvd_mul_right a b)
  obtain ⟨j, -, hj⟩ := (Nat.dvd_prime_pow hp').1 (hpk ▸ dvd_mul_left b a)
  have hi0 : i ≠ 0 := by rintro rfl; simp at hi; omega
  have hj0 : j ≠ 0 := by rintro rfl; simp at hj; omega
  have : p ∣ Nat.gcd a b :=
    Nat.dvd_gcd (hi ▸ dvd_pow_self p hi0) (hj ▸ dvd_pow_self p hj0)
  rw [h.gcd_eq_one] at this
  exact hp'.one_lt.ne' (Nat.dvd_one.mp this)

/-- The coprime split of the defining sum, given a pointwise decomposition of its terms. -/
lemma split {a b : ℕ} (h : a.Coprime b) (ha : a ≠ 0) (hb : b ≠ 0) (f L : ℕ → ℝ) (E : ℝ)
    (hpt : ∀ d₁ ∈ a.divisors, ∀ d₂ ∈ b.divisors,
      L (d₁ * d₂) * f (a * b / (d₁ * d₂)) =
        (if d₂ = 1 then L d₁ * f (a / d₁) * f b else 0) +
        (if d₁ = 1 then L d₂ * f a * f (b / d₂) else 0) +
        (if d₁ = a then (if d₂ = b then E else 0) else 0)) :
    ∑ d ∈ (a * b).divisors, L d * f (a * b / d) =
      f b * ∑ d ∈ a.divisors, L d * f (a / d) + f a * ∑ d ∈ b.divisors, L d * f (b / d) + E := by
  rw [sum_divisors_coprime h (fun d => L d * f (a * b / d))]
  rw [Finset.sum_congr rfl fun d₁ hd₁ => Finset.sum_congr rfl fun d₂ hd₂ => hpt d₁ hd₁ d₂ hd₂]
  simp only [Finset.sum_add_distrib, Finset.sum_ite_eq', Finset.sum_ite_irrel,
    Finset.sum_const_zero, Nat.one_mem_divisors, Nat.mem_divisors_self, ne_eq, ha, hb,
    not_false_eq_true, if_true, Finset.mul_sum]
  congr 1; congr 1 <;> exact Finset.sum_congr rfl fun x _ => by ring

lemma log_mul_nat {a b : ℕ} (ha : a ≠ 0) (hb : b ≠ 0) :
    Real.log ((a * b : ℕ) : ℝ) = Real.log a + Real.log b := by
  push_cast
  exact Real.log_mul (by exact_mod_cast ha) (by exact_mod_cast hb)

/-- **Prime-power support ⇒ multiplicativity.** -/
theorem multiplicative_of_support {f L : ℕ → ℝ} (hf1 : f 1 = 1) (hL : IsLogDeriv f L)
    (hs : ∀ n, 0 < n → ¬ IsPrimePow n → L n = 0) :
    ∀ a b, a.Coprime b → f (a * b) = f a * f b := by
  have hL1 := L_one hf1 hL
  suffices H : ∀ N a b, a * b = N → a.Coprime b → f (a * b) = f a * f b from
    fun a b => H _ a b rfl
  intro N
  induction N using Nat.strong_induction_on with
  | _ N ih =>
  intro a b hN h
  rcases Nat.lt_or_ge a 2 with ha | ha
  · interval_cases a
    · rw [Nat.coprime_zero_left] at h; subst h; simp [hf1]
    · simp [hf1]
  rcases Nat.lt_or_ge b 2 with hb | hb
  · interval_cases b
    · rw [Nat.coprime_zero_right] at h; subst h; simp [hf1]
    · simp [hf1]
  have ha0 : a ≠ 0 := by omega
  have hb0 : b ≠ 0 := by omega
  have key := hL (a * b)
  rw [split h ha0 hb0 f L 0 ?_, ← hL a, ← hL b, log_mul_nat ha0 hb0] at key
  · have hpos : 0 < Real.log a + Real.log b := by
      have : (1 : ℝ) < a := by exact_mod_cast ha
      have : (1 : ℝ) < b := by exact_mod_cast hb
      have := Real.log_pos (by assumption : (1 : ℝ) < a)
      have := Real.log_pos (by assumption : (1 : ℝ) < b)
      linarith
    have : (f (a * b) - f a * f b) * (Real.log a + Real.log b) = 0 := by linarith
    rcases mul_eq_zero.mp this with h0 | h0
    · linarith
    · linarith
  · intro d₁ hd₁ d₂ hd₂
    have hd₁' := Nat.dvd_of_mem_divisors hd₁
    have hd₂' := Nat.dvd_of_mem_divisors hd₂
    have hd₁0 : 0 < d₁ := Nat.pos_of_mem_divisors hd₁
    have hd₂0 : 0 < d₂ := Nat.pos_of_mem_divisors hd₂
    have hq : a * b / (d₁ * d₂) = a / d₁ * (b / d₂) := (Nat.div_mul_div_comm hd₁' hd₂').symm
    have hcq : (a / d₁).Coprime (b / d₂) :=
      (h.coprime_dvd_left (Nat.div_dvd_of_dvd hd₁')).coprime_dvd_right (Nat.div_dvd_of_dvd hd₂')
    by_cases e₁ : d₁ = 1 <;> by_cases e₂ : d₂ = 1
    · subst e₁; subst e₂; simp [hL1]
    · subst e₁
      have hlt : a * (b / d₂) < N := by
        rw [← hN]; exact Nat.mul_lt_mul_of_pos_left (Nat.div_lt_self (by omega) (by omega)) (by omega)
      have hc : a.Coprime (b / d₂) := h.coprime_dvd_right (Nat.div_dvd_of_dvd hd₂')
      rw [hq, Nat.div_one, ih _ hlt a (b / d₂) rfl hc]
      simp [e₂, show (1 : ℕ) ≠ a by omega]
      ring
    · subst e₂
      have hlt : a / d₁ * b < N := by
        rw [← hN]; exact Nat.mul_lt_mul_of_pos_right (Nat.div_lt_self (by omega) (by omega)) (by omega)
      have hc : (a / d₁).Coprime b := h.coprime_dvd_left (Nat.div_dvd_of_dvd hd₁')
      rw [hq, Nat.div_one, ih _ hlt (a / d₁) b rfl hc]
      simp [e₁]
      try ring
    · have hc : d₁.Coprime d₂ := (h.coprime_dvd_left hd₁').coprime_dvd_right hd₂'
      rw [hs _ (Nat.mul_pos hd₁0 hd₂0) (not_isPrimePow_mul hc (by omega) (by omega))]
      simp [e₁, e₂]

/-- **Multiplicativity ⇒ prime-power support.** -/
theorem support_of_multiplicative {f L : ℕ → ℝ} (hf1 : f 1 = 1) (hL : IsLogDeriv f L)
    (hmul : ∀ a b, a.Coprime b → f (a * b) = f a * f b) :
    ∀ n, 0 < n → ¬ IsPrimePow n → L n = 0 := by
  have hL1 := L_one hf1 hL
  intro n
  induction n using Nat.strong_induction_on with
  | _ n ih =>
  intro hn hpp
  rcases Nat.lt_or_ge n 2 with h2 | h2
  · interval_cases n; exact hL1
  set p := n.minFac with hpdef
  have hp : p.Prime := Nat.minFac_prime (by omega)
  set a := p ^ n.factorization p with hadef
  set b := n / a with hbdef
  have hab : a * b = n := Nat.ordProj_mul_ordCompl_eq_self n p
  have h : a.Coprime b := (Nat.coprime_ordCompl hp (by omega)).pow_left _
  have hk : 0 < n.factorization p := hp.factorization_pos_of_dvd (by omega) (Nat.minFac_dvd n)
  have ha : 1 < a := Nat.one_lt_pow (by omega) hp.one_lt
  have hb0 : b ≠ 0 := by intro hb; rw [hb, mul_zero] at hab; omega
  have hb : 1 < b := by
    rcases Nat.lt_or_ge b 2 with hb' | hb'
    · have hb1 : b = 1 := by have := Nat.pos_of_ne_zero hb0; omega
      have e := hab
      rw [hb1, mul_one] at e
      exact absurd ⟨p, n.factorization p, hp.prime, hk, e⟩ hpp
    · exact hb'
  have ha0 : a ≠ 0 := by omega
  rw [← hab]
  have key := hL (a * b)
  rw [split h ha0 hb0 f L (L (a * b)) ?_, ← hL a, ← hL b, log_mul_nat ha0 hb0, hmul a b h] at key
  · linarith
  · intro d₁ hd₁ d₂ hd₂
    have hd₁' := Nat.dvd_of_mem_divisors hd₁
    have hd₂' := Nat.dvd_of_mem_divisors hd₂
    have hd₁0 : 0 < d₁ := Nat.pos_of_mem_divisors hd₁
    have hd₂0 : 0 < d₂ := Nat.pos_of_mem_divisors hd₂
    have hd₁a : d₁ ≤ a := Nat.divisor_le hd₁
    have hd₂b : d₂ ≤ b := Nat.divisor_le hd₂
    have hq : a * b / (d₁ * d₂) = a / d₁ * (b / d₂) := (Nat.div_mul_div_comm hd₁' hd₂').symm
    have hcq : (a / d₁).Coprime (b / d₂) :=
      (h.coprime_dvd_left (Nat.div_dvd_of_dvd hd₁')).coprime_dvd_right (Nat.div_dvd_of_dvd hd₂')
    rw [hq, hmul _ _ hcq]
    by_cases e₁ : d₁ = 1 <;> by_cases e₂ : d₂ = 1
    · subst e₁; subst e₂
      simp [hL1, show ¬ (1 : ℕ) = a by omega]
    · subst e₁
      rw [if_neg e₂, if_pos rfl, if_neg (by omega : ¬ (1 : ℕ) = a), Nat.one_mul, Nat.div_one]
      ring
    · subst e₂
      rw [if_pos rfl, if_neg e₁, Nat.mul_one, Nat.div_one]
      by_cases hA : d₁ = a
      · rw [if_pos hA, if_neg (by omega : ¬ (1 : ℕ) = b)]; ring
      · rw [if_neg hA]; ring
    · rw [if_neg e₂, if_neg e₁]
      by_cases hfull : d₁ = a ∧ d₂ = b
      · obtain ⟨h1, h2⟩ := hfull
        rw [if_pos h1, if_pos h2, h1, h2, Nat.div_self (by omega), Nat.div_self (by omega), hf1]
        ring
      · have hc : d₁.Coprime d₂ := (h.coprime_dvd_left hd₁').coprime_dvd_right hd₂'
        have hlt : d₁ * d₂ < a * b := by
          rcases Nat.lt_or_ge d₁ a with h1 | h1
          · exact Nat.mul_lt_mul_of_lt_of_le h1 hd₂b (by omega)
          · have : d₂ < b := by
              rcases Nat.lt_or_ge d₂ b with h3 | h3
              · exact h3
              · exact absurd ⟨by omega, by omega⟩ hfull
            exact Nat.mul_lt_mul_of_le_of_lt hd₁a this (by omega)
        rw [ih _ (hab ▸ hlt) (Nat.mul_pos hd₁0 hd₂0) (not_isPrimePow_mul hc (by omega) (by omega))]
        by_cases hA : d₁ = a
        · rw [if_pos hA, if_neg (fun hB => hfull ⟨hA, hB⟩)]; ring
        · rw [if_neg hA]; ring

/-- **Euler product criterion (arithmetic form).** For `f(1) = 1` and any logarithmic
derivative `L` of `f`: `f` is multiplicative iff `L` vanishes off prime powers. -/
theorem multiplicative_iff_support {f L : ℕ → ℝ} (hf1 : f 1 = 1) (hL : IsLogDeriv f L) :
    (∀ a b, a.Coprime b → f (a * b) = f a * f b) ↔
      (∀ n, 0 < n → ¬ IsPrimePow n → L n = 0) :=
  ⟨support_of_multiplicative hf1 hL, multiplicative_of_support hf1 hL⟩

/-- Sanity: Mathlib's `Λ` is the logarithmic derivative of `ζ`. -/
theorem isLogDeriv_zeta :
    IsLogDeriv (fun n => if n = 0 then 0 else 1) (fun n => ArithmeticFunction.vonMangoldt n) := by
  intro n
  dsimp only
  rcases Nat.eq_zero_or_pos n with rfl | hn
  · simp
  · rw [if_neg hn.ne', one_mul, ← ArithmeticFunction.vonMangoldt_sum]
    refine Finset.sum_congr rfl fun d hd => ?_
    have : n / d ≠ 0 := (Nat.div_pos (Nat.divisor_le hd) (Nat.pos_of_mem_divisors hd)).ne'
    simp [this]

end EulerProductSupport

#print axioms EulerProductSupport.multiplicative_iff_support
#print axioms EulerProductSupport.isLogDeriv_zeta
