// ============================================================
// Skill Harness — Probabilistic Competency Types
// EPISTEMIC TIER: T2 (engineering hypothesis — Phase 1 static baseline)
// Source: sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md
// Skills are telemetry-backed probabilistic competency objects.
// They are NOT static labels, prompts, or self-declared capabilities.
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export const SKILL_HARNESS_SCHEMA_VERSION = '1.0.0' as const

// T3+ rejected at catalog admission; T4/T5 not expressible here.
export type SkillEpistemicTier = 'T0' | 'T1' | 'T2'

export type SkillEventType =
  | 'SKILL_VALIDATED'
  | 'SKILL_DEGRADED'
  | 'SKILL_DECAYED'
  | 'SKILL_SPECIALIZED'
  | 'SKILL_REJECTED'
  | 'SKILL_REINFORCED'
  | 'SKILL_TRANSFERRED'
  | 'SKILL_MERGED'
  | 'SKILL_SPLIT'

// Input required to build a SkillRecord — caller provides all fields except skill_hash.
export interface SkillInput {
  readonly skill_id: string
  readonly name: string
  readonly confidence: number               // 0.0–1.0
  readonly validated_runs: number
  readonly failure_rate: number             // 0.0–1.0
  readonly recency_score: number            // 0.0–1.0
  readonly domain_affinity: readonly string[]
  readonly dependencies: readonly string[]  // skill_id references
  readonly evidence_refs: readonly string[] // Drive file IDs or event IDs
  readonly last_validated: string           // ISO 8601
  readonly epistemic_tier: SkillEpistemicTier
  readonly primitive_mapping: string        // constitutional primitive
}

// Full probabilistic competency record — includes replay-certifiable hash.
export interface SkillRecord extends SkillInput {
  readonly skill_hash: SHA256Hex
  readonly schema_version: typeof SKILL_HARNESS_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface SkillEvent {
  readonly skill_id: string
  readonly event_type: SkillEventType
  readonly sequence: SequenceNumber
  readonly event_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export interface RawSkillManifest {
  readonly source: string   // e.g. "github.com/obra/superpowers"
  readonly path: string     // e.g. "skills/git/SKILL.md"
  readonly content: string  // raw SKILL.md file content
}

export interface SkillImportResult {
  readonly admitted: readonly SkillRecord[]
  readonly rejected: readonly { skill_id: string; reason: string }[]
  readonly catalog_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export class SkillCatalogError extends Error {
  override readonly name = 'SkillCatalogError'
}
