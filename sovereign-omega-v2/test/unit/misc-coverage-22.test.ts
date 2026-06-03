// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 22
// EPISTEMIC TIER: T0/T2
//
// Covers branch paths with zero prior coverage in:
//   memory/slab-allocator.ts
//     — allocate() decommissioned-slab skip (line 124 true)
//   verifier/execute.ts
//     — timeout inner arrow fires when verifier exceeds max_latency_ms
//   pipeline/schema.ts
//     — extractBestPositioning sort comparator (requires ≥2 candidates)
//   skill-harness/scanner/codebase-scanner.ts
//     — walkDir line 97 false: entry is neither directory nor file (symlink)
// ============================================================

import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

// ── memory/slab-allocator.ts line 124 — decommissioned slab skip ──────────────
//
// allocate() iterates tier_ids:
//   if (s.is_decommissioned) continue   ← line 124 true branch
//
// Steps:
//   1. Allocate chunk on TINY → get handle
//   2. Release → sets last_release_epoch
//   3. decommissionEmpty at epoch ≥ release + threshold → is_decommissioned=true
//   4. allocate again on TINY → loop encounters the decommissioned slab, skips it
//      and creates a fresh slab for the new allocation.

import {
  SlabAllocator,
  SLAB_DECOMMISSION_THRESHOLD,
} from '../../src/memory/slab-allocator.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

describe('SlabAllocator.allocate — decommissioned-slab skip (line 124 true)', () => {
  it('skips a decommissioned slab and allocates into a fresh slab (covers line 124 true)', async () => {
    let a = SlabAllocator.empty()

    // 1. Allocate one chunk — creates the first TINY slab
    const { allocator: a1, handle: h1 } = await a.allocate('TINY', seq(1))
    // 2. Release it — sets last_release_epoch on the slab
    const { allocator: a2 } = await a1.release(h1, seq(2))
    // 3. Decommission: current_epoch - last_release_epoch >= SLAB_DECOMMISSION_THRESHOLD
    const decommEpoch = seq(2 + SLAB_DECOMMISSION_THRESHOLD)
    const { allocator: a3, decommissioned_count } = await a2.decommissionEmpty(decommEpoch)
    expect(decommissioned_count).toBe(1)
    expect(a3.getSlabs('TINY')[0]!.is_decommissioned).toBe(true)

    // 4. Allocate again on TINY — the decommissioned slab is skipped (line 124 true),
    //    no free slab found, so a NEW slab is created.
    const { allocator: a4, handle: h2 } = await a3.allocate('TINY', seq(20))
    expect(h2.chunk_index).toBe(0)               // fresh slab, first chunk
    expect(h2.slab_id).not.toBe(h1.slab_id)     // different slab from the decommissioned one
    expect(a4.slabCount).toBe(2)                 // original (decommissioned) + new slab
    expect(a4.totalAllocated).toBe(1)            // only h2 is allocated
  })

  it('multiple decommissioned slabs are all skipped before new slab creation', async () => {
    let a = SlabAllocator.empty()

    // Create and decommission two slabs on SMALL
    for (let round = 0; round < 2; round++) {
      const { allocator: a1, handle: h } = await a.allocate('SMALL', seq(round * 10 + 1))
      const { allocator: a2 } = await a1.release(h, seq(round * 10 + 2))
      const { allocator: a3 } = await a2.decommissionEmpty(seq(round * 10 + 2 + SLAB_DECOMMISSION_THRESHOLD))
      a = a3
    }
    // Both slabs are decommissioned
    const smallSlabs = a.getSlabs('SMALL')
    expect(smallSlabs.length).toBe(2)
    expect(smallSlabs.every(s => s.is_decommissioned)).toBe(true)

    // Allocate on SMALL: both decommissioned slabs skipped → fresh slab
    const { allocator: a4, handle: h3 } = await a.allocate('SMALL', seq(100))
    expect(h3.chunk_index).toBe(0)
    expect(a4.getSlabs('SMALL').length).toBe(3) // 2 decommissioned + 1 fresh
  })
})

// ── verifier/execute.ts — timeout arrow fires on slow verifier ───────────────
//
// executeVerifiers uses Promise.race([verifier.verify(input), timeout(max_latency_ms, id)]).
// When the verifier never resolves within max_latency_ms, the timeout's inner
// rejection arrow fires, Promise.race rejects, and the catch block continues.
//
// Covered: the `() => reject(new Error(...))` arrow inside setTimeout.

import { executeVerifiers } from '../../src/verifier/execute.js'
import { verifierRegistry } from '../../src/verifier/registry.js'
import { CalibrationDomain, VerifierClass } from '../../src/core/types.js'
import type { VerifierInput } from '../../src/verifier/types.js'

const EXEC_INPUT: VerifierInput = { claim_id: 'c22-timeout', domain: 'test', content: 'coverage' }
let _uid = 0
const uid22 = () => `cov22-${++_uid}`

describe('executeVerifiers — timeout inner arrow fires (covers setTimeout callback)', () => {
  it('slow verifier times out: output is skipped and result has 0 outputs', async () => {
    const id = uid22()
    // max_latency_ms = 10 — fires after 10ms
    verifierRegistry.register({
      definition: {
        verifier_id: id,
        verifier_class: VerifierClass.V3_RETRIEVAL,
        trust_class: CalibrationDomain.ADVISORY_EXCLUDED,
        version: '1.0.0',
        description: 'never-resolves verifier for timeout coverage',
        max_latency_ms: 10,
        is_deterministic: false,
      },
      // Returns a Promise that never settles — timeout fires first
      verify: (_: VerifierInput) => new Promise(() => { /* intentionally never resolves */ }),
    })

    const result = await executeVerifiers(EXEC_INPUT, [id])
    // Timeout rejection caught by the for-loop catch block → output skipped
    expect(result.outputs).toHaveLength(0)
    expect(result.correlation_alert).toBe(false)
  })

  it('verifier that resolves after timeout is also skipped', async () => {
    const id = uid22()

    verifierRegistry.register({
      definition: {
        verifier_id: id,
        verifier_class: VerifierClass.V3_RETRIEVAL,
        trust_class: CalibrationDomain.ADVISORY_EXCLUDED,
        version: '1.0.0',
        description: 'slow verifier resolves after timeout',
        max_latency_ms: 10,
        is_deterministic: false,
      },
      verify: (_: VerifierInput) => new Promise((_, reject) => {
        // Reject after 50ms — but the 10ms timeout fires first
        setTimeout(() => reject(new Error('slow verifier rejection')), 50)
      }),
    })

    // Timeout fires at 10ms before the verifier rejects at 50ms
    const result = await executeVerifiers(EXEC_INPUT, [id])
    expect(result.outputs).toHaveLength(0)
  })
})

// ── pipeline/schema.ts — extractBestPositioning sort comparator ───────────────
//
// extractBestPositioning:
//   const best = [...candidates].sort((a, b) => b[1] - a[1])[0]
//                                               ↑ sort comparator arrow
//
// This comparator is only entered when candidates.length ≥ 2.
// All existing tests use ProjectionState with empty positioning_candidates,
// so the sort comparator arrow is never executed. Here we build a state
// with multiple candidates to fire it.

import { buildDecisionSchema } from '../../src/pipeline/schema.js'
import { createProjectionState } from '../../src/projection/reducer.js'
import type { Confidence } from '../../src/core/types.js'

const HEURISTIC: Confidence = {
  type: 'heuristic',
  value: 0.75,
  disclaimer: true,
  source: 'cov22',
}

describe('buildDecisionSchema — extractBestPositioning sort comparator (pipeline/schema.ts)', () => {
  it('sort comparator fires when positioning_candidates has ≥2 entries (covers sort arrow)', () => {
    const base = createProjectionState('1.0.0')
    // Construct state with 3 positioning candidates
    const stateWith3 = Object.freeze({
      ...base,
      positioning_candidates: Object.freeze([
        Object.freeze(['Gamma strategy', 0.6] as [string, number]),
        Object.freeze(['Alpha strategy', 0.9] as [string, number]),
        Object.freeze(['Beta strategy', 0.75] as [string, number]),
      ]),
    })

    const schema = buildDecisionSchema(stateWith3, HEURISTIC, 1.0)
    // extractBestPositioning sorts and picks highest-score: Alpha (0.9)
    expect(schema.positioning).toContain('Alpha strategy')
  })

  it('returns fallback when positioning_candidates is empty (line 78 early return)', () => {
    const base = createProjectionState('1.0.0')
    const stateEmpty = Object.freeze({ ...base, positioning_candidates: Object.freeze([]) })

    const schema = buildDecisionSchema(stateEmpty, HEURISTIC, 1.0)
    expect(schema.positioning).toBe('Positioning analysis pending.')
  })

  it('single candidate: sort comparator not needed, best is the only entry', () => {
    const base = createProjectionState('1.0.0')
    const stateOne = Object.freeze({
      ...base,
      positioning_candidates: Object.freeze([
        Object.freeze(['Solo strategy', 0.5] as [string, number]),
      ]),
    })

    const schema = buildDecisionSchema(stateOne, HEURISTIC, 1.0)
    expect(schema.positioning).toContain('Solo strategy')
  })
})

// ── skill-harness/scanner/codebase-scanner.ts line 97 false ──────────────────
//
// walkDir iterates directory entries:
//   if (entry.isDirectory()) { ... recurse ... }
//   else if (entry.isFile()) { ... process ... }   ← line 97
//
// When an entry is neither a directory nor a regular file (e.g. a symlink),
// both predicates return false and the entry is silently skipped.
// Node.js readdirSync with {withFileTypes:true} returns Dirent objects where
// isFile()=false for symlinks — they need isSymbolicLink() instead.

import { scanCodebase } from '../../src/skill-harness/scanner/codebase-scanner.js'

describe('scanCodebase walkDir — symlink entry (line 97 false branch)', () => {
  it('silently ignores symlink entries (isDirectory=false, isFile=false) — covers line 97 false', async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-cov22-sym-'))
    try {
      // Real .rs file so the scan returns at least one file
      const realFile = path.join(dir, 'lib.rs')
      fs.writeFileSync(realFile, 'pub fn ok() {}\n')

      // Symlink to the real file — dirent.isFile()=false, dirent.isDirectory()=false
      // → line 97 false branch taken (entry silently ignored)
      try {
        fs.symlinkSync(realFile, path.join(dir, 'link.rs'))
      } catch {
        // Skip symlink creation if not supported (some environments)
        return
      }

      const result = await scanCodebase(dir)
      // Scan succeeds on the real file; symlink was skipped silently
      expect(result.total_files).toBeGreaterThanOrEqual(1)
      // No double-counting — symlink was not processed as a file
      const allRefs = result.patterns.flatMap(p => p.file_refs)
      expect(allRefs.filter(r => r.includes('lib.rs')).length).toBe(1)
    } finally {
      fs.rmSync(dir, { recursive: true, force: true })
    }
  })
})
