import { describe, expect, it } from 'vitest'
import { deriveChecks } from '../../../hub/src/lib/verificationChecks.js'

const healthyStatus = { contract_version: '1.0.0', chain_valid: true }
const healthyCalibration = {
  homeostasis_zone: 'optimal', recommendation: 'MAINTAIN',
  stagnation_rate: 0.01, constitutional_factor_mean: 0.95,
}
describe('AEGIS hub verification is never a demo success claim', () => {
  it('returns NO verified checks when only demo data exists', () => {
    const r = deriveChecks('demo', healthyStatus, healthyCalibration)
    expect(r).toHaveLength(6)
    expect(r.every(c => !c.ok)).toBe(true)
    expect(r.filter(c => /not verified|DEMO/.test(c.reason))).toHaveLength(6)
  })
  it('demo chain_valid=true and correct contract version remain unverified', () => {
    const r = deriveChecks('demo', healthyStatus, healthyCalibration)
    expect(r.find(c => c.label === 'Hash chain valid')?.ok).toBe(false)
    expect(r.find(c => c.label === 'Contract version')?.ok).toBe(false)
  })
  it('live healthy backend passes each independent check', () => {
    const r = deriveChecks('live', healthyStatus, healthyCalibration)
    expect(r.every(c => c.ok)).toBe(true)
  })
  it('live invalid chain fails even when the bridge is reachable', () => {
    const r = deriveChecks('live', { ...healthyStatus, chain_valid: false }, healthyCalibration)
    expect(r.find(c => c.label === 'Bridge reachable')?.ok).toBe(true)
    expect(r.find(c => c.label === 'Hash chain valid')?.ok).toBe(false)
  })
  it('live contract mismatch and stressed homeostasis fail separately', () => {
    const r = deriveChecks('live', { ...healthyStatus, contract_version: '0.0.0' },
      { ...healthyCalibration, homeostasis_zone: 'critical' })
    expect(r.find(c => c.label === 'Contract version')?.ok).toBe(false)
    expect(r.find(c => c.label === 'Homeostasis')?.ok).toBe(false)
  })
  it('untrusted NaN or out-of-range metrics never become healthy', () => {
    const r = deriveChecks('live', healthyStatus,
      { ...healthyCalibration, stagnation_rate: Number.NaN, constitutional_factor_mean: 2 })
    expect(r.find(c => c.label === 'Stagnation guard')?.ok).toBe(false)
    expect(r.find(c => c.label === 'Constitutional factor')?.ok).toBe(false)
  })
})
