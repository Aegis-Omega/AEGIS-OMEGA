// ============================================================
// SOVEREIGN OMEGA — Codebase Scanner tests
// EPISTEMIC TIER: T2
//
// Tests for skill-harness/scanner/codebase-scanner.ts:
//   ScannerError         — error subclass
//   scanCodebase         — throws, returns ScanResult, detects patterns
//   patternToSkillInput  — field mapping, evidence_refs slice
// ============================================================

import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import {
  ScannerError,
  scanCodebase,
  patternToSkillInput,
  SCANNER_SCHEMA_VERSION,
} from '../../src/skill-harness/scanner/codebase-scanner.js'
import type { CodebasePattern } from '../../src/skill-harness/scanner/codebase-scanner.js'

// ── ScannerError ──────────────────────────────────────────

describe('ScannerError', () => {
  it('is an Error subclass with correct name and message', () => {
    const e = new ScannerError('test message')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('ScannerError')
    expect(e.message).toBe('test message')
  })
})

// ── scanCodebase — filesystem-driven tests ────────────────

let tmpDir = ''

beforeAll(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-scanner-'))
  fs.mkdirSync(path.join(tmpDir, 'src'), { recursive: true })
  // TypeScript type declarations → triggers type_system_pattern
  fs.writeFileSync(
    path.join(tmpDir, 'src', 'types.ts'),
    'export interface MyType { x: number }\nexport type Alias = string\n',
  )
  // React TSX component → triggers react_component_pattern + hooks
  fs.writeFileSync(
    path.join(tmpDir, 'src', 'App.tsx'),
    "import { useState } from 'react'\nexport function App() { const [x] = useState(0); return null }\n",
  )
  // Test file by name → triggers test_convention_pattern
  fs.writeFileSync(
    path.join(tmpDir, 'src', 'app.test.ts'),
    "describe('App', () => { it('works', () => {}) })\n",
  )
})

afterAll(() => {
  if (tmpDir) fs.rmSync(tmpDir, { recursive: true, force: true })
})

describe('scanCodebase', () => {
  it('throws ScannerError when path does not exist', async () => {
    await expect(scanCodebase('/nonexistent/path/___xyz___')).rejects.toThrow(ScannerError)
  })

  it('throws ScannerError when directory has no recognizable source files', async () => {
    const emptyDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-empty-'))
    fs.writeFileSync(path.join(emptyDir, 'README.md'), '# readme\n')
    try {
      await expect(scanCodebase(emptyDir)).rejects.toThrow(ScannerError)
    } finally {
      fs.rmSync(emptyDir, { recursive: true, force: true })
    }
  })

  it('returns frozen ScanResult with correct metadata fields', async () => {
    const result = await scanCodebase(tmpDir)
    expect(Object.isFrozen(result)).toBe(true)
    expect(result.root_path).toBe(tmpDir)
    expect(result.schema_version).toBe(SCANNER_SCHEMA_VERSION)
    expect(result.is_replay_reconstructable).toBe(true)
    expect(result.total_files).toBe(3)
  })

  it('scan_hash is a 64-char hex string', async () => {
    const result = await scanCodebase(tmpDir)
    expect(result.scan_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('scan_hash is deterministic — three scans of the same directory agree', async () => {
    const [r1, r2, r3] = await Promise.all([
      scanCodebase(tmpDir),
      scanCodebase(tmpDir),
      scanCodebase(tmpDir),
    ])
    expect(r1.scan_hash).toBe(r2.scan_hash)
    expect(r2.scan_hash).toBe(r3.scan_hash)
  })

  it('detects type_system_pattern from TypeScript interface/type declarations', async () => {
    const result = await scanCodebase(tmpDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'type_system_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('type_system')
    expect(pattern!.constitutional_primitive).toBe('FREEZE')
    expect(pattern!.frequency).toBeGreaterThan(0)
  })

  it('detects react_component_pattern from TSX files with exported functions', async () => {
    const result = await scanCodebase(tmpDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'react_component_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.constitutional_primitive).toBe('CANONICALIZE')
    expect(pattern!.evidence_summary).toContain('hooks')
  })

  it('detects test_convention_pattern from .test. file names', async () => {
    const result = await scanCodebase(tmpDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'test_convention_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('test_convention')
  })

  it('patterns array and individual patterns are frozen', async () => {
    const result = await scanCodebase(tmpDir)
    expect(Object.isFrozen(result.patterns)).toBe(true)
    for (const p of result.patterns) {
      expect(Object.isFrozen(p)).toBe(true)
    }
  })
})

// ── patternToSkillInput ────────────────────────────────────

const SAMPLE_PATTERN: CodebasePattern = {
  pattern_id: 'governance_layer_pattern',
  pattern_type: 'governance_layer',
  name: 'Constitutional Governance Layer',
  file_refs: Array.from({ length: 15 }, (_, i) => `gov${i}.ts`),
  frequency: 15,
  confidence: 0.85,
  skill_domain: ['governance', 'audit'],
  constitutional_primitive: 'HASH',
  evidence_summary: '15 governance files found',
}

describe('patternToSkillInput', () => {
  it('maps pattern fields to SkillInput correctly', () => {
    const input = patternToSkillInput(SAMPLE_PATTERN, '2024-01-01T00:00:00.000Z')
    expect(input.skill_id).toBe('governance_layer_pattern')
    expect(input.name).toBe('Constitutional Governance Layer')
    expect(input.confidence).toBe(0.85)
    expect(input.validated_runs).toBe(15)
    expect(input.failure_rate).toBe(0)
    expect(input.recency_score).toBe(1.0)
    expect(input.domain_affinity).toEqual(['governance', 'audit'])
    expect(input.dependencies).toEqual([])
    expect(input.epistemic_tier).toBe('T2')
    expect(input.primitive_mapping).toBe('HASH')
  })

  it('slices evidence_refs to at most 10 items when file_refs has more', () => {
    const input = patternToSkillInput(SAMPLE_PATTERN)
    expect(input.evidence_refs).toHaveLength(10)
  })

  it('uses the provided now parameter for last_validated', () => {
    const now = '2025-06-15T12:00:00.000Z'
    const input = patternToSkillInput(SAMPLE_PATTERN, now)
    expect(input.last_validated).toBe(now)
  })
})
