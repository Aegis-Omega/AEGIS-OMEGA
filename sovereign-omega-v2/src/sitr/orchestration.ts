// ============================================================
// SITR Orchestration Anomaly Detection — pure functions
// EPISTEMIC TIER: T0 (frame ordering is a constitutional invariant)
// Consumes CoordinationFrame[] from Gate 11 AgentCoordinator.
// ============================================================

import type { CoordinationFrame } from '../agents/types.js'
import type { OrchestrationAnomaly, SITRState } from './types.js'

// Detect ordering violations and non-replay-safe frames.
export function detectOrchestrationAnomalies(
  frames: readonly CoordinationFrame[],
  sequence: number
): readonly OrchestrationAnomaly[] {
  const anomalies: OrchestrationAnomaly[] = []
  for (let i = 0; i < frames.length; i++) {
    const frame = frames[i]
    if (frame === undefined) continue

    if (!frame.replay_safe) {
      anomalies.push(Object.freeze({
        anomaly_id: `anm-nonreplay-${frame.frame_id}`,
        sequence,
        anomaly_type: 'non_replay_safe_frame',
        affected_agent_id: frame.agent_id,
        severity: 'critical' as const,
      }))
    }

    if (i > 0) {
      const prev = frames[i - 1]
      if (prev !== undefined && frame.sequence <= prev.sequence) {
        anomalies.push(Object.freeze({
          anomaly_id: `anm-order-${frame.frame_id}`,
          sequence,
          anomaly_type: 'non_monotonic_frame_sequence',
          affected_agent_id: frame.agent_id,
          severity: 'high' as const,
        }))
      }
    }
  }
  return Object.freeze(anomalies)
}

// Map worst anomaly severity → minimum required SITRState.
export function anomalyToRequiredState(a: OrchestrationAnomaly): SITRState {
  switch (a.severity) {
    case 'critical': return 'CONSTITUTIONAL_RISK'
    case 'high':     return 'UNSTABLE'
    case 'medium':   return 'DEGRADED'
    case 'low':      return 'STABLE'
  }
}
