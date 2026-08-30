import { describe, it, expect } from 'vitest'
import { buildCorpusDocument, processDocument } from '../../src/corpus-engine/pipeline.js'
import { CORPUS_SCHEMA_VERSION } from '../../src/corpus-engine/types.js'

// ============================================================
// Gate 144 — CorpusEngine Tests
// Verifies: 5-phase RALPH pipeline, T4/T5 downgrade at ARBITRATION,
// hash-linked phase records, fibonacci_depths [1,1,2,3,5],
// corpus_lineage_hash determinism ×3.
// ============================================================

const GOVERNANCE_CONTENT = `
# Replay Sovereignty Module

This module is mechanically proven (T0). It implements hash chain verification
using canonicalizeJCS and deepFreeze patterns. All state is replay-reconstructable.
`

const T4_CONTENT = `
# Sovereign Consciousness Framework

This speculative system enables sovereign consciousness emergence across
planetary coordination mesh and civilizational memory substrate.
Unrestricted AGI transcendence is the goal.
`

describe('CORPUS_SCHEMA_VERSION', () => {
  it('is 1.0.0', () => { expect(CORPUS_SCHEMA_VERSION).toBe('1.0.0') })
})

describe('buildCorpusDocument', () => {
  it('produces frozen CorpusDocument with content_hash', async () => {
    const doc = await buildCorpusDocument('doc-1', 'github.com/test', GOVERNANCE_CONTENT)
    expect(doc.content_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(doc.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(doc)).toBe(true)
    expect(doc.document_id).toBe('doc-1')
    expect(doc.schema_version).toBe('1.0.0')
  })

  it('byte_length > 0 for non-empty content', async () => {
    const doc = await buildCorpusDocument('doc-2', 'test', GOVERNANCE_CONTENT)
    expect(doc.byte_length).toBeGreaterThan(0)
  })

  it('content_hash is deterministic ×3', async () => {
    const run = () => buildCorpusDocument('det', 'src', GOVERNANCE_CONTENT)
    const [d1, d2, d3] = await Promise.all([run(), run(), run()])
    expect(d1.content_hash).toBe(d2.content_hash)
    expect(d2.content_hash).toBe(d3.content_hash)
  })
})

describe('processDocument — 5-phase RALPH pipeline', () => {
  it('always produces exactly 5 phase records', async () => {
    const doc = await buildCorpusDocument('p1', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    expect(lineage.phases).toHaveLength(5)
  })

  it('fibonacci_depths are [1,1,2,3,5] for phases 1–5', async () => {
    const doc = await buildCorpusDocument('fib', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    expect(lineage.phases.map(p => p.fibonacci_depth)).toEqual([1, 1, 2, 3, 5])
  })

  it('phases follow RALPH order: OBSERVATION→INTERPRETATION→ARBITRATION→MUTATION→PROPAGATION', async () => {
    const doc = await buildCorpusDocument('order', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    expect(lineage.phases.map(p => p.phase)).toEqual([
      'OBSERVATION', 'INTERPRETATION', 'ARBITRATION', 'MUTATION', 'PROPAGATION',
    ])
  })

  it('all phase hashes are 64-char hex', async () => {
    const doc = await buildCorpusDocument('hash', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    for (const phase of lineage.phases) {
      expect(phase.phase_hash).toMatch(/^[0-9a-f]{64}$/)
      expect(phase.phase_input_hash).toMatch(/^[0-9a-f]{64}$/)
      expect(phase.phase_output_hash).toMatch(/^[0-9a-f]{64}$/)
    }
  })

  it('corpus_lineage_hash is 64-char hex', async () => {
    const doc = await buildCorpusDocument('lin', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    expect(lineage.corpus_lineage_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('CorpusLineageRecord is frozen', async () => {
    const doc = await buildCorpusDocument('frz', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    expect(Object.isFrozen(lineage)).toBe(true)
  })

  it('all phase records are frozen', async () => {
    const doc = await buildCorpusDocument('frz2', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    for (const phase of lineage.phases) {
      expect(Object.isFrozen(phase)).toBe(true)
    }
  })

  it('corpus_lineage_hash is deterministic ×3', async () => {
    const run = async () => {
      const doc = await buildCorpusDocument('det2', 'test', GOVERNANCE_CONTENT)
      return processDocument(doc, GOVERNANCE_CONTENT)
    }
    const [l1, l2, l3] = await Promise.all([run(), run(), run()])
    expect(l1.corpus_lineage_hash).toBe(l2.corpus_lineage_hash)
    expect(l2.corpus_lineage_hash).toBe(l3.corpus_lineage_hash)
  })

  it('different content → different corpus_lineage_hash', async () => {
    const [doc1, doc2] = await Promise.all([
      buildCorpusDocument('diff1', 'test', GOVERNANCE_CONTENT),
      buildCorpusDocument('diff2', 'test', 'different content about deployment pipelines'),
    ])
    const [l1, l2] = await Promise.all([
      processDocument(doc1, GOVERNANCE_CONTENT),
      processDocument(doc2, 'different content about deployment pipelines'),
    ])
    expect(l1.corpus_lineage_hash).not.toBe(l2.corpus_lineage_hash)
  })

  it('is_replay_reconstructable=true on lineage and all phases', async () => {
    const doc = await buildCorpusDocument('rep', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    expect(lineage.is_replay_reconstructable).toBe(true)
    for (const phase of lineage.phases) {
      expect(phase.is_replay_reconstructable).toBe(true)
    }
  })
})

describe('ARBITRATION — T4/T5 downgrade', () => {
  it('T4/T5 content: ARBITRATION phase admitted=false', async () => {
    const doc = await buildCorpusDocument('t4', 'test', T4_CONTENT)
    const lineage = await processDocument(doc, T4_CONTENT)
    const arbitration = lineage.phases.find(p => p.phase === 'ARBITRATION')
    expect(arbitration?.admitted).toBe(false)
  })

  it('T4/T5: downgrade_reason set on ARBITRATION phase', async () => {
    const doc = await buildCorpusDocument('t4r', 'test', T4_CONTENT)
    const lineage = await processDocument(doc, T4_CONTENT)
    const arbitration = lineage.phases.find(p => p.phase === 'ARBITRATION')
    expect(arbitration?.downgrade_reason).toBeDefined()
  })

  it('T4/T5: final_tier is DOWNGRADED', async () => {
    const doc = await buildCorpusDocument('t4fin', 'test', T4_CONTENT)
    const lineage = await processDocument(doc, T4_CONTENT)
    expect(lineage.final_tier).toBe('DOWNGRADED')
  })

  it('governance content: admitted=true at ARBITRATION', async () => {
    const doc = await buildCorpusDocument('gov', 'test', GOVERNANCE_CONTENT)
    const lineage = await processDocument(doc, GOVERNANCE_CONTENT)
    const arbitration = lineage.phases.find(p => p.phase === 'ARBITRATION')
    expect(arbitration?.admitted).toBe(true)
  })
})
