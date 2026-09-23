# No-Free Epistemic Gain / Conservative Consensus V1

This lane extends the already kernel-verified authority/min and
loss-uncertainty/max structure with a claim-set coordinate.

Define an epistemic state:

`E = (C, a, u)`

where:
- `C` is the set of claims asserted by the state;
- `a` is authority;
- `u` is bounded loss-accounting uncertainty.

Define the conservative order:

`x <=E y`

iff:
- `claims(x) ⊆ claims(y)`;
- `authority(x) <= authority(y)`;
- `uncertainty(x) >= uncertainty(y)`.

Under that order, the candidate meet is:

`x ∧ y = (claims(x) ∩ claims(y), min(a_x,a_y), max(u_x,u_y))`.

The load-bearing target is the universal property:

`z <=E x AND z <=E y  =>  z <=E (x ∧ y)`.

Equivalently, no conservative common output can obtain for free:
- a claim not common to the inputs;
- authority above the weaker input;
- loss uncertainty below the larger input uncertainty.

Any stronger output requires a separate verified derivation/evidence transition.

The mathematics is an elementary product-lattice construction. Mathematical
novelty is not claimed. The AEGIS research question is whether this typed meet
is useful as a safe multi-agent consensus primitive when combined with receipts,
semantic lineage, and cross-boundary authority.

authority_effect = NONE
