// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 15
// EPISTEMIC TIER: T0/T2
//
// Covers paths with zero prior coverage in:
//   core/wasm-interface.ts        — loadWasmKernel catch path,
//                                   assertWasmParity mismatch + Uint8Array path
//   ledger/persistence.ts         — deserializeChain sequence violation (line 252)
//   ledger/state-capsule.ts       — importStateCapsule empty capsule (line 222),
//                                   exportStateCapsule epochEnd overflow (lines 110-112),
//                                   exportStateCapsule state-root mismatch (line 119)
//   ledger/block-replay.ts        — replayRange fromIndex > 0 (lines 84/99)
//   consensus/synthesis-swarm.ts  — SynthesisError class (line 104),
//                                   REJECTED + DEADLOCK verdicts
// ============================================================

import { describe, it, expect, beforeAll } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

// ── core/wasm-interface.ts ────────────────────────────────────────────────────

import { loadWasmKernel, assertWasmParity } from '../../src/core/wasm-interface.js'

describe('loadWasmKernel — catch path', () => {
  it('returns { loaded: false } when WASM path cannot be fetched', async () => {
    const kernel = await loadWasmKernel('/nonexistent-cov15-fixture.wasm')
    expect(kernel.loaded).toBe(false)
    expect(kernel.hash).toBeNull()
    expect(kernel.exports).toBeNull()
  })
})

describe('assertWasmParity', () => {
  it('throws DETERMINISM_VIOLATION when string outputs differ', () => {
    expect(() => assertWasmParity('aabbcc', 'aabbdd', 'test-label'))
      .toThrow('DETERMINISM_VIOLATION')
  })

  it('does not throw when Uint8Array outputs are byte-identical', () => {
    const a = new Uint8Array([0xab, 0xcd, 0xef])
    const b = new Uint8Array([0xab, 0xcd, 0xef])
    expect(() => assertWasmParity(a, b, 'match-test')).not.toThrow()
  })
})

// ── ledger/persistence.ts — deserializeChain sequence violation ───────────────

import { deserializeChain, LedgerPersistenceError } from '../../src/ledger/persistence.js'
import { LEDGER_SCHEMA_VERSION } from '../../src/ledger/types.js'

const ZERO_H = '0'.repeat(64)

function outOfOrderChainJson(): string {
  return JSON.stringify({
    schema_version: LEDGER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
    entries: [
      { sequence: '5', previous_hash: ZERO_H, frame_hash: ZERO_H, governance_hash: ZERO_H, timestamp_ms: 1_600_000_000_000 },
      { sequence: '3', previous_hash: ZERO_H, frame_hash: ZERO_H, governance_hash: ZERO_H, timestamp_ms: 1_600_000_000_001 },
    ],
    entry_count: 2,
    merkle_root: ZERO_H,
    snapshot_sequence: '5',
  })
}

describe('deserializeChain — sequence violation', () => {
  it('throws LedgerPersistenceError when entries are out of monotonic order', async () => {
    await expect(deserializeChain(outOfOrderChainJson())).rejects.toThrow(LedgerPersistenceError)
  })

  it('error message mentions Sequence violation', async () => {
    await expect(deserializeChain(outOfOrderChainJson())).rejects.toThrow(/Sequence violation/)
  })
})

// ── ledger/state-capsule.ts — importStateCapsule empty capsule ────────────────

import {
  importStateCapsule,
  exportStateCapsule,
  StateCapsuleError,
  STATE_CAPSULE_VERSION,
} from '../../src/ledger/state-capsule.js'
import type { StateCapsule } from '../../src/ledger/state-capsule.js'
import { NODE_CHECKPOINT_VERSION } from '../../src/ledger/node-checkpoint.js'
import type { NodeCheckpoint } from '../../src/ledger/node-checkpoint.js'

const ZERO_SHA = '0'.repeat(64) as SHA256Hex

const FAKE_CKPT: NodeCheckpoint = {
  node_id: 'test-node-cov15',
  block_height: 0,
  state_root: ZERO_SHA,
  checkpoint_hash: ZERO_SHA,
  schema_version: NODE_CHECKPOINT_VERSION,
  is_replay_reconstructable: true,
}

const EMPTY_CAPSULE: StateCapsule = {
  latest_epoch: null,
  anchor_block: null,
  pending_blocks: [],
  tip_checkpoint: FAKE_CKPT,
  capsule_hash: ZERO_SHA,
  schema_version: STATE_CAPSULE_VERSION,
  is_replay_reconstructable: true,
}

describe('importStateCapsule — empty capsule', () => {
  it('throws StateCapsuleError when anchor_block=null and pending_blocks=[]', async () => {
    await expect(importStateCapsule(EMPTY_CAPSULE)).rejects.toThrow(StateCapsuleError)
  })

  it('error message says no blocks to import', async () => {
    await expect(importStateCapsule(EMPTY_CAPSULE)).rejects.toThrow(/no blocks to import/)
  })
})

// ── ledger/state-capsule.ts + block-replay.ts — build shared chains ───────────

import { assembleBlock } from '../../src/ledger/block.js'
import { BlockChain } from '../../src/ledger/block-chain.js'
import type { EpochSeal } from '../../src/ledger/epoch-seal.js'
import { EPOCH_SEAL_VERSION } from '../../src/ledger/epoch-seal.js'
import type { LedgerEntry } from '../../src/ledger/types.js'

let singleBlockChain: BlockChain
let threeBlockChain: BlockChain

beforeAll(async () => {
  const e1: LedgerEntry = {
    sequence: BigInt(1) as unknown as SequenceNumber,
    previous_hash: ZERO_SHA,
    frame_hash: ZERO_SHA,
    governance_hash: ZERO_SHA,
    timestamp_ms: 1_600_000_000_001,
  }
  const b0 = await assembleBlock(null, [e1])
  singleBlockChain = BlockChain.empty().append(b0)

  const e2: LedgerEntry = { ...e1, sequence: BigInt(2) as unknown as SequenceNumber, timestamp_ms: 1_600_000_000_002 }
  const e3: LedgerEntry = { ...e1, sequence: BigInt(3) as unknown as SequenceNumber, timestamp_ms: 1_600_000_000_003 }
  const b1 = await assembleBlock(b0, [e2])
  const b2 = await assembleBlock(b1, [e3])
  threeBlockChain = BlockChain.empty().append(b0).append(b1).append(b2)
})

describe('exportStateCapsule — empty chain', () => {
  it('throws StateCapsuleError when chain has no blocks', async () => {
    await expect(exportStateCapsule('test-node-cov15', BlockChain.empty(), null))
      .rejects.toThrow(StateCapsuleError)
  })
})

describe('exportStateCapsule — epochEnd overflow', () => {
  it('throws StateCapsuleError when EpochSeal.end_height >= chain length', async () => {
    const overflowEpoch: EpochSeal = {
      epoch_number: 0,
      start_height: 0,
      end_height: 999,
      final_state_root: ZERO_SHA,
      merkle_root: ZERO_SHA,
      seal_hash: ZERO_SHA,
      schema_version: EPOCH_SEAL_VERSION,
      is_replay_reconstructable: true,
    }
    await expect(exportStateCapsule('test-node-cov15', singleBlockChain, overflowEpoch))
      .rejects.toThrow(StateCapsuleError)
  })

  it('error message mentions EpochSeal end_height', async () => {
    const overflowEpoch: EpochSeal = {
      epoch_number: 0,
      start_height: 0,
      end_height: 999,
      final_state_root: ZERO_SHA,
      merkle_root: ZERO_SHA,
      seal_hash: ZERO_SHA,
      schema_version: EPOCH_SEAL_VERSION,
      is_replay_reconstructable: true,
    }
    await expect(exportStateCapsule('test-node-cov15', singleBlockChain, overflowEpoch))
      .rejects.toThrow(/EpochSeal end_height/)
  })
})

describe('exportStateCapsule — anchor state-root mismatch', () => {
  it('throws StateCapsuleError when final_state_root does not match anchor block', async () => {
    // end_height=0 is in range for singleBlockChain (length=1),
    // but ZERO_SHA will not match the real state_root_after computed by assembleBlock
    const mismatchEpoch: EpochSeal = {
      epoch_number: 0,
      start_height: 0,
      end_height: 0,
      final_state_root: ZERO_SHA,
      merkle_root: ZERO_SHA,
      seal_hash: ZERO_SHA,
      schema_version: EPOCH_SEAL_VERSION,
      is_replay_reconstructable: true,
    }
    await expect(exportStateCapsule('test-node-cov15', singleBlockChain, mismatchEpoch))
      .rejects.toThrow(StateCapsuleError)
  })

  it('error message mentions state_root mismatch', async () => {
    const mismatchEpoch: EpochSeal = {
      epoch_number: 0,
      start_height: 0,
      end_height: 0,
      final_state_root: ZERO_SHA,
      merkle_root: ZERO_SHA,
      seal_hash: ZERO_SHA,
      schema_version: EPOCH_SEAL_VERSION,
      is_replay_reconstructable: true,
    }
    await expect(exportStateCapsule('test-node-cov15', singleBlockChain, mismatchEpoch))
      .rejects.toThrow(/state_root_after|final_state_root/)
  })
})

// ── ledger/block-replay.ts — replayRange fromIndex > 0 ───────────────────────

import { replayRange } from '../../src/ledger/block-replay.js'

describe('replayRange — fromIndex > 0', () => {
  it('uses blocks[fromIndex-1] as prevBlock context (fromIndex=1, toIndex=2)', async () => {
    const result = await replayRange(threeBlockChain, 1, 2)
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(2)
  })

  it('single-block mid-chain slice (fromIndex=2, toIndex=2)', async () => {
    const result = await replayRange(threeBlockChain, 2, 2)
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(1)
  })

  it('full chain replay hits blocks[i-1] path for i>0 in _replayBlocks', async () => {
    const result = await replayRange(threeBlockChain, 0, 2)
    expect(result.is_valid).toBe(true)
    expect(result.block_count).toBe(3)
    expect(result.state_trace).toHaveLength(3)
  })
})

// ── consensus/synthesis-swarm.ts — SynthesisError + verdict paths ─────────────

import {
  SynthesisError,
  runSynthesisSwarm,
} from '../../src/consensus/synthesis-swarm.js'
import type { AgentRole } from '../../src/consensus/synthesis-swarm.js'

describe('SynthesisError — class instantiation', () => {
  it('is instantiable with name SynthesisError', () => {
    const err = new SynthesisError('cov15 test')
    expect(err.name).toBe('SynthesisError')
    expect(err instanceof Error).toBe(true)
    expect(err instanceof SynthesisError).toBe(true)
  })
})

describe('runSynthesisSwarm — REJECTED verdict', () => {
  it('returns REJECTED when gamma output does not parse as COMMITTED', async () => {
    const callAgent = async (_s: string, _u: string, role: AgentRole) => ({
      output: role === 'gamma' ? 'NOT COMMITTED — all invariants violated' : 'let x = 1;',
      backend: 'stub',
      latency_ms: 1,
    })
    const req = {
      task: 'stub task',
      context: 'stub context',
      constitutional_constraints: [],
      sequence: BigInt(1) as unknown as SequenceNumber,
    }
    const record = await runSynthesisSwarm(req, callAgent)
    expect(record.verdict).toBe('REJECTED')
    expect(record.committed_output_hash).toBeNull()
    expect(record.is_replay_reconstructable).toBe(true)
  })
})

describe('runSynthesisSwarm — DEADLOCK verdict', () => {
  it('returns DEADLOCK when gamma says COMMITTED but alpha/beta fingerprints diverge below threshold', async () => {
    const callAgent = async (_s: string, _u: string, role: AgentRole) => {
      if (role === 'gamma') {
        return { output: '{"verdict":"COMMITTED","violations":[],"rationale":"approved"}', backend: 'stub', latency_ms: 1 }
      }
      if (role === 'alpha') {
        // Full-featured: async, try/catch, type annotations, const, sha256, early return, loop, destructuring
        return {
          output: [
            'async function process(): Promise<string> {',
            '  try {',
            '    const val: string = getData();',
            '    if (!val) return "empty";',
            '    const items = [1, 2, 3];',
            '    for (const item of items) {',
            '      const [a, b] = [item, item + 1]; void a; void b;',
            '    }',
            '    return await sha256(val);',
            '  } catch (err) {',
            '    throw new Error(String(err));',
            '  }',
            '}',
          ].join('\n'),
          backend: 'stub',
          latency_ms: 1,
        }
      }
      // beta: minimal — no async, no types, no hashing, no error handling, no loop, no destructuring
      return { output: 'let x = 1; x = x + 2;', backend: 'stub', latency_ms: 1 }
    }
    const req = {
      task: 'stub task',
      context: 'stub context',
      constitutional_constraints: [],
      sequence: BigInt(2) as unknown as SequenceNumber,
    }
    const record = await runSynthesisSwarm(req, callAgent)
    expect(record.verdict).toBe('DEADLOCK')
    expect(record.committed_output_hash).toBeNull()
    expect(record.convergence.converged).toBe(false)
    expect(record.is_replay_reconstructable).toBe(true)
  })
})
