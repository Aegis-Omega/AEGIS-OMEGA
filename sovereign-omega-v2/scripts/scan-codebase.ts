#!/usr/bin/env tsx
/**
 * AEGIS Codebase Auto-Scanner
 * Usage: npx tsx scripts/scan-codebase.ts [--path <dir>] [--out <file>]
 *
 * Scans a codebase and produces a SkillCatalog JSON from detected patterns.
 * No API calls required — pure structural analysis.
 *
 * Example:
 *   npx tsx scripts/scan-codebase.ts --path ../cockpit
 *   npx tsx scripts/scan-codebase.ts --path /home/user/myapp --out skills.json
 */

import path from 'node:path'
import fs from 'node:fs'
import { scanCodebase, patternToSkillInput } from '../src/skill-harness/scanner/codebase-scanner.js'
import { SkillCatalog, buildSkillRecord } from '../src/skill-harness/catalog.js'

const args = process.argv.slice(2)
const pathArg = args[args.indexOf('--path') + 1] ?? '.'
const outArg  = args[args.indexOf('--out')  + 1] ?? null

const rootPath = path.resolve(pathArg)

console.log(`\nAEGIS Skill Scanner — scanning: ${rootPath}\n`)

try {
  const result = await scanCodebase(rootPath)

  console.log(`Files scanned:     ${result.total_files}`)
  console.log(`Patterns detected: ${result.patterns.length}`)
  console.log(`Scan hash:         ${result.scan_hash.slice(0, 16)}…\n`)

  let catalog = SkillCatalog.empty()
  const admitted: string[] = []
  const rejected: string[] = []

  for (const pattern of result.patterns) {
    const input = patternToSkillInput(pattern)
    const record = await buildSkillRecord(input)
    try {
      const { catalog: next } = catalog.register(record)
      catalog = next
      admitted.push(pattern.pattern_id)
      const bar = '█'.repeat(Math.round(pattern.confidence * 20)).padEnd(20, '░')
      console.log(`  ✓ ${pattern.pattern_id.padEnd(30)} [${bar}] ${(pattern.confidence * 100).toFixed(0)}%`)
      console.log(`    ${pattern.evidence_summary}`)
    } catch (e) {
      rejected.push(pattern.pattern_id)
      console.log(`  ✗ ${pattern.pattern_id} — ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const catalogHashVal = await catalog.catalogHash()
  console.log(`\nCatalog: ${admitted.length} skills admitted, ${rejected.length} rejected`)
  console.log(`Catalog hash: ${catalogHashVal.slice(0, 16)}…`)

  const output = {
    scan_hash: result.scan_hash,
    root_path: result.root_path,
    total_files: result.total_files,
    catalog_hash: catalogHashVal,
    skills: catalog.getAll(),
    scanned_at: new Date().toISOString(),
    schema_version: result.schema_version,
    is_replay_reconstructable: true,
  }

  if (outArg) {
    const outPath = path.resolve(outArg)
    fs.writeFileSync(outPath, JSON.stringify(output, null, 2))
    console.log(`\nSaved to: ${outPath}`)
  } else {
    console.log('\n' + JSON.stringify(output, null, 2))
  }

} catch (e) {
  console.error(`\nScan failed: ${e instanceof Error ? e.message : String(e)}`)
  process.exit(1)
}
