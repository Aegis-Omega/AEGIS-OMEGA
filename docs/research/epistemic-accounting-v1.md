# Epistemic Accounting V1

This formalizes invariants already present in MHP-1 rather than introducing a
new physical or information-theoretic conservation law.

For a verified semantic transition:

S = P_S disjoint-union O
T = P_T disjoint-union A

where:
- S is the source claim set;
- P_S is the preserved source domain;
- O is the declared omission set;
- T is the target claim set;
- P_T is the preserved target range;
- A is the declared addition set.

Single-step additions require exact derivation receipts.

MHP transitive composition V1 is stricter: final additions remain denied because
a derivation-composition proof object has not yet been ratified.

For an actual composite loss of an original source claim, current MHP composition
uses:

U_13 = max(U_12, U_23)

so loss uncertainty cannot be silently reduced below either predecessor value.

If there is no composite loss of the original source, V1 uses zero loss
uncertainty. This quantity is therefore loss-accounting uncertainty, not a
general posterior epistemic uncertainty measure.

The Python implementation tests these accounting rules directly. The Lean file
contains theorem candidates for partition cardinality and uncertainty
monotonicity under composite loss. Kernel replay remains required.

authority_effect = NONE
