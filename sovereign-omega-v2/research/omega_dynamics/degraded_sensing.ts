// ============================================================
// SOVEREIGN OMEGA — T3 Degraded-Sensing Reconstruction Falsifier
// EPISTEMIC TIER: T3 (research conjecture)
//
// Architectural analogy only. Integer/Q16 research state; no write-back,
// no production control, and inferred values never become measured values.
// ============================================================

import { T3_RESEARCH_ONLY, WRITE_BACK_AUTHORITY } from './types.js'

export const DSR_SCHEMA_VERSION = '1.0.0' as const
export const DSR_AUTHORITY_EFFECT = 'NONE' as const

export type DsrMethodV1 = 'HOLD_LAST' | 'LINEAR_DYNAMICS'

export interface DsrFrameV1 {
  readonly sequence: string
  readonly values_q16: readonly (number | null)[]
}

export interface DsrReconstructionV1 {
  readonly schema_version: typeof DSR_SCHEMA_VERSION
  readonly method_id: DsrMethodV1
  readonly sequence: string
  readonly values_q16: readonly (number | null)[]
  readonly inferred_mask: readonly boolean[]
  readonly uncertainty_radius_q16: readonly (number | null)[]
  readonly unavailable_channels: readonly number[]
  readonly t3_research_only: typeof T3_RESEARCH_ONLY
  readonly write_back_authority: typeof WRITE_BACK_AUTHORITY
  readonly authority_effect: typeof DSR_AUTHORITY_EFFECT
}

export interface DsrEvaluationV1 {
  readonly evaluated_inferred_channels: number
  readonly unavailable_channels: number
  readonly mean_absolute_error_q16: number | null
  readonly uncertainty_bound_violations: number
}

function assertSequence(sequence: string): void {
  if (!/^(0|[1-9][0-9]*)$/.test(sequence)) {
    throw new TypeError('sequence must be a canonical unsigned decimal string')
  }
}

function assertQ16(value: number | null, field: string): void {
  if (value === null) return
  if (!Number.isSafeInteger(value)) {
    throw new TypeError(`${field} must be a safe integer Q16 value or null`)
  }
}

function assertFrame(frame: DsrFrameV1): void {
  assertSequence(frame.sequence)
  frame.values_q16.forEach((value, index) => assertQ16(value, `values_q16[${index}]`))
}

function sameWidth(a: DsrFrameV1, b: DsrFrameV1): boolean {
  return a.values_q16.length === b.values_q16.length
}

function safeLinear(previous: number, latest: number): number | null {
  const value = latest + (latest - previous)
  return Number.isSafeInteger(value) ? value : null
}

function uncertaintyRadius(
  previous: number | null | undefined,
  latest: number | null | undefined,
): number | null {
  if (previous === null || previous === undefined || latest === null || latest === undefined) {
    return null
  }
  const radius = Math.abs(latest - previous)
  return Number.isSafeInteger(radius) ? radius : null
}

export function reconstructDegradedFrameV1(input: {
  readonly method: DsrMethodV1
  readonly current: DsrFrameV1
  readonly latest_complete_or_partial: DsrFrameV1 | null
  readonly previous_complete_or_partial: DsrFrameV1 | null
}): DsrReconstructionV1 {
  assertFrame(input.current)
  if (input.latest_complete_or_partial) assertFrame(input.latest_complete_or_partial)
  if (input.previous_complete_or_partial) assertFrame(input.previous_complete_or_partial)

  const width = input.current.values_q16.length
  for (const prior of [input.latest_complete_or_partial, input.previous_complete_or_partial]) {
    if (prior && !sameWidth(input.current, prior)) {
      throw new TypeError('all DSR frames must have identical channel width')
    }
  }

  const values: Array<number | null> = []
  const inferred: boolean[] = []
  const uncertainty: Array<number | null> = []
  const unavailable: number[] = []

  for (let index = 0; index < width; index += 1) {
    const observed = input.current.values_q16[index] ?? null
    if (observed !== null) {
      values.push(observed)
      inferred.push(false)
      uncertainty.push(0)
      continue
    }

    const latest = input.latest_complete_or_partial?.values_q16[index] ?? null
    const previous = input.previous_complete_or_partial?.values_q16[index] ?? null
    let reconstructed: number | null = null

    if (input.method === 'HOLD_LAST') {
      reconstructed = latest
    } else if (input.method === 'LINEAR_DYNAMICS') {
      if (latest !== null && previous !== null) {
        reconstructed = safeLinear(previous, latest)
      }
    } else {
      const exhaustive: never = input.method
      throw new TypeError(`unsupported DSR method: ${String(exhaustive)}`)
    }

    values.push(reconstructed)
    inferred.push(reconstructed !== null)
    uncertainty.push(
      reconstructed === null ? null : uncertaintyRadius(previous, latest),
    )
    if (reconstructed === null) unavailable.push(index)
  }

  return Object.freeze({
    schema_version: DSR_SCHEMA_VERSION,
    method_id: input.method,
    sequence: input.current.sequence,
    values_q16: Object.freeze(values),
    inferred_mask: Object.freeze(inferred),
    uncertainty_radius_q16: Object.freeze(uncertainty),
    unavailable_channels: Object.freeze(unavailable),
    t3_research_only: T3_RESEARCH_ONLY,
    write_back_authority: WRITE_BACK_AUTHORITY,
    authority_effect: DSR_AUTHORITY_EFFECT,
  })
}

export function evaluateDsrReconstructionV1(
  reconstruction: DsrReconstructionV1,
  groundTruthQ16: readonly number[],
): DsrEvaluationV1 {
  if (groundTruthQ16.length !== reconstruction.values_q16.length) {
    throw new TypeError('ground truth width must match reconstructed frame width')
  }
  groundTruthQ16.forEach((value, index) => assertQ16(value, `groundTruthQ16[${index}]`))

  let evaluated = 0
  let errorSum = 0
  let boundViolations = 0

  for (let index = 0; index < groundTruthQ16.length; index += 1) {
    if (!reconstruction.inferred_mask[index]) continue
    const predicted = reconstruction.values_q16[index]
    const truth = groundTruthQ16[index]
    if (predicted === null || truth === undefined) continue

    const error = Math.abs(predicted - truth)
    if (!Number.isSafeInteger(error) || !Number.isSafeInteger(errorSum + error)) {
      throw new RangeError('DSR evaluation overflow')
    }
    errorSum += error
    evaluated += 1

    const radius = reconstruction.uncertainty_radius_q16[index]
    if (radius !== null && radius !== undefined && error > radius) {
      boundViolations += 1
    }
  }

  return Object.freeze({
    evaluated_inferred_channels: evaluated,
    unavailable_channels: reconstruction.unavailable_channels.length,
    mean_absolute_error_q16: evaluated > 0 ? Math.floor(errorSum / evaluated) : null,
    uncertainty_bound_violations: boundViolations,
  })
}
