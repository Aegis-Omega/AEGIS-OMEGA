# Agent Coordination Model — Deterministic Sequential Scheduling

## Epistemic Tier: T1 · Gate 11

---

## Sequential Coordination Rationale

AEGIS uses sequential, deterministic coordination rather than parallel mutation.
The reason is constitutional: parallel mutation introduces nondeterminism in the
sequence of state changes, which makes replay impossible. If Agent A and Agent B
both mutate state simultaneously, the resulting state depends on which mutation
commits first — and that order cannot be reconstructed from the event log alone.

Sequential scheduling via monotonically increasing sequence numbers solves this:
every state transition has exactly one predecessor and one successor. The entire
history is replayable from any starting snapshot.

---

## AgentCoordinator State Model

`AgentCoordinator` is immutable. All mutation methods return a new instance.

```
AgentCoordinator {
  _schedule: readonly ScheduleSlot[]   // agents waiting to execute
  _frames:   readonly CoordinationFrame[]  // completed execution record
}
```

`ScheduleSlot`:
```
{ agent_id: string, sequence: number, priority: number }
```

`CoordinationFrame`:
```
{ frame_id, sequence, agent_id, action_type, mutation_ids, replay_safe }
```

---

## nextAgent Algorithm

`nextAgent(atSequence)` is a pure function. Given the current sequence number,
it returns the agent_id of the next agent to execute:

1. Filter `_schedule` to entries with `sequence <= atSequence`
2. Sort ascending by `sequence`, then by `priority` (lower = higher priority)
3. Return `sorted[0].agent_id` or `undefined` if none eligible

This is deterministic: the same `_schedule` and `atSequence` always produce the
same result regardless of insertion order or environment.

---

## CoordinationFrame Protocol

Frames are appended via `recordFrame(frame)`. The invariant:

```
frame.sequence > _frames[last].sequence
```

If this invariant is violated, `AgentCoordinationError` is thrown. Frames are
never amended, deleted, or reordered. The frame log is the cryptographic ground
truth of what happened.

---

## Replay-Determinism Requirement

Every `CoordinationFrame` must have `replay_safe: true`. A frame marked
`replay_safe: false` is a T0 violation — the frame records a side effect that
cannot be replayed, breaking the constitutional integrity guarantee.

`verifyDeterminism()` validates that the entire frame sequence is strictly
monotonic. It returns `false` if any two adjacent frames are out of order.

---

## Coordination Stability Metric

`coordinationStability(): number` returns a value in `[0, 1]`:

```
monotonic_frame_pairs / (total_frames - 1)
```

Where `monotonic_frame_pairs` counts adjacent pairs `(prev, curr)` where
`curr.sequence > prev.sequence`. A value of 1.0 means all frames arrived
in strict order. Degradation toward 0.0 signals a coordination failure.

Empty or single-frame coordinators return `1` (maximally stable by definition).
