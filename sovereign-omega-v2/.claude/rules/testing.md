# Testing Rules
## Applied to: test/**
## Epistemic Tier: T0

Every gate test must pass before the agent proceeds to the next build gate.
A partial pass is a failure. Gate 8 (full test suite) is the deployment gate.
Do not proceed to deployment without Gate 8 passing completely.

Tests must not weaken existing assertions. Adding tests is permitted.
Removing or softening an existing assertion requires a Guardian-approved
justification. If a test is failing because the implementation is wrong,
fix the implementation — do not adjust the test.

Determinism tests must run their subject function at least three times and
assert byte-identical output across all runs. One or two runs are insufficient
to confirm determinism.

Tests for the VCG tracker must use fixed timestamps derived from the epoch
constant 1_600_000_000_000, not from Date.now(). This ensures the bootstrap
CI seed is deterministic and the test is reproducible.

Integration tests for the pipeline must verify the full DecisionSchema structure,
not just individual fields. A passing score check that ignores the confidence
type or audit_trace_id is an incomplete test.
