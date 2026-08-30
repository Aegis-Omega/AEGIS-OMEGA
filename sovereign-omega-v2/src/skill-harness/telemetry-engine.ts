// ============================================================
// Skill Harness — Phase 2 Telemetry Engine
// EPISTEMIC TIER: T2 · Gate 158
//
// Processes execution evidence (from RalphLoopRecord outcomes) and
// produces updated SkillRecord + SkillEvent.
//
// Confidence update rule (Bayesian-flavored EMA):
//   learning_rate = 0.3 / sqrt(validated_runs + 1)
//   success: confidence += learning_rate * (1 - confidence)
//   failure: confidence -= learning_rate * confidence
//
// Failure rate: cumulative moving average
//   new_failure_rate = (old_rate * old_runs + (0|1)) / new_runs
//
// Recency score: exponential moving average (alpha = 0.2)
//   new_recency = 0.8 * old_recency + 0.2 * (1 | 0)
//
// Invariants preserved: no Date.now(); no Set/Map; deepFreeze outputs;
// evidence.loop_hash appended to evidence_refs (replay-certifiable chain).
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { buildSkillRecord } from './catalog.js'
import type { SkillEventType, SkillRecord } from './types.js'

export const SKILL_TELEMETRY_SCHEMA_VERSION = '1.0.0' as const

// Execution evidence derived from a completed RalphLoopRecord.
// timestamp_ms must come from the event substrate — not Date.now().
export interface SkillEvidence {
  readonly skill_id: string
  readonly agent_id: string
  readonly is_success: boolean       // true if RalphLoopRecord.is_anchored
  readonly loop_hash: SHA256Hex      // from RalphLoopRecord.loop_hash — appended to evidence_refs
  readonly sequence: SequenceNumber
  readonly timestamp_ms: number      // from event substrate (not Date.now)
}

export interface SkillTelemetryResult {
  readonly updated_record: SkillRecord
  readonly event_type: SkillEventType
  readonly event_hash: SHA256Hex     // hashValue({skill_id, event_type, sequence, loop_hash})
  readonly confidence_delta: number  // new_confidence - old_confidence
  readonly schema_version: typeof SKILL_TELEMETRY_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SkillTelemetryError extends Error {
  override readonly name = 'SkillTelemetryError'
}

// Derives event type from current confidence and success outcome.
function classifyEvent(
  old_confidence: number,
  is_success: boolean,
): SkillEventType {
  if (!is_success) return 'SKILL_DEGRADED'
  if (old_confidence >= 0.8) return 'SKILL_REINFORCED'
  return 'SKILL_VALIDATED'
}

// Clamps a number to [0, 1].
function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v))
}

// Core telemetry engine — pure function: (skill, evidence) → TelemetryResult.
// Throws SkillTelemetryError if evidence.skill_id !== skill.skill_id.
export async function processEvidence(
  skill: SkillRecord,
  evidence: SkillEvidence,
): Promise<SkillTelemetryResult> {
  if (evidence.skill_id !== skill.skill_id) {
    throw new SkillTelemetryError(
      `evidence skill_id '${evidence.skill_id}' does not match skill '${skill.skill_id}'`,
    )
  }

  const old_runs = skill.validated_runs
  const new_runs = old_runs + 1

  // Bayesian-flavored learning rate — diminishes as evidence accumulates.
  const learning_rate = 0.3 / Math.sqrt(old_runs + 1)

  const new_confidence = evidence.is_success
    ? clamp01(skill.confidence + learning_rate * (1 - skill.confidence))
    : clamp01(skill.confidence - learning_rate * skill.confidence)

  // Cumulative moving average for failure rate.
  const new_failure_rate = clamp01(
    (skill.failure_rate * old_runs + (evidence.is_success ? 0 : 1)) / new_runs,
  )

  // Exponential moving average for recency score.
  const new_recency_score = clamp01(
    0.8 * skill.recency_score + 0.2 * (evidence.is_success ? 1.0 : 0.0),
  )

  // Append loop_hash to evidence_refs — replay-certifiable chain.
  const new_evidence_refs = Object.freeze([...skill.evidence_refs, evidence.loop_hash])

  // last_validated updates only on success — "validated" means confirmed working.
  const new_last_validated = evidence.is_success
    ? new Date(evidence.timestamp_ms).toISOString()
    : skill.last_validated

  const event_type = classifyEvent(skill.confidence, evidence.is_success)

  const updated_record = await buildSkillRecord({
    skill_id: skill.skill_id,
    name: skill.name,
    confidence: new_confidence,
    validated_runs: new_runs,
    failure_rate: new_failure_rate,
    recency_score: new_recency_score,
    domain_affinity: skill.domain_affinity,
    dependencies: skill.dependencies,
    evidence_refs: new_evidence_refs,
    last_validated: new_last_validated,
    epistemic_tier: skill.epistemic_tier,
    primitive_mapping: skill.primitive_mapping,
  })

  const event_hash = await hashValue({
    skill_id: evidence.skill_id,
    event_type,
    sequence: evidence.sequence.toString(),
    loop_hash: evidence.loop_hash,
  }) as SHA256Hex

  return deepFreeze({
    updated_record,
    event_type,
    event_hash,
    confidence_delta: new_confidence - skill.confidence,
    schema_version: SKILL_TELEMETRY_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}
