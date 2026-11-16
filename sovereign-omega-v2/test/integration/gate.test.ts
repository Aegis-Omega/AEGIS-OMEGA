// ============================================================
// SOVEREIGN OMEGA — Gate Integration Tests
// ============================================================

import { describe, it, expect, beforeEach } from 'vitest'
import { RiskBudgetManager } from '../../src/gate/risk'
import { capacityRegistry, mutationOperatorRegistry } from '../../src/verifier/registry'

const EPOCH_MS = 1_600_000_000_000

describe('Risk Budget Manager — Integration', () => {
  beforeEach(async () => {
    // Register a test operator and component before each test
    try {
      mutationOperatorRegistry.register({
        operator_id: 'test-op',
        operator_version: '1.0.0',
        max_branching_factor: 3,
        is_compositionally_closed: true,
        description: 'Test mutation operator',
      })
    } catch {
      // Already registered — ignore
    }

    try {
      await capacityRegistry.register({
        component_id: 'pipeline-main',
        k_bound: 10,
        mutation_operators: ['test-op'],
        dependency_graph_hash: '0'.repeat(64) as any,
        capability_class: 'INFERENCE' as any,
        epoch_duration_ms: 3600000,
        k_measurement_version: '1.0.0',
      })
    } catch {
      // Already registered — ignore
    }
  })

  it('accepts modification when LCB > 0 with strong positive samples', () => {
    const manager = new RiskBudgetManager(EPOCH_MS)
    const samples = Array.from({ length: 50 }, () => 0.8)
    const decision = manager.evaluate('proposal-1', 'pipeline-main', samples, 1, EPOCH_MS)
    expect(decision.accepted).toBe(true)
    expect(decision.method).toBe('anytime_valid_bernstein')
  })

  it('rejects modification when samples are near-zero', () => {
    const manager = new RiskBudgetManager(EPOCH_MS)
    const samples = Array.from({ length: 20 }, () => 0.01)
    const decision = manager.evaluate('proposal-2', 'pipeline-main', samples, 1, EPOCH_MS)
    expect(decision.accepted).toBe(false)
  })

  it('tracks budget spending on acceptance', () => {
    const manager = new RiskBudgetManager(EPOCH_MS, 1.0, 10)
    const samples = Array.from({ length: 50 }, () => 0.9)
    const before = manager.currentBudget(EPOCH_MS)
    const decision = manager.evaluate('proposal-3', 'pipeline-main', samples, 1, EPOCH_MS)
    if (decision.accepted) {
      const after = manager.currentBudget(EPOCH_MS)
      expect(after).toBeLessThan(before)
    }
  })

  it('suspends when budget falls below floor', () => {
    const manager = new RiskBudgetManager(EPOCH_MS, 0.001, 10) // tiny budget
    const samples = Array.from({ length: 50 }, () => 0.9)
    // Try to exhaust budget
    for (let i = 0; i < 10; i++) {
      manager.evaluate(`proposal-${i}`, 'pipeline-main', samples, 1, EPOCH_MS)
    }
    expect(manager.isSuspended()).toBe(true)
  })

  it('rejects after freeze without statistical testing', () => {
    const manager = new RiskBudgetManager(EPOCH_MS)
    manager.freeze()
    const samples = Array.from({ length: 100 }, () => 1.0)
    const decision = manager.evaluate('proposal-frozen', 'pipeline-main', samples, 1, EPOCH_MS)
    expect(decision.accepted).toBe(false)
    expect(decision.rejection_reason).toBe('BUDGET_EXHAUSTED')
  })

  it('includes all required fields in gate decision payload', () => {
    const manager = new RiskBudgetManager(EPOCH_MS)
    const samples = Array.from({ length: 30 }, () => 0.5)
    const decision = manager.evaluate('proposal-fields', 'pipeline-main', samples, 1, EPOCH_MS)
    expect(decision.proposal_id).toBe('proposal-fields')
    expect(decision.component_id).toBe('pipeline-main')
    expect(typeof decision.lcb_value).toBe('number')
    expect(typeof decision.budget_remaining).toBe('number')
    expect(decision.method).toBe('anytime_valid_bernstein')
  })

  it('reset restores budget from external oversight event', () => {
    const manager = new RiskBudgetManager(EPOCH_MS, 0.001, 10)
    const samples = Array.from({ length: 50 }, () => 0.9)
    for (let i = 0; i < 10; i++) manager.evaluate(`p-${i}`, 'pipeline-main', samples, 1, EPOCH_MS)
    expect(manager.isSuspended()).toBe(true)
    manager.reset(1.0, EPOCH_MS + 3600000)
    expect(manager.isSuspended()).toBe(false)
    expect(manager.currentBudget(EPOCH_MS + 3600000)).toBeGreaterThan(0)
  })

  it('rejects with CAPACITY_EXCEEDED when deltaK exceeds k_bound (L59 arm 0)', () => {
    const manager = new RiskBudgetManager(EPOCH_MS)
    const samples = Array.from({ length: 50 }, () => 0.8)
    // k_bound for 'pipeline-main' is 10; deltaK=11 exceeds it → CAPACITY_EXCEEDED
    const decision = manager.evaluate('proposal-cap', 'pipeline-main', samples, 11, EPOCH_MS)
    expect(decision.accepted).toBe(false)
    expect(decision.rejection_reason).toBe('CAPACITY_EXCEEDED')
  })


  it('rejects positive LCB when the anytime e-process has not crossed its alpha threshold', () => {
    const manager = new RiskBudgetManager(EPOCH_MS)
    const before = manager.getBudgetSnapshot()
    // For maxRounds=1000, alpha_1 = 1/H_1000 ≈ 0.133592.
    // Four identical +0.5 deltas give LCB ≈ +0.04897 but
    // e-value = (1.25)^4 ≈ 2.4414 < 1/alpha ≈ 7.4855.
    const decision = manager.evaluate('proposal-short', 'pipeline-main', [0.5, 0.5, 0.5, 0.5], 1, EPOCH_MS)
    expect(decision.lcb_value).toBeGreaterThan(0)
    expect(decision.e_value).toBeCloseTo(2.44140625, 8)
    expect(decision.accepted).toBe(false)
    expect(decision.rejection_reason).toBe('E_VALUE_FAIL')
    expect(decision.risk_spent).toBe(0)
    expect(manager.getBudgetSnapshot().spent).toBe(before.spent)
    // Rejected statistical tests must still consume an alpha slot, otherwise
    // repeated failed proposals can reuse alpha_1 indefinitely.
    expect(manager.getBudgetSnapshot().round_number).toBe(before.round_number + 1)
  })

  it('counts rejected evidence tests toward the finite harmonic horizon', () => {
    const manager = new RiskBudgetManager(EPOCH_MS, 0.2, 3)
    const initialBudget = manager.currentBudget(EPOCH_MS)
    for (let k = 1; k <= 3; k++) {
      const decision = manager.evaluate(
        `proposal-rejected-${k}`, 'pipeline-main', [0.1], 1, EPOCH_MS,
      )
      expect(decision.accepted).toBe(false)
      expect(decision.risk_spent).toBe(0)
      expect(manager.getBudgetSnapshot().round_number).toBe(k)
      expect(manager.getBudgetSnapshot().spent).toBe(0)
      expect(manager.currentBudget(EPOCH_MS)).toBe(initialBudget)
    }
    expect(manager.isSuspended()).toBe(true)
    const denied = manager.evaluate('proposal-fourth', 'pipeline-main', Array(50).fill(0.9), 1, EPOCH_MS)
    expect(denied.accepted).toBe(false)
    expect(denied.rejection_reason).toBe('BUDGET_EXHAUSTED')
    expect(manager.getBudgetSnapshot().round_number).toBe(3)
  })

  it('rejects a fourth candidate even if the first three were all beneficial', () => {
    const manager = new RiskBudgetManager(EPOCH_MS, 0.2, 3)
    for (let k = 0; k < 3; k++) {
      manager.evaluate(`beneficial-${k}`, 'pipeline-main', Array(100).fill(0.9), 1, EPOCH_MS)
    }
    expect(manager.getBudgetSnapshot().round_number).toBe(3)
    expect(manager.isSuspended()).toBe(true)
    const extra = manager.evaluate('overflow-round', 'pipeline-main', Array(100).fill(0.9), 1, EPOCH_MS)
    expect(extra.accepted).toBe(false)
    expect(extra.rejection_reason).toBe('BUDGET_EXHAUSTED')
  })

  it('accepts only after both the LCB and anytime evidence thresholds hold', () => {
    const manager = new RiskBudgetManager(EPOCH_MS)
    const samples = Array(20).fill(0.5)
    const decision = manager.evaluate('proposal-supported', 'pipeline-main', samples, 1, EPOCH_MS)
    expect(decision.lcb_value).toBeGreaterThan(0)
    expect(decision.e_value).toBeGreaterThan(7.48)
    expect(decision.accepted).toBe(true)
    expect(decision.risk_spent).toBeGreaterThan(0)
    expect(manager.getBudgetSnapshot().round_number).toBe(1)
  })

  it('rejects non-finite verifier samples before clamping them to positive deltas', () => {
    for (const invalid of [Number.NaN, Infinity, -Infinity]) {
      const manager = new RiskBudgetManager(EPOCH_MS)
      const before = manager.getBudgetSnapshot()
      const decision = manager.evaluate('proposal-nonfinite', 'pipeline-main', [invalid, 0.5], 1, EPOCH_MS)
      expect(decision.accepted).toBe(false)
      expect(decision.rejection_reason).toBe('VERIFIER_INTEGRITY')
      expect(decision.e_value).toBe(0)
      expect(decision.lcb_value).toBe(0)
      expect(manager.getBudgetSnapshot()).toEqual(before)
    }
    const manager = new RiskBudgetManager(EPOCH_MS)
    expect(manager.evaluate('empty', 'pipeline-main', [], 1, EPOCH_MS).accepted).toBe(false)
  })

  it('does not accept with infinite or zero alpha for malformed budget input', () => {
    const unsupported = [
      new RiskBudgetManager(EPOCH_MS, Number.NaN),
      new RiskBudgetManager(EPOCH_MS, Infinity),
      new RiskBudgetManager(EPOCH_MS, 1000),
    ]
    for (const manager of unsupported) {
      const decision = manager.evaluate('invalid-alpha', 'pipeline-main', Array(20).fill(0.5), 1, EPOCH_MS)
      expect(decision.accepted).toBe(false)
      expect(decision.risk_spent).toBe(0)
    }
  })

  it('suspends after acceptance drains budget below floor (L95 arm 0)', () => {
    // globalBudget=0.015, maxRounds=1 → deltaAlpha = 0.015 / (1 * harmonicSum(1)) = 0.015
    // After accepting: remaining = 0.015 - 0.015 = 0 < BUDGET_SUSPEND_FLOOR (0.01)
    const manager = new RiskBudgetManager(EPOCH_MS, 0.015, 1)
    const samples = Array.from({ length: 50 }, () => 0.9)
    manager.evaluate('proposal-drain', 'pipeline-main', samples, 1, EPOCH_MS)
    expect(manager.isSuspended()).toBe(true)
  })
})
