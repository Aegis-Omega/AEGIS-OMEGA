# Conservative Consensus CRDT Exact-Source Replay V1

Scientific head:
`4c25c8d7ebe4d55b2a1dc5c93196ee6498ba0210`

Replay head:
`cb16c42a7ec39a96544736daa17cb2f9ac0607b0`

The replay is a clean fast-forward and changes only transport files.

## Execution

Python CRDT suite: **9/9 PASS**.

Pinned formal environment:
- Lean 4.33.1
- Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`

Exact SHA-256:
- NFEG: `c46bf6cf66fa8bc1890faec4c25a5e3b744a0ee2f75bafe61ee0e89ab7f4f280`
- MACC: `64d026d81063ca7deb3be3b01f320ebe2ba967ebca6d3579f7ad7c2bbbd8ba1a`
- CRDT: `7e18097e36a1a525c8afbae63f8f9236ad8dbea3890b9e1ccf03893fe61e896c`

Replay stage: `VERIFIED_EXACT_SOURCE`.

No `sorryAx`.

Kernel-verified CRDT results:

- conservative merge is an upper bound of each input in the reversed safety order;
- it is the least such upper bound;
- merge is commutative;
- associative;
- idempotent;
- a safety-order inflationary local update can only remove/preserve exact claims,
  lower/preserve authority, and raise/preserve declared loss uncertainty.

The axiom audit reports `propext`, `Classical.choice`, and `Quot.sound`.

## Boundary

This proves the algebraic state-merge properties in the stated model.

It does **not** prove network eventual delivery, scheduler fairness, Byzantine
tolerance, causal delivery, or production deployment correctness.

Those remain separate system obligations.

`application_novelty = NOT_ESTABLISHED`
`authority_effect = NONE`
