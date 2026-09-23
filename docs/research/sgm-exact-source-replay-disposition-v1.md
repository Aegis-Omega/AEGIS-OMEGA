# SGM Exact-Source Replay Disposition V1

Scientific head:

`aca2ee7dbf063de30d3ceb6b366f2dde37abf21f`

Provider-neutral replay head:

`5c736a30b51c941147de46ea3ce3df6105c67f41`

Common merge base:

`2407099500aea8877fdf3d5e87bb81dc7e5995cf`

## Source equivalence

The two heads have diverged Git histories, but the only scientific source modified
after their common merge base is:

`EpistemicAuthorityConservationV1.lean`

It has the same Git blob on both heads:

`f281ed559e35075a609a1231218902f0e292fa62`

and exact content comparison is equal.

All other verified scientific files are inherited unchanged from the same merge
base. The replay-only branch differs additionally by transport/trigger files.

Therefore the provider-neutral theorem execution is applicable to the current
scientific theorem bytes even though the transport branch is not an ancestor of
the current scientific head.

## Hosted Python execution

Six suites executed:

- authority conservation: 5/5
- semantic accounting: 8/8
- conservation kernel: 6/6
- conservation-qualified SGM: 9/9
- prior-art/spec guard: 4/4
- conservative epistemic semilattice: 5/5

Total: **37/37 PASS**.

## Lean execution

Pinned environment:

- Lean 4.33.1
- Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`

Three exact-source modules compiled successfully:

- `EpistemicAuthorityConservationV1`
- `EpistemicAccountingV1`
- `ConservativeEpistemicSemilatticeV1`

The explicit axiom audit contains no `sorryAx`.

Theorems are not described as axiom-free: some use `propext`, and the Finset
cardinality theorem additionally reports `Classical.choice` and `Quot.sound`.

## Current strongest bounded claims

1. Authority-min composition is kernel-verified for the stated Nat model.
2. NONE/zero authority is absorbing in the stated chain model.
3. Loss-uncertainty max bounds and finite disjoint-partition accounting theorems
   are kernel-verified in the stated models.
4. The min-authority/max-uncertainty merge is kernel-verified as commutative,
   associative and idempotent.
5. The SGM Python gate mechanics passed the exact provider-neutral replay.

These claims do **not** establish:
- mathematical novelty of the min/max lattice;
- global optimality of self-rewrites;
- autonomous rewrite authority;
- truth of external-world claims represented by the lattice.

`authority_effect = NONE`
