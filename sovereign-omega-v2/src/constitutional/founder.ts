// ============================================================
// SOVEREIGN OMEGA — Founder Stewardship Record
// EPISTEMIC TIER: T1 · Gate 200
//
// Anchors the originating authorship of the AEGIS-Ω Constitutional
// Runtime in the system's hash chain. The founder_hash commits to
// the exact constitution (4 directives) at time of founding — if
// the constitution changes, the hash becomes invalid.
//
// Stewardship is not authority. It is accountability: the founder
// is the named custodian of the system's constitutional identity,
// not its controller. The constitution governs; the founder authored it.
//
// Constitutional invariant: genesis_sequence = 0n — the founder
// record is anchored before any other sequence in the chain.
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const FOUNDER_SCHEMA_VERSION = '1.0.0' as const

// ─── Stewardship taxonomy ─────────────────────────────────

export type StewardshipClass =
  | 'founding-architect'      // originating author of the constitutional substrate
  | 'contributing-author'     // substantive contributor with named scope
  | 'constitutional-witness'  // chain-of-custody observer

// ─── Founder record ───────────────────────────────────────

export interface FounderRecord {
  readonly founder_name: string
  readonly founder_email: string
  readonly stewardship_class: StewardshipClass
  readonly genesis_sequence: SequenceNumber   // 0n — anchored at genesis
  readonly stewardship_scope: string          // what this founder is steward of
  readonly constitution_hash: SHA256Hex       // hash of the 4 directives at founding time
  readonly founder_hash: SHA256Hex            // hashValue({name, email, class, sequence, scope, constitution_hash})
  readonly schema_version: typeof FOUNDER_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class FounderError extends Error {
  override readonly name = 'FounderError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// ─── Factory ──────────────────────────────────────────────

export async function buildFounderRecord(input: {
  founder_name: string
  founder_email: string
  stewardship_class: StewardshipClass
  stewardship_scope: string
  constitution_hash: SHA256Hex
}): Promise<FounderRecord> {
  const genesis_sequence = 0n as SequenceNumber

  const founder_hash = await hashValue({
    founder_name: input.founder_name,
    founder_email: input.founder_email,
    stewardship_class: input.stewardship_class,
    genesis_sequence: genesis_sequence.toString(),
    stewardship_scope: input.stewardship_scope,
    constitution_hash: input.constitution_hash,
  })

  return deepFreeze<FounderRecord>({
    founder_name: input.founder_name,
    founder_email: input.founder_email,
    stewardship_class: input.stewardship_class,
    genesis_sequence,
    stewardship_scope: input.stewardship_scope,
    constitution_hash: input.constitution_hash,
    founder_hash,
    schema_version: FOUNDER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

// ─── Verification ─────────────────────────────────────────
//
// Recomputes founder_hash from fields and checks it matches.
// Returns false if any field has been tampered with.

export async function verifyFounderRecord(record: FounderRecord): Promise<boolean> {
  const expected = await hashValue({
    founder_name: record.founder_name,
    founder_email: record.founder_email,
    stewardship_class: record.stewardship_class,
    genesis_sequence: record.genesis_sequence.toString(),
    stewardship_scope: record.stewardship_scope,
    constitution_hash: record.constitution_hash,
  })
  return expected === record.founder_hash
}

// ─── Canonical founding record ───────────────────────────
//
// Tarik Skalić — founding architect of the AEGIS-Ω Constitutional Runtime.
// constitution_hash must be passed from getCanonicalDirectives() +
// buildConstitutionHash() to seal the record against the live directives.

export async function buildCanonicalFounderRecord(
  constitutionHash: SHA256Hex,
): Promise<FounderRecord> {
  return buildFounderRecord({
    founder_name: 'Tarik Skalić',
    founder_email: 'tarikskalic33@gmail.com',
    stewardship_class: 'founding-architect',
    stewardship_scope:
      'AEGIS-Ω Constitutional Runtime — constitutional governance substrate, ' +
      'Sovereign Cognition Protocol (four-directive constitution), ' +
      '1/φ holonic governance triad (martingale × swarm × router), ' +
      'Seven-Pillar distributed agent runtime, ' +
      'multi-model BFT consensus at 1/φ',
    constitution_hash: constitutionHash,
  })
}
