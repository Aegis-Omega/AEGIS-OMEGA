// ============================================================
// Misc Coverage Batch 1
// Targets:
//   agents/registry/agent-registry.ts: schema_version mismatch, retire non-match
//   environment/telemetry/env_telemetry.ts: zero sequenceSpan → 0, zero frames → 1
//   environment/snapshots/snapshot.ts: happy path + non-object input
//   sitr/intervention.ts: append to non-empty with higher sequence
//   constitutional/directives.ts: sort comparator reverse order
// ============================================================

import { describe, it, expect } from 'vitest'

// ─── AgentRegistry: schema_version mismatch + retire non-matching ─

import { AgentRegistry } from '../../src/agents/registry/agent-registry.js'
import { AgentRegistrationError, AGENT_MANIFEST_SCHEMA_VERSION } from '../../src/agents/types.js'
import { EpistemicTier } from '../../src/core/types.js'
import type { AgentManifest } from '../../src/agents/types.js'

function makeManifest(overrides: Partial<AgentManifest> = {}): AgentManifest {
  return Object.freeze({
    schema_version: AGENT_MANIFEST_SCHEMA_VERSION,
    agent_id: 'agent-001',
    name: 'Test Agent',
    agent_type: 'ResearchAgent' as AgentManifest['agent_type'],
    epistemic_tier: EpistemicTier.T2,
    capability_manifest: Object.freeze({
      capability_ids: [],
      invariant_bindings: [],
      telemetry_schema_version: '1.0.0',
    }),
    is_replay_safe: true,
    entropy_budget_fixed: 0,
    workspace_boundary: [],
    status: 'registered',
    ...overrides,
  })
}

describe('AgentRegistry: schema_version mismatch → throw', () => {
  it('throws AgentRegistrationError when schema_version does not match', () => {
    const manifest = makeManifest({ schema_version: '0.0.0' as typeof AGENT_MANIFEST_SCHEMA_VERSION })
    expect(() => AgentRegistry.empty().register(manifest, 1)).toThrow(AgentRegistrationError)
  })

  it('error message contains schema_version mismatch text', () => {
    const manifest = makeManifest({ schema_version: '9.9.9' as typeof AGENT_MANIFEST_SCHEMA_VERSION })
    expect(() => AgentRegistry.empty().register(manifest, 1)).toThrow(/schema version mismatch/)
  })
})

describe('AgentRegistry: retire non-existing agent_id returns unchanged registry', () => {
  it('retiring a non-existent agent_id leaves the registry unchanged', () => {
    const registry = AgentRegistry.empty().register(makeManifest({ agent_id: 'a1' }), 1)
    const after = registry.retire('ghost-agent', 2)
    // 'a1' still registered, 'ghost-agent' never existed
    expect(after.getActive()).toHaveLength(1)
    expect(after.getActive()[0]?.agent_id).toBe('a1')
  })

  it('retire returns a new AgentRegistry instance even when nothing changed', () => {
    const registry = AgentRegistry.empty().register(makeManifest({ agent_id: 'b1' }), 1)
    const after = registry.retire('nonexistent', 2)
    expect(after).not.toBe(registry)
  })
})

// ─── Environment Telemetry: zero inputs ─────────────────────

import {
  computeEnvironmentalDriftRate,
  computeReplayIdentityIntegrity,
} from '../../src/environment/telemetry/env_telemetry.js'

describe('computeEnvironmentalDriftRate: sequenceSpan <= 0', () => {
  it('returns 0 when sequenceSpan is 0', () => {
    expect(computeEnvironmentalDriftRate(5, 0)).toBe(0)
  })

  it('returns 0 when sequenceSpan is negative', () => {
    expect(computeEnvironmentalDriftRate(5, -10)).toBe(0)
  })

  it('returns normal rate when sequenceSpan > 0', () => {
    expect(computeEnvironmentalDriftRate(10, 5)).toBe(2)
  })
})

describe('computeReplayIdentityIntegrity: totalFrames === 0', () => {
  it('returns 1 when totalFrames is 0 (no frames to check → perfect)', () => {
    expect(computeReplayIdentityIntegrity(0, 0)).toBe(1)
  })

  it('returns 1 when totalFrames is 0 even with nonzero validFrames', () => {
    expect(computeReplayIdentityIntegrity(5, 0)).toBe(1)
  })
})

// ─── Environment Snapshot: non-object + happy path ───────────

import { deserializeSnapshot } from '../../src/environment/snapshots/snapshot.js'
import { WORKSPACE_SNAPSHOT_SCHEMA_VERSION } from '../../src/environment/types.js'

describe('deserializeSnapshot: non-object input throws', () => {
  it('throws when input is null', () => {
    expect(() => deserializeSnapshot(null)).toThrow(/not an object/)
  })

  it('throws when input is a string', () => {
    expect(() => deserializeSnapshot('hello')).toThrow()
  })

  it('throws when input is a number', () => {
    expect(() => deserializeSnapshot(42)).toThrow()
  })
})

describe('deserializeSnapshot: valid snapshot succeeds (happy path)', () => {
  it('returns the snapshot when schema_version matches', () => {
    const raw = {
      schema_version: WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
      snapshot_id: 'snap-1',
      captured_at_sequence: 0,
      is_attested: true,
      binding_count: 0,
    }
    const result = deserializeSnapshot(raw)
    expect(result).toBeDefined()
    expect(result.schema_version).toBe(WORKSPACE_SNAPSHOT_SCHEMA_VERSION)
  })

  it('result is frozen', () => {
    const raw = {
      schema_version: WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
      snapshot_id: 'snap-2',
      captured_at_sequence: 5,
      is_attested: false,
      binding_count: 0,
    }
    expect(Object.isFrozen(deserializeSnapshot(raw))).toBe(true)
  })
})

// ─── SITR InterventionLog: append to non-empty with higher seq ─

import { InterventionLog } from '../../src/sitr/intervention.js'
import type { InterventionRecord } from '../../src/sitr/types.js'

function makeRecord(seq: number): InterventionRecord {
  return Object.freeze({
    record_id: `int-${seq}`,
    sequence: seq,
    prior_state: 'STABLE',
    next_state: 'STABLE',
    trigger: 'test',
    directive_ids: [],
    is_replay_reconstructable: true,
  })
}

describe('InterventionLog: append to non-empty with higher sequence (arm 1)', () => {
  it('successfully appends when sequence is strictly higher than last', () => {
    const l0 = InterventionLog.empty()
    const l1 = l0.append(makeRecord(10))
    // Now l1 is non-empty; append record with seq=20 (valid)
    const l2 = l1.append(makeRecord(20))
    expect(l2.length).toBe(2)
  })

  it('can chain multiple appends to a non-empty log', () => {
    let log = InterventionLog.empty()
    for (const seq of [5, 10, 15]) {
      log = log.append(makeRecord(seq))
    }
    expect(log.length).toBe(3)
    expect(log.getAll()[2]?.sequence).toBe(15)
  })
})

// ─── buildConstitutionHash: reverse-order sort comparator ────

import { buildConstitutionHash, DIRECTIVES_SCHEMA_VERSION } from '../../src/constitutional/directives.js'
import type { SovereignDirective } from '../../src/constitutional/directives.js'
import type { SHA256Hex } from '../../src/core/types.js'

const HASH = '0'.repeat(64) as SHA256Hex

function makeDirective(directive_class: SovereignDirective['directive_class']): SovereignDirective {
  return Object.freeze({
    directive_class,
    description: `${directive_class} description`,
    aegis_grounding: 'test-module',
    aegis_grounding_file: 'src/test.ts',
    failure_mode_prevented: 'test failure',
    epistemic_tier: 'T2' as const,
    directive_hash: HASH,
    schema_version: DIRECTIVES_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}

describe('buildConstitutionHash: reverse-order input exercises sort comparator', () => {
  it('produces same hash regardless of directive input order', async () => {
    const directives: SovereignDirective[] = [
      makeDirective('CAUSAL_ARCHITECTURE'),
      makeDirective('ADVERSARIAL_SELF_CORRECTION'),
    ]
    const reversed: SovereignDirective[] = [...directives].reverse()
    const hash1 = await buildConstitutionHash(directives)
    const hash2 = await buildConstitutionHash(reversed)
    expect(hash1).toBe(hash2)
  })

  it('produces a non-empty hash string', async () => {
    const directives: SovereignDirective[] = [
      makeDirective('OPERATIONAL_REALISM'),
      makeDirective('EPISTEMIC_SOVEREIGNTY'),
    ]
    const hash = await buildConstitutionHash(directives)
    expect(hash).toHaveLength(64)
  })
})
