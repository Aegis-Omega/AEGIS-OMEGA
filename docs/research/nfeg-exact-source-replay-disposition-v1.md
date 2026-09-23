# NFEG Exact-Source Replay Disposition V1

Scientific head:

`acdff800a64f1322221447c62d5b711e6299d5a5`

Provider-neutral replay head:

`c63d608bf1ce6ae870b698d5e46ce6d86ec34376`

The replay head is a clean fast-forward of the scientific head and changes only
three transport files. No scientific source differs.

## Execution

- Python finite-model suite: **10/10 PASS**
- Lean: **4.33.1**
- Mathlib: `0df444a360eaa60ab8c11dca51a86af692955474`
- exact theorem-source SHA-256:
  `c46bf6cf66fa8bc1890faec4c25a5e3b744a0ee2f75bafe61ee0e89ab7f4f280`
- stage: `VERIFIED_EXACT_SOURCE`
- `sorryAx`: absent

Kernel-verified bounded results include:

- `le_meet_iff`
- `no_free_epistemic_gain`
- meet associativity
- meet commutativity
- meet idempotence

The explicit axiom audit reports `propext`, `Classical.choice`, and
`Quot.sound`; this lane does not describe those theorems as axiom-free.

## Meaning

For the stated exact-claim/authority/loss-uncertainty model, the conservative
state

`(claim intersection, min authority, max uncertainty)`

is the greatest lower bound in the declared epistemic-strength order.

This establishes the **model theorem**. It does not establish mathematical
novelty, semantic equivalence between differently encoded claims, or truth of
the underlying claims.

`authority_effect = NONE`
