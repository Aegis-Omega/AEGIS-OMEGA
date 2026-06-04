// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 21
// EPISTEMIC TIER: T0/T2
//
// Covers branch paths with zero prior coverage in:
//   skill-harness/scanner/codebase-scanner.ts
//     — SKIP.has() true branch (line 93): entry named 'node_modules'
//     — raw.length > 32_000 true branch (line 104): large file truncation
//     — hooks.length > 0 false branch (line 130): React component, no hooks
//     — mlFiles.length > 0 false branch (line 260): Python without ML imports
//   environment/kernel/capability_guard.ts
//     — CapabilityGuard constructor field initializers (lines 25-26)
// ============================================================

import { describe, it, expect, afterAll } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

// ── skill-harness/scanner — branch coverage extensions ───────────────────────

import { scanCodebase } from '../../src/skill-harness/scanner/codebase-scanner.js'

let tmpDir = ''

// Create a shared temp dir for all scanner tests in this batch
function setup(): void {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-cov21-'))
}

afterAll(() => {
  if (tmpDir) fs.rmSync(tmpDir, { recursive: true, force: true })
})

// ── line 93: SKIP.has() true branch ──────────────────────────────────────────
//
// walkDir iterates directory entries:
//   if (SKIP.has(entry.name)) continue    ← line 93 true branch
//
// Create a 'node_modules' directory (in SKIP set) inside the scan root.
// Also need at least one non-SKIP file so scanCodebase doesn't throw.

describe('scanCodebase walkDir — SKIP.has() true branch (line 93)', () => {
  it('silently skips SKIP directories like node_modules (covers line 93 true)', async () => {
    setup()
    // Directory that would be skipped (in SKIP set)
    fs.mkdirSync(path.join(tmpDir, 'node_modules'))
    // A non-SKIP Rust source file to ensure walkDir returns at least one file
    fs.writeFileSync(path.join(tmpDir, 'lib.rs'), 'pub fn add(a: i32, b: i32) -> i32 { a + b }\n')

    const result = await scanCodebase(tmpDir)

    // Scan succeeds — node_modules was skipped, lib.rs was processed
    expect(result.total_files).toBeGreaterThanOrEqual(1)
    // No file from node_modules should appear in file_refs of any pattern
    const allRefs = result.patterns.flatMap(p => p.file_refs)
    expect(allRefs.some(r => r.startsWith('node_modules/'))).toBe(false)
  })
})

// ── line 104: raw.length > 32_000 true branch — large file truncation ────────
//
// walkDir reads files:
//   content = raw.length > 32_000 ? raw.slice(0, 32_000) : raw   ← line 104 true
//
// Create a .rs file with 33,000+ characters to trigger the truncation path.

describe('scanCodebase walkDir — large file truncation (line 104 true)', () => {
  it('truncates files longer than 32_000 chars (covers line 104 true branch)', async () => {
    if (!tmpDir) setup()
    // 33,000-char Rust file (exceeds 32_000 threshold)
    const bigContent = '// big file\n' + 'pub fn noop() {}\n'.repeat(2000)
    expect(bigContent.length).toBeGreaterThan(32_000)

    const bigTmp = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-cov21-big-'))
    try {
      fs.writeFileSync(path.join(bigTmp, 'large.rs'), bigContent)
      const result = await scanCodebase(bigTmp)
      // File was processed (truncated but not thrown)
      expect(result.total_files).toBeGreaterThanOrEqual(1)
    } finally {
      fs.rmSync(bigTmp, { recursive: true, force: true })
    }
  })
})

// ── line 130: hooks.length > 0 false branch — React component without hooks ──
//
// detectPatterns() builds the React component pattern:
//   skill_domain: ['frontend', 'react', hooks.length > 0 ? 'hooks' : 'components']
//                                                            ↑ false branch: 'components'
//
// Create a TSX file with React/export-default content but NO hook imports.

describe('scanCodebase detectPatterns — React without hooks (line 130 false branch)', () => {
  it('uses "components" domain when React files have no hook imports (covers line 130 false)', async () => {
    const reactDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-cov21-react-'))
    try {
      // React component with no useState/useEffect/useCallback/useMemo/useRef/useContext
      fs.writeFileSync(
        path.join(reactDir, 'Button.tsx'),
        [
          'import React from "react"',
          'interface Props { label: string }',
          'export default function Button({ label }: Props) {',
          '  return <button>{label}</button>',
          '}',
        ].join('\n'),
      )

      const result = await scanCodebase(reactDir)
      const pattern = result.patterns.find(p => p.pattern_id === 'react_component_pattern')

      // React pattern detected; no hooks present → 'components' branch
      expect(pattern).toBeDefined()
      expect(pattern!.skill_domain).toContain('components')
      expect(pattern!.skill_domain).not.toContain('hooks')
    } finally {
      fs.rmSync(reactDir, { recursive: true, force: true })
    }
  })
})

// ── line 260: mlFiles.length > 0 false branch — Python without ML imports ────
//
// detectPatterns() builds the python_data_pattern:
//   skill_domain: ['python', 'data', 'inference', mlFiles.length > 0 ? 'ml' : 'scripting']
//                                                                         ↑ false: 'scripting'
//
// Create a directory with ONLY non-ML Python files so mlFiles.length === 0.
// The existing misc-coverage-10 test always has at least one ML Python file in the
// same tmpDir, so mlFiles.length is always > 0 there. Here we use a separate dir.

describe('scanCodebase detectPatterns — Python scripting branch (line 260 false)', () => {
  it('uses "scripting" domain when Python files have no ML imports (covers line 260 false)', async () => {
    const pyDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-cov21-py-'))
    try {
      // Pure Python data processing — no numpy/pandas/torch/sklearn/etc.
      fs.writeFileSync(
        path.join(pyDir, 'pipeline.py'),
        [
          'def process(data):',
          '    return [x * 2 for x in data]',
          '',
          'def main():',
          '    result = process([1, 2, 3])',
          '    print(result)',
        ].join('\n'),
      )
      fs.writeFileSync(
        path.join(pyDir, 'utils.py'),
        [
          'import json',
          'import os',
          '',
          'def load_config(path: str) -> dict:',
          '    with open(path) as f:',
          '        return json.load(f)',
        ].join('\n'),
      )

      const result = await scanCodebase(pyDir)
      const pattern = result.patterns.find(p => p.pattern_id === 'python_data_pattern')

      // Python pattern detected; no ML imports → 'scripting' branch
      expect(pattern).toBeDefined()
      expect(pattern!.skill_domain).toContain('scripting')
      expect(pattern!.skill_domain).not.toContain('ml')
    } finally {
      fs.rmSync(pyDir, { recursive: true, force: true })
    }
  })
})

// ── environment/kernel/capability_guard.ts lines 25-26 ───────────────────────
//
// Class field initializers execute when the constructor runs:
//   private readonly _capabilities: readonly HostCapability[] = []   ← line 25
//   private readonly _grants: readonly CapabilityGrant[] = []        ← line 26
//
// No existing test calls `new CapabilityGuard()` — the register() method uses
// Object.create() to construct instances without the constructor. A direct
// instantiation covers lines 25-26.

import { CapabilityGuard } from '../../src/environment/kernel/capability_guard.js'

describe('CapabilityGuard constructor — field initializers (lines 25-26)', () => {
  it('new CapabilityGuard() initializes _capabilities=[] and _grants=[] (covers lines 25-26)', () => {
    const guard = new CapabilityGuard()

    // Both field initializers executed — arrays start empty
    expect(guard.capabilities).toEqual([])
    expect(guard.grants).toEqual([])
  })

  it('fresh instance has zero capabilities and zero grants', () => {
    const g1 = new CapabilityGuard()
    const g2 = new CapabilityGuard()
    // Independent instances — field initializers run each time
    expect(g1.capabilities).toHaveLength(0)
    expect(g2.capabilities).toHaveLength(0)
  })
})
