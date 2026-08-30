// ============================================================
// Crypto Extended Tests — consensus/crypto.ts
// Targets uncovered branches:
//   generateKeypair: short-seed throw path
//   verifyVote:      catch path → malformed input → false
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import { generateKeypair, signVote, verifyVote } from '../../src/consensus/crypto.js'
import type { ValidatorPublicKey, ValidatorSignature } from '../../src/consensus/types.js'

const BH = '0'.repeat(64) as SHA256Hex

// ─── generateKeypair: short seed ─────────────────────────

describe('generateKeypair: short seed', () => {
  it('throws when seed is shorter than 32 bytes', async () => {
    const shortSeed = new Uint8Array(16)
    await expect(generateKeypair(shortSeed)).rejects.toThrow('Seed must be at least 32 bytes')
  })

  it('throws when seed is empty', async () => {
    await expect(generateKeypair(new Uint8Array(0))).rejects.toThrow('Seed must be at least 32 bytes')
  })

  it('accepts exactly 32 bytes', async () => {
    const kp = await generateKeypair(new Uint8Array(32))
    expect(kp.publicKey).toHaveLength(64)
  })

  it('accepts more than 32 bytes', async () => {
    const kp = await generateKeypair(new Uint8Array(64))
    expect(kp.publicKey).toHaveLength(64)
  })
})

// ─── verifyVote: catch path ───────────────────────────────

describe('verifyVote: malformed input → catch → false', () => {
  it('returns false for malformed signature (non-hex string)', async () => {
    const kp = await generateKeypair(new Uint8Array(32))
    // non-hex will cause hexToUint8Array to throw → catch returns false
    const badSig = 'ZZZZ'.repeat(32) as ValidatorSignature
    const result = await verifyVote(kp.publicKey, BH, badSig)
    expect(result).toBe(false)
  })

  it('returns false for empty string signature', async () => {
    const kp = await generateKeypair(new Uint8Array(32))
    const result = await verifyVote(kp.publicKey, BH, '' as ValidatorSignature)
    expect(result).toBe(false)
  })

  it('returns false for malformed public key (non-hex)', async () => {
    const kp = await generateKeypair(new Uint8Array(32))
    const sig = await signVote(kp.privateKey, BH)
    const result = await verifyVote('ZZZZ'.repeat(16) as ValidatorPublicKey, BH, sig)
    expect(result).toBe(false)
  })
})
