(* AEGIS Omega: conditional authority algebra, not a cryptographic verifier.
   Section hypotheses are generalized theorem parameters, not runtime checks.
   No physical experiment, RH claim, or production admission is implied. *)
Require Import Coq.Lists.List.
Import ListNotations.

Section AuthorityPoset.
  Variable A : Type.
  Variable le : A -> A -> Prop.
  Variable meet : A -> A -> A.
  Variable top : A.
  Local Infix "<=" := le.
  Local Infix "⊓" := meet (at level 40, left associativity).

  Hypothesis le_refl : forall x, x <= x.
  Hypothesis le_trans : forall x y z, x <= y -> y <= z -> x <= z.
  Hypothesis le_antisym : forall x y, x <= y -> y <= x -> x = y.
  Hypothesis meet_lb1 : forall x y, x ⊓ y <= x.
  Hypothesis meet_lb2 : forall x y, x ⊓ y <= y.
  Hypothesis meet_glb : forall x y z, z <= x -> z <= y -> z <= (x ⊓ y).
  Hypothesis top_max : forall x, x <= top.

  Fixpoint fold_meet (l : list A) : A :=
    match l with
    | [] => top
    | h :: t => h ⊓ fold_meet t
    end.

  Lemma fold_meet_in_le : forall (l : list A) (x : A),
    In x l -> fold_meet l <= x.
  Proof.
    induction l as [|h t IH]; intros x Hin.
    - destruct Hin.
    - destruct Hin as [Hhead | Htail].
      + subst h. simpl. apply meet_lb1.
      + simpl. apply le_trans with (y := fold_meet t).
        * apply meet_lb2.
        * apply IH. exact Htail.
  Qed.

  Definition compute_node_authority (g_v q_v : A) (edges : list A) : A :=
    (g_v ⊓ q_v) ⊓ fold_meet edges.

  Theorem authority_non_escalation : forall (g_v q_v e_i : A) (edges : list A),
    In e_i edges -> compute_node_authority g_v q_v edges <= e_i.
  Proof.
    intros g_v q_v e_i edges Hin.
    unfold compute_node_authority.
    apply le_trans with (y := fold_meet edges).
    - apply meet_lb2.
    - apply fold_meet_in_le. exact Hin.
  Qed.

  Theorem authority_le_grant : forall (g q : A) (edges : list A),
    compute_node_authority g q edges <= g.
  Proof.
    intros g q edges. unfold compute_node_authority.
    apply le_trans with (y := g ⊓ q); apply meet_lb1.
  Qed.

  Theorem authority_le_request : forall (g q : A) (edges : list A),
    compute_node_authority g q edges <= q.
  Proof.
    intros g q edges. unfold compute_node_authority.
    apply le_trans with (y := g ⊓ q).
    - apply meet_lb1.
    - apply meet_lb2.
  Qed.

  Variable bot : A.
  Hypothesis bot_min : forall x, bot <= x.

  Theorem fail_closed_propagation : forall (g q : A) (edges : list A),
    In bot edges -> compute_node_authority g q edges <= bot.
  Proof.
    intros g q edges Hin. apply authority_non_escalation. exact Hin.
  Qed.

  Theorem fail_closed_equality : forall (g q : A) (edges : list A),
    In bot edges -> compute_node_authority g q edges = bot.
  Proof.
    intros g q edges Hin. apply le_antisym.
    - apply fail_closed_propagation. exact Hin.
    - apply bot_min.
  Qed.

  Section RequiredPremises.
    Variable Id : Type.
    Definition resolve_authority (observation : option A) : A :=
      match observation with Some value => value | None => bot end.

    (* required is supplied by the trusted policy, not selected by a candidate.
       Root grant issuance is separate; an empty derived request is denied. *)
    Definition compute_required_authority
        (g q : A) (required : list Id) (lookup : Id -> option A) : A :=
      match required with
      | [] => bot
      | _ => compute_node_authority g q
          (map (fun id => resolve_authority (lookup id)) required)
      end.

    Theorem empty_required_denies : forall (g q : A) (lookup : Id -> option A),
      compute_required_authority g q [] lookup = bot.
    Proof. reflexivity. Qed.

    Theorem missing_required_denies : forall (g q : A) (required : list Id)
        (lookup : Id -> option A) (id : Id),
      In id required -> lookup id = None ->
      compute_required_authority g q required lookup = bot.
    Proof.
      intros g q required lookup id Hin Hmissing.
      destruct required as [|h t].
      - destruct Hin.
      - change (compute_node_authority g q
          (map (fun key => resolve_authority (lookup key)) (h :: t)) = bot).
        apply fail_closed_equality.
        assert (Hresolved : resolve_authority (lookup id) = bot).
        { rewrite Hmissing. reflexivity. }
        rewrite <- Hresolved.
        exact (@in_map Id A (fun key => resolve_authority (lookup key)) (h :: t) id Hin).
    Qed.
  End RequiredPremises.

  Section RequiredGraph.
    Variable Node : Type.
    Variable grant requested authority : Node -> A.
    Variable required : Node -> list (Node * A).
    (* This equation is a premise. It does not authenticate observations or
       prove that a caller has enumerated all required dependencies. *)
    Hypothesis node_equation : forall v,
      authority v = compute_node_authority (grant v) (requested v)
        (map (fun pc => meet (authority (fst pc)) (snd pc)) (required v)).

    Definition required_parent (u v : Node) : Prop :=
      exists cap, In (u, cap) (required v).

    Theorem required_parent_non_escalation : forall (u v : Node),
      required_parent u v -> authority v <= authority u.
    Proof.
      intros u v [cap Hin]. rewrite (node_equation v).
      apply le_trans with (y := meet (authority u) cap).
      - apply authority_non_escalation.
        exact (@in_map (Node * A) A
          (fun pc => meet (authority (fst pc)) (snd pc)) (required v) (u, cap) Hin).
      - apply meet_lb1.
    Qed.

    Inductive required_path : Node -> Node -> Prop :=
    | path_one : forall u v, required_parent u v -> required_path u v
    | path_cons : forall u v w,
        required_parent u v -> required_path v w -> required_path u w.

    Theorem required_ancestor_non_escalation : forall (u v : Node),
      required_path u v -> authority v <= authority u.
    Proof.
      intros u v Hpath.
      induction Hpath as [u v Huv | u v w Huv Hvw IH].
      - apply required_parent_non_escalation. exact Huv.
      - apply le_trans with (y := authority v).
        + exact IH.
        + apply required_parent_non_escalation. exact Huv.
    Qed.
  End RequiredGraph.
End AuthorityPoset.

(* Disjoint tags only. Semantic validity of each edge remains an external duty. *)
Inductive EvidenceKind : Type := Provenance | Mathematical | Physical.
Theorem provenance_not_math : Provenance <> Mathematical.
Proof. discriminate. Qed.
Theorem math_not_physical : Mathematical <> Physical.
Proof. discriminate. Qed.
Theorem provenance_not_physical : Provenance <> Physical.
Proof. discriminate. Qed.
