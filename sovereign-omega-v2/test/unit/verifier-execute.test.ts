// ============================================================
// SOVEREIGN OMEGA — Verifier Execution Engine tests
// EPISTEMIC TIER: T0/T1
//
// Tests for verifier/execute.ts:
//   executeVerifiers — routing, trust partition, artifact_hash,
//   correlation_matrix, correlation_alert, silent failure handling
// ============================================================

import { describe, it, expect } from 'vitest'
import { executeVerifiers } from '../../src/verifier/execute.js'
import { verifierRegistry } from '../../src/verifier/registry.js'
import { CalibrationDomain, VerifierClass } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type { Verifier, VerifierInput, VerifierOutput } from '../../src/verifier/types.js'

const H = '0'.repeat(64) as SHA256Hex

let _uid = 0
const uid = () => `exec-${++_uid}`

const INPUT: VerifierInput = { claim_id: 'c1', domain: 'test', content: 'hello' }

function makeVerifier(id: string, opts: {
  trust?: CalibrationDomain
  pass?: boolean
  throws?: boolean
} = {}): Verifier {
  const trust = opts.trust ?? CalibrationDomain.RETRIEVAL_ASSISTED
  return {
    definition: {
      verifier_id: id,
      verifier_class: VerifierClass.V3_RETRIEVAL,
      trust_class: trust,
      version: '1.0.0',
      description: 'test verifier',
      max_latency_ms: 1000,
      is_deterministic: true,
    },
    verify: (_: VerifierInput): Promise<VerifierOutput> => {
      if (opts.throws) throw new Error('verifier intentionally failed')
      return Promise.resolve({
        verifier_id: id,
        claim_id: 'c1',
        passed: opts.pass ?? true,
        raw_confidence: 1.0,
        evidence_refs: [],
        latency_ms: 10,
        determinism_flag: true,
        verifier_version: '1.0.0',
        trust_class: trust,
        artifact_hash: H,
      })
    },
  }
}

// ── executeVerifiers ──────────────────────────────────────

describe('executeVerifiers', () => {
  it('returns empty result for empty verifier ID list', async () => {
    const result = await executeVerifiers(INPUT, [])
    expect(result.outputs).toHaveLength(0)
    expect(result.calibration_eligible).toHaveLength(0)
    expect(result.advisory_only).toHaveLength(0)
    expect(result.correlation_alert).toBe(false)
  })

  it('silently skips unknown verifier IDs', async () => {
    const result = await executeVerifiers(INPUT, ['does-not-exist-exec-xyz'])
    expect(result.outputs).toHaveLength(0)
  })

  it('places GROUND_TRUTH output in calibration_eligible only', async () => {
    const id = uid()
    verifierRegistry.register(makeVerifier(id, { trust: CalibrationDomain.GROUND_TRUTH }))
    const result = await executeVerifiers(INPUT, [id])
    expect(result.calibration_eligible).toHaveLength(1)
    expect(result.advisory_only).toHaveLength(0)
    expect(result.outputs[0]!.verifier_id).toBe(id)
  })

  it('places RETRIEVAL_ASSISTED output in calibration_eligible only', async () => {
    const id = uid()
    verifierRegistry.register(makeVerifier(id, { trust: CalibrationDomain.RETRIEVAL_ASSISTED }))
    const result = await executeVerifiers(INPUT, [id])
    expect(result.calibration_eligible).toHaveLength(1)
    expect(result.advisory_only).toHaveLength(0)
  })

  it('places ADVISORY_EXCLUDED output in advisory_only only', async () => {
    const id = uid()
    verifierRegistry.register(makeVerifier(id, { trust: CalibrationDomain.ADVISORY_EXCLUDED }))
    const result = await executeVerifiers(INPUT, [id])
    expect(result.advisory_only).toHaveLength(1)
    expect(result.calibration_eligible).toHaveLength(0)
  })

  it('result and inner arrays are frozen', async () => {
    const id = uid()
    verifierRegistry.register(makeVerifier(id))
    const result = await executeVerifiers(INPUT, [id])
    expect(Object.isFrozen(result)).toBe(true)
    expect(Object.isFrozen(result.outputs)).toBe(true)
    expect(Object.isFrozen(result.calibration_eligible)).toBe(true)
    expect(Object.isFrozen(result.advisory_only)).toBe(true)
  })

  it('artifact_hash is a 64-char lowercase hex string', async () => {
    const id = uid()
    verifierRegistry.register(makeVerifier(id))
    const result = await executeVerifiers(INPUT, [id])
    expect(result.outputs[0]!.artifact_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('correlation_matrix has reciprocal 1.0 entries when two verifiers agree', async () => {
    const a = uid()
    const b = uid()
    verifierRegistry.register(makeVerifier(a, { pass: true }))
    verifierRegistry.register(makeVerifier(b, { pass: true }))
    const result = await executeVerifiers(INPUT, [a, b])
    expect(result.correlation_matrix[a]![b]).toBe(1.0)
    expect(result.correlation_matrix[b]![a]).toBe(1.0)
  })

  it('correlation_matrix has 0.0 entries when two verifiers disagree', async () => {
    const a = uid()
    const b = uid()
    verifierRegistry.register(makeVerifier(a, { pass: true }))
    verifierRegistry.register(makeVerifier(b, { pass: false }))
    const result = await executeVerifiers(INPUT, [a, b])
    expect(result.correlation_matrix[a]![b]).toBe(0.0)
    expect(result.correlation_matrix[b]![a]).toBe(0.0)
  })

  it('silently skips a verifier whose verify() throws synchronously', async () => {
    const id = uid()
    verifierRegistry.register(makeVerifier(id, { throws: true }))
    const result = await executeVerifiers(INPUT, [id])
    expect(result.outputs).toHaveLength(0)
  })

  it('correlation_alert is false with fewer than 10 calibration_eligible outputs', async () => {
    const ids: string[] = []
    for (let i = 0; i < 9; i++) {
      const id = uid()
      verifierRegistry.register(makeVerifier(id, { trust: CalibrationDomain.GROUND_TRUTH, pass: true }))
      ids.push(id)
    }
    const result = await executeVerifiers(INPUT, ids)
    expect(result.calibration_eligible).toHaveLength(9)
    expect(result.correlation_alert).toBe(false)
  })

  it('correlation_alert is true when ≥10 calibration_eligible verifiers all agree', async () => {
    const ids: string[] = []
    for (let i = 0; i < 10; i++) {
      const id = uid()
      verifierRegistry.register(makeVerifier(id, { trust: CalibrationDomain.GROUND_TRUTH, pass: true }))
      ids.push(id)
    }
    const result = await executeVerifiers(INPUT, ids)
    expect(result.calibration_eligible).toHaveLength(10)
    expect(result.correlation_alert).toBe(true)
  })
})
