import { describe, expect, it } from 'vitest'
import { CapabilityClass, type SHA256Hex, type SequenceNumber } from '../../src/core/types.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import { GraceSupervisor } from '../../src/memory/grace-supervisor.js'
import { MultiverseRegistry } from '../../src/memory/multiverse.js'
import type { HealingObservation, HealingPlanner } from '../../src/runtime/agentic-self-healing.js'
import {
  ProductionGraceHealingService,
  bootstrapProductionHealingAuthority,
} from '../../src/runtime/production-healing-wiring.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const seq = (n: number): SequenceNumber => BigInt(n) as SequenceNumber

describe('production self-healing wiring', () => {
  it('routes a real Grace fault through one retained runtime without durable apply', async () => {
    let supervisor = GraceSupervisor.create(MultiverseRegistry.empty())
    supervisor = (await supervisor.executeWithGrace(
      async registry => ({ registry: (await registry.fork('alpha', h('a'), seq(1))).registry }),
      'alpha',
      seq(1),
    )).supervisor

    const service = ProductionGraceHealingService.create({
      component_id: 'multiverse-registry',
      verifiers: [{
        verifier_id: 'production-retained-registry-v1',
        async verify({ observation, effective_state_hash }) {
          return {
            passed: effective_state_hash === observation.pre_fault_state_hash,
            evidence_hash: effective_state_hash,
            reason_code: 'EXACT_RETAINED_STATE',
          }
        },
      }],
    })

    const fault = await supervisor.executeWithGrace(
      async registry => ({ registry: (await registry.fork('alpha', h('a'), seq(2))).registry }),
      'alpha',
      seq(2),
    )
    expect(fault.faulted).toBe(true)
    expect(fault.grace_event).not.toBeNull()

    const first = await service.handleGraceFault(fault.supervisor, fault.grace_event!)
    expect(first.receipt.status).toBe('RECOVERED')
    expect(first.receipt.durable_apply_performed).toBe(false)
    expect(first.receipt.authority_effect).toBe('NONE')
    expect(service.receiptCount).toBe(1)

    const secondFault = await fault.supervisor.executeWithGrace(
      async registry => ({ registry: (await registry.fork('alpha', h('a'), seq(3))).registry }),
      'alpha',
      seq(3),
    )
    const second = await service.handleGraceFault(secondFault.supervisor, secondFault.grace_event!)
    expect(second.receipt.previous_receipt_hash).toBe(first.receipt.receipt_hash)
    expect(service.receiptCount).toBe(2)
  })

  it('bootstraps mutation authority only from explicit governed configuration and still stops at AWAITING_AUTHORITY', async () => {
    const lineage = AdaptiveLineage.empty()
    const authority = await bootstrapProductionHealingAuthority({
      operators: [{
        operator_id: 'repair-operator-v1',
        operator_version: '1.0.0',
        max_branching_factor: 2,
        is_compositionally_closed: false,
        description: 'governed bounded repair',
      }],
      capacities: [{
        component_id: 'runtime-main',
        k_bound: 2,
        mutation_operators: ['repair-operator-v1'],
        dependency_graph_hash: h('a'),
        capability_class: CapabilityClass.SELF_MODIFYING,
        epoch_duration_ms: 1000,
        k_measurement_version: '1.0.0',
      }],
      lineageEntries: () => lineage.getAll(),
    })

    expect(authority.operatorRegistry.isSealed()).toBe(true)

    const planner: HealingPlanner = {
      planner_id: 'production-durable-proposal-v1',
      async propose() {
        return {
          mode: 'PROPOSE_MUTATION',
          candidate_state_hash: h('e'),
          operator_id: 'repair-operator-v1',
          delta_k: 1,
          rationale_code: 'BOUNDED_REPAIR',
        }
      },
    }

    const observation: HealingObservation = {
      incident_id: 'production-durable-1',
      component_id: 'runtime-main',
      fault_code: 'FAULT',
      severity: 'FAULT',
      sequence: seq(1),
      state_hash: h('b'),
      pre_fault_state_hash: null,
      evidence_hash: h('d'),
      replay_diverged: false,
      is_replay_reconstructable: true,
    }

    const result = await authority.runtime.runCycle(observation, {
      planner,
      authority_preflight: authority.preflight,
      verifiers: [{
        verifier_id: 'candidate-evidence-v1',
        async verify({ plan }) {
          return { passed: true, evidence_hash: plan.candidate_state_hash }
        },
      }],
    })

    expect(result.receipt.status).toBe('AWAITING_AUTHORITY')
    expect(result.receipt.effective_state_hash).toBe(observation.state_hash)
    expect(result.receipt.quarantine_active).toBe(true)
    expect(result.receipt.volatile_reversion_applied).toBe(false)
    expect(result.receipt.durable_apply_performed).toBe(false)
    expect(result.receipt.authority_effect).toBe('NONE')
  })

  it('rejects empty production operator bootstrap instead of manufacturing authority', async () => {
    await expect(bootstrapProductionHealingAuthority({
      operators: [],
      capacities: [],
      lineageEntries: () => [],
    })).rejects.toThrow('at least one governed mutation operator required')
  })
})
