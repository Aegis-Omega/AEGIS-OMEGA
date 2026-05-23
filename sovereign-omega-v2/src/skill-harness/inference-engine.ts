// ============================================================
// Skill Harness — Phase 3 Probabilistic Inference Engine
// EPISTEMIC TIER: T2 · Gate 161
//
// Synthesizes multiple evidence events into a Beta-posterior confidence
// estimate with Wilson score credible interval.
//
// Beta posterior parameters:
//   α = (1 - failure_rate) * validated_runs + 1  (successes + Laplace prior)
//   β = failure_rate * validated_runs + 1         (failures + Laplace prior)
//   posterior_mean = α / (α + β)
//
// Wilson score 90% CI (z = 1.645):
//   Used for confidence_lower / confidence_upper.
//   Returns [0, 1] (uninformative) when validated_runs = 0.
//
// Batch inference:
//   inferSkillConfidence(skill, evidence_batch) applies processEvidence()
//   sequentially then computes the posterior over the resulting record.
//   Idempotent — same evidence_batch always produces the same result.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import { processEvidence } from './telemetry-engine.js'
import type { SkillEvidence } from './telemetry-engine.js'
import type { SkillRecord } from './types.js'

export const INFERENCE_SCHEMA_VERSION = '1.0.0' as const

// 90% credible interval constant.
const WILSON_Z = 1.645

export interface SkillInferenceRecord {
  readonly skill_id: string
  readonly posterior_alpha: number   // α = successes + 1
  readonly posterior_beta: number    // β = failures + 1
  readonly confidence_mean: number   // α / (α + β) — posterior mean
  readonly confidence_lower: number  // Wilson score lower bound (90% CI)
  readonly confidence_upper: number  // Wilson score upper bound (90% CI)
  readonly evidence_count: number    // total evidence events synthesised
  readonly inference_hash: SHA256Hex // hashValue({skill_id, alpha, beta, evidence_count})
  readonly schema_version: typeof INFERENCE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class InferenceEngineError extends Error {
  override readonly name = 'InferenceEngineError'
}

// Wilson score interval. Returns [0, 1] when n = 0 (uninformative prior).
function wilsonScore(p: number, n: number): { lower: number; upper: number } {
  if (n === 0) return { lower: 0, upper: 1 }
  const z2 = WILSON_Z * WILSON_Z
  const denom = 1 + z2 / n
  const center = (p + z2 / (2 * n)) / denom
  const half = (WILSON_Z * Math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
  return {
    lower: Math.max(0, center - half),
    upper: Math.min(1, center + half),
  }
}

// Build SkillInferenceRecord from a fully-updated SkillRecord.
async function buildInference(
  skill: SkillRecord,
  evidence_count: number,
): Promise<SkillInferenceRecord> {
  const successes = skill.validated_runs * (1 - skill.failure_rate)
  const failures = skill.validated_runs * skill.failure_rate
  const alpha = successes + 1
  const beta = failures + 1
  const mean = alpha / (alpha + beta)

  const { lower, upper } = wilsonScore(skill.confidence, skill.validated_runs)

  const inference_hash = await hashValue({
    skill_id: skill.skill_id,
    posterior_alpha: alpha,
    posterior_beta: beta,
    evidence_count: evidence_count.toString(),
  }) as SHA256Hex

  return deepFreeze({
    skill_id: skill.skill_id,
    posterior_alpha: alpha,
    posterior_beta: beta,
    confidence_mean: mean,
    confidence_lower: lower,
    confidence_upper: upper,
    evidence_count,
    inference_hash,
    schema_version: INFERENCE_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

export interface InferenceResult {
  readonly inference: SkillInferenceRecord
  readonly updated_skill: SkillRecord
  readonly is_replay_reconstructable: true
}

// Applies evidence_batch sequentially then synthesises Beta-posterior inference.
// Empty batch returns the inference over the existing skill record unchanged.
// Throws InferenceEngineError if any evidence.skill_id !== skill.skill_id.
export async function inferSkillConfidence(
  skill: SkillRecord,
  evidence_batch: readonly SkillEvidence[],
): Promise<InferenceResult> {
  let current = skill

  for (const evidence of evidence_batch) {
    if (evidence.skill_id !== skill.skill_id) {
      throw new InferenceEngineError(
        `evidence skill_id '${evidence.skill_id}' does not match '${skill.skill_id}'`,
      )
    }
    const result = await processEvidence(current, evidence)
    current = result.updated_record
  }

  const inference = await buildInference(current, evidence_batch.length)
  return deepFreeze({
    inference,
    updated_skill: current,
    is_replay_reconstructable: true as const,
  })
}
