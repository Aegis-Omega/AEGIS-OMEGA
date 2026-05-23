#!/usr/bin/env tsx
/**
 * AEGIS Horizontal Gene Transfer (HGT) Scanner
 * Usage: npx tsx scripts/hgt-scan.ts [--out <file>] [--token <github-token>]
 *
 * Scans upstream skill repositories for SKILL.md files via GitHub public API.
 * Converts detected skills into constitutional SkillRecords.
 * Produces a replay-certifiable HGTRecord.
 *
 * No auth required for public repos (60 req/hr unauthenticated, 5000/hr with token).
 *
 * Example:
 *   npx tsx scripts/hgt-scan.ts
 *   npx tsx scripts/hgt-scan.ts --out skills-hgt.json
 *   npx tsx scripts/hgt-scan.ts --token ghp_yourtoken --out skills-hgt.json
 */

import fs from 'node:fs'
import path from 'node:path'
import {
  processRepoFiles,
  buildHGTRecord,
  filterSkillFiles,
  type HGTSourceConfig,
  type HGTSkillFile,
  type GitHubTreeEntry,
} from '../src/skill-harness/hgt/hgt-scanner.js'

const args = process.argv.slice(2)
const outArg = args[args.indexOf('--out') + 1] ?? null
const tokenArg = args[args.indexOf('--token') + 1] ?? process.env['GITHUB_TOKEN'] ?? null

const SEQ = 1n as import('../src/core/types.js').SequenceNumber

const SOURCES: readonly HGTSourceConfig[] = [
  { owner: 'obra', repo: 'superpowers', description: 'Developer superpowers skill pack' },
  { owner: 'glittercowboy', repo: 'get-shit-done', description: 'Productivity workflow skills' },
  { owner: 'nextlevelbuilder', repo: 'ui-ux-pro-max-skill', description: 'UI/UX pro skills' },
  { owner: 'kepano', repo: 'obsidian-skills', description: 'Knowledge management skills' },
  { owner: '0xdesign', repo: 'design-plugin', description: 'Design workflow skills' },
]

const GITHUB_BASE = 'https://api.github.com'

function makeHeaders(): HeadersInit {
  const h: Record<string, string> = { 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' }
  if (tokenArg) h['Authorization'] = `Bearer ${tokenArg}`
  return h
}

async function getRepoTree(owner: string, repo: string): Promise<readonly GitHubTreeEntry[]> {
  const url = `${GITHUB_BASE}/repos/${owner}/${repo}/git/trees/HEAD?recursive=1`
  const res = await fetch(url, { headers: makeHeaders() })
  if (!res.ok) {
    if (res.status === 404) throw new Error(`repo not found: ${owner}/${repo}`)
    if (res.status === 403 || res.status === 429) throw new Error(`rate limited — use --token`)
    throw new Error(`GitHub API ${res.status}: ${owner}/${repo}`)
  }
  const data = await res.json() as { tree?: GitHubTreeEntry[] }
  return Object.freeze(data.tree ?? [])
}

async function getFileContent(owner: string, repo: string, filePath: string): Promise<string> {
  const url = `${GITHUB_BASE}/repos/${owner}/${repo}/contents/${encodeURIComponent(filePath)}`
  const res = await fetch(url, { headers: makeHeaders() })
  if (!res.ok) throw new Error(`cannot fetch ${filePath}: HTTP ${res.status}`)
  const data = await res.json() as { content?: string; encoding?: string }
  if (data.encoding === 'base64' && data.content) {
    return Buffer.from(data.content, 'base64').toString('utf-8')
  }
  throw new Error(`unexpected encoding: ${data.encoding}`)
}

async function scanRepo(source: HGTSourceConfig): Promise<{ repoId: string; files: readonly HGTSkillFile[] }> {
  const repoId = `${source.owner}/${source.repo}`
  try {
    console.log(`  Scanning ${repoId}...`)
    const tree = await getRepoTree(source.owner, source.repo)
    const skillPaths = filterSkillFiles(tree)
    console.log(`    Found ${skillPaths.length} SKILL.md files`)

    const files: HGTSkillFile[] = []
    for (const p of skillPaths) {
      try {
        const content = await getFileContent(source.owner, source.repo, p)
        files.push({ repo_id: repoId, path: p, raw_content: content })
      } catch (e) {
        console.log(`    ✗ ${p}: ${e instanceof Error ? e.message : String(e)}`)
      }
    }
    return { repoId, files: Object.freeze(files) }
  } catch (e) {
    console.log(`    ✗ ${repoId}: ${e instanceof Error ? e.message : String(e)}`)
    return { repoId, files: Object.freeze([]) }
  }
}

console.log('\nAEGIS HGT Scanner — cross-repo skill ingestion\n')
if (tokenArg) console.log(`Auth: GitHub token (5000 req/hr)\n`)
else console.log(`Auth: none (60 req/hr — pass --token to increase)\n`)

const allScanResults = []
let grandAdmitted = 0
let grandRejected = 0

for (const source of SOURCES) {
  const { repoId, files } = await scanRepo(source)
  const result = await processRepoFiles(repoId, files)
  allScanResults.push(result)

  grandAdmitted += result.admitted.length
  grandRejected += result.rejected.length

  for (const skill of result.admitted) {
    const bar = '█'.repeat(Math.round(skill.confidence * 20)).padEnd(20, '░')
    console.log(`    ✓ ${skill.skill_id.padEnd(35)} [${bar}] ${(skill.confidence * 100).toFixed(0)}%`)
  }
  for (const rej of result.rejected) {
    console.log(`    ✗ ${rej.skill_id} — ${rej.reason}`)
  }
}

const hgtRecord = await buildHGTRecord(allScanResults, SEQ)

console.log(`\n${'─'.repeat(60)}`)
console.log(`Repos scanned:  ${SOURCES.length}`)
console.log(`Skills admitted: ${grandAdmitted}`)
console.log(`Skills rejected: ${grandRejected}`)
console.log(`Catalog hash:   ${hgtRecord.catalog_hash.slice(0, 16)}…`)
console.log(`HGT hash:       ${hgtRecord.hgt_hash.slice(0, 16)}…`)

const output = {
  sources_scanned: hgtRecord.sources_scanned,
  total_files_found: hgtRecord.total_files_found,
  total_admitted: hgtRecord.total_admitted,
  total_rejected: hgtRecord.total_rejected,
  catalog_hash: hgtRecord.catalog_hash,
  hgt_hash: hgtRecord.hgt_hash,
  sequence: hgtRecord.sequence.toString(),
  schema_version: hgtRecord.schema_version,
  is_replay_reconstructable: true,
  scanned_at: new Date().toISOString(),
  skills: allScanResults.flatMap(r => r.admitted),
}

if (outArg) {
  const outPath = path.resolve(outArg)
  fs.writeFileSync(outPath, JSON.stringify(output, null, 2))
  console.log(`\nSaved to: ${outPath}`)
} else {
  console.log('\n' + JSON.stringify(output, null, 2))
}
