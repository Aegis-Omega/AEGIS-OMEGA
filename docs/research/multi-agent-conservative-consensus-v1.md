# Multi-Agent Conservative Consensus V1

This lane lifts No-Free Epistemic Gain from two inputs to a non-empty collection
of agent states.

Each exact state is:

E = (claim_set, authority, loss_uncertainty_bps).

Consensus is the fold of the parent conservative meet:

- claim intersection;
- minimum authority;
- maximum loss uncertainty.

The formal target is not merely order-insensitive implementation. It is the
greatest-lower-bound property:

1. consensus is below every input in the conservative epistemic order;
2. every other common lower bound is below consensus.

Therefore consensus is the strongest state multiple agents can accept without
introducing a new claim, recovering authority, or reducing loss uncertainty.

Because the binary meet is commutative, associative and idempotent, duplicate
agents and merge order do not increase consensus strength.

Any stronger aggregate must leave the conservative-consensus lane and enter the
separate proof-carrying promotion protocol.

Exact canonical claim identity is required. Semantic equivalence requires MHP
proof receipts.

Mathematical novelty is not claimed.
authority_effect = NONE.
