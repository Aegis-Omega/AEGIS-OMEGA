// ============================================================
// SOVEREIGN OMEGA — Idea-to-Roadmap Mapper tests
// EPISTEMIC TIER: T2
//
// Tests for skill-harness/roadmap/idea-mapper.ts:
//   IdeaMapperError  — error subclass
//   mapIdeaToRoadmap — throws, frozen result, phases, hashing, matching
//   refineRoadmap    — chains roadmap_hash
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  IdeaMapperError,
  mapIdeaToRoadmap,
  refineRoadmap,
  ROADMAP_SCHEMA_VERSION,
} from '../../src/skill-harness/roadmap/idea-mapper.js'
import { SkillCatalog, buildSkillRecord } from '../../src/skill-harness/catalog.js'
import type { SequenceNumber } from '../../src/core/types.js'

const SEQ1 = 1n as unknown as SequenceNumber
const SEQ2 = 2n as unknown as SequenceNumber
const EMPTY = SkillCatalog.empty()

// ── IdeaMapperError ────────────────────────────────────────

describe('IdeaMapperError', () => {
  it('is an Error subclass with correct name and message', () => {
    const e = new IdeaMapperError('test')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('IdeaMapperError')
    expect(e.message).toBe('test')
  })
})

// ── mapIdeaToRoadmap ────────────────────────────────────────

describe('mapIdeaToRoadmap', () => {
  it('throws IdeaMapperError for empty idea string', async () => {
    await expect(mapIdeaToRoadmap('', EMPTY, SEQ1)).rejects.toThrow(IdeaMapperError)
  })

  it('throws IdeaMapperError for whitespace-only idea', async () => {
    await expect(mapIdeaToRoadmap('   \t\n', EMPTY, SEQ1)).rejects.toThrow(IdeaMapperError)
  })

  it('returns a frozen WorkflowRoadmap', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(Object.isFrozen(roadmap)).toBe(true)
  })

  it('is_replay_reconstructable is true and schema_version is correct', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(roadmap.is_replay_reconstructable).toBe(true)
    expect(roadmap.schema_version).toBe(ROADMAP_SCHEMA_VERSION)
  })

  it('idea_hash is a 64-char hex string', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(roadmap.idea_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('roadmap_hash is a 64-char hex string', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(roadmap.roadmap_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is deterministic — three identical calls produce equal hashes', async () => {
    const idea = 'build a react frontend component'
    const [r1, r2, r3] = await Promise.all([
      mapIdeaToRoadmap(idea, EMPTY, SEQ1),
      mapIdeaToRoadmap(idea, EMPTY, SEQ1),
      mapIdeaToRoadmap(idea, EMPTY, SEQ1),
    ])
    expect(r1.idea_hash).toBe(r2.idea_hash)
    expect(r2.idea_hash).toBe(r3.idea_hash)
    expect(r1.roadmap_hash).toBe(r2.roadmap_hash)
    expect(r2.roadmap_hash).toBe(r3.roadmap_hash)
  })

  it('coverage_ratio is 0 when catalog is empty', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(roadmap.coverage_ratio).toBe(0)
  })

  it('fibonacci_total is positive', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(roadmap.fibonacci_total).toBeGreaterThan(0)
  })

  it('phases always begin with READ (phase_id=0) and end with HARMONIZE', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(roadmap.phases.length).toBeGreaterThanOrEqual(2)
    expect(roadmap.phases[0]!.ralph_stage).toBe('READ')
    expect(roadmap.phases[roadmap.phases.length - 1]!.ralph_stage).toBe('HARMONIZE')
    expect(roadmap.phases[0]!.phase_id).toBe(0)
  })

  it('skill_gaps are inferred from uncovered domains when catalog is empty', async () => {
    const roadmap = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    expect(roadmap.skill_gaps.length).toBeGreaterThan(0)
    expect(roadmap.skill_gaps[0]!.gap_id).toMatch(/^gap_/)
    expect(roadmap.skill_gaps[0]!.estimated_complexity).toBeGreaterThan(0)
  })

  it('different ideas produce different idea_hash values', async () => {
    const r1 = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    const r2 = await mapIdeaToRoadmap('create a rest api authentication endpoint', EMPTY, SEQ1)
    expect(r1.idea_hash).not.toBe(r2.idea_hash)
  })

  it('matched_skills populated and coverage_ratio=1 when catalog covers the idea domain', async () => {
    const record = await buildSkillRecord({
      skill_id: 'frontend_pattern',
      name: 'Frontend Component Pattern',
      confidence: 0.85,
      validated_runs: 20,
      failure_rate: 0,
      recency_score: 1.0,
      domain_affinity: ['frontend', 'react'],
      dependencies: [],
      evidence_refs: ['App.tsx'],
      last_validated: '2024-01-01T00:00:00.000Z',
      epistemic_tier: 'T2',
      primitive_mapping: 'CANONICALIZE',
    })
    const { catalog } = SkillCatalog.empty().register(record)
    const roadmap = await mapIdeaToRoadmap('build a react component', catalog, SEQ1)
    expect(roadmap.matched_skills.length).toBeGreaterThan(0)
    expect(roadmap.matched_skills[0]!.skill_id).toBe('frontend_pattern')
    expect(roadmap.coverage_ratio).toBe(1)
  })
})

// ── refineRoadmap ──────────────────────────────────────────

describe('refineRoadmap', () => {
  it('previous_roadmap_hash equals the original roadmap_hash', async () => {
    const original = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    const refined = await refineRoadmap(original, EMPTY, SEQ2)
    expect(refined.previous_roadmap_hash).toBe(original.roadmap_hash)
  })

  it('different sequence produces a different roadmap_hash', async () => {
    const original = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    const refined = await refineRoadmap(original, EMPTY, SEQ2)
    expect(refined.roadmap_hash).not.toBe(original.roadmap_hash)
  })

  it('refined roadmap is frozen', async () => {
    const original = await mapIdeaToRoadmap('build a react frontend component', EMPTY, SEQ1)
    const refined = await refineRoadmap(original, EMPTY, SEQ2)
    expect(Object.isFrozen(refined)).toBe(true)
  })
})
