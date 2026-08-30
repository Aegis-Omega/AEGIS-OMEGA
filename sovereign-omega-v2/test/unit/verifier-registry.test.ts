// ============================================================
// Verifier Registry Tests — verifier/registry.ts
// Targets uncovered branches: register throw paths,
// getCalibrationEligible filter, getCalibrationWeight all paths,
// MutationOperatorRegistry sealed/invalid throws, validate unknown,
// computeKBound product, CapacityDeclarationRegistry all throw paths,
// checkKBound all paths. Sealed tests run last (permanent state).
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  verifierRegistry,
  mutationOperatorRegistry,
  capacityRegistry,
  RegistrationError,
} from '../../src/verifier/registry.js'
import { CalibrationDomain, VerifierClass, CapabilityClass } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type { Verifier, VerifierInput, VerifierOutput } from '../../src/verifier/types.js'

// ─── Fixtures ──────────────────────────────────────────────

let _uid = 0
const uid = () => `vr-${++_uid}`
const H = '0'.repeat(64) as SHA256Hex

function makeVerifier(id: string, opts: {
  cls?: VerifierClass
  trust?: CalibrationDomain
  deterministic?: boolean
  latency?: number
} = {}): Verifier {
  return {
    definition: {
      verifier_id: id,
      verifier_class: opts.cls ?? VerifierClass.V3_RETRIEVAL,
      trust_class: opts.trust ?? CalibrationDomain.RETRIEVAL_ASSISTED,
      version: '1.0.0',
      description: 'test verifier',
      max_latency_ms: opts.latency ?? 1000,
      is_deterministic: opts.deterministic ?? true,
    },
    verify: (_: VerifierInput): Promise<VerifierOutput> => Promise.resolve({
      verifier_id: id,
      claim_id: 'c1',
      passed: true,
      raw_confidence: 1.0,
      evidence_refs: [],
      latency_ms: 10,
      determinism_flag: true,
      verifier_version: '1.0.0',
      trust_class: opts.trust ?? CalibrationDomain.RETRIEVAL_ASSISTED,
      artifact_hash: H,
    }),
  }
}

// ─── RegistrationError ────────────────────────────────────

describe('RegistrationError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new RegistrationError('msg')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('RegistrationError')
    expect(e.message).toBe('msg')
  })
})

// ─── VerifierRegistry ─────────────────────────────────────

describe('VerifierRegistry.register', () => {
  it('throws when verifier_id is empty string', () => {
    expect(() => verifierRegistry.register(makeVerifier(''))).toThrow(RegistrationError)
  })

  it('throws when V1 verifier declares is_deterministic = false', () => {
    const v = makeVerifier(uid(), { cls: VerifierClass.V1_DETERMINISTIC, deterministic: false })
    expect(() => verifierRegistry.register(v)).toThrow(RegistrationError)
  })

  it('throws when V2 verifier declares is_deterministic = false', () => {
    const v = makeVerifier(uid(), { cls: VerifierClass.V2_SCHEMA, deterministic: false })
    expect(() => verifierRegistry.register(v)).toThrow(RegistrationError)
  })

  it('throws when max_latency_ms > 30000', () => {
    const v = makeVerifier(uid(), { latency: 30_001 })
    expect(() => verifierRegistry.register(v)).toThrow(RegistrationError)
  })

  it('accepts valid V1 deterministic verifier', () => {
    const id = uid()
    verifierRegistry.register(makeVerifier(id, { cls: VerifierClass.V1_DETERMINISTIC, deterministic: true }))
    expect(verifierRegistry.get(id)).toBeDefined()
  })

  it('accepts V4 statistical verifier with is_deterministic = false', () => {
    const id = uid()
    expect(() => verifierRegistry.register(
      makeVerifier(id, { cls: VerifierClass.V4_STATISTICAL, deterministic: false })
    )).not.toThrow()
  })
})

describe('VerifierRegistry.getCalibrationEligible', () => {
  it('returns only GROUND_TRUTH and RETRIEVAL_ASSISTED verifiers', () => {
    const gtId = uid()
    const raId = uid()
    const aeId = uid()
    verifierRegistry.register(makeVerifier(gtId, { trust: CalibrationDomain.GROUND_TRUTH }))
    verifierRegistry.register(makeVerifier(raId, { trust: CalibrationDomain.RETRIEVAL_ASSISTED }))
    verifierRegistry.register(makeVerifier(aeId, { trust: CalibrationDomain.ADVISORY_EXCLUDED }))

    const eligible = verifierRegistry.getCalibrationEligible()
    const ids = eligible.map(v => v.definition.verifier_id)
    expect(ids).toContain(gtId)
    expect(ids).toContain(raId)
    expect(ids).not.toContain(aeId)
  })
})

describe('VerifierRegistry.getCalibrationWeight', () => {
  it('returns 1.0 for GROUND_TRUTH', () => {
    expect(verifierRegistry.getCalibrationWeight(CalibrationDomain.GROUND_TRUTH)).toBe(1.0)
  })

  it('returns 0.5 for RETRIEVAL_ASSISTED', () => {
    expect(verifierRegistry.getCalibrationWeight(CalibrationDomain.RETRIEVAL_ASSISTED)).toBe(0.5)
  })

  it('returns 0 for ADVISORY_EXCLUDED', () => {
    expect(verifierRegistry.getCalibrationWeight(CalibrationDomain.ADVISORY_EXCLUDED)).toBe(0)
  })
})

// ─── MutationOperatorRegistry (pre-seal) ─────────────────

describe('MutationOperatorRegistry.register (before seal)', () => {
  it('throws when operator_id is empty', () => {
    expect(() => mutationOperatorRegistry.register({
      operator_id: '',
      operator_version: '1.0.0',
      max_branching_factor: 2,
      is_compositionally_closed: true,
      description: 'test',
    })).toThrow(RegistrationError)
  })

  it('throws when max_branching_factor <= 0', () => {
    expect(() => mutationOperatorRegistry.register({
      operator_id: 'op-zero',
      operator_version: '1.0.0',
      max_branching_factor: 0,
      is_compositionally_closed: true,
      description: 'zero bf',
    })).toThrow(RegistrationError)
  })

  it('accepts a valid operator', () => {
    expect(() => mutationOperatorRegistry.register({
      operator_id: 'op-a',
      operator_version: '1.0.0',
      max_branching_factor: 2,
      is_compositionally_closed: true,
      description: 'valid',
    })).not.toThrow()
  })

  it('registers a second operator with different branching factor', () => {
    expect(() => mutationOperatorRegistry.register({
      operator_id: 'op-b',
      operator_version: '1.0.0',
      max_branching_factor: 5,
      is_compositionally_closed: true,
      description: 'second',
    })).not.toThrow()
  })
})

describe('MutationOperatorRegistry.validate', () => {
  it('throws RegistrationError for unknown operator id', () => {
    expect(() => mutationOperatorRegistry.validate(['not-registered-zzz'])).toThrow(RegistrationError)
  })

  it('does not throw for registered operator', () => {
    expect(() => mutationOperatorRegistry.validate(['op-a'])).not.toThrow()
  })
})

describe('MutationOperatorRegistry.computeKBound', () => {
  it('returns product of branching factors for multiple operators', () => {
    // op-a: 2, op-b: 5 → 10
    expect(mutationOperatorRegistry.computeKBound(['op-a', 'op-b'])).toBe(10)
  })

  it('returns single branching factor for one operator', () => {
    expect(mutationOperatorRegistry.computeKBound(['op-a'])).toBe(2)
  })
})

// ─── CapacityDeclarationRegistry ─────────────────────────

describe('CapacityDeclarationRegistry.register', () => {
  it('throws when k_bound is Infinity', async () => {
    await expect(capacityRegistry.register({
      component_id: 'cap-inf',
      k_bound: Infinity,
      mutation_operators: ['op-a'],
      dependency_graph_hash: H,
      capability_class: CapabilityClass.INFERENCE,
      epoch_duration_ms: 1000,
      k_measurement_version: '1.0.0',
    })).rejects.toThrow(RegistrationError)
  })

  it('throws when k_bound is negative', async () => {
    await expect(capacityRegistry.register({
      component_id: 'cap-neg',
      k_bound: -1,
      mutation_operators: ['op-a'],
      dependency_graph_hash: H,
      capability_class: CapabilityClass.INFERENCE,
      epoch_duration_ms: 1000,
      k_measurement_version: '1.0.0',
    })).rejects.toThrow(RegistrationError)
  })

  it('throws when computedK exceeds k_bound', async () => {
    // op-a(2) * op-b(5) = 10, k_bound = 8 → should throw
    await expect(capacityRegistry.register({
      component_id: 'cap-exceed',
      k_bound: 8,
      mutation_operators: ['op-a', 'op-b'],
      dependency_graph_hash: H,
      capability_class: CapabilityClass.INFERENCE,
      epoch_duration_ms: 1000,
      k_measurement_version: '1.0.0',
    })).rejects.toThrow(RegistrationError)
  })

  it('registers successfully when computedK ≤ k_bound', async () => {
    await expect(capacityRegistry.register({
      component_id: 'cap-ok',
      k_bound: 10,
      mutation_operators: ['op-a', 'op-b'],
      dependency_graph_hash: H,
      capability_class: CapabilityClass.INFERENCE,
      epoch_duration_ms: 1000,
      k_measurement_version: '1.0.0',
    })).resolves.toBeUndefined()
  })
})

describe('CapacityDeclarationRegistry.checkKBound', () => {
  it('throws when component is not registered', () => {
    expect(() => capacityRegistry.checkKBound('cap-unknown-xyz', 1)).toThrow(RegistrationError)
  })

  it('returns true when deltaK ≤ k_bound', () => {
    expect(capacityRegistry.checkKBound('cap-ok', 5)).toBe(true)
  })

  it('returns false when deltaK > k_bound', () => {
    expect(capacityRegistry.checkKBound('cap-ok', 11)).toBe(false)
  })
})

// ─── Seal (permanent — runs last) ─────────────────────────

describe('MutationOperatorRegistry.register (post-seal)', () => {
  it('throws after seal() is called', () => {
    mutationOperatorRegistry.seal()
    expect(() => mutationOperatorRegistry.register({
      operator_id: 'op-post-seal',
      operator_version: '1.0.0',
      max_branching_factor: 1,
      is_compositionally_closed: true,
      description: 'after seal',
    })).toThrow(RegistrationError)
  })
})
