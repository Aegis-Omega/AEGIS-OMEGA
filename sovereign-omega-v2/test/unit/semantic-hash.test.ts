/**
 * Pins sections 5.2 to 5.4: the canonical pre-image, the semantic hash, and the
 * verification predicate that section 9.2 requires and the admission module
 * originally did not compute.
 */
import { describe, expect, it } from 'vitest'
import {
  semanticHash,
  semanticPreImage,
  verifySemanticHash,
  type SemanticVertex,
} from '../../src/sovereignty/semantic-hash.js'

const h = (d: string) => `sha256:${d.repeat(64)}`
const PARENT = h('a')

const vertex = (over: Partial<SemanticVertex> = {}): SemanticVertex => ({
  id: 'v1',
  parent: PARENT,
  causal_tuple: [PARENT, PARENT, null],
  transform: 'normal_commit',
  rebase_extension: null,
  semantic_hash: 'sha256:' + '0'.repeat(64),
  hlc: { logical: 7, counter: 2, node: 'node-a' },
  authority_delta: null,
  policy_delta: null,
  rollback_digest: null,
  root9: 42,
  ...over,
})

describe('section 5.2 — canonical pre-image', () => {
  it('excludes the signature, so the hash never depends on itself', () => {
    const keys = Object.keys(semanticPreImage(vertex()))
    expect(keys).not.toContain('signature')
    expect(keys).not.toContain('semantic_hash')
  })

  it('serializes an absent optional field as explicit null, not as a dropped key', async () => {
    // A wire vertex that omits the key reads back as `undefined`. JCS drops
    // undefined-valued keys, so without coercion this would hash differently
    // from the identical document that spells the field out as null.
    const omitted = vertex()
    delete (omitted as { policy_delta?: unknown }).policy_delta
    const spelled = vertex({ policy_delta: null })

    expect(semanticPreImage(omitted)).toHaveProperty('policy_delta', null)
    expect(await semanticHash(omitted)).toBe(await semanticHash(spelled))
  })

  it('binds every field the spec lists', () => {
    expect(Object.keys(semanticPreImage(vertex())).sort()).toEqual([
      'authority_delta',
      'causal_tuple',
      'hlc',
      'id',
      'parent',
      'policy_delta',
      'rebase_extension',
      'rollback_digest',
      'root9',
      'transform',
    ])
  })

  it('keeps absent values as explicit null rather than omitting the key', () => {
    const pre = semanticPreImage(vertex())
    expect('authority_delta' in pre).toBe(true)
    expect(pre['authority_delta']).toBeNull()
  })
})

describe('section 5.3 — semantic hash', () => {
  it('is deterministic — byte-identical across repeated computation', async () => {
    const v = vertex()
    const runs = await Promise.all([semanticHash(v), semanticHash(v), semanticHash(v)])
    expect(new Set(runs).size).toBe(1)
    expect(runs[0]).toMatch(/^sha256:[0-9a-f]{64}$/)
  })

  it('is insensitive to key insertion order — JCS sorts before hashing', async () => {
    const a = await semanticHash(vertex())
    // Same values, built in a different literal order.
    const reordered: SemanticVertex = {
      root9: 42,
      hlc: { logical: 7, counter: 2, node: 'node-a' },
      transform: 'normal_commit',
      rollback_digest: null,
      policy_delta: null,
      authority_delta: null,
      rebase_extension: null,
      causal_tuple: [PARENT, PARENT, null],
      parent: PARENT,
      id: 'v1',
      semantic_hash: 'sha256:' + '0'.repeat(64),
    }
    expect(await semanticHash(reordered)).toBe(a)
  })

  it('changes when any bound field changes', async () => {
    const base = await semanticHash(vertex())
    const variants = await Promise.all([
      semanticHash(vertex({ id: 'v2' })),
      semanticHash(vertex({ root9: 43 })),
      semanticHash(vertex({ hlc: { logical: 8, counter: 2, node: 'node-a' } })),
      semanticHash(vertex({ hlc: { logical: 7, counter: 2, node: 'node-b' } })),
      semanticHash(vertex({ authority_delta: h('b') })),
      semanticHash(vertex({ causal_tuple: [PARENT, PARENT, h('c')] })),
    ])
    for (const variant of variants) expect(variant).not.toBe(base)
    expect(new Set(variants).size).toBe(variants.length)
  })

  it('does NOT change when the claimed hash changes — the claim is not an input', async () => {
    const a = await semanticHash(vertex({ semantic_hash: 'sha256:' + '0'.repeat(64) }))
    const b = await semanticHash(vertex({ semantic_hash: 'sha256:' + 'f'.repeat(64) }))
    expect(a).toBe(b)
  })
})

describe('section 5.4 — verification predicate', () => {
  it('accepts a vertex carrying its own correct hash', async () => {
    const v = vertex()
    const correct = vertex({ semantic_hash: await semanticHash(v) })
    expect(await verifySemanticHash(correct)).toBe(true)
  })

  it('rejects a vertex whose claimed hash does not match its content', async () => {
    expect(await verifySemanticHash(vertex())).toBe(false)
  })

  it('rejects content edited after the hash was computed', async () => {
    const v = vertex()
    const sealed = vertex({ semantic_hash: await semanticHash(v) })
    // Same claimed hash, one field silently altered.
    expect(await verifySemanticHash({ ...sealed, root9: 43 })).toBe(false)
  })
})
