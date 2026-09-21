import { describe, expect, it } from 'vitest'
import {
  CapabilityClass,
  type SHA256Hex,
  type SequenceNumber,
} from '../../src/core/types.js'
import { AdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import {
  capacityRegistry,
  mutationOperatorRegistry,
} from '../../src/verifier/registry.js'
import {
  createHealingAuthorityPreflight,
} from '../../src/runtime/healing-authority-adapter.js'
import type {
  HealingObservation,
  HealingPlan,
} from '../../src/runtime/agentic-self-healing.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const seq = (n: number): SequenceNumber => BigInt(n) as SequenceNumber

describe('Agentic healing authority adapter', () => {
  it('enforces registry seal, operator identity, K-bound and martingale', async () => {
    const lineage = AdaptiveLineage.empty()
    const adapter = createHealingAuthorityPreflight({
      lineageEntries: () => lineage.getAll(),
    })

    // ADR-004: gate evaluation before MutationOperatorRegistry.seal() is forbidden.
    expect(await adapter.mutationAuthorityActive()).toBe(false)

    mutationOperatorRegistry.register({
      operator_id: 'repair-operator-v1',
      operator_version: '1.0.0',
      max_branching_factor: 2,
      is_compositionally_closed: false,
      description: 'bounded test repair operator',
    })

    await capacityRegistry.register({
      component_id: 'runtime-main',
      k_bound: 2,
      mutation_operators: ['repair-operator-v1'],
      dependency_graph_hash: h('a'),
      capability_class: CapabilityClass.SELF_MODIFYING,
      epoch_duration_ms: 1_000,
      k_measurement_version: '1.0.0',
    })

    mutationOperatorRegistry.seal()

    expect(mutationOperatorRegistry.isSealed()).toBe(true)
    expect(await adapter.mutationAuthorityActive()).toBe(true)

    const observation: HealingObservation = {
      incident_id: 'inc-authority',
      component_id: 'runtime-main',
      fault_code: 'FAULT',
      severity: 'FAULT',
      sequence: seq(1),
      state_hash: h('b'),
      pre_fault_state_hash: h('c'),
      evidence_hash: h('d'),
      replay_diverged: false,
      is_replay_reconstructable: true,
    }

    const basePlan: HealingPlan = {
      mode: 'PROPOSE_MUTATION',
      candidate_state_hash: h('e'),
      operator_id: 'repair-operator-v1',
      delta_k: 1,
      rationale_code: 'BOUNDED_REPAIR',
      planner_id: 'planner',
      plan_hash: h('f'),
      observation_hash: h('1'),
      authority_effect: 'NONE',
      is_replay_reconstructable: true,
    }

    const allowed = await adapter.preflight({
      observation,
      plan: basePlan,
      operator_id: 'repair-operator-v1',
      delta_k: 1,
    })
    expect(allowed.eligible).toBe(true)
    expect(allowed.reason_code).toBe('SEALED_REGISTRY_K_BOUND_AND_MARTINGALE_OK')
    expect(allowed.evidence_hash).toMatch(/^[0-9a-f]{64}$/)

    const overK = await adapter.preflight({
      observation,
      plan: { ...basePlan, delta_k: 3 },
      operator_id: 'repair-operator-v1',
      delta_k: 3,
    })
    expect(overK.eligible).toBe(false)
    expect(overK.reason_code).toBe('K_BOUND_EXCEEDED')

    const unknown = await adapter.preflight({
      observation,
      plan: { ...basePlan, operator_id: 'unknown-op' },
      operator_id: 'unknown-op',
      delta_k: 1,
    })
    expect(unknown.eligible).toBe(false)
    expect(unknown.reason_code).toBe('UNKNOWN_MUTATION_OPERATOR')
  })
})
