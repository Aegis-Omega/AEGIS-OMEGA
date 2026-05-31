// ============================================================
// SOVEREIGN OMEGA — NodeCheckpoint (cross-node divergence detection)
// EPISTEMIC TIER: T2 · distributed architecture precursor
//
// Each node periodically publishes a NodeCheckpoint containing its
// current block height and state_root. Comparing two checkpoints
// immediately reveals whether nodes have diverged — without
// transmitting full block data. The checkpoint_hash is a
// self-verifiable commitment: SHA-256({node_id, block_height,
// state_root}). Tamper any field and verification fails.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { CommittedBlock } from './block.js'

export const NODE_CHECKPOINT_VERSION = '1.0.0' as const

export interface NodeCheckpoint {
  readonly node_id: string
  readonly block_height: number
  readonly state_root: SHA256Hex
  /** SHA-256({node_id, block_height, state_root}) — tamper-evident commitment. */
  readonly checkpoint_hash: SHA256Hex
  readonly schema_version: typeof NODE_CHECKPOINT_VERSION
  readonly is_replay_reconstructable: true
}

export interface CheckpointComparison {
  /** True iff both checkpoints reflect identical block_height and state_root. */
  readonly matches: boolean
  /** The block_height at which the comparison was made (lower of the two). */
  readonly compared_at_height: number
  /** Present when matches is false — describes which field diverged. */
  readonly reason?: string
}

export class NodeCheckpointError extends Error {
  override readonly name = 'NodeCheckpointError'
  constructor(msg: string) {
    super(msg)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// ─── Public API ────────────────────────────────────────────

/**
 * Capture a NodeCheckpoint from the tip of the local block chain.
 * node_id identifies this node (hex string from constitutional autonode).
 */
export async function captureNodeCheckpoint(
  node_id: string,
  block: CommittedBlock,
): Promise<NodeCheckpoint> {
  if (!node_id.trim()) {
    throw new NodeCheckpointError('node_id must be a non-empty string')
  }
  const block_height = block.index
  const state_root   = block.state_root_after
  const checkpoint_hash = await hashValue({ node_id, block_height, state_root })

  return deepFreeze<NodeCheckpoint>({
    node_id,
    block_height,
    state_root,
    checkpoint_hash,
    schema_version: NODE_CHECKPOINT_VERSION,
    is_replay_reconstructable: true,
  })
}

/**
 * Verify a checkpoint's self-hash. Returns true iff checkpoint_hash
 * matches SHA-256({node_id, block_height, state_root}).
 */
export async function verifyNodeCheckpoint(cp: NodeCheckpoint): Promise<boolean> {
  const expected = await hashValue({
    node_id:      cp.node_id,
    block_height: cp.block_height,
    state_root:   cp.state_root,
  })
  return cp.checkpoint_hash === expected
}

/**
 * Compare two node checkpoints for state agreement.
 * Nodes at different heights are compared at the lower height's state_root
 * only if one is an ancestor of the other (same block_height required for
 * a meaningful equality check — callers must align heights first).
 */
export function compareCheckpoints(
  a: NodeCheckpoint,
  b: NodeCheckpoint,
): CheckpointComparison {
  const compared_at_height = Math.min(a.block_height, b.block_height)

  if (a.block_height !== b.block_height) {
    return {
      matches: false,
      compared_at_height,
      reason: `height mismatch: node ${a.node_id} at ${a.block_height}, node ${b.node_id} at ${b.block_height}`,
    }
  }

  if (a.state_root !== b.state_root) {
    return {
      matches: false,
      compared_at_height,
      reason: `state_root divergence at height ${a.block_height}: ${a.state_root.slice(0, 8)}… vs ${b.state_root.slice(0, 8)}…`,
    }
  }

  return { matches: true, compared_at_height }
}
