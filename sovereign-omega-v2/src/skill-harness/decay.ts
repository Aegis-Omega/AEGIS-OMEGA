// ============================================================
// Skill Harness — Skill Decay Engine
// EPISTEMIC TIER: T2 · Gate 162
//
// Operational competency becomes stale without recent validation.
// Decay is gradual (confidence reduction) before hard rejection.
//
// Decay formula:
//   decay_factor = 0.5 ^ (inactive_days / HALF_LIFE_DAYS)
//   new_confidence = confidence * decay_factor
//
// Grace period: no decay within GRACE_PERIOD_DAYS of last_validated.
// Decay only applies when inactive_days > GRACE_PERIOD_DAYS.
//
// Penalty:
//   failure_rate >= FAILURE_RATE_PENALTY_THRESHOLD → additional × 0.9
//
// current_timestamp_ms must come from the event substrate — not Date.now().
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import { buildSkillRecord } from './catalog.js'
import type { SkillRecord } from './types.js'

export const DECAY_SCHEMA_VERSION = '1.0.0' as const

export const HALF_LIFE_DAYS = 30           // confidence halves every 30 days of inactivity
export const GRACE_PERIOD_DAYS = 7         // no decay within 7 days of last validation
export const FAILURE_RATE_PENALTY_THRESHOLD = 0.5  // additional decay penalty

export interface DecayResult {
  readonly updated_skill: SkillRecord
  readonly was_decayed: boolean         // true if any decay was applied
  readonly days_inactive: number        // days since last_validated
  readonly decay_factor: number         // multiplier applied to confidence (1.0 = no decay)
  readonly decay_hash: SHA256Hex        // hashValue({skill_id, days_inactive, factor})
  readonly schema_version: typeof DECAY_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SkillDecayError extends Error {
  override readonly name = 'SkillDecayError'
}

// Returns days between two ISO 8601 timestamp strings.
// Fractional days not preserved — integer truncation.
function daysBetween(isoFrom: string, toMs: number): number {
  const fromMs = Date.parse(isoFrom)
  if (isNaN(fromMs)) return 0
  const diffMs = toMs - fromMs
  return diffMs > 0 ? Math.floor(diffMs / 86_400_000) : 0
}

// Applies inactivity decay to a skill. current_timestamp_ms from event substrate.
// Throws SkillDecayError if current_timestamp_ms is before last_validated.
export async function decaySkill(
  skill: SkillRecord,
  current_timestamp_ms: number,
): Promise<DecayResult> {
  const days_inactive = daysBetween(skill.last_validated, current_timestamp_ms)

  if (days_inactive < 0) {
    throw new SkillDecayError(
      `current_timestamp_ms is before last_validated for skill '${skill.skill_id}'`,
    )
  }

  let decay_factor = 1.0
  let was_decayed = false

  if (days_inactive > GRACE_PERIOD_DAYS) {
    // Exponential half-life decay
    const active_days = days_inactive - GRACE_PERIOD_DAYS
    decay_factor = Math.pow(0.5, active_days / HALF_LIFE_DAYS)

    // Penalty for high failure rate
    if (skill.failure_rate >= FAILURE_RATE_PENALTY_THRESHOLD) {
      decay_factor *= 0.9
    }

    was_decayed = true
  }

  const new_confidence = Math.max(0, skill.confidence * decay_factor)

  // Recency score also decays — faster (halves every 14 days)
  const recency_decay = was_decayed
    ? Math.pow(0.5, (days_inactive - GRACE_PERIOD_DAYS) / 14)
    : 1.0
  const new_recency_score = Math.max(0, skill.recency_score * recency_decay)

  const updated_skill = await buildSkillRecord({
    skill_id: skill.skill_id,
    name: skill.name,
    confidence: new_confidence,
    validated_runs: skill.validated_runs,
    failure_rate: skill.failure_rate,
    recency_score: new_recency_score,
    domain_affinity: skill.domain_affinity,
    dependencies: skill.dependencies,
    evidence_refs: skill.evidence_refs,
    last_validated: skill.last_validated,  // last_validated unchanged — decay doesn't validate
    epistemic_tier: skill.epistemic_tier,
    primitive_mapping: skill.primitive_mapping,
  })

  const decay_hash = await hashValue({
    skill_id: skill.skill_id,
    days_inactive: days_inactive.toString(),
    decay_factor: decay_factor.toString(),
  }) as SHA256Hex

  return deepFreeze({
    updated_skill,
    was_decayed,
    days_inactive,
    decay_factor,
    decay_hash,
    schema_version: DECAY_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}
