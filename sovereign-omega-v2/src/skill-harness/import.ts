// ============================================================
// Skill Harness — Import Pipeline (RALPH Phase 1–3)
// EPISTEMIC TIER: T2
// Parses SKILL.md files (YAML frontmatter + markdown) into SkillRecord.
// Raw narrative MUST NOT propagate — only T0–T2 admitted abstractions.
// Corpus processing directive: each document through OBSERVATION→ARBITRATION.
// ============================================================

import { buildSkillRecord, SkillCatalog } from './catalog.js'
import { SkillCatalogError } from './types.js'
import type { SkillEpistemicTier, SkillImportResult, RawSkillManifest } from './types.js'

// PHASE 1 — OBSERVATION: extract name + description from SKILL.md frontmatter.
// Returns null if frontmatter cannot be parsed.
export function parseSkillFrontmatter(
  content: string
): { name: string; description: string } | null {
  const match = content.match(/^---\s*\n([\s\S]*?)\n---/)
  if (!match) return null
  /* c8 ignore next -- noUncheckedIndexedAccess artifact; match[1] is always defined when match is non-null */
  const frontmatter = match[1] ?? ''
  const nameMatch = frontmatter.match(/^name:\s*(.+)$/m)
  const descMatch = frontmatter.match(/^description:\s*(.+)$/m)
  const name = nameMatch?.[1]?.trim()
  const description = descMatch?.[1]?.trim()
  if (!name || !description) return null
  return { name, description }
}

// PHASE 2 — INTERPRETATION: assign constitutional primitive_mapping via keyword heuristic.
export function assignPrimitiveMapping(name: string, description: string): string {
  const text = (name + ' ' + description).toLowerCase()
  if (/audit|check|verify|valida|assert|inspect/.test(text)) return 'VERIFY'
  if (/hash|sign|fingerprint|integrity|certif/.test(text)) return 'HASH'
  if (/serial|format|normaliz|render|canon/.test(text)) return 'CANONICALIZE'
  if (/order|sequen|schedul|queue|priorit/.test(text)) return 'SEQUENCE'
  if (/lock|freeze|seal|immut|protect/.test(text)) return 'FREEZE'
  return 'CANONICALIZE'  // default — observational
}

// PHASE 2 — INTERPRETATION: assign domain_affinity via keyword heuristic.
export function assignDomainAffinity(name: string, description: string): readonly string[] {
  const text = (name + ' ' + description).toLowerCase()
  const domains: string[] = []
  if (/git|version|commit|branch|merge/.test(text)) domains.push('version-control')
  if (/test|spec|assert|coverage/.test(text)) domains.push('testing')
  if (/deploy|build|ci|pipeline|workflow/.test(text)) domains.push('deployment')
  if (/design|ui|ux|style|layout/.test(text)) domains.push('design')
  if (/research|analys|document/.test(text)) domains.push('research')
  if (/govern|audit|compliance|policy/.test(text)) domains.push('governance')
  if (/replay|lineage|constitutional/.test(text)) domains.push('constitutional')
  if (domains.length === 0) domains.push('operations')
  return Object.freeze(domains)
}

// PHASE 3 — ARBITRATION: classify tier. Heuristics downgrade speculative content.
// T4/T5 concepts produce tier that fails SkillEpistemicTier (T0–T2 only), blocking import.
function classifyTier(name: string, description: string): SkillEpistemicTier | 'REJECTED' {
  const text = (name + ' ' + description).toLowerCase()
  // Speculative content → reject (cannot be T0–T2 in SkillEpistemicTier)
  if (/superintellig|omniscien|omnipoten|agi\b|sentien|conscious|self.aware/.test(text)) {
    return 'REJECTED'
  }
  return 'T2'  // External skills are T2 by default until empirically validated
}

// Full RALPH Phase 1–3 import pipeline.
export async function importSkillsFromManifests(
  manifests: readonly RawSkillManifest[]
): Promise<SkillImportResult> {
  const admitted: import('./types.js').SkillRecord[] = []
  const rejected: { skill_id: string; reason: string }[] = []
  let catalog = SkillCatalog.empty()

  for (const manifest of manifests) {
    // Phase 1 — Observation
    const parsed = parseSkillFrontmatter(manifest.content)
    if (!parsed) {
      rejected.push({ skill_id: manifest.path, reason: 'OBSERVATION: missing YAML frontmatter' })
      continue
    }

    const { name, description } = parsed
    const skill_id = name.toLowerCase().replace(/[^a-z0-9]+/g, '_')

    // Phase 3 — Arbitration (tier check before mutation)
    const tier = classifyTier(name, description)
    if (tier === 'REJECTED') {
      rejected.push({ skill_id, reason: 'ARBITRATION: T4/T5 speculative content downgraded' })
      continue
    }

    // Phase 2 — Interpretation (after arbitration clears)
    const primitive_mapping = assignPrimitiveMapping(name, description)
    const domain_affinity = assignDomainAffinity(name, description)

    try {
      const record = await buildSkillRecord({
        skill_id,
        name,
        confidence: 0.5,        // Phase 1 baseline — no telemetry yet
        validated_runs: 0,
        failure_rate: 0,
        recency_score: 1.0,
        domain_affinity,
        dependencies: [],
        evidence_refs: [manifest.source],
        last_validated: '2026-05-20T00:00:00Z',
        epistemic_tier: tier,
        primitive_mapping,
      })
      const { catalog: next } = catalog.register(record)
      catalog = next
      admitted.push(record)
    } catch (e) {
      /* c8 ignore next -- buildSkillRecord and catalog.register only throw SkillCatalogError; false arm is dead */
      const reason = e instanceof SkillCatalogError ? e.message : 'CATALOG: registration failed'
      rejected.push({ skill_id, reason })
    }
  }

  const catalog_hash = await catalog.catalogHash()
  return Object.freeze({
    admitted: Object.freeze(admitted),
    rejected: Object.freeze(rejected),
    catalog_hash,
    is_replay_reconstructable: true as const,
  })
}
