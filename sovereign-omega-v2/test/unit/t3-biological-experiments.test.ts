import { describe, expect, it } from 'vitest'

import {
  evaluateDsrReconstructionV1,
  reconstructDegradedFrameV1,
} from '../../research/omega_dynamics/degraded_sensing.js'
import {
  selectResourceAwareRouteV1,
  selectStaticAdmittedRouteV1,
  type ResourceStateV1,
  type RouteCandidateV1,
} from '../../research/omega_dynamics/resource_routing.js'

describe('T3 degraded-sensing reconstruction', () => {
  it('keeps inferred state explicitly separate and preserves zero authority', () => {
    const reconstruction = reconstructDegradedFrameV1({
      method: 'LINEAR_DYNAMICS',
      previous_complete_or_partial: { sequence: '1', values_q16: [10, 20] },
      latest_complete_or_partial: { sequence: '2', values_q16: [20, 20] },
      current: { sequence: '3', values_q16: [null, 20] },
    })

    expect(reconstruction.values_q16).toEqual([30, 20])
    expect(reconstruction.inferred_mask).toEqual([true, false])
    expect(reconstruction.t3_research_only).toBe(true)
    expect(reconstruction.write_back_authority).toBe(false)
    expect(reconstruction.authority_effect).toBe('NONE')

    const evaluation = evaluateDsrReconstructionV1(reconstruction, [30, 20])
    expect(evaluation.mean_absolute_error_q16).toBe(0)
    expect(evaluation.uncertainty_bound_violations).toBe(0)
  })

  it('makes missing history unavailable instead of inventing state', () => {
    const reconstruction = reconstructDegradedFrameV1({
      method: 'LINEAR_DYNAMICS',
      previous_complete_or_partial: null,
      latest_complete_or_partial: null,
      current: { sequence: '8', values_q16: [null, 4] },
    })

    expect(reconstruction.values_q16).toEqual([null, 4])
    expect(reconstruction.unavailable_channels).toEqual([0])
    expect(reconstruction.inferred_mask).toEqual([false, false])
  })

  it('keeps a negative control: linear dynamics is not assumed universally superior', () => {
    const history = {
      previous_complete_or_partial: { sequence: '1', values_q16: [0] },
      latest_complete_or_partial: { sequence: '2', values_q16: [10] },
      current: { sequence: '3', values_q16: [null] },
    } as const

    const hold = reconstructDegradedFrameV1({ method: 'HOLD_LAST', ...history })
    const linear = reconstructDegradedFrameV1({ method: 'LINEAR_DYNAMICS', ...history })

    const holdEval = evaluateDsrReconstructionV1(hold, [9])
    const linearEval = evaluateDsrReconstructionV1(linear, [9])

    expect(holdEval.mean_absolute_error_q16).toBe(1)
    expect(linearEval.mean_absolute_error_q16).toBe(11)
  })
})

describe('T3 resource-aware routing', () => {
  const state: ResourceStateV1 = {
    uncertainty_ppm: 100_000,
    criticality: 1,
    max_latency_ms: 1_000,
    max_cost_units: 1_000,
  }

  const candidates: readonly RouteCandidateV1[] = [
    {
      candidate_id: 'denied-high-score',
      authority_admitted: false,
      predicted_correct_ppm: 999_999,
      calibration_error_ppm: 0,
      latency_ms: 10,
      cost_units: 10,
    },
    {
      candidate_id: 'cheap',
      authority_admitted: true,
      predicted_correct_ppm: 780_000,
      calibration_error_ppm: 40_000,
      latency_ms: 100,
      cost_units: 100,
    },
    {
      candidate_id: 'strong',
      authority_admitted: true,
      predicted_correct_ppm: 900_000,
      calibration_error_ppm: 20_000,
      latency_ms: 400,
      cost_units: 300,
    },
  ]

  it('never turns a denied candidate into authority', () => {
    const decision = selectResourceAwareRouteV1(state, candidates)
    expect(decision.outcome).toBe('ROUTED')
    expect(decision.selected_candidate_id).not.toBe('denied-high-score')
    expect(decision.t3_research_only).toBe(true)
    expect(decision.write_back_authority).toBe(false)
    expect(decision.authority_effect).toBe('NONE')
  })

  it('abstains when no admitted candidate satisfies a critical reliability floor', () => {
    const strict: ResourceStateV1 = {
      ...state,
      uncertainty_ppm: 500_000,
      criticality: 3,
    }
    const weak: readonly RouteCandidateV1[] = [{
      candidate_id: 'weak',
      authority_admitted: true,
      predicted_correct_ppm: 700_000,
      calibration_error_ppm: 100_000,
      latency_ms: 100,
      cost_units: 100,
    }]
    const decision = selectResourceAwareRouteV1(strict, weak)
    expect(decision.outcome).toBe('ABSTAIN')
    expect(decision.reason).toBe('INSUFFICIENT_RELIABILITY')
  })

  it('keeps the static admitted route as an explicit falsifier baseline', () => {
    const staticDecision = selectStaticAdmittedRouteV1(state, candidates)
    const adaptiveDecision = selectResourceAwareRouteV1(state, candidates)

    expect(staticDecision.selected_candidate_id).toBe('cheap')
    expect(adaptiveDecision.selected_candidate_id).toBe('strong')
  })
})
