// ============================================================
// SOVEREIGN OMEGA — Verifier Execution Engine
// EPISTEMIC TIER: T0/T1
// Verifier isolation: separate execution contexts per class.
// Correlation monitoring: tracks cross-verifier agreement.
// ============================================================

import type { VerifierOutput, VerifierInput } from './types.js'
import { verifierRegistry } from './registry.js'
import { CalibrationDomain as CD } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'

export interface ExecutionResult {
  readonly outputs: readonly VerifierOutput[]
  readonly calibration_eligible: readonly VerifierOutput[]
  readonly advisory_only: readonly VerifierOutput[]
  readonly correlation_matrix: Readonly<Record<string, Record<string, number>>>
  readonly correlation_alert: boolean
}

const CORRELATION_ALERT_THRESHOLD = 0.95
const MIN_CORRELATION_SAMPLES = 10

export async function executeVerifiers(
  input: VerifierInput,
  verifierIds: readonly string[]
): Promise<ExecutionResult> {
  const outputs: VerifierOutput[] = []

  for (const id of verifierIds) {
    const verifier = verifierRegistry.get(id)
    if (!verifier) continue

    const start = performance.now()
    try {
      const result = await Promise.race([
        verifier.verify(input),
        timeout(verifier.definition.max_latency_ms, id),
      ])

      const artifact_hash = await hashValue({
        verifier_id: id,
        claim_id: input.claim_id,
        passed: result.passed,
        raw_confidence: result.raw_confidence,
      }) as SHA256Hex

      outputs.push({
        ...result,
        latency_ms: performance.now() - start,
        artifact_hash,
      })
    } catch (err) {
      // Verifier failure is logged but does not halt pipeline
      console.warn(`Verifier ${id} failed:`, err)
    }
  }

  const calibration_eligible = outputs.filter(o =>
    o.trust_class === CD.GROUND_TRUTH || o.trust_class === CD.RETRIEVAL_ASSISTED
  )
  const advisory_only = outputs.filter(o => o.trust_class === CD.ADVISORY_EXCLUDED)

  const { matrix, alert } = computeCorrelationMatrix(calibration_eligible)

  return Object.freeze({
    outputs: Object.freeze(outputs),
    calibration_eligible: Object.freeze(calibration_eligible),
    advisory_only: Object.freeze(advisory_only),
    correlation_matrix: Object.freeze(matrix),
    correlation_alert: alert,
  })
}

function computeCorrelationMatrix(
  outputs: readonly VerifierOutput[]
): { matrix: Record<string, Record<string, number>>; alert: boolean } {
  const matrix: Record<string, Record<string, number>> = {}
  let alert = false

  for (let i = 0; i < outputs.length; i++) {
    for (let j = i + 1; j < outputs.length; j++) {
      const a = outputs[i]!
      const b = outputs[j]!
      const agreement = a.passed === b.passed ? 1.0 : 0.0

      if (!matrix[a.verifier_id]) matrix[a.verifier_id] = {}
      if (!matrix[b.verifier_id]) matrix[b.verifier_id] = {}
      matrix[a.verifier_id]![b.verifier_id] = agreement
      matrix[b.verifier_id]![a.verifier_id] = agreement

      if (agreement >= CORRELATION_ALERT_THRESHOLD && outputs.length >= MIN_CORRELATION_SAMPLES) {
        alert = true
      }
    }
  }

  return { matrix, alert }
}

function timeout(ms: number, verifierId: string): Promise<never> {
  return new Promise((_, reject) =>
    setTimeout(() => reject(new Error(`Verifier ${verifierId} timed out after ${ms}ms`)), ms)
  )
}
