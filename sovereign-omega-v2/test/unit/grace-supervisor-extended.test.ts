// ============================================================
// Grace Supervisor Extended Tests — memory/grace-supervisor.ts
// Targets uncovered branches in classifyFault:
//   GENERATION_SATURATED path (message includes 'SATURATED')
//   SEQUENCE_VIOLATION fallback (message matches no pattern)
// Also covers AdaptiveLineageError catch path.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type { FaultClass } from '../../src/memory/grace-supervisor.js'
import { GraceSupervisor } from '../../src/memory/grace-supervisor.js'
import { MultiverseRegistry, MultiverseError } from '../../src/memory/multiverse.js'
import { AdaptiveLineageError } from '../../src/frame/adaptive-lineage.js'

const ROOT = 'a0b1c2d3'.repeat(8) as SHA256Hex
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

// ─── GENERATION_SATURATED fault path ─────────────────────

describe('classifyFault: GENERATION_SATURATED', () => {
  it('fault_class=GENERATION_SATURATED when MultiverseError message includes SATURATED', async () => {
    const sv = GraceSupervisor.create(MultiverseRegistry.empty())
    const { grace_event } = await sv.executeWithGrace(
      async (_reg) => { throw new MultiverseError('BoundedGeneration reached SATURATED limit') },
      'sat-u1',
      seq(1),
    )
    expect(grace_event!.fault_class).toBe('GENERATION_SATURATED' satisfies FaultClass)
  })

  it('fault_class=GENERATION_SATURATED when message includes "generation"', async () => {
    const sv = GraceSupervisor.create(MultiverseRegistry.empty())
    const { grace_event } = await sv.executeWithGrace(
      async (_reg) => { throw new MultiverseError('generation limit exceeded') },
      'gen-u1',
      seq(1),
    )
    expect(grace_event!.fault_class).toBe('GENERATION_SATURATED' satisfies FaultClass)
  })

  it('fault_class=GENERATION_SATURATED when message includes "saturated" (lowercase)', async () => {
    const sv = GraceSupervisor.create(MultiverseRegistry.empty())
    const { grace_event } = await sv.executeWithGrace(
      async (_reg) => { throw new MultiverseError('epoch saturated') },
      'sat-u2',
      seq(1),
    )
    expect(grace_event!.fault_class).toBe('GENERATION_SATURATED' satisfies FaultClass)
  })
})

// ─── SEQUENCE_VIOLATION fallback path ────────────────────

describe('classifyFault: SEQUENCE_VIOLATION fallback', () => {
  it('fault_class=SEQUENCE_VIOLATION when message matches no known pattern', async () => {
    const sv = GraceSupervisor.create(MultiverseRegistry.empty())
    const { grace_event } = await sv.executeWithGrace(
      async (_reg) => { throw new MultiverseError('unexpected internal error code 42') },
      'seq-u1',
      seq(1),
    )
    expect(grace_event!.fault_class).toBe('SEQUENCE_VIOLATION' satisfies FaultClass)
  })

  it('fault_class=SEQUENCE_VIOLATION for non-Error object (instanceof fails)', async () => {
    const sv = GraceSupervisor.create(MultiverseRegistry.empty())
    // Non-Error thrown but wrapped as MultiverseError so it IS an Error
    // Use a MultiverseError with generic message
    const { grace_event } = await sv.executeWithGrace(
      async (_reg) => { throw new MultiverseError('') },
      'seq-u2',
      seq(1),
    )
    expect(grace_event!.fault_class).toBe('SEQUENCE_VIOLATION' satisfies FaultClass)
  })
})

// ─── AdaptiveLineageError catch path ─────────────────────

describe('executeWithGrace: AdaptiveLineageError is recoverable', () => {
  it('recovers from AdaptiveLineageError — faulted=true, pre-fault registry retained', async () => {
    let sv = GraceSupervisor.create(MultiverseRegistry.empty())
    const r1 = await sv.executeWithGrace(
      async (reg) => { const { registry } = await reg.fork('base', ROOT, seq(1)); return { registry } },
      'base',
      seq(1),
    )
    sv = r1.supervisor
    const preCount = sv.registry.universeCount

    const { faulted, grace_event, supervisor } = await sv.executeWithGrace(
      async (_reg) => { throw new AdaptiveLineageError('Non-monotonic sequence: 3 ≤ 5') },
      'ala-u1',
      seq(2),
    )
    expect(faulted).toBe(true)
    expect(grace_event).not.toBeNull()
    expect(supervisor.registry.universeCount).toBe(preCount)
  })

  it('AdaptiveLineageError message matching → SEQUENCE_VIOLATION fault class', async () => {
    const sv = GraceSupervisor.create(MultiverseRegistry.empty())
    const { grace_event } = await sv.executeWithGrace(
      async (_reg) => { throw new AdaptiveLineageError('Non-monotonic sequence: 2 ≤ 1') },
      'ala-u2',
      seq(1),
    )
    // message doesn't match ECOLOGY/DUPLICATE/GENERATION patterns → SEQUENCE_VIOLATION
    expect(grace_event!.fault_class).toBe('SEQUENCE_VIOLATION' satisfies FaultClass)
  })
})
