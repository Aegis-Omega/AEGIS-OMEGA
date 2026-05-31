// ============================================================
// SOVEREIGN OMEGA — ConstitutionalAuditLog (EU AI Act Art. 12)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// Immutable, tamper-evident record linking GovernanceDecision IDs
// to committed block indices. Each AuditTrailEntry carries:
//   audit_hash = SHA-256({decision_id, block_index,
//                          state_root_at_block, governance_hash})
// The log_root is a Merkle root over all audit_hash values.
// Any tampered entry causes verifyAll() to return false.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue, computeMerkleRootFromValues } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { CommittedBlock } from './block.js'

export const AUDIT_LOG_VERSION = '1.0.0' as const

export class AuditLogError extends Error {
  override readonly name = 'AuditLogError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface AuditTrailEntry {
  /** Governance decision identifier from GovernanceDecision.decision_id. */
  readonly decision_id: string
  /** Index of the CommittedBlock that contains this decision. */
  readonly block_index: number
  /** state_root_after of that block — binds this entry to the chain state. */
  readonly state_root_at_block: SHA256Hex
  /** SHA-256 of the GovernanceDecision (from LedgerEntry.governance_hash). */
  readonly governance_hash: SHA256Hex
  /** SHA-256({decision_id, block_index, state_root_at_block, governance_hash}). */
  readonly audit_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export interface AuditLogSnapshot {
  readonly entries: readonly AuditTrailEntry[]
  /** Merkle root of all audit_hash values in order. */
  readonly log_root: SHA256Hex
  readonly entry_count: number
  readonly schema_version: typeof AUDIT_LOG_VERSION
}

// ─── Build helpers ─────────────────────────────────────────

/** Build one AuditTrailEntry, deriving audit_hash from all fields. */
export async function buildAuditEntry(
  decision_id: string,
  block: CommittedBlock,
  governance_hash: SHA256Hex,
): Promise<AuditTrailEntry> {
  if (!decision_id.trim()) {
    throw new AuditLogError('decision_id must be a non-empty string')
  }
  const audit_hash = await hashValue({
    decision_id,
    block_index: block.index,
    state_root_at_block: block.state_root_after,
    governance_hash,
  })
  return deepFreeze<AuditTrailEntry>({
    decision_id,
    block_index:          block.index,
    state_root_at_block:  block.state_root_after,
    governance_hash,
    audit_hash,
    is_replay_reconstructable: true,
  })
}

/** Verify one AuditTrailEntry's audit_hash. Returns false on mismatch. */
export async function verifyAuditEntry(entry: AuditTrailEntry): Promise<boolean> {
  const expected = await hashValue({
    decision_id:         entry.decision_id,
    block_index:         entry.block_index,
    state_root_at_block: entry.state_root_at_block,
    governance_hash:     entry.governance_hash,
  })
  return entry.audit_hash === expected
}

// ─── Immutable append-only log ─────────────────────────────

export class ConstitutionalAuditLog {
  private readonly _entries: readonly AuditTrailEntry[]

  private constructor(entries: readonly AuditTrailEntry[]) {
    this._entries = entries
  }

  static empty(): ConstitutionalAuditLog {
    return new ConstitutionalAuditLog(deepFreeze([]))
  }

  /**
   * Append an entry. block_index must be >= all previous entries' block_index
   * (monotonic — multiple entries per block are allowed).
   * Throws AuditLogError on block_index regression.
   */
  append(entry: AuditTrailEntry): ConstitutionalAuditLog {
    const last = this._entries[this._entries.length - 1]
    if (last !== undefined && entry.block_index < last.block_index) {
      throw new AuditLogError(
        `block_index ${entry.block_index} is less than previous ${last.block_index}`,
      )
    }
    return new ConstitutionalAuditLog(deepFreeze([...this._entries, entry]))
  }

  /**
   * Verify all entries' audit_hashes. Returns false on the first mismatch.
   * Also checks block_index monotonicity.
   */
  async verifyAll(): Promise<boolean> {
    for (let i = 0; i < this._entries.length; i++) {
      const entry = this._entries[i]!
      if (!(await verifyAuditEntry(entry))) return false
      if (i > 0 && entry.block_index < this._entries[i - 1]!.block_index) return false
    }
    return true
  }

  /** Produce an immutable snapshot with a Merkle root over all audit_hashes. */
  async snapshot(): Promise<AuditLogSnapshot> {
    const hashes: SHA256Hex[] = this._entries.map(e => e.audit_hash)
    const log_root = hashes.length > 0
      ? await computeMerkleRootFromValues(hashes as readonly unknown[])
      : await hashValue({ empty: true })  // deterministic empty-log root

    return deepFreeze<AuditLogSnapshot>({
      entries:      deepFreeze([...this._entries]),
      log_root,
      entry_count:  this._entries.length,
      schema_version: AUDIT_LOG_VERSION,
    })
  }

  get length(): number { return this._entries.length }

  getAll(): readonly AuditTrailEntry[] { return this._entries }
}
