Require Import Coq.Lists.List Coq.Bool.Bool Authority_Meet.
Import ListNotations.

(* These checks deliberately fail until the missing contracts are provided. *)
Check authority_le_grant.
Check authority_le_request.
Check fail_closed_equality.
Check missing_required_denies.
Check empty_required_denies.
Check required_parent_non_escalation.
Check required_ancestor_non_escalation.
Check provenance_not_math.
Check math_not_physical.
Check provenance_not_physical.

Example supplied_bottom_blocks :
  compute_node_authority bool andb true true true [true; false; true] = false.
Proof. reflexivity. Qed.

Example raw_empty_fold_is_not_a_missingness_gate :
  compute_node_authority bool andb true true true [] = true.
Proof. reflexivity. Qed.

Example safe_derived_empty_denies :
  compute_required_authority bool andb true false nat true true [] (fun _ => Some true) = false.
Proof. reflexivity. Qed.

Example missing_required_identifier_denies :
  compute_required_authority bool andb true false nat true true [0;1]
    (fun i => match i with 0 => Some true | _ => None end) = false.
Proof. reflexivity. Qed.

Example granted_complete_candidate :
  compute_required_authority bool andb true false nat true true [0;1] (fun _ => Some true) = true.
Proof. reflexivity. Qed.

Example grant_false_denies :
  compute_required_authority bool andb true false nat false true [0] (fun _ => Some true) = false.
Proof. reflexivity. Qed.

Example unrelated_missing_identifier_is_irrelevant :
  compute_required_authority bool andb true false nat true true [0]
    (fun i => match i with 0 => Some true | _ => None end) = true.
Proof. reflexivity. Qed.

(* Fail rejects the attempted proof term, rather than leaving an admitted goal. *)
Fail Definition cannot_turn_provenance_into_math : Provenance = Mathematical := eq_refl.
Fail Definition cannot_drop_required_bottom :
  compute_node_authority bool andb true true true [false] = true := eq_refl.
