// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 14
// EPISTEMIC TIER: T0/T2
//
// Covers patterns with zero prior coverage in:
//   skill-harness/scanner/codebase-scanner.ts
//     — react_component_pattern, api_contract_pattern,
//       test_convention_pattern, state_management_pattern,
//       type_system_pattern, governance_layer_pattern,
//       build_tooling_pattern, ScannerError (non-existent path)
//   skill-harness/import.ts — constitutional domain detection
// ============================================================

import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

// ── codebase-scanner.ts — multi-pattern coverage ──────────────

import {
  scanCodebase,
} from '../../src/skill-harness/scanner/codebase-scanner.js'

let scanDir = ''

beforeAll(() => {
  scanDir = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-scanner-cov14-'))

  // React component pattern: .tsx file with exported React component + hook
  fs.writeFileSync(
    path.join(scanDir, 'Widget.tsx'),
    'import React from "react";\nexport default function Widget() { const [x] = useState(0); return <div>{x}</div>; }\n',
  )
  fs.writeFileSync(
    path.join(scanDir, 'Button.tsx'),
    'export function Button({ label }: { label: string }) { return <button>{label}</button>; }\n',
  )

  // API contract pattern: .ts file with fetch calls and HTTP methods
  fs.writeFileSync(
    path.join(scanDir, 'api.ts'),
    'export async function getData() { const r = await fetch("/api/data"); return r.json(); /* GET POST */ }\n',
  )

  // Test convention pattern: .test.ts file with describe/it
  fs.writeFileSync(
    path.join(scanDir, 'util.test.ts'),
    'import { describe, it, expect } from "vitest";\ndescribe("util", () => { it("works", () => { expect(1).toBe(1); }); });\n',
  )

  // State management pattern: file using useState/createStore
  fs.writeFileSync(
    path.join(scanDir, 'store.ts'),
    'import { createStore } from "redux";\nconst store = createStore((s = {}) => s);\n',
  )

  // Type system pattern: .ts file with interface/type exports
  fs.writeFileSync(
    path.join(scanDir, 'types.ts'),
    'export interface UserProfile { readonly id: string; readonly name: string; }\nexport type Status = "active" | "inactive";\n',
  )

  // Governance layer pattern: .ts file with audit/hash-chain/replay keywords
  fs.writeFileSync(
    path.join(scanDir, 'audit.ts'),
    '// SHA-256 hash chain replay audit constitutional martingale checkpoint ledger\nexport function verifyChain() { return true; }\n',
  )

  // Build tooling pattern: vite.config.ts (matches vite\.config in path)
  fs.writeFileSync(
    path.join(scanDir, 'vite.config.ts'),
    'export default { build: { target: "es2022" } };\n',
  )
})

afterAll(() => {
  if (scanDir) fs.rmSync(scanDir, { recursive: true, force: true })
})

describe('scanCodebase — react_component_pattern', () => {
  it('detects react_component_pattern when .tsx files with components exist', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'react_component_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('component_pattern')
    expect(pattern!.frequency).toBeGreaterThanOrEqual(1)
  })

  it('react_component_pattern skill_domain includes "hooks" when useX calls detected', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'react_component_pattern')
    expect(pattern!.skill_domain).toContain('hooks')
  })
})

describe('scanCodebase — api_contract_pattern', () => {
  it('detects api_contract_pattern when fetch/axios calls exist', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'api_contract_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('api_contract')
  })

  it('api_contract_pattern evidence_summary mentions HTTP files', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'api_contract_pattern')
    expect(pattern!.evidence_summary).toMatch(/API file/)
  })
})

describe('scanCodebase — test_convention_pattern', () => {
  it('detects test_convention_pattern when .test.ts files exist', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'test_convention_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('test_convention')
  })
})

describe('scanCodebase — state_management_pattern', () => {
  it('detects state_management_pattern when createStore/useState used', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'state_management_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('state_management')
  })
})

describe('scanCodebase — type_system_pattern', () => {
  it('detects type_system_pattern when .ts files have interface/type exports', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'type_system_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('type_system')
  })
})

describe('scanCodebase — governance_layer_pattern', () => {
  it('detects governance_layer_pattern when constitutional/audit terms present', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'governance_layer_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('governance_layer')
    expect(pattern!.skill_domain).toContain('governance')
  })
})

describe('scanCodebase — build_tooling_pattern', () => {
  it('detects build_tooling_pattern when vite.config.ts file is present', async () => {
    const result = await scanCodebase(scanDir)
    const pattern = result.patterns.find(p => p.pattern_id === 'build_tooling_pattern')
    expect(pattern).toBeDefined()
    expect(pattern!.pattern_type).toBe('build_tooling')
  })
})

describe('scanCodebase — ScannerError on non-existent path', () => {
  it('throws ScannerError when rootPath does not exist', async () => {
    const { ScannerError } = await import('../../src/skill-harness/scanner/codebase-scanner.js')
    await expect(scanCodebase('/nonexistent-path-cov14-xyz')).rejects.toThrow(ScannerError)
  })
})

// ── skill-harness/import.ts — constitutional domain detection ──

import { assignDomainAffinity } from '../../src/skill-harness/import.js'

describe('assignDomainAffinity — constitutional domain', () => {
  it('returns ["constitutional"] when name contains "replay"', () => {
    const domains = assignDomainAffinity('Replay Auditor', 'Verifies replay integrity')
    expect(domains).toContain('constitutional')
  })

  it('returns ["constitutional"] when description contains "lineage"', () => {
    const domains = assignDomainAffinity('Chain Tracker', 'Tracks lineage of governance events')
    expect(domains).toContain('constitutional')
  })

  it('returns ["constitutional"] when description contains "constitutional"', () => {
    const domains = assignDomainAffinity('Policy Enforcer', 'Enforces constitutional invariants')
    expect(domains).toContain('constitutional')
  })
})
