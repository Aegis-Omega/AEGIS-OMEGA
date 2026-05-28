// ============================================================
// SOVEREIGN OMEGA — Byte-Level Cryptographic Primitives
// EPISTEMIC TIER: T0 (mechanically enforceable)
// PRIMITIVE 6: Byte-Level Cryptographic Consistency
// ============================================================
// All hashing uses explicit byte-level operations:
// - UTF-8 encode before hashing (never hash strings directly)
// - Byte-concatenation for Merkle nodes (never string concat)
// - Cross-platform: Web Crypto API with Node crypto fallback
// ============================================================

import type { SHA256Hex } from './types.js'
import { canonicalizeJCS } from './canonicalize.js'

// ─── SHA-256 ───────────────────────────────────────────────

/**
 * Compute SHA-256 over raw bytes. Returns hex string.
 * Uses Web Crypto API (browser/WASM compatible) with Node fallback.
 */
export async function sha256Hex(input: Uint8Array): Promise<SHA256Hex> {
  const bytes = await sha256Bytes(input)
  return uint8ArrayToHex(bytes) as SHA256Hex
}

export async function sha256Bytes(input: Uint8Array): Promise<Uint8Array> {
  // Web Crypto API (browser, WASM, modern Node)
  /* c8 ignore next -- Node.js crypto fallback; Web Crypto available in all modern environments and test environments */
  if (typeof globalThis.crypto?.subtle !== 'undefined') {
    const digest = await globalThis.crypto.subtle.digest('SHA-256', input as BufferSource)
    return new Uint8Array(digest)
  }

  // Node.js fallback (older environments)
  const { createHash } = await import('node:crypto')
  const hash = createHash('sha256')
  hash.update(input)
  return new Uint8Array(hash.digest())
}

/**
 * Hash a JavaScript value via RFC 8785 canonicalisation → UTF-8 → SHA-256.
 * This is the canonical method for producing event hashes.
 */
export async function hashValue(value: unknown): Promise<SHA256Hex> {
  const canonical = canonicalizeJCS(value)
  return sha256Hex(canonical)
}

/**
 * Hash a string via UTF-8 encoding → SHA-256.
 * Never hash strings directly without UTF-8 encoding first.
 */
export async function hashString(s: string): Promise<SHA256Hex> {
  const bytes = new TextEncoder().encode(s)
  return sha256Hex(bytes)
}

// ─── Merkle Tree ───────────────────────────────────────────

/**
 * Concatenate two byte arrays for Merkle node construction.
 * Uses explicit byte-level concatenation, never string concatenation.
 * This is Primitive 6's critical implementation detail.
 */
export function merkleConcat(left: Uint8Array, right: Uint8Array): Uint8Array {
  const result = new Uint8Array(left.length + right.length)
  result.set(left, 0)
  result.set(right, left.length)
  return result
}

/**
 * Compute the Merkle root of an ordered array of byte arrays.
 * Uses arity-2 tree with duplicate padding for odd leaves.
 * Encoding: 'byte-concat-arity-2-v1' (pinned in EventSegment header).
 */
export async function computeMerkleRoot(leaves: readonly Uint8Array[]): Promise<SHA256Hex> {
  if (leaves.length === 0) {
    return sha256Hex(new Uint8Array(0))
  }

  // Hash all leaves
  let layer: Uint8Array[] = await Promise.all(leaves.map(sha256Bytes))

  // Build tree bottom-up
  while (layer.length > 1) {
    const nextLayer: Uint8Array[] = []
    for (let i = 0; i < layer.length; i += 2) {
      const left = layer[i]!
      const right = layer[i + 1] ?? layer[i]! // duplicate last node if odd
      const combined = merkleConcat(left, right)
      nextLayer.push(await sha256Bytes(combined))
    }
    layer = nextLayer
  }

  return uint8ArrayToHex(layer[0]!) as SHA256Hex
}

/**
 * Compute Merkle root from a list of canonicalisable values.
 * Each value is RFC 8785 canonicalised → UTF-8 → leaf hash.
 */
export async function computeMerkleRootFromValues(values: readonly unknown[]): Promise<SHA256Hex> {
  const leaves = values.map(v => canonicalizeJCS(v))
  return computeMerkleRoot(leaves)
}

// ─── Utility ───────────────────────────────────────────────

export function uint8ArrayToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

export function hexToUint8Array(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) throw new Error('Invalid hex string length')
  const bytes = new Uint8Array(hex.length / 2)
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.slice(i, i + 2), 16)
  }
  return bytes
}

/**
 * Verify that a SHA-256 hex string matches the expected hash of input bytes.
 * Used for envelope self-hash verification during replay.
 */
export async function verifyHash(input: Uint8Array, expectedHex: SHA256Hex): Promise<boolean> {
  const actual = await sha256Hex(input)
  return actual === expectedHex
}

/**
 * Produce a deterministic fingerprint of a RuntimeVersionPin for storage.
 */
export async function fingerprintVersionPin(pin: Record<string, unknown>): Promise<SHA256Hex> {
  return hashValue(pin)
}
