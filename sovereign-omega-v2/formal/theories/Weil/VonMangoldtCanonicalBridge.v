(**
  AEGIS Ω — canonical von Mangoldt binding v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  [PrimePowerArithmeticBridge] binds [log q = k log p] for a SUPPLIED
  certificate [(p, k, q = p^k)].  Nothing there says which [p] belongs to a
  given [q]; the weight [log p] is read off the certificate, not off [q].

  This module builds the prime base as a FUNCTION of [q] alone.  The bespoke
  predicate is made decidable through the standard-library bridge
  ([prime_dec] via [prime_alt]); a bounded search then returns the unique
  prime [p] with [p^k = q] when one exists.  Uniqueness of the base
  ([PrimalityStdlibBridge]) is what makes the search's answer canonical rather
  than merely a witness.  The von Mangoldt weight [Lambda q] is then [Log p]
  for that [p] and [0] otherwise, and for every certified prime power it
  agrees with the certificate's [log p].

  It does not implement total factorisation of arbitrary [n], canonical
  prime-power ENUMERATION, CoRN-to-O0 transport, the Guinand-Weil explicit
  formula, global Weil positivity, or RH.
*)

From Coq Require Import Arith.PeanoNat ZArith Znumtheory Lia.

Require Import CoRN.reals.NRootIR.
Require Import CoRN.transc.Exponential.
Require Import CoRN.ftc.MoreFunctions.
Require Import PrimePowerWeightBridge.
Require Import PrimePowerArithmeticBridge.
Require Import PrimalityStdlibBridge.

(* A2b-1b: the reverse direction, so the bespoke predicate is DECIDABLE *)
Lemma Znumtheory_to_prime_nat_v1 :
  forall p : nat, prime (Z.of_nat p) -> prime_nat_v1 p.
Proof.
  intros p Hp. apply prime_alt in Hp. destruct Hp as [Hgt1 Hnodiv].
  split; [lia|].
  intros d [w Hw].
  assert (Hp0 : p <> 0%nat) by lia.
  assert (Hd0 : d <> 0%nat) by (intro Hd; rewrite Hd in Hw; simpl in Hw; lia).
  assert (Hdle : (d <= p)%nat) by (destruct w; nia).
  destruct (Nat.eq_dec d 1) as [->|Hd1]; [left; reflexivity|].
  destruct (Nat.eq_dec d p) as [->|Hdp]; [right; reflexivity|].
  exfalso. apply (Hnodiv (Z.of_nat d)); [lia|].
  apply divides_nat_v1_to_Z. exists w. exact Hw.
Qed.

Definition prime_nat_v1_dec (p : nat) : {prime_nat_v1 p} + {~ prime_nat_v1 p} :=
  match prime_dec (Z.of_nat p) with
  | left H => left (Znumtheory_to_prime_nat_v1 p H)
  | right H => right (fun Hp => H (prime_nat_v1_to_Znumtheory p Hp))
  end.

(* ---- bounded exponent search: is q = b^k for some 1 <= k <= fuel ? ---- *)
Fixpoint is_power_fuel (b q fuel : nat) : bool :=
  match fuel with
  | O => false
  | S f => if Nat.eq_dec (Nat.pow b fuel) q then true else is_power_fuel b q f
  end.

Lemma is_power_fuel_sound :
  forall b q fuel, is_power_fuel b q fuel = true ->
    exists k, (0 < k <= fuel)%nat /\ Nat.pow b k = q.
Proof.
  intros b q fuel. induction fuel as [|f IH]; intros H.
  - discriminate.
  - cbn [is_power_fuel] in H.
    destruct (Nat.eq_dec (Nat.pow b (S f)) q) as [E|E].
    + exists (S f). split; [lia|exact E].
    + destruct (IH H) as [k [Hk Hbk]]. exists k. split; [lia|exact Hbk].
Qed.

Lemma is_power_fuel_complete :
  forall b q fuel k, (0 < k <= fuel)%nat -> Nat.pow b k = q ->
    is_power_fuel b q fuel = true.
Proof.
  intros b q fuel. induction fuel as [|f IH]; intros k Hk Hbk.
  - lia.
  - cbn [is_power_fuel].
    destruct (Nat.eq_dec (Nat.pow b (S f)) q) as [E|E]; [reflexivity|].
    destruct (Nat.eq_dec k (S f)) as [->|Hne]; [contradiction|].
    apply (IH k); [lia|exact Hbk].
Qed.

(* for b >= 2 the exponent is bounded by q itself: k < 2^k <= b^k = q *)
Lemma pow_ge_1 :
  forall b k, (1 <= b)%nat -> (1 <= Nat.pow b k)%nat.
Proof. intros b k Hb. induction k as [|k IH]; simpl; nia. Qed.

Lemma pow_exponent_bound :
  forall b k, (2 <= b)%nat -> (k < Nat.pow b k)%nat.
Proof.
  intros b k Hb. induction k as [|k IH]; simpl; [lia|].
  pose proof (pow_ge_1 b k ltac:(lia)). nia.
Qed.

Definition is_power_of (b q : nat) : bool := is_power_fuel b q q.

Lemma is_power_of_spec :
  forall b q, (2 <= b)%nat ->
    (is_power_of b q = true <-> exists k, (0 < k)%nat /\ Nat.pow b k = q).
Proof.
  intros b q Hb. unfold is_power_of. split.
  - intros H. destruct (is_power_fuel_sound _ _ _ H) as [k [Hk Hbk]]. exists k. split; [lia|exact Hbk].
  - intros [k [Hk Hbk]]. apply (is_power_fuel_complete b q q k); [|exact Hbk].
    pose proof (pow_exponent_bound b k Hb). lia.
Qed.

(* ---- bounded base search: largest b <= fuel that is prime and a base of q ---- *)
Fixpoint find_base_fuel (q fuel : nat) : option (sig prime_nat_v1) :=
  match fuel with
  | O => None
  | S f =>
      match prime_nat_v1_dec fuel with
      | left Hp =>
          if is_power_of fuel q then Some (exist _ fuel Hp) else find_base_fuel q f
      | right _ => find_base_fuel q f
      end
  end.

Lemma find_base_fuel_sound :
  forall q fuel p Hp, find_base_fuel q fuel = Some (exist _ p Hp) ->
    is_power_of p q = true /\ (p <= fuel)%nat.
Proof.
  intros q fuel. induction fuel as [|f IH]; intros p Hp H.
  - discriminate.
  - cbn [find_base_fuel] in H.
    destruct (prime_nat_v1_dec (S f)) as [Hs|Hs].
    + destruct (is_power_of (S f) q) eqn:E.
      * injection H as H. subst p. split; [exact E | lia].
      * destruct (IH p Hp H) as [B C]. split; [exact B | lia].
    + destruct (IH p Hp H) as [B C]. split; [exact B | lia].
Qed.

Lemma find_base_fuel_complete :
  forall q fuel p, prime_nat_v1 p -> is_power_of p q = true -> (p <= fuel)%nat ->
    find_base_fuel q fuel <> None.
Proof.
  intros q fuel. induction fuel as [|f IH]; intros p Hp Hpow Hle.
  - destruct Hp as [H _]. lia.
  - cbn [find_base_fuel].
    destruct (prime_nat_v1_dec (S f)) as [Hs|Hs].
    + destruct (is_power_of (S f) q) eqn:E; [discriminate|].
      destruct (Nat.eq_dec p (S f)) as [->|Hne]; [congruence|].
      apply (IH p); [assumption|assumption|lia].
    + destruct (Nat.eq_dec p (S f)) as [->|Hne]; [contradiction|].
      apply (IH p); [assumption|assumption|lia].
Qed.

Definition prime_power_base_sig_v1 (q : nat) : option (sig prime_nat_v1) :=
  find_base_fuel q q.

Definition prime_power_base_v1 (q : nat) : option nat :=
  option_map (@proj1_sig nat prime_nat_v1) (prime_power_base_sig_v1 q).

(* ---- canonical layer: the prime base is a function of q alone ---- *)
Theorem prime_power_base_v1_sound :
  forall q p, prime_power_base_v1 q = Some p ->
    prime_nat_v1 p /\ exists k, (0 < k)%nat /\ Nat.pow p k = q.
Proof.
  intros q p H. unfold prime_power_base_v1, prime_power_base_sig_v1 in H.
  destruct (find_base_fuel q q) as [[p' Hp']|] eqn:E; [|discriminate H].
  simpl in H. injection H as H. subst p'.
  destruct (find_base_fuel_sound _ _ _ _ E) as [Hpow _].
  split; [exact Hp'|].
  apply is_power_of_spec in Hpow; [exact Hpow | destruct Hp'; lia].
Qed.

Lemma pow_ge_base :
  forall p k, (1 <= p)%nat -> (0 < k)%nat -> (p <= Nat.pow p k)%nat.
Proof.
  intros p k Hp Hk. destruct k as [|k']; [lia|]. simpl.
  pose proof (pow_ge_1 p k' Hp). nia.
Qed.

Theorem prime_power_base_v1_complete :
  forall p k, prime_nat_v1 p -> (0 < k)%nat ->
    prime_power_base_v1 (Nat.pow p k) = Some p.
Proof.
  intros p k Hp Hk.
  assert (Hgt : (2 <= p)%nat) by (destruct Hp; lia).
  assert (Hpow : is_power_of p (Nat.pow p k) = true).
  { apply is_power_of_spec; [lia|]. exists k. split; [exact Hk|reflexivity]. }
  assert (Hle : (p <= Nat.pow p k)%nat) by (apply pow_ge_base; lia).
  unfold prime_power_base_v1, prime_power_base_sig_v1.
  destruct (find_base_fuel (Nat.pow p k) (Nat.pow p k)) as [[p' Hp']|] eqn:E.
  - destruct (find_base_fuel_sound _ _ _ _ E) as [Hpow' _].
    apply is_power_of_spec in Hpow'; [|destruct Hp'; lia].
    destruct Hpow' as [k' [Hk' Hq']].
    destruct (prime_power_base_uniqueness_v1 p' k' p k Hp' Hp Hk' Hk Hq') as [-> _].
    reflexivity.
  - exfalso. exact (find_base_fuel_complete _ _ p Hp Hpow Hle E).
Qed.

(* the canonical base of a certified prime power is the certified base:
   this is the statement a certificate-free Lambda can be built on *)
Corollary prime_power_base_v1_canonical :
  forall p k p' k', prime_nat_v1 p -> prime_nat_v1 p' ->
    (0 < k)%nat -> (0 < k')%nat -> Nat.pow p k = Nat.pow p' k' ->
    prime_power_base_v1 (Nat.pow p k) = Some p'.
Proof.
  intros p k p' k' Hp Hp' Hk Hk' Heq. rewrite Heq. apply prime_power_base_v1_complete; assumption.
Qed.

(* ---- falsifiers ---- *)
Lemma two_is_prime_nat_v1 : prime_nat_v1 2.
Proof.
  split; [lia|]. intros d [w Hw].
  assert (d <> 0%nat) by (intro Hd; rewrite Hd in Hw; simpl in Hw; lia).
  assert (w <> 0%nat) by (intro Hw0; rewrite Hw0 in Hw; rewrite Nat.mul_0_r in Hw; lia).
  destruct d as [|[|[|d']]]; [lia|left; reflexivity|right; reflexivity|nia].
Qed.

(* 64 = 2^6: the canonical base is 2 ... *)
Lemma canonical_base_of_64_is_2 : prime_power_base_v1 64 = Some 2%nat.
Proof. exact (prime_power_base_v1_complete 2 6 two_is_prime_nat_v1 ltac:(lia)). Qed.

(* ... and NOT 4, although 4^3 = 64: primality is what selects the base. *)
Lemma canonical_base_of_64_is_not_4 : prime_power_base_v1 64 <> Some 4%nat.
Proof.
  intro H. destruct (prime_power_base_v1_sound _ _ H) as [H4 _].
  exact (four_is_not_prime_nat_v1 H4).
Qed.

(* ---- the IR-valued weight, built from q alone ---- *)
Lemma prime_nat_v1_nring_positive :
  forall p : nat, prime_nat_v1 p -> [0] [<] (nring p : IR).
Proof.
  intros p [Hgt1 _]. apply nring_pos. lia.
Qed.

Definition von_mangoldt_v1 (q : nat) : IR :=
  match prime_power_base_sig_v1 q with
  | Some (exist _ p Hp) => Log (nring p) (prime_nat_v1_nring_positive p Hp)
  | None => [0]
  end.

(* certificate-free Lambda agrees with the certificate's log p *)
Theorem von_mangoldt_v1_certified_binding :
  forall certificate : prime_power_certificate_v1,
    von_mangoldt_v1 (certified_prime_power_value_v1 certificate)
    [=] certified_prime_log_v1 certificate.
Proof.
  intros c.
  pose proof (certified_prime_base_is_prime_v1 c) as Hp.
  pose proof (certified_prime_exponent_positive_v1 c) as Hk.
  pose proof (certified_prime_power_nat_identity_v1 c) as Hq.
  assert (Hcanon : prime_power_base_v1 (certified_prime_power_value_v1 c)
                   = Some (certified_prime_base_v1 c)).
  { rewrite Hq. apply prime_power_base_v1_complete; assumption. }
  unfold von_mangoldt_v1, certified_prime_log_v1, certified_prime_base_ir_v1.
  unfold prime_power_base_v1 in Hcanon.
  destruct (prime_power_base_sig_v1 (certified_prime_power_value_v1 c))
    as [[p Hp']|] eqn:E; [|discriminate Hcanon].
  simpl in Hcanon. injection Hcanon as Hcanon. subst p.
  apply Log_wd. algebra.
Qed.
