# Multi-Agent Conservative Consensus Exact-Source Replay V1

Scientific head:
`9649b1eada1ffff8740b8cf6c286f9ec961fc083`

Replay head:
`036548aafd7853b4e5e1efb37e3fa6b43c3cd63d`

The replay is a clean fast-forward that changes only transport files.

## Execution

Python multi-agent finite-model suite: **6/6 PASS**.

Lean:
- version 4.33.1
- Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`
- parent NFEG SHA-256:
  `c46bf6cf66fa8bc1890faec4c25a5e3b744a0ee2f75bafe61ee0e89ab7f4f280`
- child MACC SHA-256:
  `64d026d81063ca7deb3be3b01f320ebe2ba967ebca6d3579f7ad7c2bbbd8ba1a`
- replay stage: `VERIFIED_EXACT_SOURCE`
- `sorryAx`: absent

Kernel-verified bounded theorems:

- consensus is below the initial input;
- consensus is below every member of the list;
- every common lower bound is below consensus.

Therefore the non-empty fold is the greatest lower bound of the input states in
the stated exact-claim / authority / loss-uncertainty order.

The axiom audit reports `propext`, `Classical.choice`, and `Quot.sound`.

This does not establish semantic equivalence between different claim IDs,
network consensus, Byzantine tolerance, or mathematical novelty.

`authority_effect = NONE`
