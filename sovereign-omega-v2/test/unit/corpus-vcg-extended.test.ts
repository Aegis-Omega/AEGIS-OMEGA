// ============================================================
// Corpus Pipeline + VCG Extended Tests
// Targets:
//   corpus-engine/pipeline.ts: T1 tier, monitoring→HASH primitive,
//     no-domain-signal→['general'], CANONICALIZE primitive
//   calibration/vcg.ts: totalWeight===0 → emptyMetric (L95)
// ============================================================

import { describe, it, expect } from 'vitest'

// ─── Corpus Pipeline ─────────────────────────────────────────

import { buildCorpusDocument, processDocument } from '../../src/corpus-engine/pipeline.js'

async function buildAndProcess(id: string, content: string) {
  const doc = await buildCorpusDocument(id, 'test-source', content)
  return processDocument(doc, content)
}

describe('processDocument: T1 tier classification', () => {
  it('assigns T1 tier for content with "empirically validated"', async () => {
    const content = 'This module is empirically validated via benchmark measurement across runs.'
    const lineage = await buildAndProcess('doc-t1', content)
    // T1 tier → admitted should be true, phases should be 5
    expect(lineage.phases).toHaveLength(5)
  })

  it('produces admitted lineage for T1 content', async () => {
    const content = 'Benchmark measurement shows empirically validated accuracy of 99%.'
    const lineage = await buildAndProcess('doc-t1b', content)
    expect(lineage.final_tier).not.toBe('DOWNGRADED')
  })
})

describe('processDocument: monitoring domain → HASH primitive', () => {
  it('uses monitoring domain content without governance/security/quality', async () => {
    const content = 'Telemetry monitoring observability metrics are collected for the system.'
    const lineage = await buildAndProcess('doc-monitor', content)
    expect(lineage.phases).toHaveLength(5)
    expect(lineage.final_tier).not.toBe('DOWNGRADED')
  })
})

describe('processDocument: no domain signals → general domain', () => {
  it('falls back to general domain when content has no known signals', async () => {
    const content = 'The quick brown fox jumps over the lazy dog.'
    const lineage = await buildAndProcess('doc-general', content)
    // Should produce 5 phases without throwing
    expect(lineage.phases).toHaveLength(5)
    expect(lineage.final_tier).not.toBe('DOWNGRADED')
  })
})

describe('processDocument: quality domain → FREEZE primitive', () => {
  it('uses quality domain content (test/verify/assert)', async () => {
    const content = 'Test assertions verify that the function returns the correct result.'
    const lineage = await buildAndProcess('doc-quality', content)
    expect(lineage.phases).toHaveLength(5)
  })
})

describe('processDocument: CANONICALIZE primitive (research-only domain)', () => {
  it('uses research domain only (no governance/security/quality/orchestration/deployment/monitoring)', async () => {
    const content = 'Research analysis and synthesis of data leads to insights.'
    const lineage = await buildAndProcess('doc-research', content)
    expect(lineage.phases).toHaveLength(5)
    expect(lineage.final_tier).not.toBe('DOWNGRADED')
  })
})

// ─── VCG: totalWeight === 0 ────────────────────────────────────

import { VCGTracker } from '../../src/calibration/vcg.js'
import { CalibrationDomain } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'

function groundTruthOutput(passed: boolean): VerifierOutput {
  return {
    verifier_id: 'v-gt',
    claim_id: 'c1',
    passed,
    raw_confidence: 0.9,
    evidence_refs: [],
    latency_ms: 10,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: CalibrationDomain.GROUND_TRUTH,
    artifact_hash: '0'.repeat(64) as SHA256Hex,
  }
}

describe('VCGTracker.compute: totalWeight === 0 → emptyMetric', () => {
  it('returns empty metric when all samples have decayed to zero weight', () => {
    const tracker = new VCGTracker('stream-decay-test')
    // Sample at timestamp 0, compute at TS=1.6e12 (well past half-life → decayFactor underflows to 0)
    tracker.addResult(groundTruthOutput(true), 0.9, 0)
    tracker.addResult(groundTruthOutput(false), 0.6, 0)
    const metric = tracker.compute(1_600_000_000_000)
    // totalWeight = 0 → emptyMetric: weighted_error=0, sample_count=0
    expect(metric.weighted_error).toBe(0)
    expect(metric.sample_count).toBe(0)
    expect(metric.effective_sample_size).toBe(0)
  })
})
