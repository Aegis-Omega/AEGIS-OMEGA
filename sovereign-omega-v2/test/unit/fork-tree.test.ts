// test/unit/fork-tree.test.ts
// Gate 192 — ForkTree (DAG of universe genealogy)
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import {
  ForkTree,
  ForkTreeError,
  FORK_TREE_SCHEMA_VERSION,
} from '../../src/memory/fork-tree.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { CollapseRecord } from '../../src/memory/collapse.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const HASH_A = 'aabbccdd'.repeat(8) as SHA256Hex
const HASH_B = '11223344'.repeat(8) as SHA256Hex
const HASH_C = 'deadbeef'.repeat(8) as SHA256Hex
const HASH_D = 'cafebabe'.repeat(8) as SHA256Hex

function makeCollapseRecord(
  winner_id: string,
  winner_hash: SHA256Hex,
  sealed_ids: string[],
  collapse_hash: SHA256Hex,
  convergence_hash: SHA256Hex,
  sequence: SequenceNumber,
): CollapseRecord {
  return Object.freeze({
    winner_id,
    winner_hash,
    sealed_universes: sealed_ids.map(id => Object.freeze({
      universe_id: id,
      terminal_hash: HASH_B,
      lineage_length: 0,
      fork_hash: HASH_A,
    })),
    total_collapsed: sealed_ids.length,
    convergence_hash,
    collapse_hash,
    sequence,
    schema_version: '1.0.0' as const,
    is_replay_reconstructable: true as const,
  })
}

describe('Gate 192 — ForkTree', () => {

  describe('Constants', () => {
    it('FORK_TREE_SCHEMA_VERSION is 1.0.0', () => {
      expect(FORK_TREE_SCHEMA_VERSION).toBe('1.0.0')
    })

    it('ForkTreeError is Error subclass with correct name', () => {
      const err = new ForkTreeError('x')
      expect(err).toBeInstanceOf(Error)
      expect(err.name).toBe('ForkTreeError')
    })
  })

  describe('ForkTree.empty()', () => {
    it('starts with nodeCount=0 and collapseCount=0', () => {
      const tree = ForkTree.empty()
      expect(tree.nodeCount).toBe(0)
      expect(tree.collapseCount).toBe(0)
    })

    it('depth is 0 for empty tree', () => {
      const tree = ForkTree.empty()
      expect(tree.depth).toBe(0)
    })

    it('getChildren returns empty for genesis in empty tree', () => {
      const tree = ForkTree.empty()
      expect(tree.getChildren('genesis')).toEqual([])
    })
  })

  describe('recordFork()', () => {
    it('creates a frozen ForkNode with correct fields', async () => {
      const tree = ForkTree.empty()
      const { node } = await tree.recordFork('alpha', 'genesis', HASH_A, seq(1))
      expect(Object.isFrozen(node)).toBe(true)
      expect(node.universe_id).toBe('alpha')
      expect(node.parent).toBe('genesis')
      expect(node.fork_hash).toBe(HASH_A)
      expect(node.sequence).toBe(seq(1))
      expect(node.is_sealed).toBe(false)
      expect(node.schema_version).toBe(FORK_TREE_SCHEMA_VERSION)
      expect(node.is_replay_reconstructable).toBe(true)
    })

    it('node_hash is 64-char hex', async () => {
      const tree = ForkTree.empty()
      const { node } = await tree.recordFork('alpha', 'genesis', HASH_A, seq(1))
      expect(node.node_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(node.node_hash)).toBe(true)
    })

    it('returns new tree with incremented nodeCount (immutable pattern)', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))
      expect(t0.nodeCount).toBe(0)
      expect(t1.nodeCount).toBe(1)
      expect(t2.nodeCount).toBe(2)
    })

    it('throws ForkTreeError on duplicate universe_id', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      await expect(t1.recordFork('alpha', 'genesis', HASH_B, seq(2))).rejects.toThrow(ForkTreeError)
    })

    it('supports non-genesis parent (child of another universe)', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2, node } = await t1.recordFork('beta', 'alpha', HASH_B, seq(2))
      expect(node.parent).toBe('alpha')
      expect(t2.nodeCount).toBe(2)
    })

    it('node_hash is deterministic x3', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        const tree = ForkTree.empty()
        const { node } = await tree.recordFork('alpha', 'genesis', HASH_A, seq(1))
        return node.node_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })

    it('different universe_id → different node_hash', async () => {
      const t0 = ForkTree.empty()
      const { node: n1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { node: n2 } = await t0.recordFork('beta', 'genesis', HASH_A, seq(1))
      expect(n1.node_hash).not.toBe(n2.node_hash)
    })
  })

  describe('getChildren() and getNode()', () => {
    it('getChildren("genesis") returns direct children', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))
      const children = t2.getChildren('genesis')
      expect(children).toContain('alpha')
      expect(children).toContain('beta')
      expect(children).toHaveLength(2)
    })

    it('getChildren returns children of a universe node', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'alpha', HASH_B, seq(2))
      expect(t2.getChildren('alpha')).toContain('beta')
    })

    it('getNode returns the correct node', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const node = t1.getNode('alpha')
      expect(node).not.toBeNull()
      expect(node!.universe_id).toBe('alpha')
    })

    it('getNode returns null for unknown universe_id', () => {
      const tree = ForkTree.empty()
      expect(tree.getNode('nonexistent')).toBeNull()
    })
  })

  describe('getAncestry()', () => {
    it('returns empty array for unknown universe', () => {
      const tree = ForkTree.empty()
      expect(tree.getAncestry('unknown')).toEqual([])
    })

    it('returns single-element path for genesis child', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      expect(t1.getAncestry('alpha')).toEqual(['alpha'])
    })

    it('returns full ancestry chain for nested universes', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('root', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('child', 'root', HASH_B, seq(2))
      const { tree: t3 } = await t2.recordFork('grandchild', 'child', HASH_C, seq(3))
      expect(t3.getAncestry('grandchild')).toEqual(['root', 'child', 'grandchild'])
    })
  })

  describe('depth', () => {
    it('depth=1 for single genesis child', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      expect(t1.depth).toBe(1)
    })

    it('depth=3 for 3-level hierarchy', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('a', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('b', 'a', HASH_B, seq(2))
      const { tree: t3 } = await t2.recordFork('c', 'b', HASH_C, seq(3))
      expect(t3.depth).toBe(3)
    })
  })

  describe('recordCollapse()', () => {
    it('seals losing nodes in the tree', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))

      const record = makeCollapseRecord('alpha', HASH_A, ['beta'], HASH_C, HASH_D, seq(3))
      const { tree: t3, event } = await t2.recordCollapse(record, seq(3))

      expect(t3.getNode('beta')!.is_sealed).toBe(true)
      expect(t3.getNode('alpha')!.is_sealed).toBe(false)
      expect(Object.isFrozen(event)).toBe(true)
    })

    it('CollapseEvent has 64-char event_hash', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))

      const record = makeCollapseRecord('alpha', HASH_A, ['beta'], HASH_C, HASH_D, seq(3))
      const { event } = await t2.recordCollapse(record, seq(3))

      expect(event.event_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(event.event_hash)).toBe(true)
    })

    it('collapseCount increments', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))

      const record = makeCollapseRecord('alpha', HASH_A, ['beta'], HASH_C, HASH_D, seq(3))
      const { tree: t3 } = await t2.recordCollapse(record, seq(3))

      expect(t0.collapseCount).toBe(0)
      expect(t3.collapseCount).toBe(1)
    })

    it('getCollapseEvents returns ordered events', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))
      const { tree: t3 } = await t2.recordFork('gamma', 'genesis', HASH_C, seq(3))

      const r1 = makeCollapseRecord('alpha', HASH_A, ['beta'], HASH_C, HASH_D, seq(4))
      const { tree: t4 } = await t3.recordCollapse(r1, seq(4))

      const r2 = makeCollapseRecord('alpha', HASH_A, ['gamma'], HASH_D, HASH_C, seq(5))
      const { tree: t5 } = await t4.recordCollapse(r2, seq(5))

      expect(t5.getCollapseEvents()).toHaveLength(2)
    })

    it('event_hash is deterministic x3', async () => {
      const record = makeCollapseRecord('alpha', HASH_A, ['beta'], HASH_C, HASH_D, seq(3))

      const hashes = await Promise.all([1, 2, 3].map(async () => {
        const t0 = ForkTree.empty()
        const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
        const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))
        const { event } = await t2.recordCollapse(record, seq(3))
        return event.event_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })
  })

  describe('certify()', () => {
    it('produces a frozen ForkTreeCertificate', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const cert = await t1.certify(seq(10))
      expect(Object.isFrozen(cert)).toBe(true)
    })

    it('tree_hash is 64-char hex', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const cert = await t1.certify(seq(10))
      expect(cert.tree_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(cert.tree_hash)).toBe(true)
    })

    it('certificate fields reflect tree state', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))
      const record = makeCollapseRecord('alpha', HASH_A, ['beta'], HASH_C, HASH_D, seq(3))
      const { tree: t3 } = await t2.recordCollapse(record, seq(3))
      const cert = await t3.certify(seq(10))

      expect(cert.node_count).toBe(2)
      expect(cert.sealed_count).toBe(1)
      expect(cert.collapse_count).toBe(1)
      expect(cert.is_replay_reconstructable).toBe(true)
      expect(cert.schema_version).toBe(FORK_TREE_SCHEMA_VERSION)
    })

    it('tree_hash is deterministic x3', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        const t0 = ForkTree.empty()
        const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
        const cert = await t1.certify(seq(10))
        return cert.tree_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })

    it('different trees produce different tree_hashes', async () => {
      const t0 = ForkTree.empty()
      const { tree: t1 } = await t0.recordFork('alpha', 'genesis', HASH_A, seq(1))
      const { tree: t2 } = await t1.recordFork('beta', 'genesis', HASH_B, seq(2))
      const cert1 = await t1.certify(seq(10))
      const cert2 = await t2.certify(seq(10))
      expect(cert1.tree_hash).not.toBe(cert2.tree_hash)
    })
  })
})
