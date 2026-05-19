// ============================================================
// SITR — Systemic Intervention & Threat Response Types
// EPISTEMIC TIER: T0 (constitutional runtime defense layer)
// HOLONIC SCALE: CELLULAR (SITR layer) → ORGANISM (runtime)
// All state transitions are monotonic and replay-reconstructable.
// SITR never directly mutates agent/workflow state.
// Directives flow through E5 event substrate (phase 3 of frame execution contract).
// ============================================================

export const SITR_SCHEMA_VERSION = '1.0.0' as const

// Monotonic escalation lattice — STABLE is lowest, COMPROMISED is terminal.
// No de-escalation without explicit constitutional reset event.
export type SITRState =
  | 'STABLE'
  | 'DEGRADED'
  | 'UNSTABLE'
  | 'CONSTITUTIONAL_RISK'
  | 'CONTAINED'
  | 'COMPROMISED'

// Actions emitted by SITR as E5 events. Enforcement engine applies them deterministically.
export type ContainmentAction =
  | 'quarantine_agent'
  | 'freeze_workflow'
  | 'block_frame'
  | 'invalidate_replay_chain'
  | 'elevate_state'

export interface ContainmentDirective {
  readonly directive_id: string
  readonly sequence: number
  readonly action: ContainmentAction
  readonly target_id: string
  readonly reason: string
  readonly is_replay_reconstructable: true
}

export interface InterventionRecord {
  readonly record_id: string
  readonly sequence: number
  readonly prior_state: SITRState
  readonly next_state: SITRState
  readonly trigger: string
  readonly directive_ids: readonly string[]
  readonly is_replay_reconstructable: true
}

export interface OrchestrationAnomaly {
  readonly anomaly_id: string
  readonly sequence: number
  readonly anomaly_type: string
  readonly affected_agent_id?: string
  readonly severity: 'low' | 'medium' | 'high' | 'critical'
}

export interface ReplayViolation {
  readonly violation_id: string
  readonly sequence: number
  readonly violation_type: string
  readonly affected_workflow_id?: string
  readonly affected_frame_id?: string
}

export interface SITRTelemetrySnapshot {
  readonly current_state: SITRState
  readonly intervention_count: number
  readonly containment_actions_taken: number
  readonly replay_violations_detected: number
  readonly orchestration_anomalies_detected: number
  readonly escalation_rate: number
}

export class SITRConstraintError extends Error {
  constructor(msg: string) {
    super(msg)
    this.name = 'SITRConstraintError'
  }
}
