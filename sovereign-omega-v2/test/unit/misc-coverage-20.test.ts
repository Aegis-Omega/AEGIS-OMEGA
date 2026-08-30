// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 20
// EPISTEMIC TIER: T0/T2
//
// Covers paths with zero prior coverage in:
//   core/wasm-interface.ts        — loadWasmKernel success path (line 69)
//   gate/mutation-governance.ts   — validateKBound if(m) false branch (line 50)
//   skill-harness/scanner/codebase-scanner.ts
//                                 — walkDir readdirSync catch→return (line 90)
//                                 — walkDir readFileSync catch→continue (line 105)
// ============================================================

import { describe, it, expect, vi, afterEach } from 'vitest'
import fs from 'node:fs'

// ── core/wasm-interface.ts line 69 — WASM load success path ──────────────────
//
// loadWasmKernel() tries WebAssembly.instantiateStreaming(fetch(wasmPath)).
// The try-success path (line 69) is never reached in tests because WASM is
// unavailable in jsdom. Mocking instantiateStreaming to resolve covers line 69.

import { loadWasmKernel, getWasmKernel } from '../../src/core/wasm-interface.js'

describe('loadWasmKernel — WASM instantiation success path (line 69)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sets _kernel.loaded=true when WebAssembly.instantiateStreaming resolves (covers line 69)', async () => {
    // Mock fetch to return anything (instantiateStreaming is mocked to ignore the response)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new Uint8Array()))

    // Mock WebAssembly.instantiateStreaming to simulate successful WASM load
    const fakeExports = { memory: new WebAssembly.Memory({ initial: 1 }) }
    vi.spyOn(WebAssembly, 'instantiateStreaming').mockResolvedValue({
      instance: { exports: fakeExports } as unknown as WebAssembly.Instance,
      module:   {} as WebAssembly.Module,
    })

    const kernel = await loadWasmKernel('/fake/kernel.wasm')

    // Line 69 executed: _kernel = { loaded: true, hash: null, exports: ... }
    expect(kernel.loaded).toBe(true)
    expect(kernel.hash).toBeNull()
    expect(getWasmKernel().loaded).toBe(true)
  })
})

// ── gate/mutation-governance.ts line 50 — if(m) false branch ─────────────────
//
// validateKBound iterates appliedMigrations for componentId:
//   const m = this.migrations.get(id)
//   if (m) currentK += m.delta_k   ← line 50
//
// When markApplied() records a migrationId that was never registered,
// migrations.get(id) returns undefined → the if(m) false branch is taken.

import { MutationGovernanceRegistry } from '../../src/gate/mutation-governance.js'
import { CapabilityClass } from '../../src/core/types.js'
import type { CapacityDeclaration, SHA256Hex } from '../../src/core/types.js'

const FAKE_HASH = '0'.repeat(64) as SHA256Hex

describe('MutationGovernanceRegistry.validateKBound — if(m) false branch (line 50)', () => {
  it('silently skips applied migration ids not in the registry (covers line 50 false)', () => {
    const reg = new MutationGovernanceRegistry()

    const cap: CapacityDeclaration = {
      component_id:           'test-comp',
      k_bound:                10,
      mutation_operators:     [],
      dependency_graph_hash:  FAKE_HASH,
      capability_class:       CapabilityClass.INFERENCE,
      epoch_duration_ms:      86_400_000,
      k_measurement_version:  '1.0.0',
    }
    reg.registerCapacity(cap)

    // Mark a migration applied that was NEVER registered → migrations.get() = undefined
    reg.markApplied('test-comp', 'ghost-migration-id')

    // validateKBound must complete without error; currentK stays 0 (ghost id skipped)
    expect(() => reg.validateKBound('test-comp', 0)).not.toThrow()

    // delta=10 equals k_bound=10 exactly → does not exceed → no throw
    expect(() => reg.validateKBound('test-comp', 10)).not.toThrow()
  })

  it('K_BOUND_EXCEEDED still throws after ghost-id skipped (covers line 50 false + line 52)', () => {
    const reg = new MutationGovernanceRegistry()
    const cap: CapacityDeclaration = {
      component_id:           'test-comp-2',
      k_bound:                5,
      mutation_operators:     [],
      dependency_graph_hash:  FAKE_HASH,
      capability_class:       CapabilityClass.SCHEMA_ONLY,
      epoch_duration_ms:      86_400_000,
      k_measurement_version:  '1.0.0',
    }
    reg.registerCapacity(cap)
    reg.markApplied('test-comp-2', 'ghost-id')

    // ghost-id skipped (currentK = 0), but delta = 6 > k_bound = 5 → throws
    expect(() => reg.validateKBound('test-comp-2', 6)).toThrow('K_BOUND_EXCEEDED_test-comp-2')
  })
})

// ── skill-harness/scanner/codebase-scanner.ts — walkDir error paths ───────────
//
// walkDir catches errors from the filesystem:
//   line 90:  catch { return results }   — when readdirSync throws
//   line 105: catch { continue }         — when readFileSync throws
//
// scanCodebase → walkDir(rootPath). If readdirSync throws, walkDir returns []
// and scanCodebase throws ScannerError('No recognizable source files found').
//
// For line 105, readdirSync returns a TypeScript file entry but readFileSync
// throws → the entry is skipped (continue), no files collected → ScannerError.

import { scanCodebase, ScannerError } from '../../src/skill-harness/scanner/codebase-scanner.js'
import os from 'node:os'
import nodePath from 'node:path'

describe('scanCodebase walkDir — readdirSync catch (line 90)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('covers line 90: readdirSync throws → walkDir returns [] → ScannerError', async () => {
    // existsSync must return true so scanCodebase doesn't throw before walkDir
    vi.spyOn(fs, 'existsSync').mockReturnValue(true)
    // readdirSync throws EACCES — walkDir catch block fires (line 90)
    vi.spyOn(fs, 'readdirSync').mockImplementation(() => {
      throw Object.assign(new Error('EACCES: permission denied'), { code: 'EACCES' })
    })

    await expect(scanCodebase('/fake/protected/dir')).rejects.toThrow(ScannerError)
    await expect(scanCodebase('/fake/protected/dir')).rejects.toThrow('No recognizable source files')
  })
})

describe('scanCodebase walkDir — readFileSync catch (line 105)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('covers line 105: readFileSync throws → file skipped → ScannerError (no files)', async () => {
    // Create a temp dir with a .ts file to ensure the directory entry is found
    const tmpDir = fs.mkdtempSync(nodePath.join(os.tmpdir(), 'aegis-cov20-'))
    fs.writeFileSync(nodePath.join(tmpDir, 'dummy.ts'), '')

    try {
      // readdirSync works normally (returns the real entry)
      // readFileSync throws when called → catch block at line 105 → continue
      vi.spyOn(fs, 'readFileSync').mockImplementation(() => {
        throw Object.assign(new Error('EACCES: cannot read file'), { code: 'EACCES' })
      })

      // All files fail to read → empty content list → ScannerError
      await expect(scanCodebase(tmpDir)).rejects.toThrow(ScannerError)
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true })
      vi.restoreAllMocks()
    }
  })
})
