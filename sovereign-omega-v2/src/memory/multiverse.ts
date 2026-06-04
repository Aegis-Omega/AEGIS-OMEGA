// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH+SEQUENCE — fork_hash links universe identity to causal origin
//   replay_mapping:    ASSESS+LOCK   — each universe lineage is independently replay-certifiable
//   topology_mapping:  CONSENSUS     — convergence detection uses SwarmConvergenceRecord across universes
//
// Multiverse = multi-branch causal governance. Each "universe" is a named fork of the
// primary AdaptiveLineage, diverging at a declared fork_point. Universes evolve
// independently; convergence is detected when a quorum of universes share the same
// terminal_hash — the same 1/φ threshold that governs swarm consensus.
//
// BoundedGeneration tracks each universe's evolution count. When it saturates (⊥),
// the universe is permanently closed — no further events may be appended.
//
// Ecology constraint: MAX_UNIVERSES = MAX_SIMULATION_DEPTH = 8 (F_6, Fibonacci-capped).
// Prevents unbounded ecology growth — a T0_ABORT condition per constitutional law.
//
// Constitutional independence: each universe's MartingaleCertificate is computed
// independently. Convergence across universes is a swarm-layer property, not a
// constitutional mutation. The MultiverseRegistry itself is read-only authoritative
// state — only the owner may fork or append.

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import {
  AdaptiveLineage,
  type AdaptiveEvent,
  type AdaptiveLineageEntry,
} from '../frame/adaptive-lineage.js'
import {
  tallyVotes,
  type SwarmVote,
  type SwarmConvergenceRecord,
} from '../consensus/swarm.js'
import {
  certifyMartingale,
  type MartingaleCertificate,
} from '../constitutional/martingale.js'
import {
  makeGeneration,
  incrementGeneration,
  type BoundedGeneration,
} from './bounded-generation.js'
import { MAX_SIMULATION_DEPTH } from '../simulation/types.js'

export const MULTIVERSE_SCHEMA_VERSION = '1.0.0' as const
export const MAX_UNIVERSES = MAX_SIMULATION_DEPTH  // 8 — F_6, Fibonacci-capped ecology bound

export interface UniverseFork {
  readonly universe_id:      string
  readonly fork_point:       SHA256Hex   // entry_hash of the lineage entry at fork origin
  readonly fork_generation:  BoundedGeneration
  readonly fork_hash:        SHA256Hex   // hashValue({universe_id, fork_point, sequence})
  readonly sequence:         SequenceNumber
  readonly schema_version:   typeof MULTIVERSE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface UniverseConvergence {
  readonly swarm_record:           SwarmConvergenceRecord
  readonly converged_universe_ids: readonly string[]  // universes that voted for the winning hash
  readonly total_universes:        number
  readonly schema_version:         typeof MULTIVERSE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface UniverseCertification {
  readonly universe_id:   string
  readonly certificate:   MartingaleCertificate
  readonly lineage_length: number
  readonly fork_hash:     SHA256Hex
}

export class MultiverseError extends Error {
  override readonly name = 'MultiverseError'
}

type UniverseRecord = {
  readonly lineage:    AdaptiveLineage
  readonly fork:       UniverseFork
  readonly generation: BoundedGeneration
}

export class MultiverseRegistry {
  readonly #universes: ReadonlyMap<string, UniverseRecord>

  private constructor(universes: ReadonlyMap<string, UniverseRecord>) {
    this.#universes = universes
  }

  static empty(): MultiverseRegistry {
    return new MultiverseRegistry(new Map())
  }

  get universeCount(): number { return this.#universes.size }

  // Fork a new universe from fork_point. Throws if:
  //   - universe_id already exists
  //   - MAX_UNIVERSES (8) would be exceeded — ecology bound
  async fork(
    universe_id: string,
    fork_point: SHA256Hex,
    sequence: SequenceNumber,
  ): Promise<{ registry: MultiverseRegistry; fork: UniverseFork }> {
    if (this.#universes.has(universe_id)) {
      throw new MultiverseError(
        `[MULTIVERSE_REJECT] universe_id '${universe_id}' already exists`,
      )
    }
    if (this.#universes.size >= MAX_UNIVERSES) {
      throw new MultiverseError(
        `[MULTIVERSE_ECOLOGY] MAX_UNIVERSES=${MAX_UNIVERSES} exceeded — unbounded ecology prohibited`,
      )
    }
    const fork_generation = makeGeneration(0)
    const fork_hash = await hashValue({
      universe_id,
      fork_point,
      sequence: sequence.toString(),
    }) as SHA256Hex
    const fork = deepFreeze<UniverseFork>({
      universe_id,
      fork_point,
      fork_generation,
      fork_hash,
      sequence,
      schema_version: MULTIVERSE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
    const record: UniverseRecord = {
      lineage:    AdaptiveLineage.empty(),
      fork,
      generation: fork_generation,
    }
    const next = new Map(this.#universes)
    next.set(universe_id, record)
    return { registry: new MultiverseRegistry(next), fork }
  }

  // Append an adaptive event to a specific universe's lineage.
  // Throws if universe not found or its generation has saturated (⊥).
  async appendToUniverse(
    universe_id: string,
    event: AdaptiveEvent,
    sequence: SequenceNumber,
  ): Promise<{ registry: MultiverseRegistry; entry: AdaptiveLineageEntry }> {
    const record = this.#universes.get(universe_id)
    if (!record) {
      throw new MultiverseError(
        `[MULTIVERSE_REJECT] universe_id '${universe_id}' not found`,
      )
    }
    const next_gen = incrementGeneration(record.generation)
    /* c8 ignore next 4 -- generation saturation requires ~2^32 increments; structurally infeasible in any test run */
    if (next_gen === null) {
      throw new MultiverseError(
        `[MULTIVERSE_SATURATED] universe '${universe_id}' generation saturated — permanently closed`,
      )
    }
    const { lineage: next_lineage, entry } = await record.lineage.append(event, sequence)
    const updated: UniverseRecord = {
      lineage:    next_lineage,
      fork:       record.fork,
      generation: next_gen,
    }
    const next = new Map(this.#universes)
    next.set(universe_id, updated)
    return { registry: new MultiverseRegistry(next), entry }
  }

  // Check convergence: tally each universe's terminal_hash as a swarm vote.
  // Returns SwarmConvergenceRecord (quorum at 1/φ threshold) plus which universes converged.
  async checkConvergence(sequence: SequenceNumber): Promise<UniverseConvergence> {
    const ids = [...this.#universes.keys()].sort()
    if (ids.length === 0) {
      throw new MultiverseError(
        `[MULTIVERSE_REJECT] cannot check convergence on empty registry`,
      )
    }
    const votes: SwarmVote[] = ids.map(id => {
      const rec = this.#universes.get(id)!
      const terminal = rec.lineage.lastHash
      return { node_id: id, topology_hash: terminal, sequence }
    })
    const swarm_record = await tallyVotes(votes)
    const winning_hash = swarm_record.quorum_hash
    const converged_universe_ids = ids.filter(id => {
      const rec = this.#universes.get(id)!
      return rec.lineage.lastHash === winning_hash
    })
    return deepFreeze<UniverseConvergence>({
      swarm_record,
      converged_universe_ids,
      total_universes: ids.length,
      schema_version: MULTIVERSE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }

  // Get the AdaptiveLineage for a universe, or null if not found.
  getLineage(universe_id: string): AdaptiveLineage | null {
    return this.#universes.get(universe_id)?.lineage ?? null
  }

  // Get the fork record for a universe, or null if not found.
  getFork(universe_id: string): UniverseFork | null {
    return this.#universes.get(universe_id)?.fork ?? null
  }

  // List all universe IDs in alphabetical order (deterministic).
  listUniverses(): readonly string[] {
    return [...this.#universes.keys()].sort()
  }

  // Certify all universes: returns sorted array of {universe_id, certificate, lineage_length, fork_hash}.
  async certifyAll(): Promise<readonly UniverseCertification[]> {
    const ids = [...this.#universes.keys()].sort()
    const results: UniverseCertification[] = []
    for (const id of ids) {
      const rec = this.#universes.get(id)!
      const entries = rec.lineage.getAll()
      const certificate = await certifyMartingale(entries)
      results.push(deepFreeze<UniverseCertification>({
        universe_id:    id,
        certificate,
        lineage_length: entries.length,
        fork_hash:      rec.fork.fork_hash,
      }))
    }
    return Object.freeze(results)
  }
}
