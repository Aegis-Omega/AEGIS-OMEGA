// ============================================================
// SOVEREIGN OMEGA — Epoch Synthesis
// EPISTEMIC TIER: T2 · Gate 39
//
// Top-level HARMONIZE output. Binds DFA certificate, topology,
// and lineage into one frozen EpochRecord. The epoch_hash is
// the self-attestation of all epoch artifacts — the epoch's
// constitutional identity.
// primitive_mapping: HASH · replay_mapping: HARMONIZE
// topology_mapping: DFA + LINEAGE + CONSENSUS
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { ExecutionCertificate } from './dfa.js'
import type { GovernanceTopology } from './topology.js'
import { verifyTopology } from './topology.js'
import { buildSelfAttestation } from './attestation.js'
import { deepFreeze } from '../core/immutable.js'

export const EPOCH_SCHEMA_VERSION = '1.0.0' as const

export interface EpochInput {
  readonly dfa_certificate: ExecutionCertificate
  readonly topology: GovernanceTopology
  readonly lineage_terminal_hash: SHA256Hex | null
  readonly capsule_attestation_hash: SHA256Hex | null
}

export interface EpochRecord {
  readonly dfa_certificate_hash: SHA256Hex
  readonly topology_hash: SHA256Hex
  readonly lineage_terminal_hash: SHA256Hex | null
  readonly capsule_attestation_hash: SHA256Hex | null
  readonly sequence: SequenceNumber
  readonly epoch_hash: SHA256Hex
  readonly schema_version: typeof EPOCH_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class EpochError extends Error {
  override readonly name = 'EpochError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export async function synthesizeEpoch(input: EpochInput): Promise<EpochRecord> {
  if (!input.dfa_certificate.is_valid) {
    throw new EpochError('DFA certificate is invalid — epoch cannot be synthesized')
  }

  const topologyOk = await verifyTopology(input.topology)
  if (!topologyOk) {
    throw new EpochError('Topology verification failed — topology_hash does not match fields')
  }

  if (input.dfa_certificate.sequence !== input.topology.sequence) {
    throw new EpochError(
      `Sequence mismatch: DFA certificate seq=${input.dfa_certificate.sequence}, topology seq=${input.topology.sequence}`,
    )
  }

  const attestation = await buildSelfAttestation({
    dfa_certificate_hash: input.dfa_certificate.certificate_hash,
    topology_hash: input.topology.topology_hash,
    lineage_terminal_hash: input.lineage_terminal_hash,
    capsule_attestation_hash: input.capsule_attestation_hash,
    sequence: input.topology.sequence,
  })

  return deepFreeze<EpochRecord>({
    dfa_certificate_hash: input.dfa_certificate.certificate_hash,
    topology_hash: input.topology.topology_hash,
    lineage_terminal_hash: input.lineage_terminal_hash,
    capsule_attestation_hash: input.capsule_attestation_hash,
    sequence: input.topology.sequence,
    epoch_hash: attestation.attestation_hash,
    schema_version: EPOCH_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

export async function verifyEpoch(record: EpochRecord): Promise<boolean> {
  const attestation = await buildSelfAttestation({
    dfa_certificate_hash: record.dfa_certificate_hash,
    topology_hash: record.topology_hash,
    lineage_terminal_hash: record.lineage_terminal_hash,
    capsule_attestation_hash: record.capsule_attestation_hash,
    sequence: record.sequence,
  })
  return attestation.attestation_hash === record.epoch_hash
}
