// ============================================================
// Workflow Types — replay-safe workflow definitions
// EPISTEMIC TIER: T1
// All workflows must be replay-safe (is_replay_safe = true required).
// ============================================================

import type { SHA256Hex } from '../../core/types'
import type { WorkflowType } from '../types'

export const WORKFLOW_SCHEMA_VERSION = '1.0.0' as const

export interface WorkflowReplayFrame {
  readonly frame_id: string
  readonly workflow_id: string
  readonly sequence: number
  readonly step_type: string
  readonly input_hash: SHA256Hex
  readonly output_hash: SHA256Hex
  readonly invariant_satisfied: boolean
}

export interface WorkflowDefinition {
  readonly workflow_type: WorkflowType
  readonly required_capabilities: readonly string[]
  readonly max_mutations: number
  readonly is_replay_safe: boolean
}

export const BUILT_IN_WORKFLOWS: readonly WorkflowDefinition[] = Object.freeze([
  { workflow_type: 'research', required_capabilities: ['telemetry'], max_mutations: 0, is_replay_safe: true },
  { workflow_type: 'refactor', required_capabilities: ['filesystem'], max_mutations: 50, is_replay_safe: true },
  { workflow_type: 'replay-audit', required_capabilities: ['telemetry'], max_mutations: 0, is_replay_safe: true },
  { workflow_type: 'ontology-review', required_capabilities: ['telemetry'], max_mutations: 0, is_replay_safe: true },
  { workflow_type: 'environment-scan', required_capabilities: ['filesystem'], max_mutations: 10, is_replay_safe: true },
  { workflow_type: 'extension-review', required_capabilities: ['telemetry'], max_mutations: 0, is_replay_safe: true },
  { workflow_type: 'telemetry-analysis', required_capabilities: ['telemetry'], max_mutations: 0, is_replay_safe: true },
] as const)
