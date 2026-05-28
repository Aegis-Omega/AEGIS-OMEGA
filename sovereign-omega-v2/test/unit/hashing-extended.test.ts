// ============================================================
// Hashing Extended Tests — core/hashing.ts
// Targets uncovered branches: hexToUint8Array (odd length),
// merkleConcat, computeMerkleRoot (empty/odd/even),
// computeMerkleRootFromValues, verifyHash, fingerprintVersionPin,
// hashString determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  sha256Hex,
  hashString,
  merkleConcat,
  computeMerkleRoot,
  computeMerkleRootFromValues,
  uint8ArrayToHex,
  hexToUint8Array,
  verifyHash,
  fingerprintVersionPin,
} from '../../src/core/hashing.js'
import type { SHA256Hex } from '../../src/core/types.js'

// ─── sha256Hex ─────────────────────────────────────────────

describe('sha256Hex', () => {
  it('produces 64-char hex for empty bytes', async () => {
    const h = await sha256Hex(new Uint8Array(0))
    expect(h).toHaveLength(64)
    expect(h).toMatch(/^[0-9a-f]{64}$/)
  })

  it('deterministic across 3 runs', async () => {
    const input = new TextEncoder().encode('aegis')
    const h1 = await sha256Hex(input)
    const h2 = await sha256Hex(input)
    const h3 = await sha256Hex(input)
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different input → different hash', async () => {
    const a = await sha256Hex(new TextEncoder().encode('alpha'))
    const b = await sha256Hex(new TextEncoder().encode('beta'))
    expect(a).not.toBe(b)
  })
})

// ─── hashString ────────────────────────────────────────────

describe('hashString', () => {
  it('returns 64-char hex', async () => {
    const h = await hashString('constitutional')
    expect(h).toHaveLength(64)
  })

  it('deterministic across 3 runs', async () => {
    const h1 = await hashString('replay-sovereignty')
    const h2 = await hashString('replay-sovereignty')
    const h3 = await hashString('replay-sovereignty')
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('differs from sha256Hex of UTF-8 bytes (sanity — same)', async () => {
    const s = 'gate-8'
    const fromString = await hashString(s)
    const fromBytes = await sha256Hex(new TextEncoder().encode(s))
    expect(fromString).toBe(fromBytes)
  })
})

// ─── merkleConcat ──────────────────────────────────────────

describe('merkleConcat', () => {
  it('concatenates two non-empty arrays', () => {
    const left = new Uint8Array([1, 2, 3])
    const right = new Uint8Array([4, 5, 6])
    const result = merkleConcat(left, right)
    expect(result).toEqual(new Uint8Array([1, 2, 3, 4, 5, 6]))
  })

  it('concatenates empty left with non-empty right', () => {
    const left = new Uint8Array(0)
    const right = new Uint8Array([7, 8])
    expect(merkleConcat(left, right)).toEqual(new Uint8Array([7, 8]))
  })

  it('concatenates non-empty left with empty right', () => {
    const left = new Uint8Array([1])
    const right = new Uint8Array(0)
    expect(merkleConcat(left, right)).toEqual(new Uint8Array([1]))
  })

  it('length equals sum of inputs', () => {
    const left = new Uint8Array(10)
    const right = new Uint8Array(22)
    expect(merkleConcat(left, right).length).toBe(32)
  })
})

// ─── computeMerkleRoot ────────────────────────────────────

describe('computeMerkleRoot', () => {
  const leaf = (s: string) => new TextEncoder().encode(s)

  it('empty leaves returns hash of empty bytes', async () => {
    const h = await computeMerkleRoot([])
    const emptyHash = await sha256Hex(new Uint8Array(0))
    expect(h).toBe(emptyHash)
  })

  it('single leaf returns hash of that leaf', async () => {
    const l = leaf('only')
    const root = await computeMerkleRoot([l])
    expect(root).toHaveLength(64)
  })

  it('two leaves produces a different root than one', async () => {
    const l = leaf('x')
    const r1 = await computeMerkleRoot([l])
    const r2 = await computeMerkleRoot([l, l])
    expect(r1).not.toBe(r2)
  })

  it('three leaves (odd) does not throw — pads last node', async () => {
    const root = await computeMerkleRoot([leaf('a'), leaf('b'), leaf('c')])
    expect(root).toHaveLength(64)
  })

  it('four leaves produces a valid root', async () => {
    const root = await computeMerkleRoot([leaf('a'), leaf('b'), leaf('c'), leaf('d')])
    expect(root).toHaveLength(64)
  })

  it('same inputs → same root across 3 runs', async () => {
    const leaves = [leaf('φ'), leaf('chain'), leaf('genesis')]
    const r1 = await computeMerkleRoot(leaves)
    const r2 = await computeMerkleRoot(leaves)
    const r3 = await computeMerkleRoot(leaves)
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })

  it('order matters — [a,b] ≠ [b,a]', async () => {
    const a = leaf('alpha')
    const b = leaf('beta')
    const r1 = await computeMerkleRoot([a, b])
    const r2 = await computeMerkleRoot([b, a])
    expect(r1).not.toBe(r2)
  })
})

// ─── computeMerkleRootFromValues ──────────────────────────

describe('computeMerkleRootFromValues', () => {
  it('produces a 64-char hex root from JSON values', async () => {
    const root = await computeMerkleRootFromValues([{ a: 1 }, { b: 2 }])
    expect(root).toHaveLength(64)
  })

  it('deterministic across 3 runs', async () => {
    const values = [{ tier: 'T0' }, { gate: 8 }]
    const r1 = await computeMerkleRootFromValues(values)
    const r2 = await computeMerkleRootFromValues(values)
    const r3 = await computeMerkleRootFromValues(values)
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })
})

// ─── uint8ArrayToHex / hexToUint8Array ────────────────────

describe('uint8ArrayToHex', () => {
  it('encodes zero bytes as 00', () => {
    expect(uint8ArrayToHex(new Uint8Array([0]))).toBe('00')
  })

  it('encodes ff correctly', () => {
    expect(uint8ArrayToHex(new Uint8Array([255]))).toBe('ff')
  })

  it('round-trips through hexToUint8Array', () => {
    const original = new Uint8Array([0xde, 0xad, 0xbe, 0xef])
    const hex = uint8ArrayToHex(original)
    const roundTripped = hexToUint8Array(hex)
    expect(roundTripped).toEqual(original)
  })
})

describe('hexToUint8Array', () => {
  it('decodes a valid even-length hex string', () => {
    const bytes = hexToUint8Array('deadbeef')
    expect(bytes).toEqual(new Uint8Array([0xde, 0xad, 0xbe, 0xef]))
  })

  it('throws on odd-length hex string', () => {
    expect(() => hexToUint8Array('abc')).toThrow()
  })

  it('decodes all-zeros hex', () => {
    const bytes = hexToUint8Array('0000')
    expect(bytes).toEqual(new Uint8Array([0, 0]))
  })
})

// ─── verifyHash ────────────────────────────────────────────

describe('verifyHash', () => {
  it('returns true when hash matches input', async () => {
    const input = new TextEncoder().encode('constitutional')
    const expected = await sha256Hex(input)
    expect(await verifyHash(input, expected)).toBe(true)
  })

  it('returns false when hash does not match input', async () => {
    const input = new TextEncoder().encode('one-thing')
    const wrong = await sha256Hex(new TextEncoder().encode('another-thing'))
    expect(await verifyHash(input, wrong as SHA256Hex)).toBe(false)
  })
})

// ─── fingerprintVersionPin ────────────────────────────────

describe('fingerprintVersionPin', () => {
  it('returns a 64-char hex fingerprint', async () => {
    const fp = await fingerprintVersionPin({ schema_version: '1.0.0', projection_version: '1.0.0' })
    expect(fp).toHaveLength(64)
    expect(fp).toMatch(/^[0-9a-f]{64}$/)
  })

  it('same pin → same fingerprint across 3 runs', async () => {
    const pin = { schema_version: '1.0.0', verifier_versions: { v1: '1.0.0' } }
    const f1 = await fingerprintVersionPin(pin)
    const f2 = await fingerprintVersionPin(pin)
    const f3 = await fingerprintVersionPin(pin)
    expect(f1).toBe(f2)
    expect(f2).toBe(f3)
  })

  it('different pins produce different fingerprints', async () => {
    const f1 = await fingerprintVersionPin({ v: '1.0.0' })
    const f2 = await fingerprintVersionPin({ v: '2.0.0' })
    expect(f1).not.toBe(f2)
  })
})
