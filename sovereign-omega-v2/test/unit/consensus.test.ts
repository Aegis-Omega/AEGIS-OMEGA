// ============================================================
// Gate 19 + Gate 22 — HotStuff Ω Consensus Tests (Ed25519)
// ~26 tests: Ed25519 keypair, signing, verification, quorum
//   threshold, QC formation, kernel outcomes, determinism.
// ============================================================

import { describe, it, expect, beforeAll } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { sha256Bytes } from '../../src/core/hashing.js'
import { GENESIS_HASH } from '../../src/ledger/types.js'
import {
  type ValidatorId,
  type ValidatorKeyPair,
  type ValidatorEntry,
  type ConsensusBlock,
  type Vote,
  type ValidatorSet,
  ConsensusError,
} from '../../src/consensus/types.js'
import { generateKeypair, signVote, verifyVote } from '../../src/consensus/crypto.js'
import {
  quorumThreshold,
  validateValidatorSet,
  collectValidVotes,
  isQuorum,
} from '../../src/consensus/quorum.js'
import { runConsensusRound } from '../../src/consensus/kernel.js'

// ─── Shared keypairs (generated once) ──────────────────────

const NAMES = ['V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7']
const keypairs: Record<string, ValidatorKeyPair> = {}

beforeAll(async () => {
  for (const name of NAMES) {
    const seed = await sha256Bytes(new TextEncoder().encode(`aegis-test-validator:${name}`))
    keypairs[name] = await generateKeypair(seed)
  }
})

// ─── Helpers ───────────────────────────────────────────────

const TS = 1_600_000_000_000

function vid(name: string): ValidatorId { return name as ValidatorId }

function blockHash(n: number): SHA256Hex {
  return (n.toString(16).padStart(64, '0')) as SHA256Hex
}

function makeBlock(seq: bigint = 1n, proposer = vid('V1')): ConsensusBlock {
  return Object.freeze({
    block_hash: blockHash(1),
    sequence: seq as SequenceNumber,
    proposer,
    parent_hash: GENESIS_HASH,
    timestamp_ms: TS,
  })
}

function makeEntry(name: string): ValidatorEntry {
  return Object.freeze({ id: vid(name), publicKey: keypairs[name]!.publicKey })
}

function makeValidatorSet(names: string[], f: number): ValidatorSet {
  const validators = names.map(n => makeEntry(n))
  return Object.freeze({ validators: Object.freeze(validators), n: names.length, f })
}

async function castVote(name: string, block: ConsensusBlock): Promise<Vote> {
  return Object.freeze({
    validator: vid(name),
    block_hash: block.block_hash,
    sequence: block.sequence,
    signature: await signVote(keypairs[name]!.privateKey, block.block_hash),
  })
}

async function castAllVotes(names: string[], block: ConsensusBlock): Promise<Vote[]> {
  return Promise.all(names.map(n => castVote(n, block)))
}

// ─── Ed25519 crypto ────────────────────────────────────────

describe('Ed25519 generateKeypair / signVote / verifyVote', () => {
  it('public key is 64-char hex', () => {
    expect(keypairs['V1']!.publicKey).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(keypairs['V1']!.publicKey)).toBe(true)
  })

  it('signature is 128-char hex (64-byte Ed25519)', async () => {
    const sig = await signVote(keypairs['V1']!.privateKey, blockHash(1))
    expect(sig).toHaveLength(128)
    expect(/^[0-9a-f]{128}$/.test(sig)).toBe(true)
  })

  it('signVote is deterministic — same inputs → same output 3×', async () => {
    const bh = blockHash(42)
    const s1 = await signVote(keypairs['V1']!.privateKey, bh)
    const s2 = await signVote(keypairs['V1']!.privateKey, bh)
    const s3 = await signVote(keypairs['V1']!.privateKey, bh)
    expect(s1).toBe(s2)
    expect(s2).toBe(s3)
  })

  it('different validators produce different signatures', async () => {
    const bh = blockHash(1)
    const s1 = await signVote(keypairs['V1']!.privateKey, bh)
    const s2 = await signVote(keypairs['V2']!.privateKey, bh)
    expect(s1).not.toBe(s2)
  })

  it('different block hashes produce different signatures', async () => {
    const s1 = await signVote(keypairs['V1']!.privateKey, blockHash(1))
    const s2 = await signVote(keypairs['V1']!.privateKey, blockHash(2))
    expect(s1).not.toBe(s2)
  })

  it('verifyVote returns true for valid signature', async () => {
    const bh = blockHash(7)
    const sig = await signVote(keypairs['V1']!.privateKey, bh)
    expect(await verifyVote(keypairs['V1']!.publicKey, bh, sig)).toBe(true)
  })

  it('verifyVote returns false for wrong public key', async () => {
    const bh = blockHash(7)
    const sig = await signVote(keypairs['V1']!.privateKey, bh)
    expect(await verifyVote(keypairs['V2']!.publicKey, bh, sig)).toBe(false)
  })

  it('verifyVote returns false for wrong block_hash', async () => {
    const sig = await signVote(keypairs['V1']!.privateKey, blockHash(1))
    expect(await verifyVote(keypairs['V1']!.publicKey, blockHash(2), sig)).toBe(false)
  })

  it('generateKeypair is deterministic — same seed → same keys 3×', async () => {
    const seed = await sha256Bytes(new TextEncoder().encode('determinism-test'))
    const k1 = await generateKeypair(seed)
    const k2 = await generateKeypair(seed)
    const k3 = await generateKeypair(seed)
    expect(k1.publicKey).toBe(k2.publicKey)
    expect(k2.publicKey).toBe(k3.publicKey)
  })
})

// ─── ValidatorSet ──────────────────────────────────────────

describe('validateValidatorSet', () => {
  it('n=4,f=1 is valid', () => {
    expect(() => validateValidatorSet(makeValidatorSet(['V1','V2','V3','V4'], 1))).not.toThrow()
  })

  it('n=7,f=2 is valid', () => {
    expect(() => validateValidatorSet(makeValidatorSet(['V1','V2','V3','V4','V5','V6','V7'], 2))).not.toThrow()
  })

  it('n=3,f=1 violates n ≥ 3f+1 → throws', () => {
    expect(() => validateValidatorSet(makeValidatorSet(['V1','V2','V3'], 1))).toThrow(ConsensusError)
  })

  it('quorumThreshold(f=1) = 3', () => { expect(quorumThreshold(1)).toBe(3) })
  it('quorumThreshold(f=2) = 5', () => { expect(quorumThreshold(2)).toBe(5) })
})

// ─── collectValidVotes / isQuorum ──────────────────────────

describe('collectValidVotes', () => {
  it('all valid votes pass through', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2','V3','V4'], block)
    const valid = await collectValidVotes(block, votes, vs)
    expect(valid.length).toBe(4)
  })

  it('duplicate validator votes deduplicated — first wins', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const vote1 = await castVote('V1', block)
    const vote2 = await castVote('V2', block)
    const valid = await collectValidVotes(block, [vote1, vote1, vote2], vs)
    expect(valid.length).toBe(2)
  })

  it('unknown validator rejected', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const alien = vid('ALIEN')
    const badSig = await signVote(keypairs['V1']!.privateKey, block.block_hash)
    const vote: Vote = Object.freeze({
      validator: alien,
      block_hash: block.block_hash,
      sequence: block.sequence,
      signature: badSig,
    })
    const valid = await collectValidVotes(block, [vote], vs)
    expect(valid.length).toBe(0)
  })

  it('wrong block_hash rejected', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const wrongHash = blockHash(99)
    const sig = await signVote(keypairs['V1']!.privateKey, wrongHash)
    const vote: Vote = Object.freeze({
      validator: vid('V1'),
      block_hash: wrongHash,
      sequence: block.sequence,
      signature: sig,
    })
    const valid = await collectValidVotes(block, [vote], vs)
    expect(valid.length).toBe(0)
  })

  it('isQuorum returns true when votes >= threshold', async () => {
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2','V3'], block)
    expect(isQuorum(votes, 3)).toBe(true)
  })

  it('isQuorum returns false when below threshold', async () => {
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2'], block)
    expect(isQuorum(votes, 3)).toBe(false)
  })
})

// ─── runConsensusRound ─────────────────────────────────────

describe('runConsensusRound', () => {
  it('COMMITTED when all 4 validators vote (f=1, threshold=3)', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2','V3','V4'], block)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('COMMITTED')
    expect(result.qc).toBeDefined()
    expect(result.votes_received).toBe(4)
    expect(result.threshold).toBe(3)
  })

  it('COMMITTED when exactly threshold (3 of 4) vote', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2','V3'], block)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('COMMITTED')
    expect(result.votes_received).toBe(3)
  })

  it('NO_QUORUM when only 2 of 4 vote', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2'], block)
    const result = await runConsensusRound(block, vs, votes)
    expect(result.outcome).toBe('NO_QUORUM')
    expect(result.qc).toBeUndefined()
    expect(result.reason).toContain('2 valid votes < threshold 3')
  })

  it('NO_QUORUM when zero votes', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const result = await runConsensusRound(makeBlock(), vs, [])
    expect(result.outcome).toBe('NO_QUORUM')
  })

  it('QC is frozen', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2','V3','V4'], block)
    const result = await runConsensusRound(block, vs, votes)
    expect(Object.isFrozen(result.qc)).toBe(true)
    expect(Object.isFrozen(result.qc!.votes)).toBe(true)
  })

  it('QC hash is deterministic — same inputs → same qc_hash 3×', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const block = makeBlock()
    const votes = await castAllVotes(['V1','V2','V3','V4'], block)
    const r1 = await runConsensusRound(block, vs, votes)
    const r2 = await runConsensusRound(block, vs, votes)
    const r3 = await runConsensusRound(block, vs, votes)
    expect(r1.qc!.qc_hash).toBe(r2.qc!.qc_hash)
    expect(r2.qc!.qc_hash).toBe(r3.qc!.qc_hash)
    expect(r1.qc!.qc_hash).toHaveLength(64)
  })

  it('different block_hash → different qc_hash', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const b1: ConsensusBlock = Object.freeze({ ...makeBlock(), block_hash: blockHash(1) })
    const b2: ConsensusBlock = Object.freeze({ ...makeBlock(), block_hash: blockHash(2) })
    const v1 = await castAllVotes(['V1','V2','V3','V4'], b1)
    const v2 = await castAllVotes(['V1','V2','V3','V4'], b2)
    const r1 = await runConsensusRound(b1, vs, v1)
    const r2 = await runConsensusRound(b2, vs, v2)
    expect(r1.qc!.qc_hash).not.toBe(r2.qc!.qc_hash)
  })

  it('throws ConsensusError on invalid ValidatorSet', async () => {
    const vs = makeValidatorSet(['V1','V2','V3'], 1)
    await expect(runConsensusRound(makeBlock(), vs, [])).rejects.toThrow(ConsensusError)
  })

  it('result is frozen', async () => {
    const vs = makeValidatorSet(['V1','V2','V3','V4'], 1)
    const result = await runConsensusRound(makeBlock(), vs, [])
    expect(Object.isFrozen(result)).toBe(true)
  })
})
