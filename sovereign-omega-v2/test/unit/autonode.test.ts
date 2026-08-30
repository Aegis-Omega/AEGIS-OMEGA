import { describe, it, expect } from 'vitest'
import {
  AUTONODE_SCHEMA_VERSION,
  AutonodeError,
  isConstitutionallySound,
  type AutonodeDescriptor,
} from '../../../packages/shared/lib/autonode.js'

// ============================================================
// Full External and Internal Autonode — TypeScript unit tests
// ============================================================

const cleanDescriptor = (): AutonodeDescriptor => Object.freeze({
  node_id:             'abcd1234ef567890',
  t0_verdict:          true,
  constitutional_hash: 'a'.repeat(64),
  catalog_hash:        'b93f7af999e72bc71512e4e8fd8402c9',
  cognitive_triad:     'ALL 3 PRESENT',
  sequence:            42,
  epoch:               7,
  corruption_count:    0,
  phi_threshold:       0.6180339887498948,
  drift_risk:          0.05,
  schema_version:      AUTONODE_SCHEMA_VERSION,
  is_replay_reconstructable: true as const,
})

describe('AUTONODE_SCHEMA_VERSION', () => {
  it('is 1.0.0', () => {
    expect(AUTONODE_SCHEMA_VERSION).toBe('1.0.0')
  })
})

describe('AutonodeError', () => {
  it('is an instance of Error', () => {
    const e = new AutonodeError('test')
    expect(e).toBeInstanceOf(Error)
  })

  it('has name AutonodeError', () => {
    expect(new AutonodeError('x').name).toBe('AutonodeError')
  })
})

describe('isConstitutionallySound', () => {
  it('returns true for a clean descriptor', () => {
    expect(isConstitutionallySound(cleanDescriptor())).toBe(true)
  })

  it('returns false when t0_verdict is false', () => {
    const d = { ...cleanDescriptor(), t0_verdict: false }
    expect(isConstitutionallySound(d)).toBe(false)
  })

  it('returns false when corruption_count > 0', () => {
    const d = { ...cleanDescriptor(), corruption_count: 1 }
    expect(isConstitutionallySound(d)).toBe(false)
  })

  it('returns false when drift_risk >= phi_threshold', () => {
    const d = { ...cleanDescriptor(), drift_risk: 0.6180339887498948 }
    expect(isConstitutionallySound(d)).toBe(false)
  })

  it('returns false when drift_risk strictly equals phi_threshold', () => {
    const phi = 0.6180339887498948
    const d = { ...cleanDescriptor(), drift_risk: phi, phi_threshold: phi }
    expect(isConstitutionallySound(d)).toBe(false)
  })

  it('is deterministic — same input returns same result x3', () => {
    const d = cleanDescriptor()
    const r1 = isConstitutionallySound(d)
    const r2 = isConstitutionallySound(d)
    const r3 = isConstitutionallySound(d)
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })
})

describe('AutonodeDescriptor shape', () => {
  it('is_replay_reconstructable is always true', () => {
    expect(cleanDescriptor().is_replay_reconstructable).toBe(true)
  })

  it('schema_version matches AUTONODE_SCHEMA_VERSION', () => {
    expect(cleanDescriptor().schema_version).toBe(AUTONODE_SCHEMA_VERSION)
  })

  it('descriptor is frozen', () => {
    const d = cleanDescriptor()
    expect(Object.isFrozen(d)).toBe(true)
  })
})
