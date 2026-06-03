// ============================================================
// Skill Harness — Idea-to-Roadmap Mapper
// EPISTEMIC TIER: T2 (engineering hypothesis)
//
// Maps a natural language idea to a constitutional WorkflowRoadmap.
// Gaps between available skills and required skills become phases.
// Phases are weighted by Fibonacci sequence (complexity estimation).
// Each phase maps to a RALPH loop stage — refinement is structural.
//
// What this does that Claude Code / Codex / Cursor cannot:
//   - Uses the living SkillCatalog (persistent, not session-scoped)
//   - Gaps are real: derived from evidence-backed confidence scores
//   - Roadmap phases are Fibonacci-paced, not arbitrary bullet points
//   - Every refinement produces a new roadmap_hash — the evolution
//     of the idea is itself replay-certifiable
// ============================================================

import { hashValue } from '../../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../../core/types.js'
import type { SkillRecord } from '../types.js'
import type { SkillCatalog } from '../catalog.js'

export const ROADMAP_SCHEMA_VERSION = '1.0.0' as const

export type RalphPhase = 'READ' | 'ASSESS' | 'LOCK' | 'PROPAGATE' | 'HARMONIZE'

const RALPH_PHASES: RalphPhase[] = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE']

// Fibonacci sequence for phase complexity weighting
function fib(n: number): number {
  if (n <= 1) return 1
  let a = 1, b = 1
  for (let i = 2; i <= n; i++) { const t = a + b; a = b; b = t }
  return Math.min(b, 89)  // F_11 cap — same as FIBONACCI_CAP in scheduler
}

export interface SkillMatch {
  readonly skill_id: string
  readonly name: string
  readonly confidence: number
  readonly relevance: number  // 0.0–1.0 domain overlap score
}

export interface SkillGap {
  readonly gap_id: string      // inferred skill_id for missing skill
  readonly description: string
  readonly domain: string
  readonly estimated_complexity: number  // 1–10
}

export interface RoadmapPhase {
  readonly phase_id: number
  readonly title: string
  readonly ralph_stage: RalphPhase
  readonly matched_skills: readonly string[]  // skill_ids that cover this phase
  readonly skill_gaps: readonly string[]      // gap_ids that block this phase
  readonly deliverable: string
  readonly fibonacci_weight: number           // F_n for this phase
  readonly acceptance_criteria: readonly string[]
}

export interface WorkflowRoadmap {
  readonly idea: string
  readonly idea_hash: SHA256Hex
  readonly matched_skills: readonly SkillMatch[]
  readonly skill_gaps: readonly SkillGap[]
  readonly phases: readonly RoadmapPhase[]
  readonly fibonacci_total: number  // total complexity estimate
  readonly coverage_ratio: number   // matched_skills / (matched + gaps) — how much catalog covers the idea
  readonly sequence: SequenceNumber
  readonly roadmap_hash: SHA256Hex
  readonly schema_version: typeof ROADMAP_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class IdeaMapperError extends Error {
  override readonly name = 'IdeaMapperError'
}

// ── Keyword extraction — lightweight, no API required ─────────────────────────

const DOMAIN_KEYWORDS: Record<string, string[]> = {
  frontend:    ['ui', 'interface', 'component', 'react', 'vue', 'page', 'form', 'button', 'layout', 'design', 'dashboard', 'modal', 'chart'],
  api:         ['api', 'endpoint', 'rest', 'graphql', 'request', 'response', 'route', 'server', 'backend', 'webhook', 'socket'],
  auth:        ['auth', 'login', 'signup', 'oauth', 'jwt', 'token', 'session', 'user', 'permission', 'role', 'access'],
  data:        ['database', 'query', 'schema', 'model', 'migration', 'sql', 'nosql', 'cache', 'store', 'persist', 'storage'],
  ai:          ['ai', 'ml', 'model', 'inference', 'predict', 'generate', 'llm', 'embedding', 'prompt', 'completion', 'vector'],
  testing:     ['test', 'spec', 'coverage', 'mock', 'assert', 'verify', 'validate', 'e2e', 'unit', 'integration'],
  deployment:  ['deploy', 'ci', 'cd', 'pipeline', 'docker', 'kubernetes', 'serverless', 'vercel', 'aws', 'cloud', 'infra'],
  realtime:    ['realtime', 'live', 'stream', 'websocket', 'event', 'notification', 'push', 'broadcast', 'subscribe'],
  governance:  ['audit', 'compliance', 'governance', 'constitutional', 'replay', 'trace', 'log', 'monitor', 'alert', 'policy'],
  performance: ['performance', 'speed', 'optimize', 'cache', 'cdn', 'compress', 'lazy', 'bundle', 'profile', 'benchmark'],
}

function extractDomains(idea: string): string[] {
  const lower = idea.toLowerCase()
  const matched: string[] = []
  for (const [domain, keywords] of Object.entries(DOMAIN_KEYWORDS)) {
    if (keywords.some(kw => lower.includes(kw))) matched.push(domain)
  }
  return matched.length > 0 ? matched : ['general']
}

function scoreRelevance(skill: SkillRecord, ideaDomains: string[]): number {
  const skillDomains = new Set(skill.domain_affinity.map(d => d.toLowerCase()))
  const overlap = ideaDomains.filter(d => skillDomains.has(d)).length
  return overlap / Math.max(ideaDomains.length, 1)
}

// ── Gap inference — derives missing skills from idea domains ─────────────────

const GAP_TEMPLATES: Record<string, { desc: string; complexity: number }> = {
  frontend:    { desc: 'UI component implementation and state wiring', complexity: 3 },
  api:         { desc: 'API contract definition and integration layer', complexity: 4 },
  auth:        { desc: 'Authentication flow and session management', complexity: 5 },
  data:        { desc: 'Data persistence layer and schema design', complexity: 5 },
  ai:          { desc: 'AI inference integration and prompt engineering', complexity: 6 },
  testing:     { desc: 'Test suite coverage for new functionality', complexity: 3 },
  deployment:  { desc: 'Deployment pipeline and environment configuration', complexity: 4 },
  realtime:    { desc: 'Real-time event streaming and synchronization', complexity: 7 },
  governance:  { desc: 'Audit trail and compliance instrumentation', complexity: 4 },
  performance: { desc: 'Performance profiling and optimization pass', complexity: 5 },
}

// ── Roadmap phase builder ─────────────────────────────────────────────────────

function buildPhases(
  ideaDomains: string[],
  matchedSkills: SkillMatch[],
  gaps: SkillGap[],
): RoadmapPhase[] {
  const phases: RoadmapPhase[] = []

  // Phase 0 — READ: understand the idea and existing codebase context
  phases.push({
    phase_id: 0,
    title: 'Codebase Context Scan',
    ralph_stage: 'READ',
    matched_skills: matchedSkills.slice(0, 3).map(s => s.skill_id),
    skill_gaps: [],
    deliverable: 'Confirmed understanding of existing patterns and skill catalog coverage',
    fibonacci_weight: fib(1),
    acceptance_criteria: [
      'All relevant existing skills identified with confidence ≥ 0.6',
      'Gaps enumerated with complexity estimates',
      'No T4/T5 assumptions in scope definition',
    ],
  })

  // Phases 1–N: one phase per RALPH stage covering actual implementation domains
  const stageDomains = ideaDomains.slice(0, 4)  // max 4 impl phases
  stageDomains.forEach((domain, i) => {
    const stage = RALPH_PHASES[Math.min(i + 1, 4)] as RalphPhase
    const relevantMatches = matchedSkills.filter(s => s.skill_id.includes(domain) || s.relevance > 0.5)
    const relevantGaps = gaps.filter(g => g.domain === domain)

    phases.push({
      phase_id: i + 1,
      title: `${domain.charAt(0).toUpperCase() + domain.slice(1)} Layer Implementation`,
      ralph_stage: stage,
      matched_skills: relevantMatches.map(s => s.skill_id),
      skill_gaps: relevantGaps.map(g => g.gap_id),
      deliverable: GAP_TEMPLATES[domain]?.desc ?? `${domain} subsystem functional`,
      fibonacci_weight: fib(i + 2),
      acceptance_criteria: [
        `All ${domain} components implement required interfaces`,
        relevantGaps.length > 0 ? `${relevantGaps.length} skill gaps closed via evidence-backed implementation` : 'No skill gaps — direct implementation',
        'Constitutional audit record produced for each inference call',
      ],
    })
  })

  // Final phase — HARMONIZE: integration, testing, deployment
  phases.push({
    phase_id: phases.length,
    title: 'Integration & Constitutional Certification',
    ralph_stage: 'HARMONIZE',
    matched_skills: matchedSkills.filter(s => s.skill_id.includes('test') || s.skill_id.includes('deploy')).map(s => s.skill_id),
    skill_gaps: gaps.filter(g => g.domain === 'testing' || g.domain === 'deployment').map(g => g.gap_id),
    deliverable: 'All phases integrated, tests pass, deployment certified',
    fibonacci_weight: fib(phases.length + 1),
    acceptance_criteria: [
      'Full test suite coverage (Gate 8 equivalent)',
      'is_replay_reconstructable: true on all new records',
      'AdaptivePower(T) ≤ ReplayVerifiability(T) preserved',
    ],
  })

  return phases
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function mapIdeaToRoadmap(
  idea: string,
  catalog: SkillCatalog,
  sequence: SequenceNumber,
): Promise<WorkflowRoadmap> {
  if (!idea.trim()) throw new IdeaMapperError('Idea must not be empty')

  const idea_hash = await hashValue({ idea, sequence: sequence.toString() }) as SHA256Hex
  const ideaDomains = extractDomains(idea)

  // Score all catalog skills against the idea
  const allSkills = catalog.getAll()
  const matchedSkills: SkillMatch[] = allSkills
    .map(skill => ({
      skill_id: skill.skill_id,
      name: skill.name,
      confidence: skill.confidence,
      relevance: scoreRelevance(skill, ideaDomains),
    }))
    .filter(m => m.relevance > 0 || m.confidence > 0.7)
    .sort((a, b) => (b.relevance * b.confidence) - (a.relevance * a.confidence))
    .slice(0, 12)  // top 12 matches

  // Identify gaps: domains in the idea not covered by high-confidence catalog skills
  const coveredDomains = new Set(
    matchedSkills
      .filter(m => m.relevance > 0.3 && m.confidence > 0.5)
      .flatMap(m => {
        const skill = catalog.lookup(m.skill_id)
        /* c8 ignore next -- false branch (!skill) never reached: all matched skills exist in the catalog by construction */
        return skill ? skill.domain_affinity : []
      })
  )

  const gaps: SkillGap[] = ideaDomains
    .filter(domain => !coveredDomains.has(domain))
    .map((domain, i) => ({
      gap_id: `gap_${domain}_${i}`,
      description: GAP_TEMPLATES[domain]?.desc ?? `${domain} capability not yet in catalog`,
      domain,
      estimated_complexity: GAP_TEMPLATES[domain]?.complexity ?? 4,
    }))

  const phases = buildPhases(ideaDomains, matchedSkills, gaps)
  const fibonacci_total = phases.reduce((sum, p) => sum + p.fibonacci_weight, 0)
  const coverage_ratio = matchedSkills.filter(m => m.relevance > 0.3).length /
    Math.max(matchedSkills.filter(m => m.relevance > 0.3).length + gaps.length, 1)

  const roadmap_hash = await hashValue({
    idea_hash,
    phase_count: phases.length,
    fibonacci_total,
    coverage_ratio,
    gap_count: gaps.length,
    sequence: sequence.toString(),
  }) as SHA256Hex

  return Object.freeze({
    idea,
    idea_hash,
    matched_skills: Object.freeze(matchedSkills),
    skill_gaps: Object.freeze(gaps),
    phases: Object.freeze(phases.map(p => Object.freeze(p))),
    fibonacci_total,
    coverage_ratio,
    sequence,
    roadmap_hash,
    schema_version: ROADMAP_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

/** Re-maps a roadmap after new skills are added — the refined roadmap chains to the original */
export async function refineRoadmap(
  original: WorkflowRoadmap,
  catalog: SkillCatalog,
  sequence: SequenceNumber,
): Promise<WorkflowRoadmap & { readonly previous_roadmap_hash: SHA256Hex }> {
  const refined = await mapIdeaToRoadmap(original.idea, catalog, sequence)
  return Object.freeze({
    ...refined,
    previous_roadmap_hash: original.roadmap_hash,
  })
}
