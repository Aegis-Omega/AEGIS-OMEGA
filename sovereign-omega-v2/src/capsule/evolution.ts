// ============================================================
// SOVEREIGN OMEGA — Capability Evolution Protocol
// EPISTEMIC TIER: T2 · Gate 37
//
// Capsule manifests propose capability expansions through the
// constitutional assessment engine. Proposals are ASSESS-phase
// objects — not yet committed (pre-LOCK).
// primitive_mapping: SEQUENCE · replay_mapping: ASSESS
// topology_mapping: DFA
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { CapsuleCapabilityType, CapsuleManifest } from './types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const EVOLUTION_SCHEMA_VERSION = '1.0.0' as const

export type EvolutionVerdict = 'APPROVED' | 'REJECTED'

export interface CapabilityProposal {
  readonly proposal_id: SHA256Hex
  readonly capsule_id: string
  readonly proposed_capability: CapsuleCapabilityType
  readonly target: string
  readonly dfa_certificate_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly schema_version: typeof EVOLUTION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface EvolutionResult {
  readonly verdict: EvolutionVerdict
  readonly proposal_id: SHA256Hex
  readonly reason?: string
  readonly result_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export class EvolutionError extends Error {
  override readonly name = 'EvolutionError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export async function buildProposal(input: {
  readonly capsule_id: string
  readonly proposed_capability: CapsuleCapabilityType
  readonly target: string
  readonly dfa_certificate_hash: SHA256Hex
  readonly sequence: SequenceNumber
}): Promise<CapabilityProposal> {
  const proposal_id = await hashValue({
    capsule_id: input.capsule_id,
    proposed_capability: input.proposed_capability,
    dfa_certificate_hash: input.dfa_certificate_hash,
    sequence: input.sequence.toString(),
  })

  return deepFreeze<CapabilityProposal>({
    proposal_id,
    capsule_id: input.capsule_id,
    proposed_capability: input.proposed_capability,
    target: input.target,
    dfa_certificate_hash: input.dfa_certificate_hash,
    sequence: input.sequence,
    schema_version: EVOLUTION_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

export async function assessProposal(
  proposal: CapabilityProposal,
  existingManifest: CapsuleManifest,
  currentDfaCertHash: SHA256Hex,
): Promise<EvolutionResult> {
  const reject = async (reason: string): Promise<EvolutionResult> => {
    const result_hash = await hashValue({
      proposal_id: proposal.proposal_id,
      verdict: 'REJECTED',
      sequence: proposal.sequence.toString(),
    })
    return deepFreeze<EvolutionResult>({
      verdict: 'REJECTED',
      proposal_id: proposal.proposal_id,
      reason,
      result_hash,
      is_replay_reconstructable: true,
    })
  }

  if (proposal.dfa_certificate_hash !== currentDfaCertHash) {
    return reject('stale dfa_certificate_hash — proposal references outdated DFA epoch')
  }

  const already = existingManifest.capabilities.some(
    c => c.type === proposal.proposed_capability && c.target === proposal.target,
  )
  if (already) {
    return reject(
      `capability ${proposal.proposed_capability}:${proposal.target} already registered in manifest`,
    )
  }

  const result_hash = await hashValue({
    proposal_id: proposal.proposal_id,
    verdict: 'APPROVED',
    sequence: proposal.sequence.toString(),
  })

  return deepFreeze<EvolutionResult>({
    verdict: 'APPROVED',
    proposal_id: proposal.proposal_id,
    result_hash,
    is_replay_reconstructable: true,
  })
}
