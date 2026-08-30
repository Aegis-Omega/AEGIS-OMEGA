// ============================================================
// SOVEREIGN OMEGA — Ontology Reduction Enforcement
// EPISTEMIC TIER: T0 · Gate 33
//
// Implements machine-enforced reduction discipline:
//   unmapped abstractions are constitutionally invalid.
//
// Every new abstraction must declare four mandatory mappings:
//   primitive_mapping  — which T0 primitive it reduces to
//   replay_mapping     — which SHP phase it belongs to
//   topology_mapping   — which GovernanceTopology field it affects
//   epistemic_tier     — T0..T3 only (T4/T5 are constitutionally blocked)
//
// ReductionRegistry is append-only. admitAbstraction() returns
// ADMITTED only when all four mappings are present and the tier
// is within constitutional bounds. REJECTED otherwise.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export const REDUCTION_SCHEMA_VERSION = '1.0.0' as const

// ─── Mapping vocabularies ──────────────────────────────────

/** T0 cryptographic primitives every abstraction must reduce to. */
export type PrimitiveMapping =
  | 'HASH' | 'SEQUENCE' | 'CANONICALIZE' | 'VERIFY' | 'FREEZE'

/** The SHP phase an abstraction belongs to. */
export type ReplayMapping =
  | 'READ' | 'ASSESS' | 'LOCK' | 'PROPAGATE' | 'HARMONIZE'

/** Which GovernanceTopology field the abstraction affects. */
export type TopologyMapping =
  | 'SITR_STATE' | 'AOIE_STATE' | 'VERDICT' | 'LEDGER' | 'CONSENSUS' | 'DFA' | 'LINEAGE'

/** Admissible epistemic tiers. T4/T5 are constitutionally blocked. */
export type EpistemicTier = 'T0' | 'T1' | 'T2' | 'T3'

const BLOCKED_TIERS: ReadonlyArray<string> = ['T4', 'T5']

// ─── Types ─────────────────────────────────────────────────

/**
 * The complete constitutional record for one abstraction.
 * record_hash is hashValue(all fields) — tamper-evident.
 */
export interface OntologyRecord {
  readonly abstraction_id: string
  readonly name: string
  readonly primitive_mapping: PrimitiveMapping
  readonly replay_mapping: ReplayMapping
  readonly topology_mapping: TopologyMapping
  readonly epistemic_tier: EpistemicTier
  readonly sequence: SequenceNumber
  readonly record_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export type AdmissibilityVerdict = 'ADMITTED' | 'REJECTED'

export interface AdmissibilityResult {
  readonly abstraction_id: string
  readonly verdict: AdmissibilityVerdict
  readonly reason: string
  readonly result_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export class ReductionError extends Error {
  constructor(message: string) { super(message); this.name = 'ReductionError' }
}

// ─── OntologyRecord builder ────────────────────────────────

export interface OntologyInput {
  readonly name: string
  readonly primitive_mapping: PrimitiveMapping
  readonly replay_mapping: ReplayMapping
  readonly topology_mapping: TopologyMapping
  readonly epistemic_tier: EpistemicTier
  readonly sequence: SequenceNumber
}

export async function buildOntologyRecord(input: OntologyInput): Promise<OntologyRecord> {
  const payload = {
    name: input.name,
    primitive_mapping: input.primitive_mapping,
    replay_mapping: input.replay_mapping,
    topology_mapping: input.topology_mapping,
    epistemic_tier: input.epistemic_tier,
    sequence: input.sequence,
    schema_version: REDUCTION_SCHEMA_VERSION,
  }
  const abstraction_id = await hashValue(payload) as string
  const record_hash = await hashValue({ abstraction_id, ...payload }) as SHA256Hex
  return deepFreeze<OntologyRecord>({
    abstraction_id, record_hash,
    is_replay_reconstructable: true,
    ...input,
  })
}

// ─── Admissibility judgment ────────────────────────────────

/**
 * Admit an abstraction into the registry. Returns REJECTED if:
 *   - The tier is T4 or T5 (constitutionally blocked)
 *   - A record with the same name already exists (duplication)
 *   - Any required field would be missing (guarded by type system)
 */
export async function admitAbstraction(
  existing: readonly OntologyRecord[],
  record: OntologyRecord,
): Promise<AdmissibilityResult> {
  // Block T4/T5
  if (BLOCKED_TIERS.includes(record.epistemic_tier)) {
    const result_hash = await hashValue({ verdict: 'REJECTED', reason: 'tier_blocked', abstraction_id: record.abstraction_id }) as SHA256Hex
    return deepFreeze<AdmissibilityResult>({
      abstraction_id: record.abstraction_id,
      verdict: 'REJECTED',
      reason: `Tier ${record.epistemic_tier} is constitutionally blocked (T4/T5)`,
      result_hash, is_replay_reconstructable: true,
    })
  }

  // Reject duplicates (same name)
  if (existing.some(r => r.name === record.name)) {
    const result_hash = await hashValue({ verdict: 'REJECTED', reason: 'duplicate', name: record.name }) as SHA256Hex
    return deepFreeze<AdmissibilityResult>({
      abstraction_id: record.abstraction_id,
      verdict: 'REJECTED',
      reason: `Abstraction '${record.name}' is already registered`,
      result_hash, is_replay_reconstructable: true,
    })
  }

  const result_hash = await hashValue({ verdict: 'ADMITTED', abstraction_id: record.abstraction_id }) as SHA256Hex
  return deepFreeze<AdmissibilityResult>({
    abstraction_id: record.abstraction_id,
    verdict: 'ADMITTED',
    reason: 'All four mappings present; tier within constitutional bounds',
    result_hash, is_replay_reconstructable: true,
  })
}

// ─── ReductionRegistry ─────────────────────────────────────

/** Append-only registry of constitutionally admitted ontology records. */
export class ReductionRegistry {
  private readonly _records: readonly OntologyRecord[]
  private readonly _lastSeq: SequenceNumber | null

  private constructor(records: readonly OntologyRecord[], lastSeq: SequenceNumber | null) {
    this._records = records
    this._lastSeq = lastSeq
  }

  static empty(): ReductionRegistry {
    return new ReductionRegistry(deepFreeze([]), null)
  }

  /**
   * Attempt to register an abstraction. Returns the AdmissibilityResult.
   * If ADMITTED, returns a new registry containing the record.
   * If REJECTED, returns the same registry unchanged.
   */
  async register(record: OntologyRecord): Promise<{ registry: ReductionRegistry; result: AdmissibilityResult }> {
    if (this._lastSeq !== null && record.sequence <= this._lastSeq) {
      throw new ReductionError(`Sequence ${record.sequence} must be > last ${this._lastSeq}`)
    }
    const result = await admitAbstraction(this._records, record)
    if (result.verdict === 'ADMITTED') {
      return {
        registry: new ReductionRegistry(deepFreeze([...this._records, record]), record.sequence),
        result,
      }
    }
    return { registry: this, result }
  }

  /** True iff an abstraction with the given name is registered. */
  isKnown(name: string): boolean {
    return this._records.some(r => r.name === name)
  }

  getAll(): readonly OntologyRecord[] { return this._records }
  get length(): number { return this._records.length }
}
