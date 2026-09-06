(*
  AEGIS Ω — CoRN IR -> O₀ morphism and completion bridge (A1c)

  Reference route:

    IR --IRasCR--> CoRN fast CR
       --SlowConstructiveRealsMorphism--> O0RealsV1.

  This file first binds A1-RAT / A1-STRICT for that reference route, then
  identifies the independent CR_complete presentation built from CoRN's
  canonical rational approximation G with the reference carrier by proving
  that both are limits of the same O₀ rational sequence.

  No Axiom, Parameter, or Admitted is introduced.
*)

Require Import AnalyticDefinitions.
From Coq Require Import QArith.
From Coq Require Import Reals.Abstract.ConstructiveReals.
From Coq Require Import Reals.Abstract.ConstructiveLimits.
From Coq Require Import Reals.Abstract.ConstructiveRealsMorphisms.
Require Import CoRN.reals.R_morphism.
Require Import CoRN.reals.Q_dense.
Require Import CoRN.reals.Q_in_CReals.
Require Import CoRN.reals.fast.CRIR.
Require Import CoRN.reals.fast.CRArith.
Require Import CoRN.reals.fast.CRabs.
Require Import CoRN.reals.stdlib.ConstructiveFastReals.

Local Open Scope CR_scope.

Definition corn_fast_to_o0_morphism_a1c_v1
  : @ConstructiveRealsMorphism FastRealsConstructive O0RealsV1 :=
  @SlowConstructiveRealsMorphism FastRealsConstructive O0RealsV1.

Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=
  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x).

(* CoRN fast-real setoid equality is extensionally the equality induced by
   FastRealsConstructive's Set-valued strict order. *)
Lemma corn_fast_eq_to_stdlib_eq_a1c_v1 :
  forall x y : CR,
    (x == y)%CR ->
    CReq FastRealsConstructive x y.
Proof.
  intros x y Hxy.
  exact (proj1 (CReq_nlt x y) Hxy).
Qed.

(* The stdlib order at FastRealsConstructive is definitionally the negation
   of the reverse CoRN CRltT relation. *)
Lemma corn_fast_le_to_stdlib_le_a1c_v1 :
  forall x y : CR,
    (x <= y)%CR ->
    (CRltT y x -> False).
Proof.
  intros x y Hxy.
  exact (proj1 (CRle_not_lt x y) Hxy).
Qed.

Theorem corn_ir_to_o0_proper_v1 :
  forall x y : IR,
    x [=] y ->
    O0EqV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y).
Proof.
  intros x y Hxy.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  apply CRmorph_proper.
  apply corn_fast_eq_to_stdlib_eq_a1c_v1.
  exact (IRasCR_wd x y Hxy).
Qed.

(* A1-RAT for the reference carrier. *)
Theorem corn_ir_to_o0_preserves_rat_v1 :
  forall q : Q,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (inj_Q IR q))
      (CR_of_Q O0RealsV1 q).
Proof.
  intros q.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact (IR_inj_Q_as_CR q).
  - change
      (CReq O0RealsV1
        (CRmorph corn_fast_to_o0_morphism_a1c_v1
          (CR_of_Q FastRealsConstructive q))
        (CR_of_Q O0RealsV1 q)).
    exact (CRmorph_rat corn_fast_to_o0_morphism_a1c_v1 q).
Qed.

(* A1-STRICT for the reference carrier. *)
Theorem corn_ir_to_o0_strict_v1 :
  forall x y : IR,
    x [<] y ->
    O0LtV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y).
Proof.
  intros x y Hxy.
  unfold corn_ir_to_o0_carrier_v1, O0LtV1.
  apply CRmorph_increasing.
  exact
    (map_pres_less_unfolded
       IR CRasCReals
       (iso_map_rht CRasCReals IR CRIR_iso)
       x y Hxy).
Qed.

(* Ring/order corollaries of the two existing morphism layers. *)
Theorem corn_ir_to_o0_preserves_zero_v1 :
  O0EqV1
    (corn_ir_to_o0_carrier_v1 [0])
    O0ZeroV1.
Proof.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1, O0ZeroV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact IR_Zero_as_CR.
  - change
      (CReq O0RealsV1
        (CRmorph corn_fast_to_o0_morphism_a1c_v1
          (CR_of_Q FastRealsConstructive 0%Q))
        (CR_of_Q O0RealsV1 0%Q)).
    exact (CRmorph_zero corn_fast_to_o0_morphism_a1c_v1).
Qed.

Theorem corn_ir_to_o0_preserves_one_v1 :
  O0EqV1
    (corn_ir_to_o0_carrier_v1 [1])
    (CR_of_Q O0RealsV1 1%Q).
Proof.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact IR_One_as_CR.
  - change
      (CReq O0RealsV1
        (CRmorph corn_fast_to_o0_morphism_a1c_v1
          (CR_of_Q FastRealsConstructive 1%Q))
        (CR_of_Q O0RealsV1 1%Q)).
    exact (CRmorph_one corn_fast_to_o0_morphism_a1c_v1).
Qed.

Theorem corn_ir_to_o0_preserves_plus_v1 :
  forall x y : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (x [+] y))
      ((corn_ir_to_o0_carrier_v1 x + corn_ir_to_o0_carrier_v1 y)%ConstructiveReals).
Proof.
  intros x y.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact (IR_plus_as_CR x y).
  - exact
      (CRmorph_plus corn_fast_to_o0_morphism_a1c_v1
         (IRasCR x) (IRasCR y)).
Qed.

Theorem corn_ir_to_o0_preserves_mult_v1 :
  forall x y : IR,
    O0EqV1
      (corn_ir_to_o0_carrier_v1 (x [*] y))
      ((corn_ir_to_o0_carrier_v1 x * corn_ir_to_o0_carrier_v1 y)%ConstructiveReals).
Proof.
  intros x y.
  unfold corn_ir_to_o0_carrier_v1, O0EqV1.
  eapply CReq_trans.
  - apply CRmorph_proper.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact (IR_mult_as_CR x y).
  - exact
      (CRmorph_mult corn_fast_to_o0_morphism_a1c_v1
         (IRasCR x) (IRasCR y)).
Qed.

Theorem corn_ir_to_o0_preserves_le_v1 :
  forall x y : IR,
    x [<=] y ->
    O0LeV1
      (corn_ir_to_o0_carrier_v1 x)
      (corn_ir_to_o0_carrier_v1 y).
Proof.
  intros x y Hxy.
  unfold corn_ir_to_o0_carrier_v1, O0LeV1.
  apply CRmorph_le.
  (* Expose FastRealsConstructive.CRle as the negated reverse CRltT. *)
  change (CRltT (IRasCR y) (IRasCR x) -> False).
  apply corn_fast_le_to_stdlib_le_a1c_v1.
  exact (proj1 (IR_leEq_as_CR x y) Hxy).
Qed.

(* -------------------------------------------------------------------- *)
(* Completion identity: canonical CoRN G sequence -> O₀ CR_complete.     *)
(* -------------------------------------------------------------------- *)

(* CoRN's SeqLimit/Cauchy_Lim_prop2 and Rocq's CR_cv use equivalent
   epsilon formulations on the same fast-real carrier. This lemma is the
   only representation-level compatibility step required by the closure. *)
Lemma corn_fast_cauchy_lim_prop2_to_cv_a1c_v1 :
  forall (un : nat -> CR) (l : CR),
    CoRN.reals.R_morphism.Cauchy_Lim_prop2 CRasCReals un l ->
    CR_cv FastRealsConstructive un l.
Proof.
  intros un l Hcv p.
  assert (Heps : (0 < inject_Q_CR (1 # p))%CR).
  { apply CRlt_Qlt. reflexivity. }
  destruct (Hcv (inject_Q_CR (1 # p)) Heps) as [N HN].
  exists N.
  intros i Hi.
  change
    (CRltT (inject_Q_CR (1 # p)) (CRabs (un i - l)%CR) -> False).
  apply (proj1 (CRle_not_lt _ _)).
  apply (proj2 (CRabs_AbsSmall _ _)).
  exact (HN i Hi).
Qed.

(* Transport x_is_SeqLimit_G through the machine-proved CoRN IR -> fast CR
   isomorphism. *)
Lemma corn_ir_G_fast_cauchy_lim_prop2_v1 :
  forall x : IR,
    CoRN.reals.R_morphism.Cauchy_Lim_prop2
      CRasCReals
      (fun n : nat => IRasCR (inj_Q IR (G IR x n)))
      (IRasCR x).
Proof.
  intro x.
  exact
    (map_pres_Lim
       IR CRasCReals
       (iso_map_rht CRasCReals IR CRIR_iso)
       _ _
       (x_is_SeqLimit_G IR x)).
Qed.

(* Replace the mapped IR rational injection pointwise by FastRealsConstructive's
   canonical CR_of_Q. *)
Lemma corn_ir_G_fast_cv_v1 :
  forall x : IR,
    CR_cv FastRealsConstructive
      (fun n : nat => CR_of_Q FastRealsConstructive (G IR x n))
      (IRasCR x).
Proof.
  intro x.
  eapply CR_cv_extens
    with (xn := fun n : nat => IRasCR (inj_Q IR (G IR x n))).
  - intro n.
    apply corn_fast_eq_to_stdlib_eq_a1c_v1.
    exact (IR_inj_Q_as_CR (G IR x n)).
  - apply corn_fast_cauchy_lim_prop2_to_cv_a1c_v1.
    apply corn_ir_G_fast_cauchy_lim_prop2_v1.
Qed.

(* Morphism continuity is already a stdlib theorem (CRmorph_cv). After the
   morphism, CRmorph_rat identifies the mapped rational sequence pointwise
   with O₀'s canonical rational injection. *)
Lemma corn_ir_to_o0_reference_cv_v1 :
  forall x : IR,
    CR_cv O0RealsV1
      (fun n : nat => CR_of_Q O0RealsV1 (G IR x n))
      (corn_ir_to_o0_carrier_v1 x).
Proof.
  intro x.
  unfold corn_ir_to_o0_carrier_v1.
  eapply CR_cv_extens
    with
      (xn := fun n : nat =>
        CRmorph corn_fast_to_o0_morphism_a1c_v1
          (CR_of_Q FastRealsConstructive (G IR x n))).
  - intro n.
    apply CRmorph_rat.
  - apply CRmorph_cv.
    apply corn_ir_G_fast_cv_v1.
Qed.

(* No second hand-built Cauchy modulus: convergence itself supplies the
   Cauchy witness through Rcv_cauchy_mod. *)
Lemma corn_o0_G_seq_is_cauchy_v1 :
  forall x : IR,
    CR_cauchy O0RealsV1
      (fun n : nat => CR_of_Q O0RealsV1 (G IR x n)).
Proof.
  intro x.
  apply
    (Rcv_cauchy_mod
       (fun n : nat => CR_of_Q O0RealsV1 (G IR x n))
       (corn_ir_to_o0_carrier_v1 x)).
  apply corn_ir_to_o0_reference_cv_v1.
Qed.

Definition corn_ir_to_o0_complete_sigma_v1 (x : IR) :=
  CR_complete O0RealsV1
    (fun n : nat => CR_of_Q O0RealsV1 (G IR x n))
    (corn_o0_G_seq_is_cauchy_v1 x).

Definition corn_ir_to_o0_complete_v1 (x : IR) : O0RealV1 :=
  projT1 (corn_ir_to_o0_complete_sigma_v1 x).

Lemma corn_ir_to_o0_complete_cv_v1 :
  forall x : IR,
    CR_cv O0RealsV1
      (fun n : nat => CR_of_Q O0RealsV1 (G IR x n))
      (corn_ir_to_o0_complete_v1 x).
Proof.
  intro x.
  exact (projT2 (corn_ir_to_o0_complete_sigma_v1 x)).
Qed.

(* Both values are limits of the same O₀ sequence; Hausdorff uniqueness closes
   the bridge. *)
Theorem corn_ir_to_o0_completion_equivalence_v1 :
  forall x : IR,
    O0EqV1
      (corn_ir_to_o0_complete_v1 x)
      (corn_ir_to_o0_carrier_v1 x).
Proof.
  intro x.
  unfold O0EqV1.
  apply
    (CR_cv_unique
       (fun n : nat => CR_of_Q O0RealsV1 (G IR x n))
       (corn_ir_to_o0_complete_v1 x)
       (corn_ir_to_o0_carrier_v1 x)).
  - apply corn_ir_to_o0_complete_cv_v1.
  - apply corn_ir_to_o0_reference_cv_v1.
Qed.

(* A1-RAT transfers through completion/reference equality. *)
Theorem corn_ir_to_o0_complete_preserves_rat_v1 :
  forall q : Q,
    O0EqV1
      (corn_ir_to_o0_complete_v1 (inj_Q IR q))
      (CR_of_Q O0RealsV1 q).
Proof.
  intro q.
  unfold O0EqV1.
  eapply CReq_trans.
  - apply corn_ir_to_o0_completion_equivalence_v1.
  - apply corn_ir_to_o0_preserves_rat_v1.
Qed.

(* A1-STRICT transfers via the two order directions contained in CReq. *)
Theorem corn_ir_to_o0_complete_strict_v1 :
  forall x y : IR,
    x [<] y ->
    O0LtV1
      (corn_ir_to_o0_complete_v1 x)
      (corn_ir_to_o0_complete_v1 y).
Proof.
  intros x y Hxy.
  pose proof (corn_ir_to_o0_completion_equivalence_v1 x) as Hx.
  pose proof (corn_ir_to_o0_completion_equivalence_v1 y) as Hy.
  unfold O0EqV1 in Hx, Hy.
  unfold O0LtV1.
  eapply
    (@Coq.Reals.Abstract.ConstructiveReals.CRle_lt_trans O0RealsV1).
  - exact (proj2 Hx).
  - eapply
      (@Coq.Reals.Abstract.ConstructiveReals.CRlt_le_trans O0RealsV1).
    + exact (corn_ir_to_o0_strict_v1 x y Hxy).
    + exact (proj1 Hy).
Qed.
