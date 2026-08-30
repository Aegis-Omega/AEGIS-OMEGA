// ============================================================
// Extension / Plugin Habitat Tests
// Gate 10: sandbox isolation, replay-safe plugin execution,
//   capability boundary enforcement, plugin entropy accounting,
//   extension determinism validation
// ============================================================

import { describe, it, expect } from 'vitest'
import { EpistemicTier } from '../../src/core/types'
import type { PluginManifest, CapabilityContract, MutationReceipt } from '../../src/extensions/types'
import {
  PluginAdmissionError,
  SandboxViolationError,
  PLUGIN_MANIFEST_SCHEMA_VERSION,
} from '../../src/extensions/types'
import { ExtensionRegistry } from '../../src/extensions/registry/registry'
import {
  createSandbox,
  checkSandboxAllows,
  recordMutation,
  computeSandboxEntropyRatio,
} from '../../src/extensions/sandbox/sandbox'
import {
  createContract,
  expireContract,
  isContractActive,
} from '../../src/extensions/contracts/contract'

// ─── Test helpers ──────────────────────────────────────────

const FIXED_SCALE = 65536  // Q16.16

function makeManifest(overrides: Partial<PluginManifest> = {}): PluginManifest {
  return {
    schema_version: PLUGIN_MANIFEST_SCHEMA_VERSION,
    plugin_id: 'test-plugin-01',
    name: 'Test Plugin',
    version: '1.0.0',
    epistemic_tier: EpistemicTier.T2,
    capability_requests: [{ capability_class: 'telemetry', scope: ['/telemetry'], justification: 'read metrics' }],
    ontology_terms_used: ['plugin_telemetry'],
    is_replay_safe: true,
    entropy_budget_fixed: 10 * FIXED_SCALE,
    status: 'admitted' as const,
    ...overrides,
  }
}

function makeContract(overrides: Partial<CapabilityContract> = {}): CapabilityContract {
  return {
    contract_id: 'contract_test-plugin-01_fs-read_10',
    plugin_id: 'test-plugin-01',
    capability_id: 'fs-read-workspace',
    granted_scope: ['/workspace'],
    sequence_granted: 10,
    is_least_privilege: true,
    admissibility_reason: 'Required for test plugin workspace access',
    ...overrides,
  }
}

function makeReceipt(overrides: Partial<MutationReceipt> = {}): MutationReceipt {
  return {
    receipt_id: 'receipt_001',
    plugin_id: 'test-plugin-01',
    mutation_type: 'path_registered',
    target_path: '/workspace/output.json',
    sequence: 15,
    authorized_by_contract: 'contract_test-plugin-01_fs-read_10',
    is_replay_reconstructable: true,
    entropy_contribution_fixed: FIXED_SCALE,  // 1.0 in Q16.16
    ...overrides,
  }
}

// ─── Plugin Admission Tests ────────────────────────────────

describe('plugin admission', () => {
  it('admits a valid T2 replay-safe plugin', () => {
    const reg = ExtensionRegistry.empty().admit(makeManifest(), 10)
    expect(reg.admittedCount()).toBe(1)
  })

  it('rejects plugin with wrong schema version', () => {
    expect(() =>
      ExtensionRegistry.empty().admit(
        makeManifest({ schema_version: '2.0.0' as typeof PLUGIN_MANIFEST_SCHEMA_VERSION }),
        10
      )
    ).toThrow(PluginAdmissionError)
  })

  it('rejects T3 plugin — epistemic tier not admissible', () => {
    expect(() =>
      ExtensionRegistry.empty().admit(makeManifest({ epistemic_tier: EpistemicTier.T3 }), 10)
    ).toThrow(PluginAdmissionError)
  })

  it('rejects T4 plugin — epistemic tier not admissible', () => {
    expect(() =>
      ExtensionRegistry.empty().admit(makeManifest({ epistemic_tier: EpistemicTier.T4 }), 10)
    ).toThrow(PluginAdmissionError)
  })

  it('rejects non-replay-safe plugin', () => {
    expect(() =>
      ExtensionRegistry.empty().admit(makeManifest({ is_replay_safe: false }), 10)
    ).toThrow(PluginAdmissionError)
  })

  it('rejects duplicate plugin registration', () => {
    const reg = ExtensionRegistry.empty().admit(makeManifest(), 10)
    expect(() => reg.admit(makeManifest(), 20)).toThrow(PluginAdmissionError)
  })

  it('admitted plugin has admitted_at_sequence set', () => {
    const reg = ExtensionRegistry.empty().admit(makeManifest(), 42)
    expect(reg.manifests[0]?.admitted_at_sequence).toBe(42)
  })
})

// ─── Plugin Eviction Tests ─────────────────────────────────

describe('plugin eviction', () => {
  it('evicts plugin and expires its contracts', () => {
    const reg0 = ExtensionRegistry.empty().admit(makeManifest(), 10)
    const reg1 = reg0.addContract(makeContract())
    const reg2 = reg1.evict('test-plugin-01', 50)
    expect(reg2.manifests[0]?.status).toBe('evicted')
    const contracts = reg2.getActiveContracts('test-plugin-01')
    expect(contracts).toHaveLength(0)
  })

  it('cannot add contract to evicted plugin', () => {
    const reg = ExtensionRegistry.empty()
      .admit(makeManifest(), 10)
      .evict('test-plugin-01', 20)
    expect(() => reg.addContract(makeContract())).toThrow(PluginAdmissionError)
  })
})

// ─── Capability Contract Tests ────────────────────────────

describe('capability contracts', () => {
  it('createContract sets all required fields', () => {
    const c = createContract({
      plugin_id: 'test-plugin-01',
      capability_id: 'fs-read-workspace',
      granted_scope: ['/workspace'],
      sequence_granted: 10,
      admissibility_reason: 'workspace read access',
    })
    expect(c.is_least_privilege).toBe(true)
    expect(c.sequence_expires).toBeUndefined()
    expect(c.contract_id).toContain('test-plugin-01')
  })

  it('createContract rejects empty admissibility reason', () => {
    expect(() =>
      createContract({
        plugin_id: 'p', capability_id: 'c',
        granted_scope: [], sequence_granted: 1, admissibility_reason: '',
      })
    ).toThrow(PluginAdmissionError)
  })

  it('isContractActive returns true within grant window', () => {
    const c = makeContract({ sequence_granted: 10 })
    expect(isContractActive(c, 20)).toBe(true)
  })

  it('isContractActive returns false before grant', () => {
    const c = makeContract({ sequence_granted: 10 })
    expect(isContractActive(c, 5)).toBe(false)
  })

  it('isContractActive returns false after expiry', () => {
    const c = expireContract(makeContract({ sequence_granted: 10 }), 30)
    expect(isContractActive(c, 35)).toBe(false)
    expect(isContractActive(c, 25)).toBe(true)
  })

  it('expireContract cannot re-expire an already-expired contract', () => {
    const c = expireContract(makeContract(), 30)
    expect(() => expireContract(c, 40)).toThrow(PluginAdmissionError)
  })
})

// ─── Sandbox Isolation Tests ───────────────────────────────

describe('sandbox isolation', () => {
  function makeSandbox() {
    return createSandbox({
      plugin_id: 'test-plugin-01',
      allowed_capability_ids: ['fs-read-workspace'],
      allowed_paths: ['/workspace'],
      entropy_budget_fixed: 10 * FIXED_SCALE,
      max_mutation_count: 5,
    })
  }

  it('creates isolated sandbox', () => {
    const sb = makeSandbox()
    expect(sb.is_isolated).toBe(true)
    expect(sb.current_mutation_count).toBe(0)
    expect(sb.entropy_used_fixed).toBe(0)
  })

  it('allows mutation within sandbox bounds', () => {
    const sb = makeSandbox()
    expect(() => checkSandboxAllows(sb, 'fs-read-workspace', '/workspace/file.ts')).not.toThrow()
  })

  it('rejects mutation outside allowed capability', () => {
    const sb = makeSandbox()
    expect(() =>
      checkSandboxAllows(sb, 'network-access', '/workspace/file.ts')
    ).toThrow(SandboxViolationError)
  })

  it('rejects mutation outside allowed path', () => {
    const sb = makeSandbox()
    expect(() =>
      checkSandboxAllows(sb, 'fs-read-workspace', '/etc/passwd')
    ).toThrow(SandboxViolationError)
  })

  it('rejects mutation when mutation count exceeded', () => {
    let sb = makeSandbox()
    for (let i = 0; i < 5; i++) {
      sb = recordMutation(sb, makeReceipt({ receipt_id: `r${i}`, sequence: i + 1 }))
    }
    expect(() => checkSandboxAllows(sb, 'fs-read-workspace', '/workspace/x')).toThrow(SandboxViolationError)
  })

  it('rejects mutation outside sandbox plugin_id', () => {
    const sb = makeSandbox()
    expect(() =>
      recordMutation(sb, makeReceipt({ plugin_id: 'other-plugin' }))
    ).toThrow(SandboxViolationError)
  })
})

// ─── Plugin Entropy Accounting Tests ──────────────────────

describe('plugin entropy accounting', () => {
  it('entropy starts at 0', () => {
    const sb = createSandbox({
      plugin_id: 'p', allowed_capability_ids: [], allowed_paths: [],
      entropy_budget_fixed: 100 * FIXED_SCALE, max_mutation_count: 100,
    })
    expect(computeSandboxEntropyRatio(sb)).toBe(0)
  })

  it('entropy ratio increases with each mutation', () => {
    let sb = createSandbox({
      plugin_id: 'test-plugin-01',
      allowed_capability_ids: ['fs-read-workspace'],
      allowed_paths: ['/workspace'],
      entropy_budget_fixed: 10 * FIXED_SCALE,
      max_mutation_count: 100,
    })
    sb = recordMutation(sb, makeReceipt({ entropy_contribution_fixed: FIXED_SCALE }))
    expect(computeSandboxEntropyRatio(sb)).toBeCloseTo(0.1)  // 1/10
  })

  it('telemetryFor reports replay_safe_ratio correctly', () => {
    const reg = ExtensionRegistry.empty().admit(makeManifest(), 10)
    const receipts = [
      makeReceipt({ receipt_id: 'r1', is_replay_reconstructable: true }),
      makeReceipt({ receipt_id: 'r2', is_replay_reconstructable: false }),
    ]
    const tel = reg.telemetryFor('test-plugin-01', receipts)
    expect(tel.replay_safe_ratio).toBe(0.5)
    expect(tel.mutation_count).toBe(2)
  })

  it('telemetryFor reports replay_safe_ratio 1.0 with no mutations', () => {
    const reg = ExtensionRegistry.empty().admit(makeManifest(), 10)
    const tel = reg.telemetryFor('test-plugin-01', [])
    expect(tel.replay_safe_ratio).toBe(1)
  })

  it('telemetryFor reflects evicted plugin as sandbox_isolation_intact=false', () => {
    const reg = ExtensionRegistry.empty().admit(makeManifest(), 10).evict('test-plugin-01', 20)
    const tel = reg.telemetryFor('test-plugin-01', [])
    expect(tel.sandbox_isolation_intact).toBe(false)
  })
})

// ─── Extension Determinism Validation ─────────────────────

describe('extension determinism validation', () => {
  it('admitting same plugin twice is idempotent-safe via rejection', () => {
    const reg1 = ExtensionRegistry.empty().admit(makeManifest(), 1)
    expect(() => reg1.admit(makeManifest(), 2)).toThrow(PluginAdmissionError)
  })

  it('contract_id is deterministic from params', () => {
    const c1 = createContract({
      plugin_id: 'p', capability_id: 'c', granted_scope: [],
      sequence_granted: 42, admissibility_reason: 'test',
    })
    const c2 = createContract({
      plugin_id: 'p', capability_id: 'c', granted_scope: [],
      sequence_granted: 42, admissibility_reason: 'test',
    })
    expect(c1.contract_id).toBe(c2.contract_id)
  })

  it('sandbox_id is deterministic from plugin_id', () => {
    const sb1 = createSandbox({ plugin_id: 'p', allowed_capability_ids: [], allowed_paths: [], entropy_budget_fixed: 0, max_mutation_count: 0 })
    const sb2 = createSandbox({ plugin_id: 'p', allowed_capability_ids: [], allowed_paths: [], entropy_budget_fixed: 0, max_mutation_count: 0 })
    expect(sb1.sandbox_id).toBe(sb2.sandbox_id)
  })
})
