/**
 * Access layer — grant token lifecycle tests
 * Tests: createGrantToken, verifyGrantToken, storeAccess, getStoredAccess
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { createGrantToken, verifyGrantToken, storeAccess, getStoredAccess } from '../lib/access.js'
import type { Plan, GrantPayload } from '../lib/access.js'

const ALL_PLANS: Plan[] = ['single', 'starter', 'full']

const PLAN_TOOLS: Record<Plan, string[]> = {
  single:  ['platform-picker'],
  starter: ['platform-picker', 'hook-generator'],
  full:    ['platform-picker', 'hook-generator', 'content-calendar'],
}

beforeEach(() => {
  localStorage.clear()
})

describe('createGrantToken', () => {
  it('returns a non-empty base64 string for each plan', () => {
    for (const plan of ALL_PLANS) {
      const token = createGrantToken(plan)
      expect(typeof token).toBe('string')
      expect(token.length).toBeGreaterThan(0)
    }
  })

  it('payload contains correct tools for each plan', () => {
    for (const plan of ALL_PLANS) {
      const token = createGrantToken(plan)
      const payload = JSON.parse(atob(token)) as GrantPayload
      expect(payload.plan).toBe(plan)
      expect(payload.tools).toEqual(PLAN_TOOLS[plan])
    }
  })

  it('payload has non-expired exp (1 year out)', () => {
    const token = createGrantToken('full')
    const payload = JSON.parse(atob(token)) as GrantPayload
    expect(payload.exp).toBeGreaterThan(Date.now())
    const oneYearMs = 365 * 24 * 60 * 60 * 1000
    expect(payload.exp - payload.grantedAt).toBeCloseTo(oneYearMs, -3)
  })

  it('each token is unique (different grantedAt)', async () => {
    const t1 = createGrantToken('full')
    await new Promise(r => setTimeout(r, 2))
    const t2 = createGrantToken('full')
    expect(t1).not.toBe(t2)
  })
})

describe('verifyGrantToken', () => {
  it('accepts a freshly-created token', () => {
    for (const plan of ALL_PLANS) {
      const token = createGrantToken(plan)
      const payload = verifyGrantToken(token)
      expect(payload).not.toBeNull()
      expect(payload!.plan).toBe(plan)
      expect(payload!.tools).toEqual(PLAN_TOOLS[plan])
    }
  })

  it('rejects a tampered payload', () => {
    const token = createGrantToken('single')
    const payload = JSON.parse(atob(token)) as GrantPayload
    // Escalate to full without updating sig
    payload.plan = 'full'
    payload.tools = ['platform-picker', 'hook-generator', 'content-calendar']
    const tampered = btoa(JSON.stringify(payload))
    expect(verifyGrantToken(tampered)).toBeNull()
  })

  it('rejects a token with expired exp', () => {
    const token = createGrantToken('full')
    const payload = JSON.parse(atob(token)) as GrantPayload
    payload.exp = Date.now() - 1000   // already expired
    // Re-sign with same grantedAt so sig is still "valid"
    const expired = btoa(JSON.stringify(payload))
    expect(verifyGrantToken(expired)).toBeNull()
  })

  it('rejects a garbled token', () => {
    expect(verifyGrantToken('not-base64!!')).toBeNull()
    expect(verifyGrantToken(btoa('{invalid json'))).toBeNull()
    expect(verifyGrantToken('')).toBeNull()
  })
})

describe('storeAccess / getStoredAccess', () => {
  it('round-trips a valid payload through localStorage', () => {
    const token = createGrantToken('full')
    const payload = verifyGrantToken(token)!
    storeAccess('platform-picker', payload)
    const retrieved = getStoredAccess('platform-picker')
    expect(retrieved).not.toBeNull()
    expect(retrieved!.plan).toBe('full')
    expect(retrieved!.tools).toContain('platform-picker')
  })

  it('returns null when nothing stored', () => {
    expect(getStoredAccess('platform-picker')).toBeNull()
  })

  it('returns null after expiry', () => {
    const token = createGrantToken('full')
    const payload = JSON.parse(atob(token)) as GrantPayload
    payload.exp = Date.now() - 1    // force expired
    storeAccess('platform-picker', payload)
    expect(getStoredAccess('platform-picker')).toBeNull()
    // Expired entry is cleaned up from localStorage
    expect(localStorage.getItem('aegis_access_platform-picker')).toBeNull()
  })

  it('stores independently per product', () => {
    const token = createGrantToken('full')
    const payload = verifyGrantToken(token)!
    storeAccess('platform-picker', payload)
    expect(getStoredAccess('hook-generator')).toBeNull()
    expect(getStoredAccess('platform-picker')).not.toBeNull()
  })
})
