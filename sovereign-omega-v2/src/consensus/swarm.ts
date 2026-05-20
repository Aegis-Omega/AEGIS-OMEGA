// ============================================================
// SOVEREIGN OMEGA — Swarm Convergence Protocol
// EPISTEMIC TIER: T2 · Gate 34
//
// Multi-node topology_hash quorum voting. Proves N constitutional
// nodes converge on identical governance state.
// primitive_mapping: VERIFY · replay_mapping: LOCK
// topology_mapping: CONSENSUS
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const SWARM_SCHEMA_VERSION = '1.0.0' as const

// 1/φ — golden ratio reciprocal. φ = (1+√5)/2, so 1/φ = (√5−1)/2 ≈ 0.6180339887.
// Encodes the self-similar constitutional threshold: the complement (1−1/φ = 1/φ²)
// is also a power of φ. More principled than an arbitrary 0.67 approximation.
export const DEFAULT_QUORUM_THRESHOLD = (Math.sqrt(5) - 1) / 2

export interface SwarmVote {
  readonly node_id: string
  readonly topology_hash: SHA256Hex
  readonly sequence: SequenceNumber
}

export interface SwarmConvergenceRecord {
  readonly quorum_hash: SHA256Hex
  readonly vote_count: number
  readonly quorum_reached: boolean
  readonly quorum_threshold: number
  readonly sequence: SequenceNumber
  readonly convergence_hash: SHA256Hex
  readonly schema_version: typeof SWARM_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SwarmError extends Error {
  override readonly name = 'SwarmError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export async function tallyVotes(
  votes: readonly SwarmVote[],
  quorumThreshold: number = DEFAULT_QUORUM_THRESHOLD,
): Promise<SwarmConvergenceRecord> {
  if (votes.length === 0) {
    throw new SwarmError('Cannot tally empty vote set')
  }

  const sequence = votes[0]!.sequence
  for (const vote of votes) {
    if (vote.sequence !== sequence) {
      throw new SwarmError(
        `Sequence mismatch: expected ${sequence}, got ${vote.sequence}`,
      )
    }
  }

  // Tally votes — local Map permitted (not stored in state)
  const tally = new Map<SHA256Hex, number>()
  for (const vote of votes) {
    tally.set(vote.topology_hash, (tally.get(vote.topology_hash) ?? 0) + 1)
  }

  // Winner: max votes; tie → lexicographically first topology_hash
  let quorum_hash: SHA256Hex = votes[0]!.topology_hash
  let maxCount = 0
  for (const [hash, count] of tally) {
    if (count > maxCount || (count === maxCount && hash < quorum_hash)) {
      quorum_hash = hash
      maxCount = count
    }
  }

  const vote_count = maxCount
  const quorum_reached = vote_count / votes.length >= quorumThreshold

  const convergence_hash = await hashValue({
    quorum_hash,
    vote_count,
    quorum_reached,
    quorum_threshold: quorumThreshold,
    sequence: sequence.toString(),
  })

  return deepFreeze<SwarmConvergenceRecord>({
    quorum_hash,
    vote_count,
    quorum_reached,
    quorum_threshold: quorumThreshold,
    sequence,
    convergence_hash,
    schema_version: SWARM_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}
