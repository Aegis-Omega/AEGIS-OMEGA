# Core Determinism Invariants
## Applied to: src/core/**, src/event/**, src/gate/**
## Epistemic Tier: T0

These rules are active for all files under src/core/, src/event/, and src/gate/.
They represent mechanically enforceable constraints. Violation is never acceptable.

Never use Date.now() in any logic outside src/event/uuid.ts. All temporal semantics
derive from event.timestamp_ms. If you need the current time for a computation,
the timestamp must arrive as a parameter sourced from the event substrate.

Never derive sequence numbers from array.length, events.length, or any count of
in-memory structures. Sequence numbers are assigned atomically by IndexedDBSequenceAllocator
inside a transaction with the event append. They are the authority; array length is a
consequence, never a source.

Never use Set or Map in ProjectionState. Use arrays exclusively. This is required for
RFC 8785 canonicalization to produce deterministic output. Sets and Maps do not have
guaranteed iteration order across JavaScript engines.

Never use JSON.stringify for integrity-critical operations. Always use canonicalizeJCS
from src/core/canonicalize.ts, which implements RFC 8785 with lexicographic key ordering,
explicit NFC normalization, circular reference detection, and correct handling of
undefined, NaN, and Infinity.

When a RuntimeVersionPin validation fails, abort with a hard error. Never fall back
to a default version, a best-guess match, or silent degradation.

deepFreeze every state object immediately after construction. Reducers receive frozen
state and return new frozen state. No reducer may mutate its input.
