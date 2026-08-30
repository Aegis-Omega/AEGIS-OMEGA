// ============================================================
// SOVEREIGN OMEGA — Miscellaneous Coverage Batch 9
// EPISTEMIC TIER: T0/T1
//
// Covers pure-function modules with zero prior test coverage:
//   core/ordering.ts          — compareUtf8, sortUtf8, sortObjectKeys
//   core/wasm-interface.ts    — assertWasmParity, getWasmKernel
//   extensions/contracts/contract.ts — createContract, expireContract, isContractActive
//   environment/workspace/introspection.ts — 6 pure functions
// ============================================================

import { describe, it, expect } from 'vitest'

// ── core/ordering.ts ────────────────────────────────────────

import {
  compareUtf8,
  sortUtf8,
  sortObjectKeys,
} from '../../src/core/ordering.js'

describe('compareUtf8', () => {
  it('equal strings return 0', () => {
    expect(compareUtf8('abc', 'abc')).toBe(0)
  })

  it('shorter string is less when it is a prefix of the longer', () => {
    expect(compareUtf8('ab', 'abc')).toBeLessThan(0)
    expect(compareUtf8('abc', 'ab')).toBeGreaterThan(0)
  })

  it('byte-wise ordering: "b" > "a"', () => {
    expect(compareUtf8('b', 'a')).toBeGreaterThan(0)
    expect(compareUtf8('a', 'b')).toBeLessThan(0)
  })

  it('empty string is less than any non-empty string', () => {
    expect(compareUtf8('', 'a')).toBeLessThan(0)
    expect(compareUtf8('a', '')).toBeGreaterThan(0)
  })

  it('two empty strings are equal', () => {
    expect(compareUtf8('', '')).toBe(0)
  })

  it('is deterministic — three calls with same args produce equal sign', () => {
    const r1 = compareUtf8('foo', 'bar')
    const r2 = compareUtf8('foo', 'bar')
    const r3 = compareUtf8('foo', 'bar')
    expect(Math.sign(r1)).toBe(Math.sign(r2))
    expect(Math.sign(r2)).toBe(Math.sign(r3))
  })
})

describe('sortUtf8', () => {
  it('sorts strings in byte-wise order', () => {
    const sorted = sortUtf8(['c', 'a', 'b'], x => x)
    expect(sorted).toEqual(['a', 'b', 'c'])
  })

  it('empty array returns empty array', () => {
    expect(sortUtf8([], x => x as string)).toEqual([])
  })

  it('single-element array is unchanged', () => {
    expect(sortUtf8(['x'], x => x)).toEqual(['x'])
  })

  it('does not mutate the original array', () => {
    const original = ['z', 'a', 'm']
    sortUtf8(original, x => x)
    expect(original).toEqual(['z', 'a', 'm'])
  })

  it('uses key function for comparison', () => {
    const items = [{ k: 'c' }, { k: 'a' }, { k: 'b' }]
    const sorted = sortUtf8(items, x => x.k)
    expect(sorted.map(i => i.k)).toEqual(['a', 'b', 'c'])
  })
})

describe('sortObjectKeys', () => {
  it('returns keys in byte-wise sorted order', () => {
    const keys = sortObjectKeys({ z: 1, a: 2, m: 3 })
    expect(keys).toEqual(['a', 'm', 'z'])
  })

  it('empty object returns empty array', () => {
    expect(sortObjectKeys({})).toEqual([])
  })

  it('single-key object returns that key', () => {
    expect(sortObjectKeys({ x: 1 })).toEqual(['x'])
  })

  it('is deterministic — three calls produce equal output', () => {
    const obj = { z: 1, a: 2, n: 3, b: 4 }
    const r1 = sortObjectKeys(obj)
    const r2 = sortObjectKeys(obj)
    const r3 = sortObjectKeys(obj)
    expect(r1).toEqual(r2)
    expect(r2).toEqual(r3)
  })
})

// ── core/wasm-interface.ts ──────────────────────────────────

import {
  assertWasmParity,
  getWasmKernel,
} from '../../src/core/wasm-interface.js'

describe('assertWasmParity', () => {
  it('does not throw when JS and WASM outputs match (Uint8Array)', () => {
    const bytes = new Uint8Array([0xab, 0xcd])
    expect(() => assertWasmParity(bytes, bytes, 'test-label')).not.toThrow()
  })

  it('does not throw when JS and WASM outputs match (hex strings)', () => {
    const hex = 'deadbeef'
    expect(() => assertWasmParity(hex, hex, 'test-label')).not.toThrow()
  })

  it('throws DETERMINISM_VIOLATION when outputs differ (strings)', () => {
    expect(() =>
      assertWasmParity('aaaa', 'bbbb', 'label')
    ).toThrow('DETERMINISM_VIOLATION')
  })

  it('throws DETERMINISM_VIOLATION when outputs differ (Uint8Array)', () => {
    const jsOut = new Uint8Array([0x01])
    const wasmOut = new Uint8Array([0x02])
    expect(() => assertWasmParity(jsOut, wasmOut, 'label')).toThrow('DETERMINISM_VIOLATION')
  })

  it('includes the label in the error message', () => {
    try {
      assertWasmParity('aa', 'bb', 'my-label')
    } catch (err) {
      expect((err as Error).message).toContain('my-label')
    }
  })
})

describe('getWasmKernel', () => {
  it('returns kernel with loaded=false before any WASM is loaded', () => {
    const kernel = getWasmKernel()
    expect(kernel.loaded).toBe(false)
  })

  it('initial kernel has null hash', () => {
    expect(getWasmKernel().hash).toBeNull()
  })

  it('initial kernel has null exports', () => {
    expect(getWasmKernel().exports).toBeNull()
  })
})

// ── extensions/contracts/contract.ts ───────────────────────

import {
  createContract,
  expireContract,
  isContractActive,
} from '../../src/extensions/contracts/contract.js'
import { PluginAdmissionError } from '../../src/extensions/types.js'

describe('createContract', () => {
  const baseParams = {
    plugin_id: 'plugin-a',
    capability_id: 'cap-read',
    granted_scope: ['scope-1', 'scope-2'],
    sequence_granted: 10,
    admissibility_reason: 'least-privilege read access granted',
  }

  it('returns a frozen contract with correct fields', () => {
    const c = createContract(baseParams)
    expect(Object.isFrozen(c)).toBe(true)
    expect(c.plugin_id).toBe('plugin-a')
    expect(c.capability_id).toBe('cap-read')
    expect(c.sequence_granted).toBe(10)
    expect(c.is_least_privilege).toBe(true)
    expect(c.admissibility_reason).toBe('least-privilege read access granted')
  })

  it('contract_id encodes plugin+capability+sequence', () => {
    const c = createContract(baseParams)
    expect(c.contract_id).toContain('plugin-a')
    expect(c.contract_id).toContain('cap-read')
    expect(c.contract_id).toContain('10')
  })

  it('granted_scope is frozen', () => {
    const c = createContract(baseParams)
    expect(Object.isFrozen(c.granted_scope)).toBe(true)
  })

  it('throws PluginAdmissionError when admissibility_reason is empty', () => {
    expect(() =>
      createContract({ ...baseParams, admissibility_reason: '' })
    ).toThrow(PluginAdmissionError)
  })
})

describe('expireContract', () => {
  it('returns a new contract with sequence_expires set', () => {
    const c = createContract({
      plugin_id: 'p1',
      capability_id: 'cap-x',
      granted_scope: [],
      sequence_granted: 5,
      admissibility_reason: 'reason',
    })
    const expired = expireContract(c, 20)
    expect(expired.sequence_expires).toBe(20)
    expect(Object.isFrozen(expired)).toBe(true)
  })

  it('throws PluginAdmissionError if contract already expired', () => {
    const c = createContract({
      plugin_id: 'p2',
      capability_id: 'cap-y',
      granted_scope: [],
      sequence_granted: 1,
      admissibility_reason: 'reason',
    })
    const expired = expireContract(c, 10)
    expect(() => expireContract(expired, 15)).toThrow(PluginAdmissionError)
  })
})

describe('isContractActive', () => {
  const c = createContract({
    plugin_id: 'p3',
    capability_id: 'cap-z',
    granted_scope: [],
    sequence_granted: 5,
    admissibility_reason: 'reason',
  })

  it('returns true when atSequence >= sequence_granted and no expiry', () => {
    expect(isContractActive(c, 5)).toBe(true)
    expect(isContractActive(c, 100)).toBe(true)
  })

  it('returns false when atSequence < sequence_granted', () => {
    expect(isContractActive(c, 4)).toBe(false)
  })

  it('returns false after expiry sequence', () => {
    const expired = expireContract(c, 20)
    expect(isContractActive(expired, 20)).toBe(false)
    expect(isContractActive(expired, 19)).toBe(true)
    expect(isContractActive(expired, 5)).toBe(true)
  })
})

// ── environment/workspace/introspection.ts ──────────────────

import {
  canonicalizePath,
  deterministicWorkspaceId,
  deterministicPathId,
  detectInstallationContext,
  buildGovernedPath,
  buildGovernedWorkspace,
} from '../../src/environment/workspace/introspection.js'

describe('canonicalizePath', () => {
  it('normalizes backslashes to forward slashes', () => {
    expect(canonicalizePath('C:\\foo\\bar')).toBe('C:/foo/bar')
  })

  it('collapses repeated slashes', () => {
    expect(canonicalizePath('a//b///c')).toBe('a/b/c')
  })

  it('removes trailing slash', () => {
    expect(canonicalizePath('/foo/bar/')).toBe('/foo/bar')
  })

  it('removes trailing /. segment', () => {
    expect(canonicalizePath('/foo/.')).toBe('/foo')
  })

  it('normalizes /./ in path', () => {
    expect(canonicalizePath('/foo/./bar')).toBe('/foo/bar')
  })

  it('returns "/" for empty string', () => {
    expect(canonicalizePath('')).toBe('/')
  })

  it('is deterministic — three calls produce equal output', () => {
    const r1 = canonicalizePath('a//b/./c/')
    const r2 = canonicalizePath('a//b/./c/')
    const r3 = canonicalizePath('a//b/./c/')
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })
})

describe('deterministicWorkspaceId', () => {
  it('returns a string starting with "ws_"', () => {
    expect(deterministicWorkspaceId('/repo')).toMatch(/^ws_[0-9a-f]{8}$/)
  })

  it('same path → same id', () => {
    expect(deterministicWorkspaceId('/repo')).toBe(deterministicWorkspaceId('/repo'))
  })

  it('different paths → different ids', () => {
    expect(deterministicWorkspaceId('/a')).not.toBe(deterministicWorkspaceId('/b'))
  })
})

describe('deterministicPathId', () => {
  it('returns a string starting with "path_"', () => {
    expect(deterministicPathId('/src/foo.ts')).toMatch(/^path_[0-9a-f]{8}$/)
  })

  it('is deterministic', () => {
    const a = deterministicPathId('/src/foo.ts')
    const b = deterministicPathId('/src/foo.ts')
    expect(a).toBe(b)
  })
})

describe('detectInstallationContext', () => {
  it('detects monorepo when package.json + packages present', () => {
    expect(detectInstallationContext(['package.json', 'packages', 'src'])).toBe('monorepo')
  })

  it('detects ci-environment when .github present', () => {
    expect(detectInstallationContext(['.github', 'README.md'])).toBe('ci-environment')
  })

  it('detects container when Dockerfile present', () => {
    expect(detectInstallationContext(['Dockerfile', 'src'])).toBe('container')
  })

  it('detects standalone when package.json present without packages', () => {
    expect(detectInstallationContext(['package.json', 'src'])).toBe('standalone')
  })

  it('returns development when no known markers present', () => {
    expect(detectInstallationContext(['foo.txt', 'bar.md'])).toBe('development')
  })
})

describe('buildGovernedPath', () => {
  it('returns a frozen governed path with canonicalized path', () => {
    const gp = buildGovernedPath('/src//foo/', 'read-only', false)
    expect(Object.isFrozen(gp)).toBe(true)
    expect(gp.canonical_path).toBe('/src/foo')
    expect(gp.access_class).toBe('read-only')
    expect(gp.is_constitutional).toBe(false)
    expect(gp.path_id).toMatch(/^path_[0-9a-f]{8}$/)
  })

  it('constitutional flag is preserved', () => {
    const gp = buildGovernedPath('/gate.py', 'governed-write', true)
    expect(gp.is_constitutional).toBe(true)
  })
})

describe('buildGovernedWorkspace', () => {
  it('returns a frozen workspace with correct fields', () => {
    const gp = buildGovernedPath('/src', 'read-only', false)
    const ws = buildGovernedWorkspace({
      canonicalRoot: '/repo',
      installationContext: 'standalone',
      governedPaths: [gp],
      activeCapabilityIds: ['cap-a'],
    })
    expect(Object.isFrozen(ws)).toBe(true)
    expect(ws.canonical_root).toBe('/repo')
    expect(ws.installation_context).toBe('standalone')
    expect(ws.governed_paths).toHaveLength(1)
    expect(ws.active_capability_ids).toContain('cap-a')
    expect(ws.workspace_id).toMatch(/^ws_[0-9a-f]{8}$/)
  })
})
