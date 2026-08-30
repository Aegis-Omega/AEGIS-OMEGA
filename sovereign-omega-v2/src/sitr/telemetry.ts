// ============================================================
// SITR Telemetry — pure computation of SITR runtime metrics
// EPISTEMIC TIER: T1 (provisional; T2 thresholds under review)
// No wall-clock. No side effects. All metrics bounded.
// ============================================================

import type { SITRState, SITRTelemetrySnapshot } from './types.js'

// [0,1] fraction of sequences that contained an intervention
export function computeEscalationRate(
  interventions: number,
  totalSequences: number
): number {
  if (totalSequences === 0) return 0
  return Math.min(1, interventions / totalSequences)
}

export function buildSITRTelemetry(params: {
  currentState: SITRState
  interventionCount: number
  containmentActionsTaken: number
  replayViolationsDetected: number
  orchestrationAnomaliesDetected: number
  totalSequences: number
}): SITRTelemetrySnapshot {
  return Object.freeze({
    current_state: params.currentState,
    intervention_count: params.interventionCount,
    containment_actions_taken: params.containmentActionsTaken,
    replay_violations_detected: params.replayViolationsDetected,
    orchestration_anomalies_detected: params.orchestrationAnomaliesDetected,
    escalation_rate: computeEscalationRate(params.interventionCount, params.totalSequences),
  })
}
