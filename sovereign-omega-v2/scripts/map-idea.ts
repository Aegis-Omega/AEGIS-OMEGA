#!/usr/bin/env tsx
/**
 * AEGIS Idea-to-Roadmap Mapper
 * Usage: npx tsx scripts/map-idea.ts --idea "<your idea>" [--skills <skills.json>]
 *
 * Maps a natural language idea to a constitutional WorkflowRoadmap.
 * If --skills is provided, uses that catalog. Otherwise starts with an empty catalog.
 *
 * Example:
 *   npx tsx scripts/map-idea.ts --idea "Build a real-time collaboration whiteboard"
 *   npx tsx scripts/map-idea.ts --idea "Add EU AI Act compliance audit trail" --skills ./skills.json
 */

import path from 'node:path'
import fs from 'node:fs'
import { mapIdeaToRoadmap } from '../src/skill-harness/roadmap/idea-mapper.js'
import { SkillCatalog, buildSkillRecord } from '../src/skill-harness/catalog.js'
import type { SkillInput } from '../src/skill-harness/types.js'

const args = process.argv.slice(2)
const ideaArg   = args[args.indexOf('--idea')   + 1] ?? ''
const skillsArg = args[args.indexOf('--skills') + 1] ?? null

if (!ideaArg) {
  console.error('Usage: npx tsx scripts/map-idea.ts --idea "<idea>" [--skills <skills.json>]')
  process.exit(1)
}

console.log(`\nAEGIS Idea Mapper\n`)
console.log(`Idea: "${ideaArg}"\n`)

let catalog = SkillCatalog.empty()

if (skillsArg) {
  const skillsPath = path.resolve(skillsArg)
  try {
    const raw = JSON.parse(fs.readFileSync(skillsPath, 'utf-8')) as { skills?: SkillInput[] }
    const skills = raw.skills ?? []
    for (const input of skills) {
      try {
        const record = await buildSkillRecord(input as SkillInput)
        const { catalog: next } = catalog.register(record)
        catalog = next
      } catch { /* skip duplicates */ }
    }
    console.log(`Loaded ${catalog.size} skills from ${skillsPath}\n`)
  } catch (e) {
    console.warn(`Could not load skills file: ${e instanceof Error ? e.message : String(e)}\n`)
  }
}

try {
  const roadmap = await mapIdeaToRoadmap(ideaArg, catalog, 1n as import('../src/core/types.js').SequenceNumber)

  // Print matched skills
  if (roadmap.matched_skills.length > 0) {
    console.log('Matched skills from catalog:')
    for (const s of roadmap.matched_skills.slice(0, 6)) {
      const bar = '█'.repeat(Math.round(s.confidence * 10)).padEnd(10, '░')
      console.log(`  ${s.skill_id.padEnd(35)} [${bar}] conf=${(s.confidence * 100).toFixed(0)}% rel=${(s.relevance * 100).toFixed(0)}%`)
    }
    console.log()
  }

  // Print gaps
  if (roadmap.skill_gaps.length > 0) {
    console.log('Skill gaps (not yet in catalog):')
    for (const g of roadmap.skill_gaps) {
      console.log(`  ✗ ${g.gap_id.padEnd(35)} complexity=${g.estimated_complexity}/10`)
      console.log(`    ${g.description}`)
    }
    console.log()
  }

  // Print roadmap
  const coveragePct = (roadmap.coverage_ratio * 100).toFixed(0)
  console.log(`Coverage: ${coveragePct}% of idea domains have catalog skills`)
  console.log(`Fibonacci complexity total: ${roadmap.fibonacci_total} (F-weighted phases)\n`)

  console.log('Roadmap phases:')
  console.log('═'.repeat(70))
  for (const phase of roadmap.phases) {
    const gapStr = phase.skill_gaps.length > 0 ? ` [${phase.skill_gaps.length} gap(s)]` : ' ✓'
    console.log(`\nPhase ${phase.phase_id} [${phase.ralph_stage}] — F=${phase.fibonacci_weight}${gapStr}`)
    console.log(`  ${phase.title}`)
    console.log(`  Deliverable: ${phase.deliverable}`)
    for (const criterion of phase.acceptance_criteria) {
      console.log(`  • ${criterion}`)
    }
  }
  console.log('\n' + '═'.repeat(70))
  console.log(`\nRoadmap hash: ${roadmap.roadmap_hash.slice(0, 16)}…`)
  console.log(`is_replay_reconstructable: ${roadmap.is_replay_reconstructable}`)
  console.log()

} catch (e) {
  console.error(`Failed: ${e instanceof Error ? e.message : String(e)}`)
  process.exit(1)
}
