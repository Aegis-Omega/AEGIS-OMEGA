// ============================================================
// Skill Harness — Phase 5 Collaborative Multi-Agent Specialization
// EPISTEMIC TIER: T2 · Gate 166
//
// Peer consensus signals and skill transfer between agents.
//
// Skill transfer:
//   Source agent proposes transferring a skill to a target agent.
//   Transferred skill starts with discounted confidence:
//     seeded_confidence = source_confidence × TRANSFER_DISCOUNT
//   validated_runs reset to 0 — target must earn its own evidence.
//
// Peer consensus:
//   N agents each hold a version of the same skill_id.
//   Weighted-average confidence = Σ(conf_i × runs_i) / Σ(runs_i).
//   Uninformative (zero total runs) → arithmetic mean.
//   Requires ≥ MIN_PEER_CONSENSUS_AGENTS profiles.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { buildSkillRecord } from './catalog.js'
import type { SkillRecord } from './types.js'

export const COLLABORATION_SCHEMA_VERSION = '1.0.0' as const

export const TRANSFER_DISCOUNT = 0.7       // seeded_confidence = source × 0.7
export const MIN_PEER_CONSENSUS_AGENTS = 2 // minimum for consensus

export interface SkillTransferProposal {
  readonly proposal_id: SHA256Hex           // hashValue({source_skill_hash, target_agent_id, sequence})
  readonly source_agent_id: string
  readonly target_agent_id: string
  readonly source_skill_hash: SHA256Hex
  readonly skill_id: string
  readonly seeded_confidence: number        // source_confidence × TRANSFER_DISCOUNT
  readonly sequence: SequenceNumber
  readonly schema_version: typeof COLLABORATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface SkillTransferResult {
  readonly proposal: SkillTransferProposal
  readonly transferred_skill: SkillRecord
  readonly transfer_hash: SHA256Hex         // hashValue({proposal_id, transferred_skill.skill_hash})
  readonly schema_version: typeof COLLABORATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface PeerConsensusResult {
  readonly skill_id: string
  readonly consensus_confidence: number
  readonly participating_agents: readonly string[]
  readonly agent_count: number
  readonly consensus_hash: SHA256Hex
  readonly schema_version: typeof COLLABORATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class CollaborationError extends Error {
  override readonly name = 'CollaborationError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// Proposes transferring source_skill from source_agent to target_agent.
// Throws CollaborationError if source_agent_id === target_agent_id.
export async function proposeSkillTransfer(
  source_skill: SkillRecord,
  source_agent_id: string,
  target_agent_id: string,
  sequence: SequenceNumber,
): Promise<SkillTransferProposal> {
  if (source_agent_id === target_agent_id) {
    throw new CollaborationError(
      `Source and target agent must differ; both are '${source_agent_id}'`,
    )
  }

  const seeded_confidence = Math.min(1, source_skill.confidence * TRANSFER_DISCOUNT)

  const proposal_id = await hashValue({
    source_skill_hash: source_skill.skill_hash,
    target_agent_id,
    sequence: sequence.toString(),
  }) as SHA256Hex

  return deepFreeze({
    proposal_id,
    source_agent_id,
    target_agent_id,
    source_skill_hash: source_skill.skill_hash,
    skill_id: source_skill.skill_id,
    seeded_confidence,
    sequence,
    schema_version: COLLABORATION_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

// Applies a transfer proposal, creating a new SkillRecord for the target agent.
// validated_runs is reset to 0 — target must earn its own evidence.
export async function applySkillTransfer(
  proposal: SkillTransferProposal,
  source_skill: SkillRecord,
): Promise<SkillTransferResult> {
  const transferred_skill = await buildSkillRecord({
    skill_id: source_skill.skill_id,
    name: source_skill.name,
    confidence: proposal.seeded_confidence,
    validated_runs: 0,
    failure_rate: source_skill.failure_rate,
    recency_score: source_skill.recency_score * TRANSFER_DISCOUNT,
    domain_affinity: source_skill.domain_affinity,
    dependencies: source_skill.dependencies,
    evidence_refs: [],
    last_validated: source_skill.last_validated,
    epistemic_tier: source_skill.epistemic_tier,
    primitive_mapping: source_skill.primitive_mapping,
  })

  const transfer_hash = await hashValue({
    proposal_id: proposal.proposal_id,
    transferred_skill_hash: transferred_skill.skill_hash,
  }) as SHA256Hex

  return deepFreeze({
    proposal,
    transferred_skill,
    transfer_hash,
    schema_version: COLLABORATION_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

export interface PeerProfile {
  readonly agent_id: string
  readonly skill: SkillRecord
}

// Aggregates peer skill versions into a consensus confidence estimate.
// Weighted by validated_runs; falls back to arithmetic mean if all runs = 0.
// Throws CollaborationError if profiles.length < MIN_PEER_CONSENSUS_AGENTS
// or if any skill_id does not match the first profile's skill_id.
export async function peerConsensus(
  profiles: readonly PeerProfile[],
): Promise<PeerConsensusResult> {
  if (profiles.length < MIN_PEER_CONSENSUS_AGENTS) {
    throw new CollaborationError(
      `Peer consensus requires ≥ ${MIN_PEER_CONSENSUS_AGENTS} agents; received ${profiles.length}`,
    )
  }

  const skill_id = profiles[0]!.skill.skill_id
  for (const p of profiles) {
    if (p.skill.skill_id !== skill_id) {
      throw new CollaborationError(
        `Peer consensus skill_id mismatch: expected '${skill_id}', got '${p.skill.skill_id}' for agent '${p.agent_id}'`,
      )
    }
  }

  const totalRuns = profiles.reduce((sum, p) => sum + p.skill.validated_runs, 0)
  let consensus_confidence: number
  if (totalRuns === 0) {
    // Uninformative prior — arithmetic mean
    consensus_confidence = profiles.reduce((sum, p) => sum + p.skill.confidence, 0) / profiles.length
  } else {
    consensus_confidence = profiles.reduce((sum, p) => sum + p.skill.confidence * p.skill.validated_runs, 0) / totalRuns
  }
  consensus_confidence = Math.min(1, Math.max(0, consensus_confidence))

  const participating_agents = profiles.map(p => p.agent_id)

  const consensus_hash = await hashValue({
    skill_id,
    consensus_confidence: consensus_confidence.toString(),
    agent_count: profiles.length.toString(),
    participating_agents: participating_agents.join(','),
  }) as SHA256Hex

  return deepFreeze({
    skill_id,
    consensus_confidence,
    participating_agents,
    agent_count: profiles.length,
    consensus_hash,
    schema_version: COLLABORATION_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}
