/-
Copyright 2026 The Formal Conjectures Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-/
import Mathlib

/-!
# Tail-weight renormalisation cannot break a Feshbach–Schur certificate (HOLON V9)

The Schur matrix of the Arb certificate is `S(B) = A − μ G − (c − μ)⁻¹ B`, where `B` is the projected tail bound
`Σ_j (c_j / p_j) z_j z_jᵀ` (`c_j ≥ 0`, weights `p_j > 0`). Two facts:

* `schur_mono`: if `S(B)` is positive semidefinite and `B − B'` is positive semidefinite, then so is `S(B')`
  (`μ < c`). Any change that does not increase the tail bound in the Loewner order keeps every certified direction.
* `renorm_eq`: dropping atoms that vanish on the projected space and rescaling the remaining weights by
  `p'_j = p_j / P` multiplies the tail bound by `P`: `Σ_j (c_j/(p_j/P)) M_j = P • Σ_j (c_j/p_j) M_j`.
  With `0 ≤ P ≤ 1` and `B ⪰ 0`, `B − P • B = (1 − P) • B ⪰ 0`, so `schur_renorm` follows.

Matrices are real and indexed by a finite type. Not RH.
-/

namespace AEGIS.CvSTailRenormV1

open Matrix

variable {n : Type*} [Fintype n] [DecidableEq n]

theorem schur_mono (A G B B' : Matrix n n ℝ) (μ c : ℝ) (hc : μ < c)
    (hold : (A - μ • G - (c - μ)⁻¹ • B).PosSemidef) (hle : (B - B').PosSemidef) :
    (A - μ • G - (c - μ)⁻¹ • B').PosSemidef := by
  have hpos : 0 ≤ (c - μ)⁻¹ := inv_nonneg.mpr (sub_nonneg.mpr hc.le)
  have h := hold.add (hle.smul hpos)
  have e : A - μ • G - (c - μ)⁻¹ • B' = (A - μ • G - (c - μ)⁻¹ • B) + (c - μ)⁻¹ • (B - B') := by
    rw [smul_sub]; abel
  rw [e]; exact h

theorem renorm_eq {ι : Type*} (s : Finset ι) (cw p : ι → ℝ) (M : ι → Matrix n n ℝ) (P : ℝ) :
    ∑ j ∈ s, (cw j / (p j / P)) • M j = P • ∑ j ∈ s, (cw j / p j) • M j := by
  rw [Finset.smul_sum]
  refine Finset.sum_congr rfl fun j _ => ?_
  rw [smul_smul]
  congr 1
  rw [div_div_eq_mul_div]
  ring

theorem schur_renorm (A G B : Matrix n n ℝ) (μ c P : ℝ) (hc : μ < c) (hB : B.PosSemidef)
    (hP1 : P ≤ 1) (hold : (A - μ • G - (c - μ)⁻¹ • B).PosSemidef) :
    (A - μ • G - (c - μ)⁻¹ • (P • B)).PosSemidef := by
  refine schur_mono A G B (P • B) μ c hc hold ?_
  have e : B - P • B = (1 - P) • B := by rw [sub_smul, one_smul]
  rw [e]; exact hB.smul (sub_nonneg.mpr hP1)

/-- The V9 statement: tail atoms with indices outside `act` are dropped (they vanish on the projected space, so the
bound over `act` with weights `p` is already valid), the active weights are rescaled by `P = Σ_{act} p`, and the
certificate at the old weights transfers to the rescaled ones. -/
theorem schur_renorm_sum {ι : Type*} (act : Finset ι) (cw p : ι → ℝ) (z : ι → Matrix n n ℝ)
    (A G : Matrix n n ℝ) (μ c P : ℝ) (hc : μ < c) (hP1 : P ≤ 1)
    (hterm : ∀ j ∈ act, ((cw j / p j) • z j).PosSemidef)
    (hold : (A - μ • G - (c - μ)⁻¹ • ∑ j ∈ act, (cw j / p j) • z j).PosSemidef) :
    (A - μ • G - (c - μ)⁻¹ • ∑ j ∈ act, (cw j / (p j / P)) • z j).PosSemidef := by
  rw [renorm_eq]
  exact schur_renorm A G _ μ c P hc (Matrix.posSemidef_sum act hterm) hP1 hold

end AEGIS.CvSTailRenormV1

#print axioms AEGIS.CvSTailRenormV1.schur_mono
#print axioms AEGIS.CvSTailRenormV1.renorm_eq
#print axioms AEGIS.CvSTailRenormV1.schur_renorm
#print axioms AEGIS.CvSTailRenormV1.schur_renorm_sum
