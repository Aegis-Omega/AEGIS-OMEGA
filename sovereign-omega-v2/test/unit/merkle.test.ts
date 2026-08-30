import { describe, it, expect } from 'vitest'
import { computeMerkleRoot, merkleConcat } from '../../src/core/hashing'

describe('Merkle Tree Construction — Gate 5', () => {
  it('produces deterministic root for same leaves', async () => {
    const leaves = [
      new TextEncoder().encode('leaf1'),
      new TextEncoder().encode('leaf2'),
      new TextEncoder().encode('leaf3'),
    ]
    const root1 = await computeMerkleRoot(leaves)
    const root2 = await computeMerkleRoot(leaves)
    expect(root1).toBe(root2)
  })

  it('produces different root for different leaves', async () => {
    const leaves1 = [new TextEncoder().encode('a'), new TextEncoder().encode('b')]
    const leaves2 = [new TextEncoder().encode('a'), new TextEncoder().encode('c')]
    const root1 = await computeMerkleRoot(leaves1)
    const root2 = await computeMerkleRoot(leaves2)
    expect(root1).not.toBe(root2)
  })

  it('handles single leaf', async () => {
    const leaves = [new TextEncoder().encode('single')]
    const root = await computeMerkleRoot(leaves)
    expect(root).toHaveLength(64) // SHA-256 hex
  })

  it('handles even number of leaves', async () => {
    const leaves = [1, 2, 3, 4].map(n => new TextEncoder().encode(String(n)))
    const root = await computeMerkleRoot(leaves)
    expect(root).toHaveLength(64)
  })

  it('handles odd number of leaves with duplication', async () => {
    const leaves = [1, 2, 3].map(n => new TextEncoder().encode(String(n)))
    const root = await computeMerkleRoot(leaves)
    expect(root).toHaveLength(64)
  })

  it('uses byte concatenation, not string concatenation', () => {
    const left = new Uint8Array([1, 2, 3])
    const right = new Uint8Array([4, 5, 6])
    const concat = merkleConcat(left, right)
    expect(concat).toEqual(new Uint8Array([1, 2, 3, 4, 5, 6]))
    expect(concat.length).toBe(6)
  })

  it('detects tampered leaf (different root)', async () => {
    const original = [new TextEncoder().encode('a'), new TextEncoder().encode('b')]
    const tampered = [new TextEncoder().encode('a'), new TextEncoder().encode('B')] // 'b' → 'B'
    const root1 = await computeMerkleRoot(original)
    const root2 = await computeMerkleRoot(tampered)
    expect(root1).not.toBe(root2)
  })

  it('order matters for root computation', async () => {
    const leaves1 = [new TextEncoder().encode('a'), new TextEncoder().encode('b')]
    const leaves2 = [new TextEncoder().encode('b'), new TextEncoder().encode('a')]
    const root1 = await computeMerkleRoot(leaves1)
    const root2 = await computeMerkleRoot(leaves2)
    expect(root1).not.toBe(root2)
  })
})
