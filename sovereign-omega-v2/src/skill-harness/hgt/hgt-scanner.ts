// ============================================================
// Skill Harness — Horizontal Gene Transfer (HGT) Scanner
// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
//
// Cross-repo skill ingestion: scan upstream repositories for
// SKILL.md files, extract constitutional SkillRecords, build
// a replay-certifiable HGTRecord.
//
// Source-agnostic: caller provides file contents (GitHub API,
// local filesystem, any fetch mechanism). This module processes.
// ============================================================

import { hashValue } from '../../core/hashing.js'
import { deepFreeze } from '../../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../../core/types.js'
import { importSkillsFromManifests } from '../import.js'
import type { SkillRecord, RawSkillManifest } from '../types.js'

export const HGT_SCHEMA_VERSION = '1.0.0' as const

export interface HGTSourceConfig {
  readonly owner: string
  readonly repo: string
  readonly description: string
}

export interface HGTSkillFile {
  readonly repo_id: string      // 'owner/repo'
  readonly path: string         // e.g. 'skills/git/SKILL.md'
  readonly raw_content: string
}

export interface HGTScanResult {
  readonly repo_id: string
  readonly files_found: number
  readonly admitted: readonly SkillRecord[]
  readonly rejected: readonly { skill_id: string; reason: string }[]
  readonly source_hash: SHA256Hex   // hashValue({repo_id, file_paths_sorted})
  readonly is_replay_reconstructable: true
}

export interface HGTRecord {
  readonly sources_scanned: readonly string[]
  readonly total_files_found: number
  readonly total_admitted: number
  readonly total_rejected: number
  readonly catalog_hash: SHA256Hex
  readonly hgt_hash: SHA256Hex   // hashValue(all source_hashes + catalog_hash + sequence)
  readonly sequence: SequenceNumber
  readonly schema_version: typeof HGT_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class HGTError extends Error {
  override readonly name = 'HGTError'
}

// ── Process files from one repo ──────────────────────────────────────────────

export async function processRepoFiles(
  repo_id: string,
  files: readonly HGTSkillFile[],
): Promise<HGTScanResult> {
  if (files.length === 0) {
    const source_hash = await hashValue({ repo_id, file_paths: [] }) as SHA256Hex
    return deepFreeze({
      repo_id, files_found: 0,
      admitted: Object.freeze([]),
      rejected: Object.freeze([]),
      source_hash,
      is_replay_reconstructable: true as const,
    })
  }

  const manifests: RawSkillManifest[] = files.map(f => ({
    source: `github.com/${repo_id}`,
    path: f.path,
    content: f.raw_content,
  }))

  const result = await importSkillsFromManifests(manifests)

  const sorted_paths = files.map(f => f.path).slice().sort()
  const source_hash = await hashValue({ repo_id, file_paths: sorted_paths }) as SHA256Hex

  return deepFreeze({
    repo_id,
    files_found: files.length,
    admitted: result.admitted,
    rejected: result.rejected,
    source_hash,
    is_replay_reconstructable: true as const,
  })
}

// ── Build final HGT record from all scan results ─────────────────────────────

export async function buildHGTRecord(
  results: readonly HGTScanResult[],
  sequence: SequenceNumber,
): Promise<HGTRecord> {
  const sources_scanned = results.map(r => r.repo_id)
  const total_files_found = results.reduce((s, r) => s + r.files_found, 0)
  const total_admitted = results.reduce((s, r) => s + r.admitted.length, 0)
  const total_rejected = results.reduce((s, r) => s + r.rejected.length, 0)

  // Combine all admitted skills to compute catalog_hash
  const all_skill_hashes = results
    .flatMap(r => r.admitted.map(s => s.skill_hash))
    .slice()
    .sort()
  const catalog_hash = await hashValue({ skill_hashes: all_skill_hashes }) as SHA256Hex

  const source_hashes = results.map(r => r.source_hash).slice().sort()
  const hgt_hash = await hashValue({
    source_hashes,
    catalog_hash,
    total_admitted,
    total_rejected,
    sequence: sequence.toString(),
  }) as SHA256Hex

  return deepFreeze({
    sources_scanned: Object.freeze(sources_scanned),
    total_files_found,
    total_admitted,
    total_rejected,
    catalog_hash,
    hgt_hash,
    sequence,
    schema_version: HGT_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

// ── Parse GitHub API file tree to HGTSkillFile list ──────────────────────────

export interface GitHubTreeEntry {
  readonly path: string
  readonly type: string
  readonly url?: string
}

export function filterSkillFiles(tree: readonly GitHubTreeEntry[]): readonly string[] {
  return Object.freeze(
    tree
      .filter(e => e.type === 'blob' && /SKILL\.md$/i.test(e.path))
      .map(e => e.path)
  )
}
