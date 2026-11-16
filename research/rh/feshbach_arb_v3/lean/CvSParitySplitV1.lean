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
# Parity split of the Feshbach–Schur certificate (parity duel V1)

The band matrices of the certificate commute with the reflection `P : e_m ↦ e_{−m}` (`α` odd, `S, σ` odd,
`CC, XC, cos` even, the row set `|n| ≤ NP` symmetric). For a basis split into reflection-even columns `Be`
(`P Be = Be`) and reflection-odd columns `Bo` (`P Bo = −Bo`):

* `cross_zero`: `Beᵀ S Bo = 0` whenever `Pᵀ S = S P`, an exact identity, not a small interval;
* `blocks_posSemidef`: a positive definite even block and a positive semidefinite odd block give a positive
  semidefinite block-diagonal matrix (Mathlib's `PosDef.fromBlocks₁₁` with zero coupling);
* `congr_posSemidef`: `Tᵀ S T` is positive semidefinite whenever `S` is (any `T`), so the certificate can be checked in
  the parity basis `B = Z T` and read back in any other basis of the same space.

Real matrices over finite index types. Not RH.
-/

namespace AEGIS.CvSParitySplitV1

open Matrix

variable {r e o : Type*} [Fintype r] [Fintype e] [Fintype o] [DecidableEq e] [DecidableEq o]

theorem cross_zero (P S : Matrix r r ℝ) (Be : Matrix r e ℝ) (Bo : Matrix r o ℝ)
    (hPS : Pᵀ * S = S * P) (he : P * Be = Be) (ho : P * Bo = -Bo) :
    Beᵀ * S * Bo = 0 := by
  have h : Beᵀ * S * Bo = -(Beᵀ * S * Bo) := by
    calc Beᵀ * S * Bo = (P * Be)ᵀ * S * Bo := by rw [he]
      _ = Beᵀ * (Pᵀ * S) * Bo := by rw [transpose_mul]; simp only [Matrix.mul_assoc]
      _ = Beᵀ * (S * (P * Bo)) := by rw [hPS]; simp only [Matrix.mul_assoc]
      _ = -(Beᵀ * S * Bo) := by rw [ho]; simp only [Matrix.mul_neg, Matrix.mul_assoc]
  ext i j
  have := congrFun (congrFun h i) j
  simp only [Matrix.neg_apply, Matrix.zero_apply] at this ⊢
  linarith

theorem blocks_posSemidef (Se : Matrix e e ℝ) (So : Matrix o o ℝ) (he : Se.PosDef) (ho : So.PosSemidef) :
    (fromBlocks Se 0 0 So).PosSemidef := by
  haveI : Invertible Se := he.isUnit.invertible
  have h := (PosDef.fromBlocks₁₁ (0 : Matrix e o ℝ) So he).2 (by simpa using ho)
  simpa using h

theorem congr_posSemidef {m : Type*} [Fintype m] (S : Matrix r r ℝ) (T : Matrix r m ℝ) (hS : S.PosSemidef) :
    (Tᵀ * S * T).PosSemidef := by
  convert hS.conjTranspose_mul_mul_same T using 2
  rw [conjTranspose_eq_transpose_of_trivial]

end AEGIS.CvSParitySplitV1

#print axioms AEGIS.CvSParitySplitV1.cross_zero
#print axioms AEGIS.CvSParitySplitV1.blocks_posSemidef
#print axioms AEGIS.CvSParitySplitV1.congr_posSemidef
