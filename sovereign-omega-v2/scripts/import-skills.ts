#!/usr/bin/env tsx
// ============================================================
// AEGIS Skill Generator — scripts/import-skills.ts
// Populates the constitutional skill catalog from seed sources.
//
// Usage:
//   npx tsx scripts/import-skills.ts               # cognitive triad only
//   npx tsx scripts/import-skills.ts --all         # triad + manifests
//   npx tsx scripts/import-skills.ts --out catalog.json
// ============================================================

import { buildSkillRecord, SkillCatalog } from '../src/skill-harness/catalog.js'
import { checkSkillResonance } from '../src/skill-harness/resonance.js'
import { checkPropagation } from '../src/skill-harness/propagation.js'
import { COGNITIVE_TRIAD, COGNITIVE_TRIAD_IDS } from '../src/skill-harness/seeds.js'
import { CORE_AGENT_SKILL_INPUTS } from '../src/skill-harness/manifests/core-agents.js'
import { ANTIGRAVITY_SKILL_INPUTS } from '../src/skill-harness/manifests/antigravity.js'
import type { SkillInput } from '../src/skill-harness/types.js'
import { writeFileSync } from 'node:fs'

const PHI = (Math.sqrt(5) - 1) / 2

const args = process.argv.slice(2)
const includeAll = args.includes('--all')
const outFile = args.find(a => a.startsWith('--out='))?.slice(6) ?? null

// ── Colour helpers ──────────────────────────────────────────
const GREEN  = (s: string) => `\x1b[32m${s}\x1b[0m`
const GOLD   = (s: string) => `\x1b[33m${s}\x1b[0m`
const RED    = (s: string) => `\x1b[31m${s}\x1b[0m`
const CYAN   = (s: string) => `\x1b[36m${s}\x1b[0m`
const DIM    = (s: string) => `\x1b[2m${s}\x1b[0m`
const BOLD   = (s: string) => `\x1b[1m${s}\x1b[0m`

function bar(value: number, max: number, width = 20): string {
  const filled = Math.round((value / max) * width)
  return '█'.repeat(filled) + '░'.repeat(width - filled)
}

function drLabel(n: number): string {
  if (n === 0) return '9'
  const r = n % 9
  return String(r === 0 ? 9 : r)
}

function vortexLabel(nameLen: number): string {
  const dr = nameLen === 0 ? 9 : (nameLen % 9 === 0 ? 9 : nameLen % 9)
  return [3, 6, 9].includes(dr) ? GOLD('Triadic') : DIM('Hexadic')
}

// ── Main ────────────────────────────────────────────────────
async function main() {
  console.log()
  console.log(BOLD('═══════════════════════════════════════════════════════'))
  console.log(BOLD('  AEGIS Skill Generator — Constitutional Catalog Build'))
  console.log(BOLD('═══════════════════════════════════════════════════════'))
  console.log(DIM(`  φ = ${PHI.toFixed(16)}`))
  console.log(DIM(`  PHI_THRESHOLD (1/φ) governs: resonance, propagation, swarm`))
  console.log()

  // Collect sources
  const sources: Array<{ label: string; inputs: readonly SkillInput[] }> = [
    { label: 'Cognitive Triad (genesis seeds)', inputs: COGNITIVE_TRIAD },
  ]
  if (includeAll) {
    sources.push({ label: 'Core Agent Manifests (Gate 130)', inputs: CORE_AGENT_SKILL_INPUTS })
    sources.push({ label: 'Antigravity Pack', inputs: ANTIGRAVITY_SKILL_INPUTS })
  }

  let catalog = SkillCatalog.empty()
  let admitted = 0
  let rejected = 0
  const catalogRecords: object[] = []

  for (const { label, inputs } of sources) {
    console.log(CYAN(`▶ Source: ${label}`))
    console.log(DIM(`  ${inputs.length} skill(s) to process`))
    console.log()

    for (const input of inputs) {
      const record = await buildSkillRecord(input)
      const res = checkSkillResonance(record)

      // 3-layer propagation check (direct link, broadcast domain)
      const allDomains = [...new Set(record.domain_affinity)]
      const prop = checkPropagation(record, [], allDomains)

      const certified = res.is_certified ? GREEN('CERTIFIED') : res.is_resonant ? GOLD('RESONANT') : RED('BREACH')
      const depth_pips = '●'.repeat(res.resonance_depth) + '○'.repeat(4 - res.resonance_depth)

      console.log(`  ${BOLD(record.name.padEnd(26))} ${certified}`)
      console.log(`  ${DIM('skill_id:')} ${record.skill_id}`)
      console.log(`  ${DIM('tier:')} ${record.epistemic_tier}  ${DIM('vortex:')} ${vortexLabel(record.name.length)} (dr=${drLabel(record.name.length)})`)
      console.log(`  ${DIM('depth:')} ${depth_pips} ${res.resonance_depth}/4   ${DIM('coeff:')} ${res.resonance_coefficient.toFixed(3)}`)
      console.log(`  ${DIM('φ-head:')} ${bar(Math.max(res.phi_headroom, 0), PHI)} ${res.phi_headroom.toFixed(4)}`)
      console.log(`  ${DIM('network:')} LAN=${res.is_resonant ? '✓' : '✗'}  IP=${prop.ip_resonant ? '✓' : '✗'}  WWW=${prop.www_resonant ? '✓' : '✗'}  propagate=${prop.can_propagate ? GREEN('YES') : RED('NO')}`)

      try {
        const { catalog: next } = catalog.registerResonant(record)
        catalog = next
        admitted++
        console.log(`  ${GREEN('✓ ADMITTED')} — catalog size: ${catalog.size}`)
        catalogRecords.push({
          skill_id: record.skill_id,
          name: record.name,
          epistemic_tier: record.epistemic_tier,
          is_certified: res.is_certified,
          is_resonant: res.is_resonant,
          resonance_depth: res.resonance_depth,
          resonance_coefficient: res.resonance_coefficient,
          phi_headroom: res.phi_headroom,
          vortex_triadic: res.vortex_triadic,
          can_propagate: prop.can_propagate,
          skill_hash: record.skill_hash,
        })
      } catch (e: unknown) {
        rejected++
        const msg = e instanceof Error ? e.message : String(e)
        console.log(`  ${RED('✗ REJECTED')} — ${msg.slice(0, 80)}`)
      }
      console.log()
    }
  }

  // ── Summary ───────────────────────────────────────────────
  const catalogHash = await catalog.catalogHash()
  const cognitiveTriadPresent = COGNITIVE_TRIAD_IDS.every(id => catalog.lookup(id) !== null)

  console.log(BOLD('═══════════════════════════════════════════════════════'))
  console.log(BOLD('  Catalog Summary'))
  console.log(BOLD('═══════════════════════════════════════════════════════'))
  console.log(`  Admitted : ${GREEN(String(admitted))}`)
  console.log(`  Rejected : ${rejected > 0 ? RED(String(rejected)) : DIM(String(rejected))}`)
  console.log(`  Total    : ${catalog.size}`)
  console.log(`  Catalog hash : ${DIM(catalogHash.slice(0, 32))}...`)
  console.log(`  Cognitive Triad : ${cognitiveTriadPresent ? GREEN('ALL 3 PRESENT ✓') : RED('INCOMPLETE ✗')}`)
  console.log()

  if (cognitiveTriadPresent) {
    console.log(GREEN('  ✓ Constitutional sound floor established.'))
    console.log(GREEN('  ✓ Every swarm agent position can receive the 3 genesis seeds.'))
    console.log(DIM('    replay_sovereignty + hash_chain_seal + ring_harmony_verifier'))
  }
  console.log()

  if (outFile) {
    const out = {
      generated_at: new Date().toISOString(),
      catalog_hash: catalogHash,
      admitted,
      rejected,
      cognitive_triad_present: cognitiveTriadPresent,
      skills: catalogRecords,
    }
    writeFileSync(outFile, JSON.stringify(out, null, 2))
    console.log(DIM(`  Output written to ${outFile}`))
    console.log()
  }

  process.exit(rejected > 0 && admitted === 0 ? 1 : 0)
}

main().catch(err => {
  console.error(RED('FATAL:'), err)
  process.exit(1)
})
