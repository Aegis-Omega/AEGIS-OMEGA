// ============================================================
// Environment Adaptation Layer Tests
// Gate 10: deterministic environment reconstruction, capability admission,
//   replay-compatible snapshots, mutation lineage, path canonicalization,
//   host adaptation determinism
// ============================================================

import { describe, it, expect } from 'vitest'
import { EpistemicTier } from '../../src/core/types'
import type { HostCapability, EnvironmentMutation, EnvironmentBinding } from '../../src/environment/types'
import {
  CapabilityAdmissionError,
  MutationRejectedError,
  WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
} from '../../src/environment/types'
import { createCapabilityGuard } from '../../src/environment/kernel/capability_guard'
import {
  canonicalizePath,
  deterministicWorkspaceId,
  deterministicPathId,
  detectInstallationContext,
  buildGovernedPath,
  buildGovernedWorkspace,
} from '../../src/environment/workspace/introspection'
import { MutationLedger } from '../../src/environment/memory/mutation_ledger'
import {
  buildSnapshot,
  exportSnapshot,
  deserializeSnapshot,
  canonicalizeWorkspaceState,
} from '../../src/environment/snapshots/snapshot'
import {
  buildEnvironmentTelemetry,
  computeEnvironmentEntropy,
  computeMutationVelocity,
  computeReplayReconstructionIntegrity,
  computeAdaptationPressureIndex,
  computeConstitutionalStabilityScore,
} from '../../src/environment/telemetry/env_telemetry'
import type { SHA256Hex } from '../../src/core/types'

// ─── Test helpers ──────────────────────────────────────────

const mockHash = (s: string) => s.padEnd(64, '0') as SHA256Hex

function makeCapability(overrides: Partial<HostCapability> = {}): HostCapability {
  return {
    capability_id: 'fs-read-workspace',
    class: 'filesystem',
    name: 'Filesystem Read — workspace directory',
    provenance_tier: EpistemicTier.T1,
    ontology_term: 'filesystem_capability',
    admissibility_reason: 'Required for workspace introspection',
    entropy_impact_bounded: true,
    ...overrides,
  }
}

function makeMutation(overrides: Partial<EnvironmentMutation> = {}): EnvironmentMutation {
  return {
    mutation_id: 'mut_001',
    sequence: 1,
    mutation_type: 'path_registered',
    target_path: '/workspace/src',
    prev_state_hash: mockHash('prev'),
    next_state_hash: mockHash('next'),
    provenance_source: 'ENVIRONMENT_CONSTITUTION.md RULE-01',
    admitted_by: 'fs-read-workspace',
    is_replay_reconstructable: true,
    ...overrides,
  }
}

// ─── Canonical Path Serialization Tests ────────────────────

describe('canonical path serialization', () => {
  it('normalizes backslashes to forward slashes', () => {
    expect(canonicalizePath('C:\\Users\\tarik\\myapp')).toBe('C:/Users/tarik/myapp')
  })

  it('collapses repeated slashes', () => {
    expect(canonicalizePath('/home//user///myapp')).toBe('/home/user/myapp')
  })

  it('removes trailing slash', () => {
    expect(canonicalizePath('/home/user/myapp/')).toBe('/home/user/myapp')
  })

  it('preserves root path', () => {
    expect(canonicalizePath('/')).toBe('/')
  })

  it('is deterministic — identical input produces identical output', () => {
    const raw = '/home/user/myapp//src/./core/'
    const a = canonicalizePath(raw)
    const b = canonicalizePath(raw)
    expect(a).toBe(b)
  })

  it('deterministicWorkspaceId is stable for same root', () => {
    const id1 = deterministicWorkspaceId('/home/user/myapp')
    const id2 = deterministicWorkspaceId('/home/user/myapp')
    expect(id1).toBe(id2)
    expect(id1).toMatch(/^ws_[0-9a-f]{8}$/)
  })

  it('deterministicWorkspaceId differs for different roots', () => {
    const a = deterministicWorkspaceId('/home/user/myapp')
    const b = deterministicWorkspaceId('/home/user/other')
    expect(a).not.toBe(b)
  })

  it('deterministicPathId is stable and distinct', () => {
    const a = deterministicPathId('/src/core')
    const b = deterministicPathId('/src/core')
    const c = deterministicPathId('/src/event')
    expect(a).toBe(b)
    expect(a).not.toBe(c)
    expect(a).toMatch(/^path_[0-9a-f]{8}$/)
  })
})

// ─── Installation Context Detection ────────────────────────

describe('host adaptation determinism — installation context', () => {
  it('detects monorepo when package.json + packages present', () => {
    expect(detectInstallationContext(['package.json', 'packages', 'src'])).toBe('monorepo')
  })

  it('detects standalone when only package.json present', () => {
    expect(detectInstallationContext(['package.json', 'src', 'dist'])).toBe('standalone')
  })

  it('detects container from Dockerfile', () => {
    expect(detectInstallationContext(['Dockerfile', 'src'])).toBe('container')
  })

  it('detects ci-environment from .github', () => {
    expect(detectInstallationContext(['.github', 'src', 'package.json'])).toBe('ci-environment')
  })

  it('falls back to development with no signals', () => {
    expect(detectInstallationContext(['README.md', 'notes.txt'])).toBe('development')
  })

  it('is deterministic — same inputs always produce same context', () => {
    const inputs = ['package.json', 'packages', 'crates']
    expect(detectInstallationContext(inputs)).toBe(detectInstallationContext(inputs))
  })
})

// ─── Capability Admission Tests ────────────────────────────

describe('capability admission', () => {
  it('registers a valid T1 capability', () => {
    const guard = createCapabilityGuard().register(makeCapability())
    expect(guard.capabilitySurfaceArea()).toBe(1)
  })

  it('rejects T3 capability — provenance tier too low', () => {
    expect(() =>
      createCapabilityGuard().register(makeCapability({ provenance_tier: EpistemicTier.T3 }))
    ).toThrow(CapabilityAdmissionError)
  })

  it('rejects capability with unbounded entropy impact', () => {
    expect(() =>
      createCapabilityGuard().register(makeCapability({ entropy_impact_bounded: false }))
    ).toThrow(CapabilityAdmissionError)
  })

  it('rejects capability with empty ontology term', () => {
    expect(() =>
      createCapabilityGuard().register(makeCapability({ ontology_term: '' }))
    ).toThrow(CapabilityAdmissionError)
  })

  it('grants a capability and returns active grant', () => {
    const guard0 = createCapabilityGuard().register(makeCapability())
    const { guard: guard1, grant } = guard0.grant({
      capability_id: 'fs-read-workspace',
      granted_to: 'workspace-agent',
      scope: ['/home/user/myapp'],
      sequence_granted: 10,
    })
    expect(grant.capability_id).toBe('fs-read-workspace')
    expect(grant.least_privilege).toBe(true)
    expect(guard1.grants).toHaveLength(1)
  })

  it('rejects grant for unregistered capability', () => {
    expect(() =>
      createCapabilityGuard().grant({
        capability_id: 'unknown-cap',
        granted_to: 'agent',
        scope: [],
        sequence_granted: 1,
      })
    ).toThrow(CapabilityAdmissionError)
  })

  it('isAuthorized returns true for active grant', () => {
    const guard0 = createCapabilityGuard().register(makeCapability())
    const { guard: guard1 } = guard0.grant({
      capability_id: 'fs-read-workspace',
      granted_to: 'agent',
      scope: ['/workspace'],
      sequence_granted: 5,
    })
    const mutation = makeMutation({ sequence: 10 })
    expect(guard1.isAuthorized(mutation)).toBe(true)
  })

  it('isAuthorized returns false after revocation', () => {
    const guard0 = createCapabilityGuard().register(makeCapability())
    const { guard: guard1, grant } = guard0.grant({
      capability_id: 'fs-read-workspace',
      granted_to: 'agent',
      scope: ['/workspace'],
      sequence_granted: 5,
    })
    const guard2 = guard1.revoke(grant.grant_id, 15)
    const mutation = makeMutation({ sequence: 20 })
    expect(guard2.isAuthorized(mutation)).toBe(false)
  })
})

// ─── Environment Mutation Lineage Tests ───────────────────

describe('environment mutation lineage', () => {
  it('MutationLedger starts empty', () => {
    const ledger = MutationLedger.empty()
    expect(ledger.length).toBe(0)
    expect(ledger.mutations).toHaveLength(0)
  })

  it('append adds mutation and replay frame', () => {
    const ledger = MutationLedger.empty().append(makeMutation(), mockHash('state1'))
    expect(ledger.length).toBe(1)
    expect(ledger.frames).toHaveLength(1)
  })

  it('enforces monotonic sequence ordering', () => {
    const ledger = MutationLedger.empty().append(makeMutation({ sequence: 5 }), mockHash('s1'))
    expect(() =>
      ledger.append(makeMutation({ sequence: 5 }), mockHash('s2'))
    ).toThrow(MutationRejectedError)
  })

  it('rejects earlier sequence after higher', () => {
    const ledger = MutationLedger.empty().append(makeMutation({ sequence: 10 }), mockHash('s1'))
    expect(() =>
      ledger.append(makeMutation({ sequence: 9 }), mockHash('s2'))
    ).toThrow(MutationRejectedError)
  })

  it('verifyStructural passes for valid ledger', () => {
    const ledger = MutationLedger.empty()
      .append(makeMutation({ sequence: 1, mutation_id: 'a' }), mockHash('s1'))
      .append(makeMutation({ sequence: 2, mutation_id: 'b' }), mockHash('s2'))
      .append(makeMutation({ sequence: 3, mutation_id: 'c' }), mockHash('s3'))
    expect(ledger.verifyStructural()).toEqual({ valid: true })
  })

  it('filterByType returns only matching mutations', () => {
    const ledger = MutationLedger.empty()
      .append(makeMutation({ sequence: 1, mutation_id: 'a', mutation_type: 'path_registered' }), mockHash('s1'))
      .append(makeMutation({ sequence: 2, mutation_id: 'b', mutation_type: 'capability_granted' }), mockHash('s2'))
    expect(ledger.filterByType('path_registered')).toHaveLength(1)
    expect(ledger.filterByType('capability_granted')).toHaveLength(1)
    expect(ledger.filterByType('workspace_added')).toHaveLength(0)
  })

  it('mutationVelocity returns 0 for empty ledger', () => {
    expect(MutationLedger.empty().mutationVelocity(10)).toBe(0)
  })
})

// ─── Replay-Compatible Snapshot Tests ─────────────────────

describe('replay-compatible snapshot', () => {
  function makeWorkspace() {
    const paths = [
      buildGovernedPath('/home/user/myapp', 'read-only', false),
      buildGovernedPath('/home/user/myapp/sovereign-omega-v2/python/gate.py', 'read-only', true),
    ]
    return buildGovernedWorkspace({
      canonicalRoot: '/home/user/myapp',
      installationContext: 'monorepo',
      governedPaths: paths,
      activeCapabilityIds: ['fs-read-workspace'],
    })
  }

  it('builds snapshot with correct schema version', () => {
    const ws = makeWorkspace()
    const snap = buildSnapshot({ workspace: ws, bindings: [], sequence: 42, totalMutations: 3 })
    expect(snap.schema_version).toBe(WORKSPACE_SNAPSHOT_SCHEMA_VERSION)
  })

  it('snapshot_id is deterministic for same inputs', () => {
    const ws = makeWorkspace()
    const snap1 = buildSnapshot({ workspace: ws, bindings: [], sequence: 42, totalMutations: 3 })
    const snap2 = buildSnapshot({ workspace: ws, bindings: [], sequence: 42, totalMutations: 3 })
    expect(snap1.snapshot_id).toBe(snap2.snapshot_id)
  })

  it('snapshot_id changes when sequence changes', () => {
    const ws = makeWorkspace()
    const snap1 = buildSnapshot({ workspace: ws, bindings: [], sequence: 42, totalMutations: 3 })
    const snap2 = buildSnapshot({ workspace: ws, bindings: [], sequence: 43, totalMutations: 3 })
    expect(snap1.snapshot_id).not.toBe(snap2.snapshot_id)
  })

  it('snapshot is attested', () => {
    const ws = makeWorkspace()
    const snap = buildSnapshot({ workspace: ws, bindings: [], sequence: 1, totalMutations: 0 })
    const exported = exportSnapshot(snap, 0)
    expect(exported.is_attested).toBe(true)
  })

  it('deserializeSnapshot rejects wrong schema version', () => {
    expect(() =>
      deserializeSnapshot({ schema_version: '2.0.0', snapshot_id: 'snap_abc', captured_at_sequence: 0 })
    ).toThrow('schema version mismatch')
  })

  it('canonicalizeWorkspaceState is deterministic', () => {
    const ws = makeWorkspace()
    const a = canonicalizeWorkspaceState(ws, [], 10)
    const b = canonicalizeWorkspaceState(ws, [], 10)
    expect(a).toBe(b)
  })
})

// ─── Environment Telemetry Tests ──────────────────────────

describe('environment telemetry', () => {
  it('environment_entropy is 0 with no mutations', () => {
    const state = {
      state_id: 'st0', sequence: 0,
      workspace: buildGovernedWorkspace({ canonicalRoot: '/ws', installationContext: 'development', governedPaths: [], activeCapabilityIds: [] }),
      active_bindings: [] as readonly EnvironmentBinding[],
      mutation_count: 0,
      entropy_fixed: 0,
      adaptation_pressure_index_fixed: 0,
    }
    expect(computeEnvironmentEntropy(state)).toBe(0)
  })

  it('mutation_velocity is 0 for zero sequence span', () => {
    expect(computeMutationVelocity(10, 0)).toBe(0)
  })

  it('replay_reconstruction_integrity is 1 with no mutations', () => {
    expect(computeReplayReconstructionIntegrity(0, 0)).toBe(1)
  })

  it('replay_reconstruction_integrity degrades with non-reconstructable mutations', () => {
    expect(computeReplayReconstructionIntegrity(8, 10)).toBeCloseTo(0.8)
  })

  it('constitutional_stability_score is 1 at zero pressure', () => {
    expect(computeConstitutionalStabilityScore(0)).toBe(1)
  })

  it('constitutional_stability_score is 0 at max pressure', () => {
    expect(computeConstitutionalStabilityScore(1)).toBe(0)
  })

  it('adaptation_pressure_index is bounded [0,1]', () => {
    const p = computeAdaptationPressureIndex(0.5, 0.5, 0.5)
    expect(p).toBeGreaterThanOrEqual(0)
    expect(p).toBeLessThanOrEqual(1)
  })

  it('buildEnvironmentTelemetry returns all required fields', () => {
    const state = {
      state_id: 'st0', sequence: 100,
      workspace: buildGovernedWorkspace({ canonicalRoot: '/ws', installationContext: 'monorepo', governedPaths: [], activeCapabilityIds: [] }),
      active_bindings: [] as readonly EnvironmentBinding[],
      mutation_count: 5,
      entropy_fixed: 0,
      adaptation_pressure_index_fixed: 0,
    }
    const tel = buildEnvironmentTelemetry({
      state, bindings: [], mutationCount: 5, reconstructableMutations: 5,
      totalMutations: 5, sequenceSpan: 100, uniqueEnvironmentHashes: 3,
      validFrames: 5, totalFrames: 5,
    })
    expect(tel).toHaveProperty('environment_entropy')
    expect(tel).toHaveProperty('capability_surface_area')
    expect(tel).toHaveProperty('mutation_velocity')
    expect(tel).toHaveProperty('replay_reconstruction_integrity')
    expect(tel).toHaveProperty('adaptation_pressure_index')
    expect(tel).toHaveProperty('constitutional_stability_score')
    expect(tel).toHaveProperty('environmental_drift_rate')
    expect(tel).toHaveProperty('replay_identity_integrity')
  })
})
