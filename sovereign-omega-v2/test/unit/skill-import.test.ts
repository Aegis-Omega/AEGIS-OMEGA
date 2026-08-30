import { describe, it, expect } from 'vitest'
import {
  parseSkillFrontmatter,
  assignPrimitiveMapping,
  assignDomainAffinity,
  importSkillsFromManifests,
} from '../../src/skill-harness/import.js'
import type { RawSkillManifest } from '../../src/skill-harness/types.js'

// ============================================================
// Gate 126 — Skill Import Pipeline Tests
// Fixtures are representative SKILL.md content derived from
// the format documented in obra/superpowers and antigravity-awesome-skills.
// RALPH Phase 1–3: Observation → Interpretation → Arbitration.
// ============================================================

const GIT_SKILL: RawSkillManifest = {
  source: 'github.com/obra/superpowers',
  path: 'skills/git-workflow/SKILL.md',
  content: `---
name: git-workflow
description: Automatically invoked when committing, branching, or reviewing git history to enforce clean version control hygiene.
---

# Git Workflow Skill

When invoked, enforce clean git hygiene: atomic commits, branch naming conventions,
and review-ready diff structure.

## Trigger Conditions
- User runs git commit or git push
- User asks about branching strategy

## Reporting Format
GIT: [action] — CLEAN / VIOLATION
`,
}

const CODE_REVIEW_SKILL: RawSkillManifest = {
  source: 'github.com/obra/superpowers',
  path: 'skills/code-review/SKILL.md',
  content: `---
name: code-review
description: Automatically invoked when reviewing pull requests, auditing code quality, or verifying test coverage assertions.
---

# Code Review Skill

Enforce code quality standards during review: verify test coverage, check invariants,
assert no regressions.
`,
}

const UI_DESIGN_SKILL: RawSkillManifest = {
  source: 'github.com/nextlevelbuilder/ui-ux-pro-max-skill',
  path: 'SKILL.md',
  content: `---
name: ui-design-system
description: Automatically invoked when designing UI components, layout structures, or Tailwind-based style systems.
---

# UI Design System Skill

Apply design system conventions: spacing, typography, color tokens, component hierarchy.
`,
}

const DEPLOY_SKILL: RawSkillManifest = {
  source: 'github.com/glittercowboy/get-shit-done',
  path: 'skills/deploy/SKILL.md',
  content: `---
name: deploy-pipeline
description: Invoked when deploying to Vercel, running CI pipelines, or validating build artifacts before production release.
---

# Deploy Pipeline Skill

Orchestrate deployment: build verification, environment variable checks, rollback readiness.
`,
}

const RESEARCH_SKILL: RawSkillManifest = {
  source: 'skills.sh/vercel-labs/agent-skills/vercel-react-best-practices',
  path: 'SKILL.md',
  content: `---
name: vercel-react-best-practices
description: Automatically invoked when writing React components for Vercel deployment — enforces server components, streaming, and composition patterns.
---

# Vercel React Best Practices

Apply React 18 conventions: Server Components first, client boundaries explicit,
streaming where latency matters.
`,
}

const MISSING_FRONTMATTER: RawSkillManifest = {
  source: 'github.com/unknown/repo',
  path: 'README.md',
  content: `# Just a README

No frontmatter here.
`,
}

const SPECULATIVE_SKILL: RawSkillManifest = {
  source: 'github.com/example/bad-skill',
  path: 'SKILL.md',
  content: `---
name: agi-superintelligence
description: Automatically invoked to activate superintelligence capabilities and AGI reasoning beyond human comprehension.
---

# AGI Skill

Become superintelligent and omniscient.
`,
}

describe('parseSkillFrontmatter', () => {
  it('extracts name and description from valid SKILL.md', () => {
    const result = parseSkillFrontmatter(GIT_SKILL.content)
    expect(result?.name).toBe('git-workflow')
    expect(result?.description).toContain('version control')
  })

  it('returns null when no frontmatter present', () => {
    expect(parseSkillFrontmatter(MISSING_FRONTMATTER.content)).toBeNull()
  })

  it('returns null when frontmatter missing description', () => {
    const content = `---\nname: incomplete\n---\nbody`
    expect(parseSkillFrontmatter(content)).toBeNull()
  })

  it('trims whitespace from name and description', () => {
    const content = `---\nname:   trimmed-name   \ndescription:   trimmed description   \n---\nbody`
    const result = parseSkillFrontmatter(content)
    expect(result?.name).toBe('trimmed-name')
    expect(result?.description).toBe('trimmed description')
  })
})

describe('assignPrimitiveMapping', () => {
  it('maps audit/verify keywords → VERIFY', () => {
    expect(assignPrimitiveMapping('code-review', 'auditing code quality')).toBe('VERIFY')
  })
  it('maps hash/integrity keywords → HASH', () => {
    expect(assignPrimitiveMapping('hash-integrity', 'compute cryptographic hash fingerprint')).toBe('HASH')
  })
  it('maps format/normalize keywords → CANONICALIZE', () => {
    expect(assignPrimitiveMapping('formatter', 'normalize code format')).toBe('CANONICALIZE')
  })
  it('maps schedule/queue keywords → SEQUENCE', () => {
    expect(assignPrimitiveMapping('task-queue', 'schedule and order tasks')).toBe('SEQUENCE')
  })
  it('maps freeze/seal keywords → FREEZE', () => {
    expect(assignPrimitiveMapping('config-lock', 'seal and freeze configuration')).toBe('FREEZE')
  })
  it('defaults to CANONICALIZE for unknown keywords', () => {
    expect(assignPrimitiveMapping('misc-skill', 'does miscellaneous things')).toBe('CANONICALIZE')
  })
})

describe('assignDomainAffinity', () => {
  it('assigns version-control for git keywords', () => {
    const domains = assignDomainAffinity('git-workflow', 'commit and branch management')
    expect(domains).toContain('version-control')
  })
  it('assigns design for ui/ux keywords', () => {
    const domains = assignDomainAffinity('ui-system', 'UI layout and design components')
    expect(domains).toContain('design')
  })
  it('assigns deployment for build/deploy keywords', () => {
    const domains = assignDomainAffinity('deploy', 'CI pipeline and build verification')
    expect(domains).toContain('deployment')
  })
  it('defaults to operations for unknown content', () => {
    const domains = assignDomainAffinity('unknown', 'does something')
    expect(domains).toContain('operations')
  })
  it('is frozen', () => {
    expect(Object.isFrozen(assignDomainAffinity('test', 'test'))).toBe(true)
  })
})

describe('importSkillsFromManifests', () => {
  it('admits valid skills', async () => {
    const result = await importSkillsFromManifests([GIT_SKILL, CODE_REVIEW_SKILL])
    expect(result.admitted.length).toBe(2)
    expect(result.rejected.length).toBe(0)
  })

  it('rejects manifest with missing frontmatter', async () => {
    const result = await importSkillsFromManifests([MISSING_FRONTMATTER])
    expect(result.admitted.length).toBe(0)
    expect(result.rejected.length).toBe(1)
    expect(result.rejected[0]?.reason).toContain('OBSERVATION')
  })

  it('rejects speculative T4/T5 content at ARBITRATION', async () => {
    const result = await importSkillsFromManifests([SPECULATIVE_SKILL])
    expect(result.admitted.length).toBe(0)
    expect(result.rejected.length).toBe(1)
    expect(result.rejected[0]?.reason).toContain('ARBITRATION')
  })

  it('mixed batch: valid + invalid', async () => {
    const manifests = [GIT_SKILL, MISSING_FRONTMATTER, SPECULATIVE_SKILL, UI_DESIGN_SKILL]
    const result = await importSkillsFromManifests(manifests)
    expect(result.admitted.length).toBe(2)
    expect(result.rejected.length).toBe(2)
  })

  it('catalog_hash is 64-char hex', async () => {
    const result = await importSkillsFromManifests([GIT_SKILL])
    expect(result.catalog_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is deterministic ×3', async () => {
    const manifests = [GIT_SKILL, CODE_REVIEW_SKILL, DEPLOY_SKILL]
    const [r1, r2, r3] = await Promise.all([
      importSkillsFromManifests(manifests),
      importSkillsFromManifests(manifests),
      importSkillsFromManifests(manifests),
    ])
    expect(r1.catalog_hash).toBe(r2.catalog_hash)
    expect(r2.catalog_hash).toBe(r3.catalog_hash)
  })

  it('is_replay_reconstructable is true', async () => {
    const result = await importSkillsFromManifests([RESEARCH_SKILL])
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('admitted records are frozen', async () => {
    const result = await importSkillsFromManifests([GIT_SKILL])
    expect(Object.isFrozen(result.admitted)).toBe(true)
    expect(Object.isFrozen(result.admitted[0])).toBe(true)
  })

  it('evidence_refs contains the source repo', async () => {
    const result = await importSkillsFromManifests([GIT_SKILL])
    expect(result.admitted[0]?.evidence_refs).toContain('github.com/obra/superpowers')
  })

  it('all admitted skills have T2 epistemic_tier', async () => {
    const result = await importSkillsFromManifests([GIT_SKILL, UI_DESIGN_SKILL, DEPLOY_SKILL])
    for (const record of result.admitted) {
      expect(record.epistemic_tier).toBe('T2')
    }
  })

  it('empty manifest list → admitted=[], catalog_hash is deterministic', async () => {
    const [r1, r2] = await Promise.all([
      importSkillsFromManifests([]),
      importSkillsFromManifests([]),
    ])
    expect(r1.admitted.length).toBe(0)
    expect(r1.catalog_hash).toBe(r2.catalog_hash)
  })
})
