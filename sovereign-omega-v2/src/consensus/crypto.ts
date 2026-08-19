// ============================================================
// SOVEREIGN OMEGA — Consensus Cryptography (Ed25519)
// EPISTEMIC TIER: T2 · Gate 22
//
// Production Ed25519 signing via @noble/ed25519 (RFC 8032,
// FIPS 186-5, ZIP215). Replaces Gate 19 FNV-1a stub.
//
// Key properties:
//   - Async: uses the browser/modern-Node Web Crypto SHA-512 path
//   - Deterministic: same (privateKey, message) → same signature
//   - Zero network I/O
//   - generateKeypair(seed) → deterministic from 32-byte seed
// ============================================================

import * as ed from '@noble/ed25519'
import { uint8ArrayToHex, hexToUint8Array } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import type { ValidatorPublicKey, ValidatorSignature, ValidatorKeyPair } from './types.js'

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
  const publicKeyBytes = await ed.getPublicKeyAsync(privateKey)
  return {
    privateKey,
    publicKey: uint8ArrayToHex(publicKeyBytes) as ValidatorPublicKey,
  }
}

// ─── Generic signing / verification ───────────────────────

export async function signBytes(privateKey: Uint8Array, message: Uint8Array): Promise<string> {
  const signature = await ed.signAsync(message, privateKey)
  return uint8ArrayToHex(signature)
}

export async function verifyBytes(
  publicKeyHex: string,
  message: Uint8Array,
  signatureHex: string,
): Promise<boolean> {
  try {
    return await ed.verifyAsync(
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
