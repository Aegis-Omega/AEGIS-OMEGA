// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH      — collapse_hash anchors the entire decoherence event
//   replay_mapping:    LOCK      — collapse IS the LOCK boundary; post-collapse = new canonical chain
//   topology_mapping:  CONSENSUS — collapse requires quorum_reached=true from checkConvergence()
//
// Multiverse Collapse Protocol — decoherence of parallel universes into one canonical timeline.
//
// Lifecycle: fork() → appendToUniverse() → checkConvergence() → collapse()
//
// Collapse rules:
//   1. Requires quorum_reached=true from a prior UniverseConvergence record.
//   2. The winning universe (quorum_hash match) becomes the new canonical AdaptiveLineage.
//   3. All losing universes are permanently sealed (their entries recorded in the CollapseRecord).
//   4. The resulting MultiverseRegistry contains only the winning universe under the canonical ID.
//   5. CollapseRecord is frozen, hash-linked, replay-certifiable — auditable decoherence proof.
//
// Quantum decoherence analogy (T2 framing — not T3 physics claim):
// Multiple governance branches evolve in parallel. When the swarm observes quorum on one
// terminal hash, that branch becomes the authoritative causal chain. The others are sealed.
// The collapse_hash encodes all sealed universe hashes — nothing is lost, everything is auditable.

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import {
  MultiverseRegistry,
  type UniverseConvergence,
} from './multiverse.js'

export const COLLAPSE_SCHEMA_VERSION = '1.0.0' as const

export interface SealedUniverse {
  readonly universe_id:    string
  readonly terminal_hash:  SHA256Hex   // lastHash at time of collapse
  readonly lineage_length: number
  readonly fork_hash:      SHA256Hex
}

export interface CollapseRecord {
  readonly winner_id:        string          // universe that won the quorum
  readonly winner_hash:      SHA256Hex       // quorum_hash (winning terminal_hash)
  readonly sealed_universes: readonly SealedUniverse[]  // sorted by universe_id
  readonly total_collapsed:  number          // count of sealed (non-winning) universes
  readonly convergence_hash: SHA256Hex       // from swarm_record.convergence_hash
  readonly collapse_hash:    SHA256Hex       // hashValue(winner_id, winner_hash, sealed hashes, sequence)
  readonly sequence:         SequenceNumber
  readonly schema_version:   typeof COLLAPSE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface CollapseResult {
  readonly registry:        MultiverseRegistry  // new registry — only winner survives as 'canonical'
  readonly record:          CollapseRecord
  readonly canonical_id:    string              // always 'canonical' after collapse
}

export class CollapseError extends Error {
  override readonly name = 'CollapseError'
}

// Collapse a multiverse to its winner. Requires quorum_reached=true.
// The winning universe is re-registered as 'canonical' in the output registry.
// All other universes are sealed (recorded, not carried forward).
// The winner_id must be one of the converged_universe_ids in the convergence record.
export async function collapseMultiverse(
  registry: MultiverseRegistry,
  convergence: UniverseConvergence,
  sequence: SequenceNumber,
): Promise<CollapseResult> {
  if (!convergence.swarm_record.quorum_reached) {
    throw new CollapseError(
      '[COLLAPSE_REJECT] Cannot collapse: quorum not reached — convergence.swarm_record.quorum_reached=false',
    )
  }
  if (convergence.converged_universe_ids.length === 0) {
    throw new CollapseError(
      '[COLLAPSE_REJECT] Cannot collapse: no converged universes',
    )
  }

  // Pick the first converged universe (alphabetically — deterministic)
  const winner_id = [...convergence.converged_universe_ids].sort()[0]!
  const winner_hash = convergence.swarm_record.quorum_hash

  // Gather all certifications to extract lineage metadata
  const all_certs = await registry.certifyAll()
  const winner_cert = all_certs.find(c => c.universe_id === winner_id)
  if (!winner_cert) {
    throw new CollapseError(
      `[COLLAPSE_REJECT] winner_id '${winner_id}' not found in registry`,
    )
  }

  // Seal all non-winning universes
  const sealed: SealedUniverse[] = all_certs
    .filter(c => c.universe_id !== winner_id)
    .map(c => {
      const lineage = registry.getLineage(c.universe_id)!
      return deepFreeze<SealedUniverse>({
        universe_id:    c.universe_id,
        terminal_hash:  lineage.lastHash,
        lineage_length: c.lineage_length,
        fork_hash:      c.fork_hash,
      })
    })
    .sort((a, b) => a.universe_id.localeCompare(b.universe_id))

  // Build collapse hash: commits the full decoherence event to the audit chain
  const collapse_hash = await hashValue({
    winner_id,
    winner_hash,
    sealed_hashes: sealed.map(s => s.terminal_hash),
    convergence_hash: convergence.swarm_record.convergence_hash,
    sequence: sequence.toString(),
  }) as SHA256Hex

  const record = deepFreeze<CollapseRecord>({
    winner_id,
    winner_hash,
    sealed_universes:  sealed,
    total_collapsed:   sealed.length,
    convergence_hash:  convergence.swarm_record.convergence_hash,
    collapse_hash,
    sequence,
    schema_version:    COLLAPSE_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })

  // Build new registry: re-fork 'canonical' from winner_hash, replay winner's lineage
  const winner_lineage = registry.getLineage(winner_id)!
  const winner_fork    = registry.getFork(winner_id)!

  // Seed the new registry with 'canonical' pointing to the winner's fork_point
  let canonical_reg = MultiverseRegistry.empty()
  const { registry: seeded } = await canonical_reg.fork(
    'canonical',
    winner_fork.fork_point,
    sequence,
  )
  canonical_reg = seeded

  // Replay all entries from the winner's lineage into 'canonical'
  for (const entry of winner_lineage.getAll()) {
    const { registry: advanced } = await canonical_reg.appendToUniverse(
      'canonical',
      entry.event,
      entry.sequence,
    )
    canonical_reg = advanced
  }

  return deepFreeze<CollapseResult>({
    registry:     canonical_reg,
    record,
    canonical_id: 'canonical',
  })
}
