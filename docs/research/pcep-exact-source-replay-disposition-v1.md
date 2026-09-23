# PCEP Exact-Source Replay Disposition V1

Scientific head:

`31b9d6ea43ad84173653d54ad9387be8bfa469bd`

Replay head:

`c51f605eb19f20d73c90735e6ef2e4df3ca7f703`

The replay is a clean fast-forward of the scientific head and changes only
provider-neutral transport files.

## Hosted execution

Python promotion/anti-splicing suite: **11/11 PASS**.

Lean:
- version 4.33.1
- Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`
- parent NFEG source SHA-256:
  `c46bf6cf66fa8bc1890faec4c25a5e3b744a0ee2f75bafe61ee0e89ab7f4f280`
- child PCEP source SHA-256:
  `78626e14eaf6baff6fc680b9d6babad572c33166422e96cc516497a39e3ad0fb`
- replay stage: `VERIFIED_EXACT_SOURCE`
- `sorryAx`: absent

Kernel-verified child theorems establish that positive gain in any of the
declared dimensions causes a candidate to cease being a common lower bound:

- exact claim gain;
- authority gain;
- loss-uncertainty reduction;
- disjunction of those positive gains.

Axiom audit reports `propext`, `Classical.choice`, and `Quot.sound`.

## Separate Python result

The proof-carrying promotion receipt mechanics were executed independently and
passed 11 tests covering exact obligation coverage, missing receipts, duplicate
obligations, untrusted roots, state splicing, extra receipts, and the
three-dimension promotion case.

Even complete receipt coverage yields only:

`ELIGIBLE_FOR_SEPARATE_PROMOTION_ONLY`

It never mutates claims or authority.

`automatic_promotion = false`
`application_novelty = NOT_ESTABLISHED`
`authority_effect = NONE`
