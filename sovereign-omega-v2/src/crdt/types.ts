// ============================================================
// SOVEREIGN OMEGA — CRDT Lattice Types
// EPISTEMIC TIER: T2 · Gate 20
//
// Monotonic semilattice join operations for distributed state
// merge. Laws (mechanically tested):
//   Commutativity:  join(a, b) = join(b, a)
//   Associativity:  join(join(a,b),c) = join(a,join(b,c))
//   Idempotency:    join(a, a) = a
//   Monotonicity:   a ≤ b ⟹ join(a,x) ≤ join(b,x)
// ============================================================

/** Signals an irreconcilable conflict in a join operation.
 *  Thrown when the same key exists with different content in both operands. */
export class CRDTConflictError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'CRDTConflictError'
  }
}
