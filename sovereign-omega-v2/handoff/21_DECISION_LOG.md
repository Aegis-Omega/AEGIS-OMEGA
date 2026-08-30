# Architectural Decision Records
EPISTEMIC TIER: T0

ADR-001: Append-only event substrate mandatory. Any mutable state cannot provide forensic guarantees. FROZEN.
ADR-002: V1/V2 only in calibration; V4/V5 Advisory-Excluded permanently. FROZEN.
ADR-003: Bernstein bounds required for E4 gate. Hoeffding assumes IID; adaptive systems violate IID. FROZEN.
ADR-004: MutationOperatorRegistry.seal() before gate evaluations. Dynamic injection is a hard error. FROZEN.
ADR-005: Version mismatch causes hard abort, never silent fallback. FROZEN.
ADR-006: core_matrix.py is a separate layer from the TypeScript runtime. 8GB RAM requires byte-level optimisation outside the TypeScript execution model. ACTIVE.
ADR-007: PGCS must pass before TGCS or AFSE telemetry is meaningful. Disk swapping invalidates all timing profiles. ACTIVE.
