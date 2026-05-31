// ============================================================
// SOVEREIGN OMEGA — DivergenceMonitor (multi-node fork detection)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// assessDivergence() groups NodeCheckpoints by state_root, finds
// the plurality root, and checks whether the agreeing fraction
// reaches the BFT threshold 1/φ ≈ 0.6180339887. Checkpoints must
// all be at the same block_height — height mismatch throws.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { deepFreeze } from '../core/immutable.js'
import type { NodeCheckpoint } from './node-checkpoint.js'

/** BFT quorum threshold: 1/φ = (√5−1)/2 ≈ 0.6180339887 */
const BFT_QUORUM = (Math.sqrt(5) - 1) / 2

export class DivergenceMonitorError extends Error {
  override readonly name = 'DivergenceMonitorError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface DivergenceReport {
  readonly block_height: number
  /**
   * The state root held by the plurality of nodes, or null when no plurality
   * exists (e.g. a perfect split with an even number of nodes).
   */
  readonly consensus_root: SHA256Hex | null
  /** node_ids agreeing on consensus_root. Empty when consensus_root is null. */
  readonly in_consensus: readonly string[]
  /** node_ids whose state_root differs from consensus_root (or all if null). */
  readonly diverged: readonly string[]
  /**
   * Fraction of nodes in consensus (0–1). Zero when consensus_root is null.
   * Equals in_consensus.length / total node count.
   */
  readonly quorum_fraction: number
  /** True iff quorum_fraction >= BFT_QUORUM (≈ 0.618). */
  readonly bft_achieved: boolean
  readonly total_nodes: number
}

// ─── Public API ────────────────────────────────────────────

/**
 * Assess multi-node state agreement from a set of NodeCheckpoints.
 * All checkpoints must be at the same block_height.
 * Throws DivergenceMonitorError if:
 *   - checkpoints array is empty
 *   - checkpoints have differing block_height values
 */
export function assessDivergence(
  checkpoints: readonly NodeCheckpoint[],
): DivergenceReport {
  if (checkpoints.length === 0) {
    throw new DivergenceMonitorError('At least one checkpoint is required')
  }

  const height = checkpoints[0]!.block_height
  for (const cp of checkpoints) {
    if (cp.block_height !== height) {
      throw new DivergenceMonitorError(
        `Height mismatch: expected ${height}, got ${cp.block_height} from node ${cp.node_id}`,
      )
    }
  }

  // Group node_ids by state_root
  const groups = new Map<SHA256Hex, string[]>()
  for (const cp of checkpoints) {
    const group = groups.get(cp.state_root)
    if (group) {
      group.push(cp.node_id)
    } else {
      groups.set(cp.state_root, [cp.node_id])
    }
  }

  // Find plurality (largest group); null on tie
  let pluralityRoot: SHA256Hex | null = null
  let maxCount = 0
  let tieDetected = false

  for (const [root, nodes] of groups) {
    if (nodes.length > maxCount) {
      maxCount    = nodes.length
      pluralityRoot = root
      tieDetected  = false
    } else if (nodes.length === maxCount) {
      tieDetected = true
    }
  }

  if (tieDetected) {
    // Perfect split — no consensus root
    pluralityRoot = null
    maxCount      = 0
  }

  const total          = checkpoints.length
  const inConsensus    = pluralityRoot !== null ? (groups.get(pluralityRoot) ?? []) : []
  const diverged       = checkpoints
    .filter(cp => cp.state_root !== pluralityRoot)
    .map(cp => cp.node_id)
  const quorumFraction = pluralityRoot !== null ? maxCount / total : 0
  const bftAchieved    = quorumFraction >= BFT_QUORUM

  return deepFreeze<DivergenceReport>({
    block_height:    height,
    consensus_root:  pluralityRoot,
    in_consensus:    deepFreeze(inConsensus),
    diverged:        deepFreeze(diverged),
    quorum_fraction: quorumFraction,
    bft_achieved:    bftAchieved,
    total_nodes:     total,
  })
}

/**
 * Convenience: returns true iff all nodes agree on the same state_root.
 * Requires at least one checkpoint; throws on empty.
 */
export function allAgree(checkpoints: readonly NodeCheckpoint[]): boolean {
  if (checkpoints.length === 0) {
    throw new DivergenceMonitorError('At least one checkpoint is required')
  }
  const root = checkpoints[0]!.state_root
  return checkpoints.every(cp => cp.state_root === root && cp.block_height === checkpoints[0]!.block_height)
}
