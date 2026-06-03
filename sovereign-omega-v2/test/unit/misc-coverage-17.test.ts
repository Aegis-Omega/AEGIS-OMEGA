// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 17
// EPISTEMIC TIER: T0/T2
//
// Covers paths with zero prior coverage in:
//   lib/telemetry.ts        — notify() body (lines 27-28), fetchOnce ok
//                             (lines 35-36), fetchOnce !ok (line 34),
//                             fetchOnce non-AbortError catch (line 39)
//   skill-harness/import.ts — assignDomainAffinity research branch (line 49)
//   skill-harness/propagation.ts — semantic_alignment zero branch (line 98)
//   skill-harness/roadmap/idea-mapper.ts — sort comparator (line 214)
// ============================================================

import { describe, it, expect, vi, afterEach } from 'vitest'
import { subscribeTelemetry } from '../../src/lib/telemetry.js'
import type { TelemetryState, TelemetrySnapshot } from '../../src/lib/telemetry.js'

// ── lib/telemetry.ts — notify + fetchOnce paths ───────────────────────────────
//
// The module uses global mutable state (abortController, listeners, currentState).
// Each test subscribes, awaits the first fetchOnce cycle, then unsubscribes to
// abort the polling loop. Tests are sequential; unsub() cleans module state
// between runs (abortController = null, listeners cleared).

describe('lib/telemetry — notify + fetchOnce branch coverage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('covers lines 27-28, 35-36: notify sets currentState and broadcasts on ok fetch', async () => {
    const snapshot: TelemetrySnapshot = {
      sequence: 10,
      epoch: 2,
      avg_vcg_error: 0.001,
      drift_index: 0.5,
      pgcs_passes: true,
      failsafe_state: 'stable',
      corruption_count: 0,
      calibrator_passes_100k: true,
    }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(snapshot),
    } as Response)

    const received: TelemetryState[] = []
    const unsub = subscribeTelemetry(s => received.push(s))

    // Yield to the event loop so the async loop() runs fetchOnce once
    await new Promise<void>(r => setTimeout(r, 10))

    // The last element is from notify() inside fetchOnce — covers lines 27-28, 35-36
    const last = received.at(-1)
    expect(last).toEqual({ status: 'online', data: snapshot })
    unsub()
  })

  it('covers line 34: fetchOnce notifies error state when bridge returns !ok', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 503,
    } as Response)

    const received: TelemetryState[] = []
    const unsub = subscribeTelemetry(s => received.push(s))

    await new Promise<void>(r => setTimeout(r, 10))

    // notify({ status: 'error', message: 'Bridge 503' }) — line 34
    const last = received.at(-1)
    expect(last).toEqual({ status: 'error', message: 'Bridge 503' })
    unsub()
  })

  it('covers line 39: fetchOnce notifies offline on non-AbortError fetch failure', async () => {
    // TypeError.name === 'TypeError', not 'AbortError' — hits the offline branch at line 39
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('network unavailable'))

    const received: TelemetryState[] = []
    const unsub = subscribeTelemetry(s => received.push(s))

    await new Promise<void>(r => setTimeout(r, 10))

    // notify({ status: 'offline' }) — line 39
    const last = received.at(-1)
    expect(last).toEqual({ status: 'offline' })
    unsub()
  })

  it('AbortError is silently swallowed — no extra notification beyond initial state', async () => {
    const abortErr = new DOMException('The user aborted a request.', 'AbortError')
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(abortErr)

    const received: TelemetryState[] = []
    const unsub = subscribeTelemetry(s => received.push(s))

    await new Promise<void>(r => setTimeout(r, 10))
    const countBefore = received.length
    // AbortError path returns without calling notify — count does not grow
    expect(countBefore).toBe(1)  // only the direct listener(currentState) call
    unsub()
  })
})

// ── skill-harness/import.ts — assignDomainAffinity research branch (line 49) ─

import { assignDomainAffinity } from '../../src/skill-harness/import.js'

describe('assignDomainAffinity — research/analysis/document branch (line 49)', () => {
  it('pushes research domain when name/description contains "research"', () => {
    const domains = assignDomainAffinity('document research', 'systematic analysis tool')
    expect(domains).toContain('research')
  })

  it('pushes research when text contains "analys" substring', () => {
    const domains = assignDomainAffinity('analysis engine', 'deep analytical framework')
    expect(domains).toContain('research')
  })

  it('pushes research when text contains "document"', () => {
    const domains = assignDomainAffinity('document processor', 'pdf handling utility')
    expect(domains).toContain('research')
  })

  it('research domain stacks with other matched domains', () => {
    // text matches both "test" (testing) and "document" (research)
    const domains = assignDomainAffinity('test document runner', 'spec and research')
    expect(domains).toContain('research')
    expect(domains).toContain('testing')
  })
})

// ── skill-harness/propagation.ts — semantic_alignment zero (line 98) ──────────

import { checkPropagation } from '../../src/skill-harness/propagation.js'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'
import type { SkillInput } from '../../src/skill-harness/types.js'

const EMPTY_DOMAINS_INPUT: SkillInput = {
  skill_id: 'cov17_empty_affinity',
  name: 'hash-chain-ops',   // resonant name for LAN gate
  confidence: 0.9,
  validated_runs: 10,
  failure_rate: 0.05,
  recency_score: 0.9,
  domain_affinity: [],       // empty — covers line 98 ternary true branch (? 0)
  dependencies: [],
  evidence_refs: ['ref_001'],
  last_validated: '2026-01-01T00:00:00Z',
  epistemic_tier: 'T1',
  primitive_mapping: 'HASH',
}

describe('checkPropagation — empty domain_affinity (line 98 ternary ? 0 branch)', () => {
  it('semantic_alignment is 0 when source_unique is empty (covers line 98 ? 0 path)', async () => {
    const record = await buildSkillRecord(EMPTY_DOMAINS_INPUT)
    const report = checkPropagation(record, [], ['testing', 'deployment'])
    expect(report.semantic_alignment).toBe(0)
    expect(report.www_resonant).toBe(false)
  })

  it('can_propagate is false and network_depth reflects no www layer', async () => {
    const record = await buildSkillRecord(EMPTY_DOMAINS_INPUT)
    const report = checkPropagation(record, [], ['alpha'])
    expect(report.semantic_alignment).toBe(0)
    expect(report.can_propagate).toBe(false)
  })
})

// ── skill-harness/roadmap/idea-mapper.ts — sort comparator (line 214) ─────────

import { mapIdeaToRoadmap } from '../../src/skill-harness/roadmap/idea-mapper.js'
import { SkillCatalog } from '../../src/skill-harness/catalog.js'
import type { SequenceNumber } from '../../src/core/types.js'

const SEQ1 = BigInt(1) as unknown as SequenceNumber

describe('mapIdeaToRoadmap — sort comparator invoked with 2+ matched skills (line 214)', () => {
  it('sorts matched skills by relevance×confidence descending; comparator called when 2+ entries pass filter', async () => {
    // Idea triggers DOMAIN_KEYWORDS: 'testing' (test) and 'deployment' (deploy, pipeline)
    const idea = 'deploy and test the ci pipeline'

    // Skill A: covers both domains → relevance = 2/2 = 1.0, conf = 0.9 → score 0.9
    const skillA = await buildSkillRecord({
      skill_id: 'cov17_deploy_test',
      name: 'deploy-test-seal',
      confidence: 0.9,
      validated_runs: 15,
      failure_rate: 0.02,
      recency_score: 0.95,
      domain_affinity: ['testing', 'deployment'],
      dependencies: [],
      evidence_refs: ['ci.yml'],
      last_validated: '2026-01-01T00:00:00Z',
      epistemic_tier: 'T2',
      primitive_mapping: 'CANONICALIZE',
    })

    // Skill B: covers only testing → relevance = 1/2 = 0.5, conf = 0.8 → score 0.4
    const skillB = await buildSkillRecord({
      skill_id: 'cov17_test_only',
      name: 'test-suite-ops',
      confidence: 0.8,
      validated_runs: 10,
      failure_rate: 0.05,
      recency_score: 0.85,
      domain_affinity: ['testing'],
      dependencies: [],
      evidence_refs: ['spec.ts'],
      last_validated: '2026-01-01T00:00:00Z',
      epistemic_tier: 'T2',
      primitive_mapping: 'CANONICALIZE',
    })

    const { catalog: c1 } = SkillCatalog.empty().register(skillA)
    const { catalog } = c1.register(skillB)

    const roadmap = await mapIdeaToRoadmap(idea, catalog, SEQ1)

    // Both skills match (relevance > 0) — sort comparator is invoked (line 214)
    expect(roadmap.matched_skills.length).toBeGreaterThanOrEqual(2)

    // Higher-scoring skill (A: score 0.9) must sort before lower-scoring (B: score 0.4)
    const ids = roadmap.matched_skills.map(m => m.skill_id)
    const idxA = ids.indexOf('cov17_deploy_test')
    const idxB = ids.indexOf('cov17_test_only')
    expect(idxA).not.toBe(-1)
    expect(idxB).not.toBe(-1)
    expect(idxA).toBeLessThan(idxB)
  })
})
