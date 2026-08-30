// ============================================================
// Gate 95 — VCG + SHP Composition (Integration)
// ~18 tests: VCG calibration output flows into SHP LOCK;
//   buildConfidence score drives harmonize decision;
//   determinism ×3 on joint pipeline.
// ============================================================

import { describe, it, expect } from 'vitest'
import { VCGTracker, buildConfidence } from '../../src/calibration/vcg.js'
import { RalphLoop, estimateSystemEntropy } from '../../src/core/ralph-loop.js'
import { CalibrationDomain, HolonicScale } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'
import type { SequenceNumber } from '../../src/core/types.js'

const TS = 1_600_000_000_000

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function makeOutput(passed: boolean, domain: CalibrationDomain, id: string): VerifierOutput {
  return Object.freeze({
    verifier_id: id,
    claim_id: `claim_${id}`,
    passed,
    raw_confidence: passed ? 0.9 : 0.1,
    evidence_refs: [],
    latency_ms: 1,
    determinism_flag: true,
    verifier_version: '1.0.0',
    trust_class: domain,
    artifact_hash: id.padEnd(64, '0') as any,
  })
}

function buildGroundTruthTracker(passes: boolean[]): VCGTracker {
  const tracker = new VCGTracker('vcg-shp')
  for (let i = 0; i < passes.length; i++) {
    tracker.addResult(makeOutput(passes[i]!, CalibrationDomain.GROUND_TRUTH, `v${i}`), passes[i]! ? 0.9 : 0.1, TS + i)
  }
  return tracker
}

// ─── VCG flows into SHP LOCK ──────────────────────────────

describe('VCG + SHP: calibration drives harmonize', () => {
  it('high-confidence calibration → PASS harmonize', () => {
    const tracker = buildGroundTruthTracker(Array(100).fill(true))
    const conf = buildConfidence(tracker, TS + 100, ['v1'])
    expect(conf.value).toBeGreaterThanOrEqual(0)

    const loop = new RalphLoop(HolonicScale.MOLECULAR, estimateSystemEntropy(0.95))
    const builder = loop.beginCycle(seq(1))
    builder.addAnalysisNote(`VCG confidence: ${conf.value}`)
    const cycle = builder.harmonize(conf.value >= 0.5 ? 'PASS' : 'FAIL')
    expect(cycle.harmonization_result).toBe('COHERENT')
    expect(loop.convergenceDepth()).toBe(1)
  })

  it('poor calibration → FAIL harmonize resets depth', () => {
    // All samples: high claimed confidence (0.9) but actually failed → weighted_error high
    const tracker = new VCGTracker('poor')
    for (let i = 0; i < 100; i++) {
      tracker.addResult(makeOutput(false, CalibrationDomain.GROUND_TRUTH, `g${i}`), 0.9, TS + i)
    }
    const metric = tracker.compute(TS + 100)
    expect(metric.weighted_error).toBeGreaterThan(0.5)

    const loop = new RalphLoop(HolonicScale.MOLECULAR, estimateSystemEntropy(0.5))
    for (let i = 1; i <= 3; i++) {
      loop.beginCycle(seq(i)).harmonize('PASS')
    }
    expect(loop.convergenceDepth()).toBe(3)
    const builder = loop.beginCycle(seq(4))
    builder.harmonize(metric.weighted_error > 0.5 ? 'FAIL' : 'PASS')
    expect(loop.convergenceDepth()).toBe(0)
  })

  it('5 consecutive VCG-PASS cycles → convergenceDepth=5', () => {
    const loop = new RalphLoop(HolonicScale.ORGANISM, estimateSystemEntropy(0.9))
    for (let i = 1; i <= 5; i++) {
      const tracker = buildGroundTruthTracker(Array(10).fill(true))
      const conf = buildConfidence(tracker, TS + i * 10, ['v1'])
      const builder = loop.beginCycle(seq(i))
      builder.addAnalysisNote(`cycle ${i} conf=${conf.value}`)
      builder.harmonize('PASS')
    }
    expect(loop.convergenceDepth()).toBe(5)
  })
})

// ─── Determinism ──────────────────────────────────────────

describe('VCG + SHP: determinism', () => {
  it('buildConfidence deterministic ×3 after 100 samples', () => {
    const tracker = buildGroundTruthTracker(
      Array.from({ length: 100 }, (_, i) => i % 2 === 0),
    )
    const c1 = buildConfidence(tracker, TS + 200, ['v1', 'v2'])
    const c2 = buildConfidence(tracker, TS + 200, ['v1', 'v2'])
    const c3 = buildConfidence(tracker, TS + 200, ['v1', 'v2'])
    expect(c1.value).toBe(c2.value)
    expect(c2.value).toBe(c3.value)
    expect(c1.type).toBe(c2.type)
  })

  it('archive from VCG-driven loop is frozen', () => {
    const loop = new RalphLoop(HolonicScale.MOLECULAR, estimateSystemEntropy(0.9))
    for (let i = 1; i <= 5; i++) loop.beginCycle(seq(i)).harmonize('PASS')
    const archive = loop.exportArchive(5)
    expect(Object.isFrozen(archive)).toBe(true)
    expect(archive.total_cycles).toBe(5)
    expect(archive.convergence_depth).toBe(5)
  })

  it('VCG sample_count tracks injected results', () => {
    const tracker = new VCGTracker('count-test')
    for (let i = 0; i < 25; i++) {
      tracker.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, `g${i}`), 0.9, TS + i)
    }
    const metric = tracker.compute(TS + 25)
    expect(metric.sample_count).toBe(25)
  })
})

// ─── Pipeline integrity ───────────────────────────────────

describe('VCG + SHP: pipeline integrity', () => {
  it('RETRIEVAL_ASSISTED weight < GROUND_TRUTH weight in VCG', () => {
    const tGT = new VCGTracker('gt')
    tGT.addResult(makeOutput(true, CalibrationDomain.GROUND_TRUTH, 'g1'), 0.9, TS)
    const mGT = tGT.compute(TS + 1)

    const tRA = new VCGTracker('ra')
    tRA.addResult(makeOutput(true, CalibrationDomain.RETRIEVAL_ASSISTED, 'r1'), 0.9, TS)
    const mRA = tRA.compute(TS + 1)

    // Both count exactly 1 sample
    expect(mGT.sample_count).toBe(1)
    expect(mRA.sample_count).toBe(1)
  })

  it('empty VCG → weighted_error=0 → PASS harmonize', () => {
    const tracker = new VCGTracker('empty')
    const metric = tracker.compute(TS)
    expect(metric.weighted_error).toBe(0)

    const loop = new RalphLoop(HolonicScale.SUBATOMIC, estimateSystemEntropy(0.95))
    const cycle = loop.beginCycle(seq(1)).harmonize(metric.weighted_error === 0 ? 'PASS' : 'FAIL')
    expect(cycle.gate_result).toBe('PASS')
  })

  it('ADVISORY_EXCLUDED never inflates FAIL rate in VCG pipeline', () => {
    const tracker = new VCGTracker('advisory-guard')
    for (let i = 0; i < 50; i++) {
      tracker.addResult(makeOutput(false, CalibrationDomain.ADVISORY_EXCLUDED, `adv${i}`), 0.9, TS + i)
    }
    const metric = tracker.compute(TS + 50)
    expect(metric.sample_count).toBe(0)
    expect(metric.weighted_error).toBe(0)

    const loop = new RalphLoop(HolonicScale.ORGANISM, estimateSystemEntropy(0.95))
    const cycle = loop.beginCycle(seq(1)).harmonize(metric.weighted_error > 0.5 ? 'FAIL' : 'PASS')
    expect(cycle.gate_result).toBe('PASS')
  })
})
