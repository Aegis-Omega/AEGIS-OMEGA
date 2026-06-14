/**
 * Platform Contract — canonical schema invariants
 * EPISTEMIC TIER: T0
 *
 * Verifies that PLATFORM_DEPARTMENTS and exported constants in
 * packages/shared/lib/platform-contract.ts remain internally consistent.
 * These assertions catch spec-drift before it reaches the bridge or clients.
 */
import { describe, it, expect } from 'vitest'
import {
  PLATFORM_CONTRACT_VERSION,
  PLATFORM_DEPARTMENTS,
} from '../../../packages/shared/lib/platform-contract.js'

describe('PLATFORM_CONTRACT_VERSION', () => {
  it('is exactly 1.0.0', () => {
    expect(PLATFORM_CONTRACT_VERSION).toBe('1.0.0')
  })

  it('is semver-shaped (N.N.N)', () => {
    expect(PLATFORM_CONTRACT_VERSION).toMatch(/^\d+\.\d+\.\d+$/)
  })
})

describe('PLATFORM_DEPARTMENTS roster', () => {
  it('has exactly 39 departments', () => {
    expect(PLATFORM_DEPARTMENTS).toHaveLength(39)
  })

  it('every department has non-empty id, role, and category', () => {
    for (const dept of PLATFORM_DEPARTMENTS) {
      expect(typeof dept.id).toBe('string')
      expect(dept.id.length).toBeGreaterThan(0)
      expect(typeof dept.role).toBe('string')
      expect(dept.role.length).toBeGreaterThan(0)
      expect(typeof dept.category).toBe('string')
      expect(dept.category.length).toBeGreaterThan(0)
    }
  })

  it('all department IDs are unique', () => {
    const ids = PLATFORM_DEPARTMENTS.map(d => d.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('all department roles are unique', () => {
    const roles = PLATFORM_DEPARTMENTS.map(d => d.role)
    expect(new Set(roles).size).toBe(roles.length)
  })

  it('includes the Guardian (constitutional enforcement sentinel)', () => {
    const guardian = PLATFORM_DEPARTMENTS.find(d => d.id === 'CON-09')
    expect(guardian?.role).toBe('Guardian')
    expect(guardian?.category).toBe('constitutional')
  })

  it('includes constitutional Audit department', () => {
    const audit = PLATFORM_DEPARTMENTS.find(d => d.id === 'CON-01')
    expect(audit?.role).toBe('Audit')
    expect(audit?.category).toBe('constitutional')
  })

  it('all categories are from the known set', () => {
    const KNOWN = new Set([
      'revenue', 'marketing', 'sales', 'product',
      'engineering', 'operations', 'research', 'finance',
      'executive', 'governance', 'constitutional',
    ])
    for (const dept of PLATFORM_DEPARTMENTS) {
      expect(KNOWN.has(dept.category)).toBe(true)
    }
  })

  it('IDs follow the PREFIX-NN pattern', () => {
    for (const dept of PLATFORM_DEPARTMENTS) {
      expect(dept.id).toMatch(/^[A-Z]{2,4}-\d{2}$/)
    }
  })

  it('constitutional departments activate last (verifier-last invariant)', () => {
    const ids = PLATFORM_DEPARTMENTS.map(d => d.id)
    const constitutional = PLATFORM_DEPARTMENTS.filter(d => d.category === 'constitutional')
    const nonConstitutional = PLATFORM_DEPARTMENTS.filter(d => d.category !== 'constitutional')

    expect(constitutional.length).toBeGreaterThanOrEqual(2)

    const lastNonConIdx = Math.max(...nonConstitutional.map(d => ids.indexOf(d.id)))
    const firstConIdx   = Math.min(...constitutional.map(d => ids.indexOf(d.id)))
    expect(firstConIdx).toBeGreaterThan(lastNonConIdx)
  })

  it('Guardian is the last department in the roster', () => {
    const guardian = PLATFORM_DEPARTMENTS.find(d => d.role === 'Guardian')
    expect(guardian?.id).toBe('CON-09')
    expect(PLATFORM_DEPARTMENTS.indexOf(guardian!)).toBe(38)
  })
})
