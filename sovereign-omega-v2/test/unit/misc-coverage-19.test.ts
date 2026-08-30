// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 19
// EPISTEMIC TIER: T0/T2
//
// Covers paths with zero prior coverage in:
//   core/fixedpoint.ts        — bernsteinLCBQ32 non-finite variance term (line 89)
//   memory/fork-tree.ts       — recordCollapse with unknown sealed_id (line 158 false)
//                             — getAncestry cycle guard (line 175)
//   ledger/state-capsule.ts   — verifyStateCapsule catch→false (line 196)
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'

// ── core/fixedpoint.ts line 89 — non-finite variance term ────────────────────
//
// bernsteinLCBQ32(sum, sumSq, n, alpha):
//   variance = (sumSq - mulQ32(sum,sum)/n) / (n-1)
//   varianceTermF = Math.sqrt(2 * fromQ32(variance) * fromQ32(logTerm) / Number(n))
//
// When sumSq = 2n**1024n (a bigint far above IEEE 754 max ≈ 2^1023.97):
//   fromQ32(variance) = Number(2n**1024n) / 2**32 = Infinity
//   varianceTermF = Math.sqrt(Infinity) = Infinity → !isFinite → RangeError line 89

import { bernsteinLCBQ32, toQ32, type Q32_32 } from '../../src/core/fixedpoint.js'

describe('bernsteinLCBQ32 — non-finite variance term (line 89)', () => {
  it('throws RangeError when fromQ32(variance) overflows to Infinity (covers line 89)', () => {
    // sumSq = 2^1024 as Q32_32: Number(2n**1024n) = Infinity (exceeds IEEE 754 max)
    // sum = 0n so sumSqMean = 0, rawVariance = sumSq, variance = rawVariance (n=2)
    const hugeSumSq = (2n ** 1024n) as Q32_32
    expect(() =>
      bernsteinLCBQ32(
        0n as Q32_32,       // sum = 0
        hugeSumSq,          // sumSq → Infinity when converted to float
        2n,                 // n = 2 so n > 1 branch taken, variance = rawVariance
        toQ32(0.05),        // alpha = 0.05, logTerm is finite
      )
    ).toThrow(RangeError)
  })

  it('error message mentions non-finite variance term', () => {
    const hugeSumSq = (2n ** 1024n) as Q32_32
    expect(() =>
      bernsteinLCBQ32(0n as Q32_32, hugeSumSq, 2n, toQ32(0.05))
    ).toThrow('non-finite variance term')
  })
})

// ── memory/fork-tree.ts line 158 — sealed_id not in nodes (if(existing) false) ─
//
// recordCollapse iterates sealed_ids:
//   const existing = next_nodes.get(id)
//   if (existing) { ... }          ← line 158
//
// When the sealed_universe_id is not in the tree, existing = undefined → false branch.

import { ForkTree } from '../../src/memory/fork-tree.js'
import type { CollapseRecord } from '../../src/memory/collapse.js'
import { COLLAPSE_SCHEMA_VERSION } from '../../src/memory/collapse.js'

const FAKE_HASH = '0'.repeat(64) as import('../../src/core/types.js').SHA256Hex
const SEQ1 = BigInt(1) as unknown as SequenceNumber

describe('ForkTree.recordCollapse — sealed_id not in nodes (line 158 false)', () => {
  it('silently skips sealed_id that does not exist in the tree (covers line 158 false)', async () => {
    const tree = ForkTree.empty()

    // CollapseRecord with a sealed_universe_id that was never added to the tree
    const record: CollapseRecord = {
      winner_id:         'winner-a',
      winner_hash:       FAKE_HASH,
      sealed_universes:  [{
        universe_id:    'nonexistent-universe',
        terminal_hash:  FAKE_HASH,
        lineage_length: 0,
        fork_hash:      FAKE_HASH,
      }],
      total_collapsed:   1,
      convergence_hash:  FAKE_HASH,
      collapse_hash:     FAKE_HASH,
      sequence:          SEQ1,
      schema_version:    COLLAPSE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    }

    // Should complete without error — the missing id is just silently skipped
    const { tree: tree2, event } = await tree.recordCollapse(record, SEQ1)
    expect(event.sealed_ids).toEqual(['nonexistent-universe'])
    // Tree node count unchanged — no node was sealed
    expect(tree2.nodeCount).toBe(0)
  })
})

// ── memory/fork-tree.ts line 175 — cycle guard in getAncestry ────────────────
//
// getAncestry walks parent chain:
//   if (visited.has(current)) break   ← line 175
//
// Create two nodes where A's parent is B and B's parent is A.
// recordFork() does not validate that the parent exists, so cycles are possible.
// getAncestry('a') → walk to 'b' → walk back to 'a' → visited.has('a') → break.

describe('ForkTree.getAncestry — cycle guard (line 175)', () => {
  it('breaks on cycle and returns partial path without infinite loop (covers line 175)', async () => {
    const tree0 = ForkTree.empty()
    // node 'u-alpha' with parent 'u-beta' (u-beta doesn't exist yet)
    const { tree: tree1 } = await tree0.recordFork('u-alpha', 'u-beta', FAKE_HASH, SEQ1)
    // node 'u-beta' with parent 'u-alpha' → creates a cycle: alpha→beta→alpha→…
    const { tree: tree2 } = await tree1.recordFork('u-beta', 'u-alpha', FAKE_HASH, SEQ1)

    // getAncestry must terminate and return a finite path
    const path = tree2.getAncestry('u-alpha')
    expect(Array.isArray(path)).toBe(true)
    // The cycle guard broke before appending all nodes — path is non-empty but finite
    expect(path.length).toBeGreaterThanOrEqual(1)
    // 'u-alpha' was visited first, so it appears in path
    expect(path).toContain('u-alpha')
  })
})

// ── ledger/state-capsule.ts line 196 — verifyStateCapsule catch→false ─────────
//
// verifyStateCapsule wraps everything in try/catch:
//   try { ... } catch { return false }   ← line 196
//
// Accessing capsule.tip_checkpoint.checkpoint_hash throws TypeError when
// tip_checkpoint is null — the catch block returns false instead of propagating.

import { verifyStateCapsule } from '../../src/ledger/state-capsule.js'
import type { StateCapsule } from '../../src/ledger/state-capsule.js'
import { STATE_CAPSULE_VERSION } from '../../src/ledger/state-capsule.js'

describe('verifyStateCapsule — catch returns false (line 196)', () => {
  it('returns false (not throws) when tip_checkpoint is null — catch block fires (covers line 196)', async () => {
    const badCapsule = {
      latest_epoch:    null,
      anchor_block:    null,
      pending_blocks:  [],
      tip_checkpoint:  null,   // accessing .checkpoint_hash will throw TypeError
      capsule_hash:    FAKE_HASH,
      schema_version:  STATE_CAPSULE_VERSION,
      is_replay_reconstructable: true,
    } as unknown as StateCapsule

    // Must resolve false, never reject — the catch block swallows the TypeError
    await expect(verifyStateCapsule(badCapsule)).resolves.toBe(false)
  })

  it('returns false (not throws) when capsule fields are deeply malformed', async () => {
    const malformed = {
      latest_epoch:   { seal_hash: null },  // wrong shape — will cause issues deeper
      anchor_block:   null,
      pending_blocks: [],
      tip_checkpoint: null,
      capsule_hash:   FAKE_HASH,
      schema_version: STATE_CAPSULE_VERSION,
      is_replay_reconstructable: true,
    } as unknown as StateCapsule

    await expect(verifyStateCapsule(malformed)).resolves.toBe(false)
  })
})
