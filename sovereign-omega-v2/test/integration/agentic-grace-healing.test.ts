import { describe, expect, it } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { GraceSupervisor } from '../../src/memory/grace-supervisor.js'
import { MultiverseRegistry } from '../../src/memory/multiverse.js'
import {
  AgenticSelfHealingRuntime,
  type HealingPlanInput,
} from '../../src/runtime/agentic-self-healing.js'
import {
  createGraceRetentionRecoveryAdapter,
  hashMultiverseRegistry,
  healingObservationFromGrace,
} from '../../src/runtime/grace-healing-adapter.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const seq = (n: number): SequenceNumber => BigInt(n) as SequenceNumber

describe('GraceSupervisor → Agentic Self-Healing integration', () => {
  it('certifies retained pre-fault registry as RECOVERED after duplicate-universe fault', async () => {
    let grace = GraceSupervisor.create(MultiverseRegistry.empty())

    const first = await grace.executeWithGrace(
      async registry => {
        const { registry: next } = await registry.fork('alpha', h('a'), seq(1))
        return { registry: next }
      },
      'alpha',
      seq(1),
    )
    grace = first.supervisor

    const preFaultHash = await hashMultiverseRegistry(grace.registry)

    const fault = await grace.executeWithGrace(
      async registry => {
        const { registry: next } = await registry.fork('alpha', h('a'), seq(2))
        return { registry: next }
      },
      'alpha',
      seq(2),
    )

    expect(fault.faulted).toBe(true)
    expect(fault.grace_event?.fault_class).toBe('DUPLICATE_UNIVERSE')
    expect(await hashMultiverseRegistry(fault.supervisor.registry)).toBe(preFaultHash)

    const graceEvent = fault.grace_event
    if (graceEvent === null) throw new Error('expected grace event')

    const observation = await healingObservationFromGrace(
      fault.supervisor,
      graceEvent,
      'multiverse-registry',
    )

    expect(observation.state_hash).toBe(preFaultHash)
    expect(observation.pre_fault_state_hash).toBe(preFaultHash)
    expect(observation.evidence_hash).toBe(graceEvent.grace_hash)

    const plan: HealingPlanInput = {
      mode: 'GRACE_REVERSION',
      candidate_state_hash: preFaultHash,
      rationale_code: 'GRACE_RETAINED_PREFAULT_STATE',
    }

    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation,
      {
        planner: {
          planner_id: 'grace-planner-v1',
          async propose() { return plan },
        },
        volatile_recovery: createGraceRetentionRecoveryAdapter(fault.supervisor),
        verifiers: [{
          verifier_id: 'retained-registry-hash-v1',
          async verify({ effective_state_hash }) {
            return {
              passed: effective_state_hash === preFaultHash,
              evidence_hash: preFaultHash,
              reason_code: 'PREFAULT_STATE_HASH_MATCH',
            }
          },
        }],
      },
    )

    expect(result.receipt.status).toBe('RECOVERED')
    expect(result.receipt.reason_code).toBe('GRACE_REVERSION_VERIFIED')
    expect(result.receipt.effective_state_hash).toBe(preFaultHash)
    expect(result.receipt.volatile_reversion_applied).toBe(true)
    expect(result.receipt.durable_apply_performed).toBe(false)
    expect(result.receipt.authority_effect).toBe('NONE')
  })

  it('multiverse registry hash is deterministic', async () => {
    let a = MultiverseRegistry.empty()
    let b = MultiverseRegistry.empty()

    a = (await a.fork('alpha', h('a'), seq(1))).registry
    b = (await b.fork('alpha', h('a'), seq(1))).registry

    const [a1, a2, b1] = await Promise.all([
      hashMultiverseRegistry(a),
      hashMultiverseRegistry(a),
      hashMultiverseRegistry(b),
    ])

    expect(a1).toBe(a2)
    expect(a1).toBe(b1)
    expect(a1).toMatch(/^[0-9a-f]{64}$/)
  })
})
