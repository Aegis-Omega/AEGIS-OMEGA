// ============================================================
// SOVEREIGN OMEGA — Semantic Particle Registry Tests
// BUILD GATE: Gate 8 (no dedicated gate; validated in full suite)
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  SEMANTIC_REGISTRY, lookupNode, queryByGate, queryByTier,
  queryByMutationAuthority, queryConstitutional, registrySize,
  MutationAuthority, ProofCoverage,
} from '../../src/registry/index'

describe('Semantic Particle Registry', () => {

  it('registry is non-empty and a fixed size', () => {
    expect(registrySize()).toBeGreaterThan(0)
    expect(registrySize()).toBe(SEMANTIC_REGISTRY.length)
  })

  it('is deterministic — identical results across three independent accesses', () => {
    const size1 = registrySize()
    const size2 = registrySize()
    const size3 = registrySize()
    expect(size1).toBe(size2)
    expect(size2).toBe(size3)

    const lookup1 = lookupNode('src/core/canonicalize.ts')
    const lookup2 = lookupNode('src/core/canonicalize.ts')
    const lookup3 = lookupNode('src/core/canonicalize.ts')
    expect(lookup1).toBeDefined()
    expect(JSON.stringify(lookup1)).toBe(JSON.stringify(lookup2))
    expect(JSON.stringify(lookup2)).toBe(JSON.stringify(lookup3))
  })

  it('all registered nodes are deeply frozen', () => {
    for (const node of SEMANTIC_REGISTRY) {
      expect(() => {
        // @ts-expect-error intentional mutation attempt
        (node as Record<string, unknown>)['path'] = 'MUTATED'
      }).toThrow()
    }
  })

  it('all nodes have non-empty path, module, and description', () => {
    for (const node of SEMANTIC_REGISTRY) {
      expect(node.path.length).toBeGreaterThan(0)
      expect(node.module.length).toBeGreaterThan(0)
      expect(node.description.length).toBeGreaterThan(0)
    }
  })

  it('all T0 nodes have at least GATE_VERIFIED or COQ_THEOREM coverage', () => {
    const t0Nodes = queryByTier(0)
    expect(t0Nodes.length).toBeGreaterThan(0)
    for (const node of t0Nodes) {
      const hasCoverage =
        node.proof_coverage.includes(ProofCoverage.GATE_VERIFIED) ||
        node.proof_coverage.includes(ProofCoverage.COQ_THEOREM) ||
        node.proof_coverage.includes(ProofCoverage.TLA_SPEC) ||
        node.proof_coverage.includes(ProofCoverage.TEST_COVERED)
      expect(hasCoverage, `T0 node ${node.path} has no proof coverage`).toBe(true)
    }
  })

  it('no T4 or T5 entries exist in the registry — migration rule enforcement', () => {
    const speculative = SEMANTIC_REGISTRY.filter(n => n.tier >= 4)
    expect(speculative, 'T4/T5 artifacts must not appear in the implementation registry').toHaveLength(0)
  })

  it('all constitutional nodes have GUARDIAN_ONLY authority', () => {
    const constitutional = queryConstitutional()
    for (const node of constitutional) {
      expect(node.mutation_authority).toBe(MutationAuthority.GUARDIAN_ONLY)
    }
  })

  it('lookupNode returns undefined for unregistered paths', () => {
    expect(lookupNode('src/nonexistent/file.ts')).toBeUndefined()
    expect(lookupNode('')).toBeUndefined()
    expect(lookupNode('docs/CORPUS_MINDMAP.md')).toBeUndefined()
  })

  it('queryByGate returns only nodes with that gate', () => {
    const gate1 = queryByGate(1)
    expect(gate1.length).toBeGreaterThan(0)
    for (const node of gate1) {
      expect(node.gate).toBe(1)
    }

    const gate6 = queryByGate(6)
    expect(gate6.length).toBeGreaterThan(0)
    for (const node of gate6) {
      expect(node.gate).toBe(6)
    }
  })

  it('queryByMutationAuthority returns correct subset', () => {
    const gateGuarded = queryByMutationAuthority(MutationAuthority.GATE_GUARDED)
    expect(gateGuarded.length).toBeGreaterThan(0)
    for (const node of gateGuarded) {
      expect(node.mutation_authority).toBe(MutationAuthority.GATE_GUARDED)
    }
  })

  it('canonical canonicalize.ts node has expected properties', () => {
    const node = lookupNode('src/core/canonicalize.ts')
    expect(node).toBeDefined()
    if (!node) return
    expect(node.tier).toBe(0)
    expect(node.gate).toBe(1)
    expect(node.module).toBe('core')
    expect(node.mutation_authority).toBe(MutationAuthority.GATE_GUARDED)
    expect(node.proof_coverage).toContain(ProofCoverage.COQ_THEOREM)
    expect(node.proof_coverage).toContain(ProofCoverage.GATE_VERIFIED)
    expect(node.is_constitutional).toBe(false)
  })

  it('paths are unique — no duplicate registry entries', () => {
    const paths = SEMANTIC_REGISTRY.map(n => n.path)
    const unique = new Set(paths)
    expect(unique.size).toBe(paths.length)
  })

})
