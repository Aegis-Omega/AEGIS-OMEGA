# Attestation semantics: closure is not content

Audit of the Coq attestation bundle for cycle
`22026c355df352ae24026a9683156545d8ac5335`
(`cycle-receipt.json` branch `integration/rh-weil-evidence-v1`, authority
`LOCAL_EXACT_HEAD_REPLAY_NOT_REMOTE_CI`).

Re-derive everything below with:

```
python3 research/rh/audit_attestation_semantics.py \
  --assumptions <bundle>/coq-attestation/assumptions \
  --source-root sovereign-omega-v2/formal/theories \
  --obligation FiniteLowerBoundV1 \
  --strict
```

## The headline number, and what it does not mean

| | |
|---|---|
| receipts | 51 |
| `Closed under the global context` | 48 |
| substantive | 38 |
| **tautologies** | **5** |
| source not locatable in any of 431 branches | 8 |

48 of 51 receipts are genuinely axiom-free — no classical logic, nothing
`Admitted`. That is a true statement about the *proofs*.

It is not a statement about the *theorems*. `Print Assumptions` answers "does
this proof rest on axioms?", never "does this theorem assert anything?". Five
of those closures are the identity function:

```coq
Theorem global_weil_positivity_v1_pointwise :
  forall QW, GlobalWeilPositivityV1 QW -> forall f, O0LeV1 O0ZeroV1 (QW f).
Proof. intros QW H f. exact (H f). Qed.
```

and `GlobalWeilPositivityV1 QW` is *defined* as `forall f, O0LeV1 O0ZeroV1 (QW f)`.
The theorem is `(forall f. P f) -> (forall f. P f)`. It is closed under the
global context because it says nothing.

The five, as the tool reports them:

- `AnalyticDefinitions.global_weil_positivity_v1_pointwise`
- `AnalyticDefinitions.o0_real_order_refl_v1`
- `Globalization.finite_lower_bound_v1_specialize`
- `O0ProductionConstructiveProbe.o0_production_real_order_reflexive`
- `O0TrustProbeConstructive.o0_trust_probe_constructive_order_refl`

The names read like conclusions. The receipts are green. Neither fact carries
mathematical weight, and nothing in a `Print Assumptions` log distinguishes
them from the 38 that do.

## The one substantive globalization theorem, and its real hypothesis

`globalization_ready_implies_global_weil_positivity_v1` is **not** a tautology:
113 lines of genuine constructive epsilon/delta over `ConstructiveReals`, using
`CR_Q_dense` and `CR_of_Q_lt`. It is correct.

What it proves is

```
pointwise_converges_v1 QR QW  /\  vanishing_nonnegative_error_v1 eps  /\  FiniteLowerBoundV1 QR eps
  ->  GlobalWeilPositivityV1 QW
```

and the third hypothesis is

```coq
Definition FiniteLowerBoundV1 (QR) (eps) : Prop :=
  forall (n : nat) (f : AdmissibleTestFunctionV1),
    O0LeV1 (O0OppV1 (eps n)) (QR n f).
```

`-eps n <= QR n f` for every `n` and every admissible `f` — that is finite Weil
positivity itself. The theorem is a correct limit-passing step from finite
positivity to global positivity; the difficulty is entirely in the hypothesis,
which no receipt supplies. The tool reports `FiniteLowerBoundV1: NOT DISCHARGED`.

`Globalization.v` states this in its own header, ahead of this audit:

> This module proves the abstract finite-to-limit order step on the constructive
> O0 real carrier. It does not identify QW with the classical Weil form and it
> does not prove the Weil criterion or RH.

`QuadraticFormV1` and `AdmissibleTestFunctionV1` are abstract carriers. Nothing
ties them to `riemannZeta`.

## Why the Gram positivity does not close the gap either

`ArchTailOrder.weighted_gram_energy_nonnegative` is substantive and correct:
`sum_k weight k * <feature k, x>^2 >= 0` whenever every `weight k >= 0`. It is
the PSD lemma one would use if the finite form had that shape.

It is never instantiated. Searching every `.lean` and `.v` blob across 431
branches (154 distinct blobs, 80 Lean and 74 Coq):

- `weighted_gram_energy` appears only in `ArchTailOrder.v`
- `FiniteLowerBoundV1` appears only in `Globalization.v`
- **no** blob combines a Gram/PSD term with `vonMangoldt` or `zeta`

The PSD lemma and the globalization implication are never connected, and neither
reaches `riemannZeta`.

`FiniteBridge.v` does not supply the bound either. Its tail theorems are three
rationals and `lra`:

```coq
Theorem bounded_positive_tail_certifies_negative :
  forall (qT delta B : Q),
    0 <= delta -> delta <= B -> qT + B < 0 -> qT + delta < 0.
Proof. intros qT delta B Hdelta Hbound Hnegative. lra. Qed.
```

In `bounded_positive_tail_preserves_nonnegative` the hypothesis `delta <= B` is
not even used, so `B` is a dead parameter. And the module's own third theorem,
`gray_zone_can_change_sign`, exhibits `qT = -B/2`, `delta- = 0`, `delta+ = B`:
within one tail bound the sign goes either way. That is the author being
accurate, and it is the sharpest statement in the file.

## Q -> R costs the closure

The `FiniteBridge.v` carried in the pushed corpus imports only `QArith`,
`Psatz`, `Ring`, `Field` — hence axiom-free. A later revision compiled in CI
reports

```
ClassicalDedekindReals.sig_not_dec
ClassicalDedekindReals.sig_forall_dec
FunctionalExtensionality.functional_extensionality_dep
```

Those reach the proof only through `Coq.Reals`. Moving a module from `Q` to `R`
forfeits "Closed under the global context", for that module and for everything
downstream of it. Any closure tally is therefore specific to a revision, and
the 48/51 above is stale the moment such a move lands.

## Standing conclusion

A great deal is proved here, constructively and without axioms — lattice
convergence, lock irreversibility, Gram energy, divided-difference symmetries,
the prime/pole dictionary, and a correct limit-passing argument. None of it
closes, and the receipts that sound like closures are the tautologies.

The remaining gap is one named proposition: `FiniteLowerBoundV1` for the true
Weil form, together with the identification of `QW` with it. It is not a lemma
on the way to RH. Weil's criterion is an equivalence, so that proposition **is**
RH, which is why every route through this corpus arrives at the same wall.

This audit proves no new mathematics.
