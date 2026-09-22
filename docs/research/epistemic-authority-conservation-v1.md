# Epistemic Authority Conservation V1

MHP-1 states:

authority(derived_node) <= min(authority(source), verified_transform, applicable_policy)

This induces a meet/min algebra on authority levels.

For a chain of verified transitions, the terminal authority is bounded by the
minimum of the initial authority and every transform/policy cap encountered.

Consequences:

1. authority cannot increase by composition;
2. once a chain is downgraded, later high-authority gates cannot restore it;
3. NONE is absorbing;
4. self-improvement can improve capability while remaining authority-neutral;
5. evidence preservation and authority preservation are distinct properties.

This is an AEGIS-local formalisation of the architecture invariant. The Python
tests exhaustively check the finite four-level lattice used by V1. The Lean file
contains a general Nat-valued theorem candidate; kernel replay is still required.

authority_effect = NONE
