// ============================================================
// SOVEREIGN OMEGA — Gate Migration Registry tests
// EPISTEMIC TIER: T0
//
// Tests for gate/migrations/index.ts:
//   registerGateMigration — register, sealed throws
//   migrateGatePayload    — match, no match
//   sealGateMigrations    — permanent seal (runs last)
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  registerGateMigration,
  migrateGatePayload,
  sealGateMigrations,
} from '../../src/gate/migrations/index.js'
import type { GateDecisionPayload } from '../../src/gate/types.js'

function makePayload(method: string = 'anytime_valid_bernstein'): GateDecisionPayload {
  return {
    proposal_id: 'p1',
    component_id: 'c1',
    lcb_value: 0.8,
    e_value: 0.05,
    delta_metric: 0.1,
    sample_size: 100,
    accepted: true,
    risk_spent: 0.1,
    budget_remaining: 0.9,
    freeze_triggered: false,
    method: method as 'anytime_valid_bernstein',
  }
}

// ── registerGateMigration ────────────────────────────────

describe('registerGateMigration', () => {
  it('registers a migration without throwing', () => {
    expect(() => registerGateMigration({
      from_version: '1.0.0',
      to_version: '2.0.0',
      migrate: (p) => ({ ...(p as GateDecisionPayload), method: 'anytime_valid_bernstein' }),
    })).not.toThrow()
  })

  it('registers a second migration with different versions', () => {
    expect(() => registerGateMigration({
      from_version: '2.0.0',
      to_version: '3.0.0',
      migrate: (p) => makePayload(),
    })).not.toThrow()
  })
})

// ── migrateGatePayload ────────────────────────────────────

describe('migrateGatePayload', () => {
  it('returns null when no migration is registered for the given version pair', () => {
    const result = migrateGatePayload({}, '0.0.0', '99.0.0')
    expect(result).toBeNull()
  })

  it('applies a registered migration and returns the transformed payload', () => {
    const result = migrateGatePayload({ method: 'anytime_valid_bernstein' }, '1.0.0', '2.0.0')
    expect(result).not.toBeNull()
    expect(result!.method).toBe('anytime_valid_bernstein')
  })

  it('applies the second registered migration (2.0.0 → 3.0.0)', () => {
    const result = migrateGatePayload({}, '2.0.0', '3.0.0')
    expect(result).not.toBeNull()
    expect(result!.proposal_id).toBe('p1')
  })
})

// ── sealGateMigrations (runs last — permanent state change) ──

describe('sealGateMigrations', () => {
  it('throws after seal is called', () => {
    sealGateMigrations()
    expect(() => registerGateMigration({
      from_version: '4.0.0',
      to_version: '5.0.0',
      migrate: (p) => makePayload(),
    })).toThrow('sealed')
  })
})
