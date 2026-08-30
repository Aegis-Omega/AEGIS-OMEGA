// ============================================================
// Simulation Branch Engine — Type Seams
// EPISTEMIC TIER: T2 (engineering hypothesis — seam only, Gate 146)
// Branch simulation is T2; "causal forecast" is T3 (not implemented).
// MAX_SIMULATION_DEPTH = 8 = fibonacciInterval(6) — bounded recursion.
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const SIMULATION_SCHEMA_VERSION = '1.0.0' as const
export const MAX_SIMULATION_DEPTH = 8  // F_6 = 8 — Fibonacci-capped depth

export type BranchOutcome = 'STABLE' | 'DRIFT' | 'VIOLATION' | 'CONVERGENT'

export interface SimulationBranch {
  readonly branch_id: SHA256Hex          // hashValue({parent_topology_hash, branch_index, sequence})
  readonly parent_topology_hash: SHA256Hex
  readonly branch_index: number
  readonly depth: number                 // ≤ MAX_SIMULATION_DEPTH
  readonly outcome: BranchOutcome
  readonly schema_version: typeof SIMULATION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class SimulationError extends Error {
  override readonly name = 'SimulationError'
}

export async function buildBranch(input: {
  parent_topology_hash: SHA256Hex
  branch_index: number
  depth: number
  outcome: BranchOutcome
  sequence: SequenceNumber
}): Promise<SimulationBranch> {
  if (input.depth > MAX_SIMULATION_DEPTH) {
    throw new SimulationError(
      `depth ${input.depth} exceeds MAX_SIMULATION_DEPTH ${MAX_SIMULATION_DEPTH}`
    )
  }
  if (input.depth < 0) {
    throw new SimulationError('depth must be non-negative')
  }
  const branch_id = await hashValue({
    parent_topology_hash: input.parent_topology_hash,
    branch_index: input.branch_index,
    sequence: input.sequence.toString(),
  }) as SHA256Hex
  return deepFreeze<SimulationBranch>({
    branch_id,
    parent_topology_hash: input.parent_topology_hash,
    branch_index: input.branch_index,
    depth: input.depth,
    outcome: input.outcome,
    schema_version: SIMULATION_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}
