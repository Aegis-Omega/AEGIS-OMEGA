// ============================================================
// SOVEREIGN OMEGA — Self-Attestation Protocol
// EPISTEMIC TIER: T0 · Gate 35
//
// Unified attestation composing DFA cert + topology hash +
// lineage terminal + capsule attestation into one digest.
// primitive_mapping: HASH · replay_mapping: HARMONIZE
// topology_mapping: DFA + LINEAGE
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const ATTESTATION_SCHEMA_VERSION = '1.0.0' as const

export interface AttestationInput {
  readonly dfa_certificate_hash: SHA256Hex
  readonly topology_hash: SHA256Hex
  readonly lineage_terminal_hash: SHA256Hex | null
  readonly capsule_attestation_hash: SHA256Hex | null
  readonly sequence: SequenceNumber
}

export interface SelfAttestationRecord {
  readonly dfa_certificate_hash: SHA256Hex
  readonly topology_hash: SHA256Hex
  readonly lineage_terminal_hash: SHA256Hex | null
  readonly capsule_attestation_hash: SHA256Hex | null
  readonly sequence: SequenceNumber
  readonly attestation_hash: SHA256Hex
  readonly schema_version: typeof ATTESTATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class AttestationError extends Error {
  override readonly name = 'AttestationError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export async function buildSelfAttestation(
  input: AttestationInput,
): Promise<SelfAttestationRecord> {
  const attestation_hash = await hashValue({
    dfa_certificate_hash: input.dfa_certificate_hash,
    topology_hash: input.topology_hash,
    lineage_terminal_hash: input.lineage_terminal_hash ?? 'genesis',
    capsule_attestation_hash: input.capsule_attestation_hash ?? 'none',
    sequence: input.sequence.toString(),
  })

  return deepFreeze<SelfAttestationRecord>({
    dfa_certificate_hash: input.dfa_certificate_hash,
    topology_hash: input.topology_hash,
    lineage_terminal_hash: input.lineage_terminal_hash,
    capsule_attestation_hash: input.capsule_attestation_hash,
    sequence: input.sequence,
    attestation_hash,
    schema_version: ATTESTATION_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

export async function verifySelfAttestation(
  record: SelfAttestationRecord,
): Promise<boolean> {
  const expected = await hashValue({
    dfa_certificate_hash: record.dfa_certificate_hash,
    topology_hash: record.topology_hash,
    lineage_terminal_hash: record.lineage_terminal_hash ?? 'genesis',
    capsule_attestation_hash: record.capsule_attestation_hash ?? 'none',
    sequence: record.sequence.toString(),
  })
  return expected === record.attestation_hash
}
