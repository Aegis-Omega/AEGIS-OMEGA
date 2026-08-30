# Non-Negotiable Invariants
EPISTEMIC TIER: T0

TypeScript layer:
1. No Date.now() in core logic — use event.timestamp_ms
2. No array.length for sequence numbers — use IndexedDBSequenceAllocator
3. No Set or Map in ProjectionState — arrays only
4. RFC 8785 JCS for all hashing — never JSON.stringify
5. deepFreeze all state after construction
6. Version mismatch = hard abort, never silent fallback
7. Bernstein bounds not Hoeffding — adaptive sampling violates IID
8. MutationOperatorRegistry.seal() before gate evaluations
9. V4/V5 verifiers never in VCG calibration

Python layer:
10. All temporal semantics use event sequence number, never time.time()
11. Bit-shifted integer arithmetic in all determinism-critical paths
12. PGCS must pass (zero disk I/O) before TGCS telemetry is meaningful
13. Epoch failsafe corruption_count = 0 at all times
14. Anchor tokens immutable after epoch 0
