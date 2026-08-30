// ============================================================
// SOVEREIGN OMEGA — HotStuff Ω Consensus Kernel
// EPISTEMIC TIER: T2 · Gate 19
//
// runConsensusRound() is a pure function: (block, vs, votes) → result.
// No network I/O, no timers, no side effects.
// Outcome is COMMITTED iff 2f+1 valid votes were cast for block_hash.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import {
  validateValidatorSet,
  collectValidVotes,
  isQuorum,
  formQC,
  quorumThreshold,
} from './quorum.js'
import type { ConsensusBlock, ConsensusResult, Vote, ValidatorSet } from './types.js'

/**
 * Execute one HotStuff consensus round.
 *
 * Pure function — no I/O, no Date.now(), no global state.
 * Same inputs always produce the same ConsensusResult.
 *
 * @param block   The proposed block (frame_hash + sequence)
 * @param vs      Validator set (must satisfy n ≥ 3f+1)
 * @param votes   All votes received (may include invalid/duplicate)
 * @returns       Frozen ConsensusResult
 */
export async function runConsensusRound(
  block: ConsensusBlock,
  vs: ValidatorSet,
  votes: readonly Vote[],
): Promise<ConsensusResult> {
  validateValidatorSet(vs)

  const threshold = quorumThreshold(vs.f)
  const validVotes = await collectValidVotes(block, votes, vs)

  if (!isQuorum(validVotes, threshold)) {
    return deepFreeze<ConsensusResult>({
      outcome: 'NO_QUORUM',
      block,
      votes_received: validVotes.length,
      threshold,
      reason: `${validVotes.length} valid votes < threshold ${threshold}`,
    })
  }

  const qc = await formQC(block, validVotes, threshold)

  return deepFreeze<ConsensusResult>({
    outcome: 'COMMITTED',
    qc,
    block,
    votes_received: validVotes.length,
    threshold,
  })
}
