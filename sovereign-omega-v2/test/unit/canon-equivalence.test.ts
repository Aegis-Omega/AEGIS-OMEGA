// ============================================================
// SOVEREIGN OMEGA — Cross-Language Canonical Digest Equivalence
// EPISTEMIC TIER: T0
// Provenance Phase 1: the TS T0 path (canonicalizeJCS → SHA-256)
// and python/canonical_envelope.py must produce byte-identical
// digests for every shared vector. Python side:
// python/tests/test_canon_equivalence.py. Float policy: ADR 0001
// (docs/adr/0001-envelope-float-encoding.md) — no raw floats in
// any vector.
// ============================================================

import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { hashValue } from '../../src/core/hashing'

interface CanonVector {
  readonly name: string
  readonly input: unknown
  readonly sha256: string
}

const vectorsPath = join(
  dirname(fileURLToPath(import.meta.url)),
  '..', 'vectors', 'canon-vectors.json'
)
const vectors: CanonVector[] = JSON.parse(readFileSync(vectorsPath, 'utf-8')).vectors

describe('Cross-language canonical digest equivalence — Provenance Phase 1', () => {
  it('has at least 10 shared vectors', () => {
    expect(vectors.length).toBeGreaterThanOrEqual(10)
  })

  it('contains no raw floats in any vector (ADR 0001)', () => {
    const hasFloat = (v: unknown): boolean => {
      if (typeof v === 'number') return !Number.isInteger(v)
      if (Array.isArray(v)) return v.some(hasFloat)
      if (v !== null && typeof v === 'object') {
        return Object.values(v as Record<string, unknown>).some(hasFloat)
      }
      return false
    }
    for (const vec of vectors) {
      expect(hasFloat(vec.input), `raw float in vector: ${vec.name}`).toBe(false)
    }
  })

  for (const vec of vectors) {
    it(`digest matches Python canonical_envelope.canon(): ${vec.name}`, async () => {
      const got = await hashValue(vec.input)
      expect(got).toBe(vec.sha256)
    })
  }

  it('digests are deterministic across three runs', async () => {
    for (const vec of vectors.slice(0, 3)) {
      const runs = await Promise.all([
        hashValue(vec.input), hashValue(vec.input), hashValue(vec.input),
      ])
      expect(runs[0]).toBe(vec.sha256)
      expect(runs[1]).toBe(vec.sha256)
      expect(runs[2]).toBe(vec.sha256)
    }
  })
})
