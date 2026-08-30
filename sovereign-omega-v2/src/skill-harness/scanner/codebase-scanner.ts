// ============================================================
// Skill Harness — Codebase Auto-Scanner
// EPISTEMIC TIER: T2 (engineering hypothesis)
//
// Scans a codebase and produces constitutional SkillRecords
// from detected patterns. Skills are evidence-backed (file refs),
// not self-declared. Confidence derives from pattern frequency.
//
// Two modes:
//   structural — pure AST/file analysis, no API calls (fast)
//   deep       — constitutional AI-enhanced semantic extraction
// ============================================================

import fs from 'node:fs'
import path from 'node:path'
import { hashValue } from '../../core/hashing.js'
import type { SHA256Hex } from '../../core/types.js'
import type { SkillInput } from '../types.js'

export const SCANNER_SCHEMA_VERSION = '1.0.0' as const

export type PatternType =
  | 'component_pattern'
  | 'api_contract'
  | 'test_convention'
  | 'state_management'
  | 'data_pipeline'
  | 'infrastructure'
  | 'type_system'
  | 'algorithm'
  | 'governance_layer'
  | 'build_tooling'

export interface CodebasePattern {
  readonly pattern_id: string
  readonly pattern_type: PatternType
  readonly name: string
  readonly file_refs: readonly string[]      // relative paths that exhibit pattern
  readonly frequency: number                 // count of files
  readonly confidence: number               // frequency / total_files, capped at 0.95
  readonly skill_domain: readonly string[]  // maps to domain_affinity
  readonly constitutional_primitive: string // HASH/SEQUENCE/VERIFY/CANONICALIZE/FREEZE
  readonly evidence_summary: string         // one-line description of what was found
}

export interface ScanResult {
  readonly root_path: string
  readonly total_files: number
  readonly patterns: readonly CodebasePattern[]
  readonly scan_hash: SHA256Hex
  readonly schema_version: typeof SCANNER_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class ScannerError extends Error {
  override readonly name = 'ScannerError'
}

// ── File type → pattern domain mapping ───────────────────────────────────────

const EXT_DOMAINS: Record<string, { domains: string[]; primitive: string }> = {
  '.tsx': { domains: ['frontend', 'components', 'react'], primitive: 'CANONICALIZE' },
  '.jsx': { domains: ['frontend', 'components', 'react'], primitive: 'CANONICALIZE' },
  '.ts':  { domains: ['typescript', 'types', 'logic'],   primitive: 'SEQUENCE' },
  '.js':  { domains: ['javascript', 'scripting'],        primitive: 'SEQUENCE' },
  '.py':  { domains: ['python', 'inference', 'data'],    primitive: 'HASH' },
  '.rs':  { domains: ['rust', 'systems', 'performance'], primitive: 'VERIFY' },
  '.sql': { domains: ['database', 'queries'],            primitive: 'FREEZE' },
  '.json': { domains: ['config', 'schema'],              primitive: 'CANONICALIZE' },
  '.yaml': { domains: ['config', 'orchestration'],       primitive: 'SEQUENCE' },
  '.toml': { domains: ['config', 'rust', 'build'],      primitive: 'FREEZE' },
}

// ── Pattern detectors — structural analysis (no API required) ─────────────────

interface FileStat {
  rel: string
  ext: string
  content: string
  lines: number
}

function walkDir(root: string, rel = ''): FileStat[] {
  const results: FileStat[] = []
  const SKIP = new Set(['node_modules', '.git', 'dist', 'target', '.next', '__pycache__', 'coverage'])
  const absDir = path.join(root, rel)

  let entries: fs.Dirent[]
  try { entries = fs.readdirSync(absDir, { withFileTypes: true }) }
  catch { return results }

  for (const entry of entries) {
    if (SKIP.has(entry.name)) continue
    const relPath = rel ? `${rel}/${entry.name}` : entry.name
    if (entry.isDirectory()) {
      results.push(...walkDir(root, relPath))
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase()
      if (!EXT_DOMAINS[ext]) continue
      const absPath = path.join(absDir, entry.name)
      let content = ''
      try {
        const raw = fs.readFileSync(absPath, 'utf-8')
        content = raw.length > 32_000 ? raw.slice(0, 32_000) : raw
      } catch { continue }
      results.push({ rel: relPath, ext, content, lines: content.split('\n').length })
    }
  }
  return results
}

function detectPatterns(files: FileStat[]): CodebasePattern[] {
  const totalFiles = files.length
  const patterns: CodebasePattern[] = []

  // ── Component pattern (React/UI) ──
  const componentFiles = files.filter(f =>
    (f.ext === '.tsx' || f.ext === '.jsx') &&
    /export\s+(default\s+)?function\s+[A-Z]/.test(f.content)
  )
  if (componentFiles.length > 0) {
    const hooks = componentFiles.filter(f => /use[A-Z]\w+/.test(f.content))
    patterns.push({
      pattern_id: 'react_component_pattern',
      pattern_type: 'component_pattern',
      name: 'React Component Architecture',
      file_refs: componentFiles.map(f => f.rel),
      frequency: componentFiles.length,
      confidence: Math.min(0.95, componentFiles.length / Math.max(totalFiles, 1) * 8),
      skill_domain: ['frontend', 'react', hooks.length > 0 ? 'hooks' : 'components'],
      constitutional_primitive: 'CANONICALIZE',
      evidence_summary: `${componentFiles.length} components detected, ${hooks.length} use hooks`,
    })
  }

  // ── API contract (REST/fetch) ──
  const apiFiles = files.filter(f =>
    /fetch\s*\(|axios\.|\.get\(|\.post\(|@app\.route|FastAPI|express\(\)|router\.|@Controller/.test(f.content)
  )
  if (apiFiles.length > 0) {
    const restFiles = apiFiles.filter(f => /GET|POST|PUT|DELETE|PATCH/.test(f.content))
    patterns.push({
      pattern_id: 'api_contract_pattern',
      pattern_type: 'api_contract',
      name: 'API Contract Layer',
      file_refs: apiFiles.map(f => f.rel),
      frequency: apiFiles.length,
      confidence: Math.min(0.95, 0.5 + restFiles.length / Math.max(apiFiles.length, 1) * 0.45),
      skill_domain: ['api', 'http', 'integration'],
      constitutional_primitive: 'VERIFY',
      evidence_summary: `${apiFiles.length} API files, ${restFiles.length} with explicit HTTP methods`,
    })
  }

  // ── Test convention ──
  const testFiles = files.filter(f =>
    /\.test\.|\.spec\.|_test\.|test_/.test(f.rel) ||
    /describe\s*\(|it\s*\(|test\s*\(|#\[test\]|def test_/.test(f.content)
  )
  if (testFiles.length > 0) {
    const coverageRatio = testFiles.length / Math.max(files.filter(f => !f.rel.includes('test')).length, 1)
    patterns.push({
      pattern_id: 'test_convention_pattern',
      pattern_type: 'test_convention',
      name: 'Test Convention & Coverage',
      file_refs: testFiles.map(f => f.rel),
      frequency: testFiles.length,
      confidence: Math.min(0.95, 0.3 + coverageRatio * 2),
      skill_domain: ['testing', 'quality', 'determinism'],
      constitutional_primitive: 'VERIFY',
      evidence_summary: `${testFiles.length} test files, ${(coverageRatio * 100).toFixed(0)}% ratio vs source`,
    })
  }

  // ── State management ──
  const stateFiles = files.filter(f =>
    /useState|useReducer|createSlice|createStore|Zustand|MobX|Pinia|signal\(|atom\(|writable\(/.test(f.content)
  )
  if (stateFiles.length > 0) {
    patterns.push({
      pattern_id: 'state_management_pattern',
      pattern_type: 'state_management',
      name: 'State Management Architecture',
      file_refs: stateFiles.map(f => f.rel),
      frequency: stateFiles.length,
      confidence: Math.min(0.90, stateFiles.length / Math.max(totalFiles, 1) * 6),
      skill_domain: ['state', 'data-flow', 'reactivity'],
      constitutional_primitive: 'SEQUENCE',
      evidence_summary: `${stateFiles.length} files with state management primitives`,
    })
  }

  // ── Type system ──
  const typeFiles = files.filter(f =>
    f.ext === '.ts' && /^(export\s+)?(interface|type)\s+\w+/m.test(f.content)
  )
  if (typeFiles.length > 0) {
    const brandedTypes = typeFiles.filter(f => /declare\s+const.*brand|__brand|readonly.*tag/.test(f.content))
    patterns.push({
      pattern_id: 'type_system_pattern',
      pattern_type: 'type_system',
      name: 'TypeScript Type Architecture',
      file_refs: typeFiles.map(f => f.rel),
      frequency: typeFiles.length,
      confidence: Math.min(0.95, 0.6 + brandedTypes.length / Math.max(typeFiles.length, 1) * 0.35),
      skill_domain: ['typescript', 'types', 'safety'],
      constitutional_primitive: 'FREEZE',
      evidence_summary: `${typeFiles.length} type files, ${brandedTypes.length} with branded types`,
    })
  }

  // ── Governance / audit layer ──
  const govFiles = files.filter(f =>
    /replay|audit|hash.*chain|SHA.*256|constitutional|martingale|checkpoint|ledger/.test(f.content)
  )
  if (govFiles.length > 0) {
    patterns.push({
      pattern_id: 'governance_layer_pattern',
      pattern_type: 'governance_layer',
      name: 'Constitutional Governance Layer',
      file_refs: govFiles.map(f => f.rel),
      frequency: govFiles.length,
      confidence: Math.min(0.95, 0.7 + govFiles.length / Math.max(totalFiles, 1) * 3),
      skill_domain: ['governance', 'audit', 'constitutional', 'replay'],
      constitutional_primitive: 'HASH',
      evidence_summary: `${govFiles.length} files with governance/audit primitives`,
    })
  }

  // ── Infrastructure / build ──
  const infraFiles = files.filter(f =>
    /Dockerfile|docker-compose|vercel\.json|\.github|CI|pipeline|workflow|Makefile|build\.sh/.test(f.rel) ||
    /vite\.config|webpack\.config|rollup\.config|tsconfig/.test(f.rel)
  )
  if (infraFiles.length > 0) {
    patterns.push({
      pattern_id: 'build_tooling_pattern',
      pattern_type: 'build_tooling',
      name: 'Build & Infrastructure Tooling',
      file_refs: infraFiles.map(f => f.rel),
      frequency: infraFiles.length,
      confidence: Math.min(0.90, 0.5 + infraFiles.length / 5 * 0.4),
      skill_domain: ['devops', 'build', 'deployment'],
      constitutional_primitive: 'SEQUENCE',
      evidence_summary: `${infraFiles.length} infra/build files detected`,
    })
  }

  // ── Python data / inference ──
  const pyFiles = files.filter(f => f.ext === '.py')
  if (pyFiles.length > 0) {
    const mlFiles = pyFiles.filter(f => /numpy|torch|tensorflow|sklearn|pandas|inference|model/.test(f.content))
    patterns.push({
      pattern_id: 'python_data_pattern',
      pattern_type: 'data_pipeline',
      name: 'Python Data & Inference Pipeline',
      file_refs: pyFiles.map(f => f.rel),
      frequency: pyFiles.length,
      confidence: Math.min(0.90, 0.4 + mlFiles.length / Math.max(pyFiles.length, 1) * 0.55),
      skill_domain: ['python', 'data', 'inference', mlFiles.length > 0 ? 'ml' : 'scripting'],
      constitutional_primitive: 'HASH',
      evidence_summary: `${pyFiles.length} Python files, ${mlFiles.length} with ML/inference imports`,
    })
  }

  // ── Rust systems ──
  const rsFiles = files.filter(f => f.ext === '.rs')
  if (rsFiles.length > 0) {
    const unsafeFiles = rsFiles.filter(f => /unsafe\s*\{/.test(f.content))
    patterns.push({
      pattern_id: 'rust_systems_pattern',
      pattern_type: 'algorithm',
      name: 'Rust Systems Programming',
      file_refs: rsFiles.map(f => f.rel),
      frequency: rsFiles.length,
      confidence: Math.min(0.90, 0.65 + rsFiles.length / Math.max(totalFiles, 1) * 4),
      skill_domain: ['rust', 'systems', 'performance', 'safety'],
      constitutional_primitive: 'VERIFY',
      evidence_summary: `${rsFiles.length} Rust files, ${unsafeFiles.length} with unsafe blocks`,
    })
  }

  return patterns.filter(p => p.frequency > 0)
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function scanCodebase(rootPath: string): Promise<ScanResult> {
  if (!fs.existsSync(rootPath)) {
    throw new ScannerError(`Path does not exist: ${rootPath}`)
  }

  const files = walkDir(rootPath)
  if (files.length === 0) {
    throw new ScannerError(`No recognizable source files found under: ${rootPath}`)
  }

  const patterns = detectPatterns(files)

  const scan_hash = await hashValue({
    root_path: rootPath,
    total_files: files.length,
    pattern_ids: patterns.map(p => p.pattern_id).sort(),
    schema_version: SCANNER_SCHEMA_VERSION,
  }) as SHA256Hex

  return Object.freeze({
    root_path: rootPath,
    total_files: files.length,
    patterns: Object.freeze(patterns.map(p => Object.freeze(p))),
    scan_hash,
    schema_version: SCANNER_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

/** Convert a ScanResult pattern into a SkillInput ready for catalog admission */
export function patternToSkillInput(
  pattern: CodebasePattern,
  now = new Date().toISOString(),
): SkillInput {
  return {
    skill_id: pattern.pattern_id,
    name: pattern.name,
    confidence: pattern.confidence,
    validated_runs: pattern.frequency,
    failure_rate: 0,
    recency_score: 1.0,
    domain_affinity: pattern.skill_domain,
    dependencies: [],
    evidence_refs: pattern.file_refs.slice(0, 10) as string[],
    last_validated: now,
    epistemic_tier: 'T2',
    primitive_mapping: pattern.constitutional_primitive,
  }
}
