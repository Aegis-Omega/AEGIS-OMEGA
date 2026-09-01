(**
  AEGIS Ω — primality activation bridge v1

  Production FORMAL_MATH_EVIDENCE_ONLY.

  [PrimePowerArithmeticBridge] exports [prime_nat_v1] as irreducibility:
  [1 < p] together with a divisor classification.  Every analytic identity
  there consumes only [1 < p]; the divisor clause is inert.

  This module activates it.  Irreducibility alone does not yield Euclid's
  lemma - that implication is a theorem about unique factorisation, not an
  unfolding of the definition - so the divisor clause is transported to
  [Znumtheory.prime] through [prime_alt], where [prime_mult] supplies
  Euclid, and carried back to [nat].  Base uniqueness for prime powers then
  follows, and it is the first statement in this corpus whose truth depends
  on primality rather than on [1 < p].

  It does not implement total factorisation, total von Mangoldt evaluation,
  canonical prime-power enumeration, CoRN-to-O0 transport, the Guinand-Weil
  explicit formula, global Weil positivity, or RH.
*)

From Coq Require Import Arith.PeanoNat ZArith Znumtheory Lia.

Require Import PrimePowerArithmeticBridge.

Lemma divides_nat_v1_to_Z :
  forall d n : nat, divides_nat_v1 d n -> (Z.of_nat d | Z.of_nat n).
Proof.
  intros d n [w Hw]. exists (Z.of_nat w).
  rewrite Hw, Nat2Z.inj_mul. ring.
Qed.

Lemma divides_Z_to_nat_v1 :
  forall d n : nat, (Z.of_nat d | Z.of_nat n) -> divides_nat_v1 d n.
Proof.
  intros d n [q Hq].
  destruct (Nat.eq_dec d 0) as [->|Hd].
  - (* d = 0 forces n = 0; the witness is irrelevant *)
    simpl in Hq. assert (n = 0%nat) by (apply Nat2Z.inj; lia).
    subst. exists 0%nat. reflexivity.
  - assert (Hdpos : (0 < Z.of_nat d)%Z) by lia.
    assert (Hn0 : (0 <= Z.of_nat n)%Z) by apply Nat2Z.is_nonneg.
    assert (Hq0 : (0 <= q)%Z) by nia.
    exists (Z.to_nat q).
    apply Nat2Z.inj. rewrite Nat2Z.inj_mul, Z2Nat.id by assumption. lia.
Qed.

Lemma prime_nat_v1_to_Znumtheory :
  forall p : nat, prime_nat_v1 p -> prime (Z.of_nat p).
Proof.
  intros p [Hgt1 Hclass].
  apply prime_alt. split.
  - lia.
  - intros n [Hn1 Hnp] Hdiv.
    assert (Hn0 : (0 <= n)%Z) by lia.
    set (m := Z.to_nat n).
    assert (Hm : Z.of_nat m = n) by (unfold m; apply Z2Nat.id; assumption).
    assert (Hdivnat : divides_nat_v1 m p).
    { apply divides_Z_to_nat_v1. rewrite Hm. exact Hdiv. }
    destruct (Hclass m Hdivnat) as [Hm1 | Hmp].
    + subst m. rewrite Hm1 in Hm. simpl in Hm. lia.
    + subst m. rewrite Hmp in Hm. lia.
Qed.

Theorem prime_nat_v1_euclid :
  forall p a b : nat,
    prime_nat_v1 p ->
    divides_nat_v1 p (a * b) ->
    divides_nat_v1 p a \/ divides_nat_v1 p b.
Proof.
  intros p a b Hp Hdiv.
  assert (Hz : (Z.of_nat p | Z.of_nat a * Z.of_nat b)).
  { rewrite <- Nat2Z.inj_mul. apply divides_nat_v1_to_Z. exact Hdiv. }
  destruct (prime_mult (Z.of_nat p) (prime_nat_v1_to_Znumtheory p Hp)
                       (Z.of_nat a) (Z.of_nat b) Hz) as [H|H];
    [left|right]; apply divides_Z_to_nat_v1; exact H.
Qed.

Lemma prime_nat_v1_not_divides_one :
  forall p : nat, prime_nat_v1 p -> ~ divides_nat_v1 p 1.
Proof.
  intros p [Hgt1 _] [w Hw].
  destruct p as [|p']; [lia|].
  destruct w as [|w']; [rewrite Nat.mul_0_r in Hw; discriminate|].
  nia.
Qed.

Lemma prime_nat_v1_divides_pow :
  forall p q k : nat,
    prime_nat_v1 p -> divides_nat_v1 p (Nat.pow q k) -> divides_nat_v1 p q.
Proof.
  intros p q k Hp. induction k as [|k IH]; intros Hdiv.
  - simpl in Hdiv. exfalso. exact (prime_nat_v1_not_divides_one p Hp Hdiv).
  - simpl in Hdiv.
    destruct (prime_nat_v1_euclid p q (Nat.pow q k) Hp Hdiv) as [H|H].
    + exact H.
    + exact (IH H).
Qed.

Theorem prime_power_base_uniqueness_v1 :
  forall p k p' k' : nat,
    prime_nat_v1 p -> prime_nat_v1 p' ->
    (0 < k)%nat -> (0 < k')%nat ->
    Nat.pow p k = Nat.pow p' k' ->
    p = p' /\ k = k'.
Proof.
  intros p k p' k' Hp Hp' Hk Hk' Heq.
  assert (Hbase : p = p').
  { assert (Hdiv : divides_nat_v1 p (Nat.pow p' k')).
    { rewrite <- Heq. destruct k as [|k0]; [lia|].
      exists (Nat.pow p k0). simpl. reflexivity. }
    destruct (Hp') as [Hgt1' Hclass'].
    destruct (Hp) as [Hgt1 _].
    destruct (Hclass' p (prime_nat_v1_divides_pow p p' k' Hp Hdiv)) as [H1|Hpp].
    - lia.
    - exact Hpp. }
  subst p'.
  split; [reflexivity|].
  destruct Hp as [Hgt1 _].
  apply (Nat.pow_inj_r p k k'); [lia | exact Heq].
Qed.

(* Falsification: the conclusion is FALSE for merely-greater-than-one bases.
   4^3 = 64 = 2^6 with 4 <> 2 and 3 <> 6.  The only hypothesis that blocks
   this instance is primality, so primality is load-bearing here. *)
Example base_uniqueness_fails_without_primality :
  Nat.pow 4 3 = Nat.pow 2 6 /\ (4 <> 2)%nat /\ (3 <> 6)%nat.
Proof. split; [reflexivity|]. split; discriminate. Qed.

Example four_is_not_prime_nat_v1 : ~ prime_nat_v1 4.
Proof.
  intros [_ Hclass].
  destruct (Hclass 2%nat (ex_intro _ 2%nat eq_refl)) as [H|H]; discriminate.
Qed.
