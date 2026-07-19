// ============================================================
// SOVEREIGN OMEGA — Consensus Cryptography (Ed25519)
// EPISTEMIC TIER: T2 · Gate 22
//
// Production Ed25519 signing via @noble/ed25519 (RFC 8032,
// FIPS 186-5, ZIP215). Replaces Gate 19 FNV-1a stub.
//
// Key properties:
//   - Async: no WebCrypto dependency (uses noble's built-in sha512)
//   - Deterministic: same (privateKey, message) → same signature
//   - Zero network I/O
//   - generateKeypair(seed) → deterministic from 32-byte seed
// ============================================================

import * as ed from '@noble/ed25519'
import { createHash } from 'node:crypto'
import { uint8ArrayToHex, hexToUint8Array } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import type { ValidatorPublicKey, ValidatorSignature, ValidatorKeyPair } from './types.js'

// Wire Node.js sha512 into @noble/ed25519 v3 (required outside browser).
// The type cast is necessary because Node's Buffer.digest() is typed as
// Uint8Array<ArrayBufferLike> while noble expects Uint8Array<ArrayBuffer>.
;(ed.hashes as Record<string, unknown>)['sha512'] = (msg: Uint8Array): Uint8Array =>
  Uint8Array.from(createHash('sha512').update(msg).digest())

// ─── Key generation ────────────────────────────────────────

/**
 * Derive a deterministic Ed25519 keypair from a 32-byte seed.
 * In production, seeds must come from a CSPRNG; for tests,
 * deterministic seeds (e.g. SHA-256 of validator name) are acceptable.
 */
export async function generateKeypair(seed: Uint8Array): Promise<ValidatorKeyPair> {
  if (seed.length < 32) {
    throw new Error(`Seed must be at least 32 bytes, got ${seed.length}`)
  }
  const privateKey = seed.slice(0, 32)
  const publicKeyBytes = await ed.getPublicKey(privateKey)
  return {
    privateKey,
    publicKey: uint8ArrayToHex(publicKeyBytes) as ValidatorPublicKey,
  }
}

// ─── Generic signing / verification ───────────────────────

export async function signBytes(privateKey: Uint8Array, message: Uint8Array): Promise<string> {
  const signature = await ed.sign(message, privateKey)
  return uint8ArrayToHex(signature)
}

export async function verifyBytes(
  publicKeyHex: string,
  message: Uint8Array,
  signatureHex: string,
): Promise<boolean> {
  try {
    return await ed.verify(
      hexToUint8Array(signatureHex),
      message,
      hexToUint8Array(publicKeyHex),
    )
  } catch {
    return false
  }
}

// ─── Vote signing / verification ──────────────────────────

/**
 * Sign a block_hash with the given Ed25519 private key.
 * Message is the UTF-8 encoding of the block_hash hex string.
 * Returns a 128-char hex string (64-byte Ed25519 signature).
 */
export async function signVote(
  privateKey: Uint8Array,
  blockHash: SHA256Hex,
): Promise<ValidatorSignature> {
  return await signBytes(privateKey, new TextEncoder().encode(blockHash)) as ValidatorSignature
}

/**
 * Verify a vote signature against the validator's public key.
 * Returns true iff the signature is a valid Ed25519 signature
 * over UTF-8(blockHash) for the given public key.
 */
export async function verifyVote(
  publicKey: ValidatorPublicKey,
  blockHash: SHA256Hex,
  signature: ValidatorSignature,
): Promise<boolean> {
  return verifyBytes(publicKey, new TextEncoder().encode(blockHash), signature)
}
