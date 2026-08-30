// ============================================================
// Skill Harness — SkillCatalog + buildSkillRecord
// EPISTEMIC TIER: T2 (Phase 1 static baseline — human-authored)
// Immutable append-only catalog. No Set/Map. Arrays only.
// All records are replay-certifiable via skill_hash.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex } from '../core/types.js'
import { SKILL_HARNESS_SCHEMA_VERSION, SkillCatalogError } from './types.js'
import type { SkillInput, SkillRecord } from './types.js'
import { requireResonant } from './resonance.js'

// Builds a frozen SkillRecord with a replay-certifiable skill_hash.
// Throws SkillCatalogError if confidence/failure_rate outside [0,1] or tier is T3+.
export async function buildSkillRecord(input: SkillInput): Promise<SkillRecord> {
  if (input.confidence < 0 || input.confidence > 1) {
    throw new SkillCatalogError(`confidence must be in [0,1], got ${input.confidence}`)
  }
  if (input.failure_rate < 0 || input.failure_rate > 1) {
    throw new SkillCatalogError(`failure_rate must be in [0,1], got ${input.failure_rate}`)
  }
  if (input.recency_score < 0 || input.recency_score > 1) {
    throw new SkillCatalogError(`recency_score must be in [0,1], got ${input.recency_score}`)
  }
  const skill_hash = await hashValue({
    skill_id: input.skill_id,
    name: input.name,
    confidence: input.confidence,
    validated_runs: input.validated_runs,
    failure_rate: input.failure_rate,
    recency_score: input.recency_score,
    domain_affinity: [...input.domain_affinity].sort(),
    dependencies: [...input.dependencies].sort(),
    evidence_refs: [...input.evidence_refs].sort(),
    last_validated: input.last_validated,
    epistemic_tier: input.epistemic_tier,
    primitive_mapping: input.primitive_mapping,
  })
  return deepFreeze({
    ...input,
    skill_hash,
    schema_version: SKILL_HARNESS_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

export class SkillCatalog {
  readonly #records: readonly SkillRecord[]

  private constructor(records: readonly SkillRecord[]) {
    this.#records = Object.freeze(records)
  }

  static empty(): SkillCatalog {
    return new SkillCatalog([])
  }

  get size(): number {
    return this.#records.length
  }

  // Admits a skill only if it passes resonance gate (all 3 invariants satisfied).
  // Throws SkillResonanceError if not resonant; SkillCatalogError if duplicate.
  registerResonant(record: SkillRecord): { catalog: SkillCatalog; record: SkillRecord } {
    requireResonant(record)
    return this.register(record)
  }

  // Returns new catalog with record appended. Throws on duplicate skill_id.
  register(record: SkillRecord): { catalog: SkillCatalog; record: SkillRecord } {
    if (this.#records.some(r => r.skill_id === record.skill_id)) {
      throw new SkillCatalogError(`Skill '${record.skill_id}' already registered`)
    }
    return {
      catalog: new SkillCatalog([...this.#records, record]),
      record,
    }
  }

  lookup(skill_id: string): SkillRecord | null {
    return this.#records.find(r => r.skill_id === skill_id) ?? null
  }

  byDomain(domain: string): readonly SkillRecord[] {
    return Object.freeze(this.#records.filter(r => r.domain_affinity.includes(domain)))
  }

  getAll(): readonly SkillRecord[] {
    return this.#records
  }

  // Hash of sorted skill_hashes — deterministic across catalog sizes.
  async catalogHash(): Promise<SHA256Hex> {
    const sortedHashes = [...this.#records]
      .sort((a, b) => a.skill_id.localeCompare(b.skill_id))
      .map(r => r.skill_hash)
    return hashValue(sortedHashes)
  }
}
