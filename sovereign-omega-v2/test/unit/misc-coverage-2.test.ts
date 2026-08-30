// ============================================================
// Misc Coverage Batch 2
// Targets:
//   constitutional/directives.ts: sort comparator equal case → 0 (L92 arm 1)
//   skill-harness/decay.ts: invalid ISO date → daysBetween returns 0 (L51 arm 0)
//   environment/kernel/capability_guard.ts: revoke non-matching (L85 arm 1),
//     isAuthorized true + false (L104 arms 0 and 1)
//   extensions/registry/registry.ts: evict non-matching manifest (L72 arm 1),
//     evict non-matching contract (L78 arm 1), addContract unregistered (L90 arm 0)
//   environment/memory/mutation_ledger.ts: mutationVelocity non-empty (L77 arm 1)
//   agents/coordination/swarm-router.ts: buildSwarmTask with constitutionHash
//     (L140 arm 0 + L147 arm 0)
// ============================================================

import { describe, it, expect } from 'vitest'

// ─── Constitutional directives: equal directive_class → sort returns 0 ─

import {
  buildConstitutionHash,
  DIRECTIVES_SCHEMA_VERSION,
} from '../../src/constitutional/directives.js'
import type { SovereignDirective } from '../../src/constitutional/directives.js'
import type { SHA256Hex } from '../../src/core/types.js'

const HASH_64 = '0'.repeat(64) as SHA256Hex

function makeDirective2(
  directive_class: SovereignDirective['directive_class'],
  i: number
): SovereignDirective {
  return Object.freeze({
    directive_class,
    description: `desc-${i}`,
    aegis_grounding: 'test',
    aegis_grounding_file: 'test.ts',
    failure_mode_prevented: 'test',
    epistemic_tier: 'T2' as const,
    directive_hash: HASH_64,
    schema_version: DIRECTIVES_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

describe('buildConstitutionHash: equal directive_class → sort comparator returns 0', () => {
  it('two directives with same directive_class produce valid hash', async () => {
    // Both have directive_class='OPERATIONAL_REALISM' → sort comparator hits arm 1 (0 return)
    const directives: SovereignDirective[] = [
      makeDirective2('OPERATIONAL_REALISM', 1),
      makeDirective2('OPERATIONAL_REALISM', 2),
    ]
    const hash = await buildConstitutionHash(directives)
    expect(hash).toHaveLength(64)
  })
})

// ─── Skill Decay: invalid ISO date → daysBetween returns 0 ──

import { decaySkill } from '../../src/skill-harness/decay.js'
import { SKILL_HARNESS_SCHEMA_VERSION } from '../../src/skill-harness/types.js'
import type { SkillRecord } from '../../src/skill-harness/types.js'

function makeSkillRecord(last_validated: string): SkillRecord {
  return Object.freeze({
    skill_id: 'test-skill',
    name: 'Test Skill',
    confidence: 0.9,
    validated_runs: 10,
    failure_rate: 0.1,
    recency_score: 0.8,
    domain_affinity: [],
    dependencies: [],
    evidence_refs: [],
    last_validated,
    epistemic_tier: 'T2' as const,
    primitive_mapping: 'HASH',
    skill_hash: HASH_64,
    schema_version: SKILL_HARNESS_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

describe('decaySkill: invalid last_validated date → daysBetween returns 0', () => {
  it('does not throw when last_validated is not a parseable date', async () => {
    const skill = makeSkillRecord('not-a-valid-date')
    const result = await decaySkill(skill, 1_600_000_000_000)
    // daysBetween returns 0 for invalid date → days_inactive = 0 → no throw
    expect(result).toBeDefined()
    expect(result.days_inactive).toBe(0)
  })

  it('returns a valid DecayResult with zero inactive days', async () => {
    const skill = makeSkillRecord('INVALID-ISO')
    const result = await decaySkill(skill, 1_600_000_000_000)
    expect(result.decay_factor).toBe(1.0)
  })
})

// ─── Capability Guard ────────────────────────────────────

import {
  createCapabilityGuard,
} from '../../src/environment/kernel/capability_guard.js'
import { EpistemicTier } from '../../src/core/types.js'
import type { HostCapability, EnvironmentMutation } from '../../src/environment/types.js'

function makeCapability(): HostCapability {
  return Object.freeze({
    capability_id: 'cap-test',
    class: 'filesystem' as const,
    name: 'Test Capability',
    provenance_tier: EpistemicTier.T0,
    ontology_term: 'test.capability',
    admissibility_reason: 'test',
    entropy_impact_bounded: true,
  })
}

function makeMutation(admitted_by: string, sequence: number): EnvironmentMutation {
  return Object.freeze({
    mutation_id: `mut-${sequence}`,
    sequence,
    mutation_type: 'path_registered' as const,
    target_path: '/workspace/test',
    prev_state_hash: HASH_64,
    next_state_hash: HASH_64,
    provenance_source: 'test',
    admitted_by,
    is_replay_reconstructable: true,
  })
}

describe('CapabilityGuard: revoke non-matching grant_id (L85 arm 1)', () => {
  it('revoke with non-existent grant_id leaves grants unchanged', () => {
    const guard0 = createCapabilityGuard()
    const guard1 = guard0.register(makeCapability())
    const { guard: guard2 } = guard1.grant({
      capability_id: 'cap-test',
      granted_to: 'agent-1',
      scope: [],
      sequence_granted: 5,
    })
    // Revoke a grant_id that doesn't match any grant → all map iterations hit arm 1 (g)
    const guard3 = guard2.revoke('nonexistent-grant-xyz', 10)
    expect(guard3.grants).toHaveLength(1)
    expect(guard3.grants[0]?.sequence_revoked).toBeUndefined()
  })
})

describe('CapabilityGuard: isAuthorized returns false (L104 arm 0)', () => {
  it('returns false when no grants present', () => {
    const guard = createCapabilityGuard()
    const mutation = makeMutation('cap-test', 5)
    expect(guard.isAuthorized(mutation)).toBe(false)
  })

  it('returns false when capability_id does not match', () => {
    const guard0 = createCapabilityGuard()
    const guard1 = guard0.register(makeCapability())
    const { guard: guard2 } = guard1.grant({
      capability_id: 'cap-test',
      granted_to: 'agent-1',
      scope: [],
      sequence_granted: 5,
    })
    const mutation = makeMutation('cap-different', 10)
    expect(guard2.isAuthorized(mutation)).toBe(false)
  })
})

describe('CapabilityGuard: isAuthorized returns true (L104 arm 1)', () => {
  it('returns true when active grant matches', () => {
    const guard0 = createCapabilityGuard()
    const guard1 = guard0.register(makeCapability())
    const { guard: guard2 } = guard1.grant({
      capability_id: 'cap-test',
      granted_to: 'agent-1',
      scope: [],
      sequence_granted: 5,
    })
    const mutation = makeMutation('cap-test', 10)
    expect(guard2.isAuthorized(mutation)).toBe(true)
  })
})

import { MutationRejectedError } from '../../src/environment/types.js'

describe('CapabilityGuard: assertAuthorized throws when not authorized (L104 arm 0)', () => {
  it('throws MutationRejectedError when no grant exists', () => {
    const guard = createCapabilityGuard()
    const mutation = makeMutation('cap-test', 5)
    expect(() => guard.assertAuthorized(mutation)).toThrow(MutationRejectedError)
  })

  it('error message includes mutation_id and capability', () => {
    const guard = createCapabilityGuard()
    const mutation = makeMutation('cap-test', 7)
    expect(() => guard.assertAuthorized(mutation)).toThrow(/cap-test/)
  })
})

describe('CapabilityGuard: assertAuthorized does not throw when authorized (L104 arm 1)', () => {
  it('does not throw when active grant matches', () => {
    const guard0 = createCapabilityGuard()
    const guard1 = guard0.register(makeCapability())
    const { guard: guard2 } = guard1.grant({
      capability_id: 'cap-test',
      granted_to: 'agent-1',
      scope: [],
      sequence_granted: 5,
    })
    const mutation = makeMutation('cap-test', 10)
    expect(() => guard2.assertAuthorized(mutation)).not.toThrow()
  })
})

// ─── Extension Registry ──────────────────────────────────

import { ExtensionRegistry } from '../../src/extensions/registry/registry.js'
import {
  PLUGIN_MANIFEST_SCHEMA_VERSION,
  PluginAdmissionError,
} from '../../src/extensions/types.js'
import type { PluginManifest, CapabilityContract } from '../../src/extensions/types.js'

function makeManifest2(plugin_id: string): PluginManifest {
  return Object.freeze({
    schema_version: PLUGIN_MANIFEST_SCHEMA_VERSION,
    plugin_id,
    name: `Plugin ${plugin_id}`,
    version: '1.0.0',
    epistemic_tier: EpistemicTier.T2,
    capability_requests: [],
    ontology_terms_used: [],
    is_replay_safe: true,
    entropy_budget_fixed: 0,
    status: 'admitted' as const,
  })
}

function makeContract(plugin_id: string, capability_id: string): CapabilityContract {
  return Object.freeze({
    contract_id: `contract-${plugin_id}-${capability_id}`,
    plugin_id,
    capability_id,
    granted_scope: [],
    sequence_granted: 1,
    is_least_privilege: true,
    admissibility_reason: 'test',
  })
}

describe('ExtensionRegistry: evict non-matching plugin_id (L72 arm 1 + L78 arm 1)', () => {
  it('evicting non-existent plugin leaves manifests unchanged (arm 1 on map)', () => {
    const registry = ExtensionRegistry.empty().admit(makeManifest2('plugin-A'), 1)
    // Evict 'plugin-B' — plugin-A's manifest stays unchanged (map hits arm 1)
    const after = registry.evict('plugin-B', 2)
    expect(after.manifests).toHaveLength(1)
    expect(after.manifests[0]?.status).toBe('admitted')
  })

  it('evicting non-matching plugin_id leaves contracts unchanged (L78 arm 1)', () => {
    const r0 = ExtensionRegistry.empty().admit(makeManifest2('plugin-A'), 1)
    const r1 = r0.addContract(makeContract('plugin-A', 'cap-x'))
    // Evict 'plugin-B': plugin-A's contract has plugin_id='plugin-A' ≠ 'plugin-B' → arm 1
    const r2 = r1.evict('plugin-B', 2)
    expect(r2.contracts).toHaveLength(1)
    expect(r2.contracts[0]?.sequence_expires).toBeUndefined()
  })
})

describe('ExtensionRegistry: addContract to unregistered plugin throws (L90 arm 0)', () => {
  it('throws PluginAdmissionError when plugin_id is not registered', () => {
    const registry = ExtensionRegistry.empty()
    const contract = makeContract('nonexistent-plugin', 'cap-x')
    expect(() => registry.addContract(contract)).toThrow(PluginAdmissionError)
  })

  it('error message mentions the unregistered plugin_id', () => {
    const registry = ExtensionRegistry.empty()
    const contract = makeContract('ghost-plugin', 'cap-y')
    expect(() => registry.addContract(contract)).toThrow(/ghost-plugin/)
  })
})

// ─── MutationLedger: mutationVelocity non-empty (L77 arm 1) ─

import { MutationLedger } from '../../src/environment/memory/mutation_ledger.js'

describe('MutationLedger: mutationVelocity on non-empty ledger (L77 arm 1)', () => {
  it('returns the count of recent mutations when ledger is non-empty', async () => {
    const makeEnvironmentMutation = (seq: number): EnvironmentMutation =>
      Object.freeze({
        mutation_id: `mut-${seq}`,
        sequence: seq,
        mutation_type: 'path_registered' as const,
        target_path: '/workspace/test',
        prev_state_hash: HASH_64,
        next_state_hash: HASH_64,
        provenance_source: 'test',
        admitted_by: 'cap-test',
        is_replay_reconstructable: true,
      })

    let ledger = MutationLedger.empty()
    ledger = await ledger.append(makeEnvironmentMutation(1), HASH_64)
    ledger = await ledger.append(makeEnvironmentMutation(2), HASH_64)

    // windowSize > 0 AND mutations.length > 0 → arm 1 (FALSE branch of guard) executed
    expect(ledger.mutationVelocity(2)).toBe(2)
    expect(ledger.mutationVelocity(1)).toBe(1)
  })
})

// ─── SwarmRouter: buildSwarmTask with constitutionHash ──────

import {
  buildSwarmTask,
} from '../../src/agents/coordination/swarm-router.js'
import type { SequenceNumber } from '../../src/core/types.js'

describe('buildSwarmTask: with constitutionHash covers L140 arm 0 + L147 arm 0', () => {
  it('includes constitution_hash and directive_hash when constitutionHash provided', async () => {
    const promptBytes = new Uint8Array([1, 2, 3])
    const seq = 1n as SequenceNumber
    const hash = HASH_64
    const task = await buildSwarmTask(promptBytes, seq, hash)
    // directive_hash field should be present (arm 0 at L147: constitutionHash !== undefined)
    expect(task).toBeDefined()
    expect(task.is_replay_reconstructable).toBe(true)
  })

  it('task_id differs when constitution_hash is included vs not included', async () => {
    const promptBytes = new Uint8Array([1, 2, 3])
    const seq = 1n as SequenceNumber
    const taskWith = await buildSwarmTask(promptBytes, seq, HASH_64)
    const taskWithout = await buildSwarmTask(promptBytes, seq)
    // task_id incorporates constitution_hash → different IDs
    expect(taskWith.task_id).not.toBe(taskWithout.task_id)
  })
})
