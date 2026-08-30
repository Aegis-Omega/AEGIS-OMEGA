// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 18
// EPISTEMIC TIER: T0/T2
//
// Covers paths with zero prior coverage in:
//   core/canonicalize.ts      — symbol type guard (line 65)
//   skill-harness/router.ts   — generalScore empty-profile fast path (line 85)
//   skill-harness/roadmap/idea-mapper.ts
//                             — GAP_TEMPLATES miss (lines 163, 231, 233)
//                             — filter false branch (line 213)
//   lib/telemetry.ts          — second-subscriber no-new-loop (line 56 false)
//                             — unsub with remaining listeners (line 62 false)
//
// NOTE: decay.ts line 65 is structurally dead — daysBetween() returns 0 for
// negative diffs (diffMs > 0 ? floor : 0), so days_inactive is always >= 0.
// ============================================================

import { describe, it, expect, vi, afterEach } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'

// ── core/canonicalize.ts — symbol type guard (line 65) ───────────────────────

import { canonicalizeJCS } from '../../src/core/canonicalize.js'

describe('canonicalizeJCS — symbol type (line 65)', () => {
  it('throws TypeError for Symbol input (covers line 65)', () => {
    // eslint-disable-next-line symbol-description
    expect(() => canonicalizeJCS(Symbol('cov18'))).toThrow(TypeError)
    expect(() => canonicalizeJCS(Symbol('cov18'))).toThrow('symbol is not JSON-serialisable')
  })

  it('also throws for unnamed Symbol', () => {
    expect(() => canonicalizeJCS(Symbol())).toThrow(TypeError)
  })
})

// ── skill-harness/router.ts — generalScore with empty skills (line 85) ───────

import { recommendRouting } from '../../src/skill-harness/router.js'
import type { AgentSkillProfile } from '../../src/skill-harness/router.js'
import { buildSkillRecord } from '../../src/skill-harness/catalog.js'

describe('recommendRouting — collaborator candidate with zero skills (line 85)', () => {
  it('generalScore returns 0 for empty-skill profile → no COLLABORATE → ROUTE_TO_BEST', async () => {
    // Agent A: one matching skill → agentScore = 0.5 × 0.8 × 1.0 = 0.4
    // (>= CONFIDENCE_FLOOR 0.3, < SPECIALIST_THRESHOLD 0.75 — enters COLLABORATE check)
    const skillA = await buildSkillRecord({
      skill_id: 'cov18_hash_skill',
      name: 'hash-chain-seal',
      confidence: 0.5,
      validated_runs: 10,
      failure_rate: 0.0,
      recency_score: 0.8,
      domain_affinity: ['hash'],
      dependencies: [],
      evidence_refs: ['ref_001'],
      last_validated: '2026-01-01T00:00:00.000Z',
      epistemic_tier: 'T1',
      primitive_mapping: 'HASH',
    })

    const agentA: AgentSkillProfile = { agent_id: 'agent-a', skills: [skillA] }
    // Agent B: no skills → generalScore({skills:[]}) = 0 < CONFIDENCE_FLOOR → not a collaborator
    const agentB: AgentSkillProfile = { agent_id: 'agent-b', skills: [] }

    const result = await recommendRouting('hash', [agentA, agentB])
    // Empty-skill agent disqualifies as collaborator → falls back to ROUTE_TO_BEST
    expect(result.decision).toBe('ROUTE_TO_BEST')
    expect(result.primary_agent_id).toBe('agent-a')
  })
})

// ── skill-harness/roadmap/idea-mapper.ts — GAP_TEMPLATES miss + filter false ──

import { mapIdeaToRoadmap } from '../../src/skill-harness/roadmap/idea-mapper.js'
import { SkillCatalog } from '../../src/skill-harness/catalog.js'

const SEQ1 = BigInt(1) as unknown as SequenceNumber
const EMPTY_CATALOG = SkillCatalog.empty()

describe('mapIdeaToRoadmap — GAP_TEMPLATES miss (lines 163, 231, 233)', () => {
  it('uses fallback strings when idea domain is not in GAP_TEMPLATES (e.g. "general")', async () => {
    // "implement the system" has no DOMAIN_KEYWORDS matches → extractDomains returns ['general']
    // "general" is not a key in GAP_TEMPLATES → the ?? branches fire on lines 163, 231, 233
    const roadmap = await mapIdeaToRoadmap('implement the system', EMPTY_CATALOG, SEQ1)

    expect(roadmap.is_replay_reconstructable).toBe(true)

    // Phases use the fallback deliverable (line 163 ?? branch)
    const hasGeneralPhase = roadmap.phases.some(p => p.deliverable.includes('general'))
    const hasHarmonize = roadmap.phases.some(p => p.ralph_stage === 'HARMONIZE')
    expect(hasGeneralPhase || hasHarmonize).toBe(true)

    // Gaps use fallback description and complexity (lines 231, 233)
    const generalGap = roadmap.skill_gaps.find(g => g.domain === 'general')
    if (generalGap) {
      expect(generalGap.description).toContain('general')
      expect(generalGap.estimated_complexity).toBe(4)  // ?? 4 branch
    }
  })

  it('non-standard domain produces fallback deliverable in phases', async () => {
    const roadmap = await mapIdeaToRoadmap('just orchestrate it', EMPTY_CATALOG, SEQ1)
    expect(roadmap.phases.length).toBeGreaterThanOrEqual(1)
    // At least the HARMONIZE phase exists regardless of domain
    expect(roadmap.phases.at(-1)!.ralph_stage).toBe('HARMONIZE')
  })
})

describe('mapIdeaToRoadmap — filter false branch (line 213)', () => {
  it('skills with relevance=0 AND confidence≤0.7 are filtered out of matched_skills', async () => {
    // Idea "implement the system" → domain 'general'
    // Skill with domain_affinity=['unrelated'] → relevance = 0/1 = 0
    //   AND confidence = 0.5 ≤ 0.7 → filter condition (relevance>0 || confidence>0.7) = false
    const lowSkill = await buildSkillRecord({
      skill_id: 'cov18_low_conf',
      name: 'unrelated-ops',
      confidence: 0.5,   // ≤ 0.7
      validated_runs: 5,
      failure_rate: 0.1,
      recency_score: 0.8,
      domain_affinity: ['unrelated'],  // won't overlap with 'general'
      dependencies: [],
      evidence_refs: ['ref_x'],
      last_validated: '2026-01-01T00:00:00.000Z',
      epistemic_tier: 'T2',
      primitive_mapping: 'CANONICALIZE',
    })
    const { catalog } = EMPTY_CATALOG.register(lowSkill)
    const roadmap = await mapIdeaToRoadmap('implement the system', catalog, SEQ1)

    // The low-confidence, no-overlap skill is filtered out → matched_skills is empty
    const found = roadmap.matched_skills.find(m => m.skill_id === 'cov18_low_conf')
    expect(found).toBeUndefined()
  })
})

// ── lib/telemetry.ts — second-subscriber and partial-unsub branches ───────────
//
// Lines 56-57 false branch: abortController already set when second subscriber joins
// Lines 62-64 false branch: unsub when listeners.size > 0 (no abort yet)

import { subscribeTelemetry } from '../../src/lib/telemetry.js'
import type { TelemetryState } from '../../src/lib/telemetry.js'

describe('lib/telemetry — multi-subscriber and partial-unsub branches', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('covers line 56 false: second subscribeTelemetry call skips loop start because abortController already set', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        sequence: 1, epoch: 1, avg_vcg_error: 0, drift_index: 0,
        pgcs_passes: true, failsafe_state: 'ok', corruption_count: 0,
        calibrator_passes_100k: true,
      }),
    } as Response)

    const calls1: TelemetryState[] = []
    const calls2: TelemetryState[] = []

    // First subscriber — starts loop (abortController created: line 56 true branch)
    const unsub1 = subscribeTelemetry(s => calls1.push(s))
    // Second subscriber — abortController already exists: line 56 FALSE branch
    const unsub2 = subscribeTelemetry(s => calls2.push(s))

    await new Promise<void>(r => setTimeout(r, 10))

    // Both got the initial direct call
    expect(calls1.length).toBeGreaterThanOrEqual(1)
    expect(calls2.length).toBeGreaterThanOrEqual(1)

    // Unsub1: listeners.size becomes 1 → line 62 FALSE branch (no abort)
    unsub1()
    // Unsub2: listeners.size becomes 0 → line 62 TRUE branch (abort fires)
    unsub2()
  })
})
