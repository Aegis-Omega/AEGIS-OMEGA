# Conservative Consensus CRDT V1

State-based CRDTs are established prior art. Their standard convergence argument
uses a join-semilattice, monotone local updates, and eventual delivery. AEGIS
does not claim those ideas as new.

This lane applies that machinery to the existing conservative epistemic algebra.

## Order reversal

The parent epistemic order reads:

x <=E y  iff  x is no stronger than y.

Define a safety order by reversal:

x <=S y  iff  y <=E x.

Under <=S, the conservative meet from No-Free Epistemic Gain becomes a join.

The merge therefore:

- intersects exact canonical claims;
- takes minimum authority;
- takes maximum declared loss uncertainty.

## Native local updates

A CRDT-native local update must be inflationary in <=S.

Equivalently, it may only:

- remove or preserve exact claims;
- lower or preserve authority;
- increase or preserve loss uncertainty.

A new claim, authority increase, or uncertainty reduction is not a native CRDT
update. It must use the separate Proof-Carrying Epistemic Promotion protocol.

## Convergence boundary

Commutativity, associativity and idempotence make merge order and duplicates
irrelevant.

Conditional strong convergence claim:

Replicas that eventually receive the same updates/states and apply this merge
reach the same state.

This lane does not establish network fairness, eventual delivery, Byzantine
tolerance, or production correctness.

Prior art:
- CRDT semilattice convergence is established;
- AEGIS application novelty is NOT_ESTABLISHED.

authority_effect = NONE.
