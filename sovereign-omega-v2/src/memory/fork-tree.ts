// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH+SEQUENCE — node_hash chains every fork and collapse event
//   replay_mapping:    HARMONIZE     — the tree is the HARMONIZE-phase record of multiverse evolution
//   topology_mapping:  LINEAGE       — ForkTree IS the causal lineage of the multiverse itself
//
// ForkTree — directed acyclic graph of universe genealogy.
//
// Every fork() creates a ForkNode pointing to its parent (or 'genesis').
// Every collapse() creates a CollapseEvent sealing losing nodes and declaring a winner.
// The tree grows monotonically — nodes are never removed, only sealed.
//
// Across multiple collapse-and-rebirth cycles, the ForkTree accumulates the full
// causal history of the multiverse: which universes descended from which,
// which collapses sealed which timelines, and which lineage won each epoch.
//
// tree_hash (in ForkTreeCertificate) commits the entire DAG in one 64-char hex digest —
// a replay-certifiable proof of the complete multiverse genealogy.

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { CollapseRecord } from './collapse.js'

export const FORK_TREE_SCHEMA_VERSION = '1.0.0' as const

export type ForkParent = string | 'genesis'

export interface ForkNode {
  readonly universe_id:  string
  readonly parent:       ForkParent
  readonly fork_hash:    SHA256Hex   // from UniverseFork.fork_hash
  readonly sequence:     SequenceNumber
  readonly is_sealed:    boolean     // true after a collapse seals this universe as a loser
  readonly node_hash:    SHA256Hex   // hashValue({universe_id, parent, fork_hash, sequence})
  readonly schema_version: typeof FORK_TREE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface CollapseEvent {
  readonly winner_id:      string
  readonly sealed_ids:     readonly string[]  // universe_ids sealed by this collapse
  readonly collapse_hash:  SHA256Hex          // from CollapseRecord.collapse_hash
  readonly sequence:       SequenceNumber
  readonly event_hash:     SHA256Hex          // hashValue({winner_id, sealed_ids, collapse_hash, sequence})
  readonly schema_version: typeof FORK_TREE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface ForkTreeCertificate {
  readonly node_count:    number
  readonly sealed_count:  number
  readonly collapse_count: number
  readonly depth:         number       // max ancestry depth from genesis
  readonly tree_hash:     SHA256Hex    // hashValue(all node_hashes + event_hashes in order)
  readonly sequence:      SequenceNumber
  readonly schema_version: typeof FORK_TREE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class ForkTreeError extends Error {
  override readonly name = 'ForkTreeError'
}

export class ForkTree {
  readonly #nodes:   ReadonlyMap<string, ForkNode>       // universe_id → ForkNode
  readonly #events:  readonly CollapseEvent[]            // ordered collapse history
  readonly #children: ReadonlyMap<string, readonly string[]>  // parent → child ids

  private constructor(
    nodes: ReadonlyMap<string, ForkNode>,
    events: readonly CollapseEvent[],
    children: ReadonlyMap<string, readonly string[]>,
  ) {
    this.#nodes    = nodes
    this.#events   = events
    this.#children = children
  }

  static empty(): ForkTree {
    return new ForkTree(new Map(), [], new Map())
  }

  get nodeCount(): number { return this.#nodes.size }
  get collapseCount(): number { return this.#events.length }

  // Record a universe fork. Throws if universe_id already exists.
  async recordFork(
    universe_id: string,
    parent: ForkParent,
    fork_hash: SHA256Hex,
    sequence: SequenceNumber,
  ): Promise<{ tree: ForkTree; node: ForkNode }> {
    if (this.#nodes.has(universe_id)) {
      throw new ForkTreeError(
        `[FORK_TREE_REJECT] universe_id '${universe_id}' already in tree`,
      )
    }
    const node_hash = await hashValue({
      universe_id,
      parent,
      fork_hash,
      sequence: sequence.toString(),
    }) as SHA256Hex
    const node = deepFreeze<ForkNode>({
      universe_id,
      parent,
      fork_hash,
      sequence,
      is_sealed: false,
      node_hash,
      schema_version: FORK_TREE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
    const next_nodes = new Map(this.#nodes)
    next_nodes.set(universe_id, node)

    // Update children map
    const next_children = new Map(this.#children)
    const parent_key = parent
    const existing = next_children.get(parent_key) ?? []
    next_children.set(parent_key, Object.freeze([...existing, universe_id]))

    return {
      tree: new ForkTree(next_nodes, this.#events, next_children),
      node,
    }
  }

  // Record a collapse event: seal losing universes, mark the event in history.
  async recordCollapse(
    record: CollapseRecord,
    sequence: SequenceNumber,
  ): Promise<{ tree: ForkTree; event: CollapseEvent }> {
    const sealed_ids = record.sealed_universes.map(s => s.universe_id)

    const event_hash = await hashValue({
      winner_id: record.winner_id,
      sealed_ids,
      collapse_hash: record.collapse_hash,
      sequence: sequence.toString(),
    }) as SHA256Hex

    const event = deepFreeze<CollapseEvent>({
      winner_id:     record.winner_id,
      sealed_ids,
      collapse_hash: record.collapse_hash,
      sequence,
      event_hash,
      schema_version: FORK_TREE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })

    // Seal losing nodes
    const next_nodes = new Map(this.#nodes)
    for (const id of sealed_ids) {
      const existing = next_nodes.get(id)
      if (existing) {
        next_nodes.set(id, deepFreeze({ ...existing, is_sealed: true }))
      }
    }

    return {
      tree: new ForkTree(next_nodes, [...this.#events, event], this.#children),
      event,
    }
  }

  // Get ancestry path from genesis to universe_id (inclusive), [] if not found.
  getAncestry(universe_id: string): readonly string[] {
    const path: string[] = []
    let current: string | undefined = universe_id
    const visited = new Set<string>()
    while (current !== undefined && current !== 'genesis') {
      if (visited.has(current)) break  // cycle guard
      const node = this.#nodes.get(current)
      if (!node) break  // unknown node — stop before adding to path
      visited.add(current)
      path.unshift(current)
      current = node.parent === 'genesis' ? undefined : node.parent
    }
    return Object.freeze(path)
  }

  // Get direct children of a universe_id (or 'genesis').
  getChildren(parent: ForkParent): readonly string[] {
    return this.#children.get(parent) ?? Object.freeze([])
  }

  // Get a specific node, or null.
  getNode(universe_id: string): ForkNode | null {
    return this.#nodes.get(universe_id) ?? null
  }

  // Get all collapse events in order.
  getCollapseEvents(): readonly CollapseEvent[] {
    return this.#events
  }

  // Max depth: longest ancestry chain from genesis.
  get depth(): number {
    let max = 0
    for (const id of this.#nodes.keys()) {
      const ancestry = this.getAncestry(id)
      if (ancestry.length > max) max = ancestry.length
    }
    return max
  }

  // Certify the entire DAG in one frozen record.
  async certify(sequence: SequenceNumber): Promise<ForkTreeCertificate> {
    const nodes = [...this.#nodes.values()].sort((a, b) =>
      a.universe_id.localeCompare(b.universe_id),
    )
    const sealed_count = nodes.filter(n => n.is_sealed).length
    const tree_hash = await hashValue({
      node_hashes:  nodes.map(n => n.node_hash),
      event_hashes: this.#events.map(e => e.event_hash),
      sequence: sequence.toString(),
    }) as SHA256Hex
    return deepFreeze<ForkTreeCertificate>({
      node_count:     nodes.length,
      sealed_count,
      collapse_count: this.#events.length,
      depth:          this.depth,
      tree_hash,
      sequence,
      schema_version: FORK_TREE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }
}
