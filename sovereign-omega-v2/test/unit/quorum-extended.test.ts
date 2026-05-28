// ============================================================
// Quorum Extended Tests — consensus/quorum.ts
// Targets uncovered branches:
//   validateValidatorSet: n !== validators.length throw
//   collectValidVotes: wrong sequence → skip, invalid sig → skip
//   formQC: votes < threshold → throw
// ============================================================

import { describe, it, expect, beforeAll } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { sha256Bytes } from '../../src/core/hashing.js'
import {
  type ValidatorId,
  type ValidatorKeyPair,
  type ConsensusBlock,
  type Vote,
  type ValidatorSet,
  ConsensusError,
} from '../../src/consensus/types.js'
import { generateKeypair, signVote } from '../../src/consensus/crypto.js'
import {
  validateValidatorSet,
  collectValidVotes,
  formQC,
} from '../../src/consensus/quorum.js'

// ─── Test fixtures ────────────────────────────────────────────

const NAMES = ['V1', 'V2', 'V3', 'V4']
const keypairs: Record<string, ValidatorKeyPair> = {}

beforeAll(async () => {
  for (const name of NAMES) {
    const seed = await sha256Bytes(new TextEncoder().encode(`quorum-ext-test:${name}`))
    keypairs[name] = await generateKeypair(seed)
  }
})

function vid(name: string): ValidatorId { return name as ValidatorId }

function blockHash(n: number): SHA256Hex {
  return n.toString(16).padStart(64, '0') as SHA256Hex
}

function makeBlock(seq = 1): ConsensusBlock {
  return Object.freeze({
    block_hash: blockHash(42),
    sequence: seq as unknown as SequenceNumber,
    proposer: vid('V1'),
    timestamp_ms: 1_600_000_000_000,
    parent_hash: blockHash(0),
  })
}

function makeValidatorSet(names: string[], f: number): ValidatorSet {
  const validators = names.map(n => ({
    id: vid(n),
    publicKey: keypairs[n]!.publicKey,
  }))
  return Object.freeze({
    validators: Object.freeze(validators),
    n: validators.length,
    f,
  })
}

async function castVote(name: string, block: ConsensusBlock): Promise<Vote> {
  const sig = await signVote(keypairs[name]!.privateKey, block.block_hash)
  return Object.freeze({ validator: vid(name), block_hash: block.block_hash, sequence: block.sequence, signature: sig })
}

// ─── validateValidatorSet: n !== validators.length throw ─────

describe('validateValidatorSet: n vs validators.length mismatch', () => {
  it('throws ConsensusError when n > validators.length', () => {
    const vs: ValidatorSet = Object.freeze({
      validators: Object.freeze([
        { id: vid('V1'), publicKey: keypairs['V1']!.publicKey },
        { id: vid('V2'), publicKey: keypairs['V2']!.publicKey },
      ]),
      n: 5,
      f: 1,
    })
    expect(() => validateValidatorSet(vs)).toThrow(ConsensusError)
  })

  it('throws ConsensusError when n < validators.length', () => {
    const vs: ValidatorSet = Object.freeze({
      validators: Object.freeze([
        { id: vid('V1'), publicKey: keypairs['V1']!.publicKey },
        { id: vid('V2'), publicKey: keypairs['V2']!.publicKey },
        { id: vid('V3'), publicKey: keypairs['V3']!.publicKey },
        { id: vid('V4'), publicKey: keypairs['V4']!.publicKey },
      ]),
      n: 2,
      f: 0,
    })
    expect(() => validateValidatorSet(vs)).toThrow(ConsensusError)
  })

  it('error message contains actual n and validators.length', () => {
    const vs: ValidatorSet = Object.freeze({
      validators: Object.freeze([{ id: vid('V1'), publicKey: keypairs['V1']!.publicKey }]),
      n: 3,
      f: 0,
    })
    expect(() => validateValidatorSet(vs)).toThrow(/3/)
    expect(() => validateValidatorSet(vs)).toThrow(/1/)
  })
})

// ─── collectValidVotes: wrong sequence → skipped ─────────────

describe('collectValidVotes: vote with wrong sequence is skipped', () => {
  it('vote with sequence !== block.sequence is not collected', async () => {
    const vs = makeValidatorSet(['V1', 'V2', 'V3', 'V4'], 1)
    const block = makeBlock(10)
    const sig = await signVote(keypairs['V1']!.privateKey, block.block_hash)
    const wrongSeqVote: Vote = Object.freeze({
      validator: vid('V1'),
      block_hash: block.block_hash,
      sequence: 999 as unknown as SequenceNumber,
      signature: sig,
    })
    const valid = await collectValidVotes(block, [wrongSeqVote], vs)
    expect(valid.length).toBe(0)
  })
})

// ─── collectValidVotes: invalid signature → skipped ──────────

describe('collectValidVotes: invalid signature is skipped', () => {
  it('vote with corrupted signature is not collected', async () => {
    const vs = makeValidatorSet(['V1', 'V2', 'V3', 'V4'], 1)
    const block = makeBlock(5)
    // Sign over a different hash → signature is invalid for block.block_hash
    const wrongHash = blockHash(99)
    const sig = await signVote(keypairs['V1']!.privateKey, wrongHash)
    const badSigVote: Vote = Object.freeze({
      validator: vid('V1'),
      block_hash: block.block_hash,
      sequence: block.sequence,
      signature: sig,
    })
    const valid = await collectValidVotes(block, [badSigVote], vs)
    expect(valid.length).toBe(0)
  })
})

// ─── formQC: insufficient votes → throw ──────────────────────

describe('formQC: throws when votes < threshold', () => {
  it('throws ConsensusError when 0 votes provided for threshold 3', async () => {
    const block = makeBlock()
    await expect(formQC(block, [], 3)).rejects.toThrow(ConsensusError)
  })

  it('throws ConsensusError when votes < threshold', async () => {
    const block = makeBlock()
    const vote = await castVote('V1', block)
    await expect(formQC(block, [vote], 3)).rejects.toThrow(ConsensusError)
  })

  it('error message contains vote count and threshold', async () => {
    const block = makeBlock()
    const vote = await castVote('V1', block)
    await expect(formQC(block, [vote], 3)).rejects.toThrow(/1/)
    await expect(formQC(block, [vote], 3)).rejects.toThrow(/3/)
  })

  it('does NOT throw when votes >= threshold', async () => {
    const block = makeBlock()
    const v1 = await castVote('V1', block)
    const v2 = await castVote('V2', block)
    const v3 = await castVote('V3', block)
    await expect(formQC(block, [v1, v2, v3], 3)).resolves.toBeDefined()
  })
})
