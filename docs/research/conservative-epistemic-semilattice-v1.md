# Conservative Epistemic Semilattice V1

For loss-bearing AEGIS summaries define:

(a,u) ⊗ (b,v) = (min(a,b), max(u,v))

where:
- authority is ordered by increasing operational power;
- u is declared loss uncertainty in basis points.

The merge is conservative:
- authority never exceeds either input;
- uncertainty never falls below either input.

Because min and max are each commutative, associative and idempotent, the product
merge has the same three properties.

This gives AEGIS a candidate deterministic merge algebra for conservative
epistemic summaries across independent agents, branches, or replay orderings.

It does not prove that the underlying claims are true.
It does not turn general uncertainty into a scalar sufficient statistic.
The uncertainty coordinate here is specifically the bounded loss-accounting
quantity used by this V1 abstraction.

Status:
- Python finite-lattice tests: source prepared;
- Lean theorem candidates: source prepared;
- kernel replay: pending exact-head execution;
- distributed/CRDT deployment: not established;
- authority_effect: NONE.
