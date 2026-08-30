// ============================================================
// Gate 56 — Consensus Adversarial
// ~22 tests: f=2 (n=7, threshold=5) and f=4 (n=13, threshold=9)
//   configurations; all-wrong-block_hash; mix valid + wrong-hash;
//   duplicate votes from same validator; invalid validator;
//   10 concurrent rounds → identical results; QC structure.
//
// Gaps filled vs test/unit/consensus.test.ts:
//   - f=2 configuration (n=7, threshold=5)
//   - f=4 configuration (n=13, threshold=9)
//   - All 7 votes have wrong block_hash → NO_QUORUM
//   - 5 correct + 2 wrong → COMMITTED (threshold=5 exactly met)
//   - 3 correct + 4 wrong → NO_QUORUM (4 < threshold 5)
//   - Duplicate vote from same validator → counted once
//   - Vote from unknown validator → filtered
//   - 10 concurrent rounds → identical outcome and threshold
// ============================================================

import { describe, it, expect, beforeAll } from 'vitest'
import { runConsensusRound } from '../../src/consensus/kernel.js'
import { generateKeypair, signVote } from '../../src/consensus/crypto.js'
import { quorumThreshold } from '../../src/consensus/quorum.js'
import type {
  ConsensusBlock, Vote, ValidatorSet, ValidatorEntry, ValidatorId, ValidatorKeyPair,
} from '../../src/consensus/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

// ─── Fixtures ─────────────────────────────────────────────

type ValidatorDef = { entry: ValidatorEntry; keypair: ValidatorKeyPair }

async function buildValidators(n: number): Promise<ValidatorDef[]> {
  return Promise.all(
    Array.from({ length: n }, async (_, i) => {
      const seed = new Uint8Array(32).fill(0)
      seed[0] = i + 1
      const keypair = await generateKeypair(seed)
      const id = `v${i}` as ValidatorId
      return {
        entry: Object.freeze<ValidatorEntry>({ id, publicKey: keypair.publicKey }),
        keypair,
      }
    }),
  )
}

function makeValidatorSet(defs: ValidatorDef[], f: number): ValidatorSet {
  return Object.freeze<ValidatorSet>({
    validators: Object.freeze(defs.map(d => d.entry)),
    n: defs.length,
    f,
  })
}

function makeBlock(blockChar = 'b', s = 1): ConsensusBlock {
  return Object.freeze<ConsensusBlock>({
    block_hash: h(blockChar),
    sequence: seq(s),
    proposer: 'v0' as ValidatorId,
    parent_hash: h('0'),
    timestamp_ms: 1_600_000_000_000,
  })
}

async function castVotes(
  defs: ValidatorDef[],
  count: number,
  blockHash: SHA256Hex,
  blockSeq: SequenceNumber,
): Promise<Vote[]> {
  return Promise.all(
    defs.slice(0, count).map(async d => {
      const sig = await signVote(d.keypair.privateKey, blockHash)
      return Object.freeze<Vote>({
        validator: d.entry.id,
        block_hash: blockHash,
        sequence: blockSeq,
        signature: sig,
      })
    }),
  )
}

// ─── f=2 configuration (n=7, threshold=5) ─────────────────

describe('Consensus: f=2, n=7, threshold=5', () => {
  let defs7: ValidatorDef[]

  beforeAll(async () => { defs7 = await buildValidators(7) })

  it('quorumThreshold(2) === 5', () => {
    expect(quorumThreshold(2)).toBe(5)
  })

  it('exactly 5 valid votes → COMMITTED', async () => {
    const block = makeBlock('b', 1)
    const vs = makeValidatorSet(defs7, 2)
    const votes = await castVotes(defs7, 5, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('COMMITTED')
    expect(result.votes_received).toBe(5)
    expect(result.threshold).toBe(5)
  })

  it('all 7 valid votes → COMMITTED', async () => {
    const block = makeBlock('b', 2)
    const vs = makeValidatorSet(defs7, 2)
    const votes = await castVotes(defs7, 7, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('COMMITTED')
    expect(result.votes_received).toBe(7)
  })

  it('4 valid votes → NO_QUORUM', async () => {
    const block = makeBlock('c', 3)
    const vs = makeValidatorSet(defs7, 2)
    const votes = await castVotes(defs7, 4, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('NO_QUORUM')
    expect(result.votes_received).toBe(4)
  })

  it('all 7 votes have wrong block_hash → NO_QUORUM (0 valid)', async () => {
    const block = makeBlock('b', 4)
    const vs = makeValidatorSet(defs7, 2)
    const votes = await castVotes(defs7, 7, h('z'), block.sequence)  // wrong hash
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('NO_QUORUM')
    expect(result.votes_received).toBe(0)
  })

  it('5 correct + 2 wrong-hash → COMMITTED (threshold exactly met)', async () => {
    const block = makeBlock('b', 5)
    const vs = makeValidatorSet(defs7, 2)
    const correct = await castVotes(defs7.slice(0, 5), 5, block.block_hash, block.sequence)
    const wrong = await castVotes(defs7.slice(5), 2, h('z'), block.sequence)
    const result = await runConsensusRound(block, vs, [...correct, ...wrong])
    expect(result.outcome).toBe('COMMITTED')
    expect(result.votes_received).toBe(5)
  })

  it('3 correct + 4 wrong-hash → NO_QUORUM', async () => {
    const block = makeBlock('b', 6)
    const vs = makeValidatorSet(defs7, 2)
    const correct = await castVotes(defs7.slice(0, 3), 3, block.block_hash, block.sequence)
    const wrong = await castVotes(defs7.slice(3), 4, h('z'), block.sequence)
    const result = await runConsensusRound(block, vs, [...correct, ...wrong])
    expect(result.outcome).toBe('NO_QUORUM')
    expect(result.votes_received).toBe(3)
  })
})

// ─── f=4 configuration (n=13, threshold=9) ────────────────

describe('Consensus: f=4, n=13, threshold=9', () => {
  let defs13: ValidatorDef[]

  beforeAll(async () => { defs13 = await buildValidators(13) })

  it('quorumThreshold(4) === 9', () => {
    expect(quorumThreshold(4)).toBe(9)
  })

  it('exactly 9 valid votes → COMMITTED', async () => {
    const block = makeBlock('d', 10)
    const vs = makeValidatorSet(defs13, 4)
    const votes = await castVotes(defs13, 9, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('COMMITTED')
    expect(result.votes_received).toBe(9)
    expect(result.threshold).toBe(9)
  })

  it('8 valid votes → NO_QUORUM', async () => {
    const block = makeBlock('d', 11)
    const vs = makeValidatorSet(defs13, 4)
    const votes = await castVotes(defs13, 8, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('NO_QUORUM')
    expect(result.votes_received).toBe(8)
  })

  it('all 13 votes correct → COMMITTED, votes_received=13', async () => {
    const block = makeBlock('d', 12)
    const vs = makeValidatorSet(defs13, 4)
    const votes = await castVotes(defs13, 13, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('COMMITTED')
    expect(result.votes_received).toBe(13)
  })
})

// ─── Edge cases ───────────────────────────────────────────

describe('Consensus: edge cases', () => {
  let defs7: ValidatorDef[]

  beforeAll(async () => { defs7 = await buildValidators(7) })

  it('duplicate vote from same validator counted once', async () => {
    const block = makeBlock('e', 20)
    const vs = makeValidatorSet(defs7, 2)
    const singleVote = (await castVotes(defs7, 1, block.block_hash, block.sequence))[0]!
    // Send the same vote 7 times — should only count as 1
    const votes = Array.from({ length: 7 }, () => singleVote)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('NO_QUORUM')
    expect(result.votes_received).toBe(1)
  })

  it('vote from unknown validator is filtered', async () => {
    const block = makeBlock('e', 21)
    const vs = makeValidatorSet(defs7, 2)
    const goodVotes = await castVotes(defs7, 4, block.block_hash, block.sequence)
    // Fabricate a vote from unknown validator
    const unknownVote = Object.freeze<Vote>({
      validator: 'unknown-validator' as ValidatorId,
      block_hash: block.block_hash,
      sequence: block.sequence,
      signature: 'a'.repeat(128) as Vote['signature'],
    })
    const result = await runConsensusRound(block, vs, [...goodVotes, unknownVote])
    expect(result.votes_received).toBe(4)
    expect(result.outcome).toBe('NO_QUORUM')
  })

  it('COMMITTED result has qc with correct block_hash', async () => {
    const block = makeBlock('f', 30)
    const vs = makeValidatorSet(defs7, 2)
    const votes = await castVotes(defs7, 5, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.qc).toBeDefined()
    expect(result.qc!.block_hash).toBe(block.block_hash)
    expect(result.qc!.qc_hash).toHaveLength(64)
  })

  it('NO_QUORUM result has no qc', async () => {
    const block = makeBlock('f', 31)
    const vs = makeValidatorSet(defs7, 2)
    const result = await runConsensusRound(block, vs, [])
    expect(result.outcome).toBe('NO_QUORUM')
    expect(result.qc).toBeUndefined()
  })
})

// ─── Concurrent determinism ───────────────────────────────

describe('Consensus: concurrent determinism', () => {
  it('10 concurrent rounds on identical input → identical outcome and threshold', async () => {
    const defs = await buildValidators(7)
    const block = makeBlock('g', 40)
    const vs = makeValidatorSet(defs, 2)
    const votes = await castVotes(defs, 5, block.block_hash, block.sequence)
    const results = await Promise.all(
      Array.from({ length: 10 }, () => runConsensusRound(block, vs, votes)),
    )
    for (const r of results) {
      expect(r.outcome).toBe(results[0]!.outcome)
      expect(r.threshold).toBe(results[0]!.threshold)
      expect(r.votes_received).toBe(results[0]!.votes_received)
      expect(r.qc?.block_hash).toBe(results[0]!.qc?.block_hash)
    }
  })

  it('result is frozen', async () => {
    const defs = await buildValidators(7)
    const block = makeBlock('g', 41)
    const vs = makeValidatorSet(defs, 2)
    const votes = await castVotes(defs, 5, block.block_hash, block.sequence)
    const result = await runConsensusRound(block, vs, votes)
    expect(Object.isFrozen(result)).toBe(true)
  })
})
