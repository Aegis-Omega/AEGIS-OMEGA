/**
 * CI-only native E4 producer test, copied into the exact PR #817 source tree.
 * Tests the REAL RiskBudgetManager implementation, not a mocked decision.
 * Deterministic synthetic samples DO NOT constitute mutation safety evidence.
 * This file is intentionally not picked up by the generic Vitest test glob.
 */
import { describe, it, expect } from 'vitest'
import { writeFileSync } from 'node:fs'
import { RiskBudgetManager } from '../../src/gate/risk.js'
import { capacityRegistry, mutationOperatorRegistry } from '../../src/verifier/registry.js'
import { CapabilityClass } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'

const epoch = 1_700_000_000_000
const component = 'bridge-e4-synthetic-mutation'
const operator = 'bridge-e4-synthetic-test-v1'
const permittedHash = '0'.repeat(64) as SHA256Hex

describe('native E4 decision emitted from PR #817 actual source', () => {
  it('evaluates a declared self-modifying component and emits the real gate payload', async () => {
    mutationOperatorRegistry.register({
      operator_id: operator, operator_version: '1.0.0',
      max_branching_factor: 1, is_compositionally_closed: true,
      description: 'Deterministic CI-only mutation admission probe',
    })
    await capacityRegistry.register({
      component_id: component, k_bound: 1,
      mutation_operators: [operator],
      dependency_graph_hash: permittedHash,
      capability_class: CapabilityClass.SELF_MODIFYING,
      epoch_duration_ms: 3600000, k_measurement_version: '1.0.0',
    })
    const declared = capacityRegistry.get(component)
    expect(declared?.capability_class).toBe(CapabilityClass.SELF_MODIFYING)
    expect(declared?.mutation_operators).toContain(operator)
    const beneficial = new RiskBudgetManager(epoch)
    const decision = beneficial.evaluate(
      'E4:source:verified:1', component, Array(24).fill(0.5), 1, epoch,
    )
    expect(decision.accepted).toBe(true)
    expect(decision.method).toBe('anytime_valid_bernstein')
    expect(decision.lcb_value).toBeGreaterThan(0)
    expect(decision.e_value).toBeGreaterThanOrEqual(1 / decision.risk_spent)
    expect(decision.sample_size).toBe(24)
    const weak = new RiskBudgetManager(epoch)
    const insufficient = weak.evaluate(
      'E4:source:weak:2', component, Array(4).fill(0.5), 1, epoch,
    )
    expect(insufficient.lcb_value).toBeGreaterThan(0)
    expect(insufficient.accepted).toBe(false)
    expect(insufficient.rejection_reason).toBe('E_VALUE_FAIL')
    expect(insufficient.e_value).toBeLessThan(
      1 / (weak.currentBudget(epoch) / harmonicSum(1000))
    )
    const destination = process.env.AEGIS_NATIVE_E4_DECISION_PATH
    expect(destination).toBeTruthy()
    writeFileSync(destination!, JSON.stringify({
      schema: 'AEGIS_E4_NATIVE_PR817_TEST_V1',
      source: 'RiskBudgetManager.evaluate',
      fixture_class: 'SYNTHETIC_CI_ONLY_NOT_MUTATION_PROOF',
      exact_e4_source_sha: process.env.AEGIS_NATIVE_E4_SOURCE_SHA,
      capability_class: declared.capability_class,
      registered_operator: operator,
      decision,
      insufficient,
      sequence: 17,
      payload_hex: Buffer.from('native-e4-payload', 'utf8').toString('hex'),
      verifier_hex: '00',
      context_hex: Buffer.from('native-e4-probe', 'utf8').toString('hex'),
    }) + '\n')
  })
})
function harmonicSum(n: number): number {
  let sum = 0
  for (let k = 1; k <= n; k++) sum += 1 / k
  return sum
}
