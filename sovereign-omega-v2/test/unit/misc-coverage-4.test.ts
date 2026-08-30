// ============================================================
// Misc Coverage Batch 4
// Targets:
//   constitutional/martingale.ts: assertMartingaleAnchored drift_bounded=false (L110 arm 0)
//   skill-harness/resonance.ts: digitalRoot(0) with empty name (L37 arm 0),
//     isPalindrome([]) with empty domain_affinity (L43 arm 0)
//   agents/workflows/workflow-engine.ts: recordFrame non-matching workflow_id (L64 arm 1)
//   core/tier.ts: classifyPathTier with docs/research/ and docs/vision/ (L82, L84 arm 0)
//   gate/hoeffding.ts: empiricalMean n=0 (L93 arm 1),
//     normalQuantile with p<0.5 via computeMinSampleSize targetPower<0.5 (L193/194 arm 1)
//   frame/lineage.ts: certifyLineage with non-monotone sequence (L179 arm 0)
//   skill-harness/import.ts: assignDomainAffinity empty domains (L48 arm 0),
//     importSkillsFromManifests SkillCatalogError (L115 arm 0) vs other error (arm 1)
//   ledger/persistence.ts: deserializeChain with SyntaxError (L242 arm 1)
// ============================================================

import { describe, it, expect } from 'vitest'

// ─── Constitutional Martingale: drift_bounded=false (L110 arm 0) ──

import {
  assertMartingaleAnchored,
  MartingaleViolation,
  MARTINGALE_SCHEMA_VERSION,
  MUTATION_RATE_LIMIT,
} from '../../src/constitutional/martingale.js'
import type { MartingaleCertificate } from '../../src/constitutional/martingale.js'
import type { SHA256Hex } from '../../src/core/types.js'

const HASH_64 = '0'.repeat(64) as SHA256Hex

function makeMartingaleCert(overrides: Partial<MartingaleCertificate> = {}): MartingaleCertificate {
  return Object.freeze({
    is_anchored: true,
    drift_bounded: true,
    entropy_bounded: true,
    adaptive_power: 0,
    replay_verifiability: 5,
    adaptive_ratio: 0,
    mutation_rate_limit: MUTATION_RATE_LIMIT,
    terminal_hash: HASH_64,
    certificate_hash: HASH_64,
    schema_version: MARTINGALE_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
    ...overrides,
  })
}

describe('assertMartingaleAnchored: drift_bounded=false throws (L110 arm 0)', () => {
  it('throws MartingaleViolation when drift_bounded is false (is_anchored=true)', () => {
    const cert = makeMartingaleCert({ is_anchored: true, drift_bounded: false })
    expect(() => assertMartingaleAnchored(cert)).toThrow(MartingaleViolation)
  })

  it('error message mentions drift when drift_bounded=false', () => {
    const cert = makeMartingaleCert({ is_anchored: true, drift_bounded: false })
    expect(() => assertMartingaleAnchored(cert)).toThrow(/drift/)
  })
})

// ─── Skill Resonance: digitalRoot(0) and isPalindrome([]) ────

import { checkSkillResonance } from '../../src/skill-harness/resonance.js'
import { SKILL_HARNESS_SCHEMA_VERSION } from '../../src/skill-harness/types.js'
import type { SkillRecord } from '../../src/skill-harness/types.js'

function makeSkillRecord5(overrides: Partial<SkillRecord> = {}): SkillRecord {
  return Object.freeze({
    skill_id: 'resonance-test',
    name: 'Test Skill',
    confidence: 0.9,
    validated_runs: 5,
    failure_rate: 0.1,
    recency_score: 0.8,
    domain_affinity: ['a', 'b', 'a'],
    dependencies: [],
    evidence_refs: ['ref1'],
    last_validated: '2026-01-01T00:00:00Z',
    epistemic_tier: 'T2' as const,
    primitive_mapping: 'HASH',
    skill_hash: HASH_64,
    schema_version: SKILL_HARNESS_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
    ...overrides,
  })
}

describe('checkSkillResonance: digitalRoot(0) when name is empty (L37 arm 0)', () => {
  it('handles skill with empty name without throwing (digitalRoot(0) → 9, vortex_triadic)', () => {
    // name.length === 0 → digitalRoot(0) → arm 0: if(n===0) return 9 → vortex_triadic=true
    const skill = makeSkillRecord5({ name: '' })
    const result = checkSkillResonance(skill)
    expect(result).toBeDefined()
    expect(result.vortex_triadic).toBe(true) // digitalRoot(0) returns 9 ∈ {3,6,9}
  })
})

describe('checkSkillResonance: isPalindrome([]) when domain_affinity is empty (L43 arm 0)', () => {
  it('returns false for ring_valid when domain_affinity is empty', () => {
    // domain_affinity=[] → isPalindrome([]) → arr.length===0 → arm 0: return false
    const skill = makeSkillRecord5({ domain_affinity: [] })
    const result = checkSkillResonance(skill)
    expect(result.ring_valid).toBe(false)
  })
})

// ─── WorkflowEngine: recordFrame non-matching workflow_id (L64 arm 1) ─

import { WorkflowEngine } from '../../src/agents/workflows/workflow-engine.js'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types.js'

function makeWfFrame(workflow_id: string, seq: number): WorkflowReplayFrame {
  return Object.freeze({
    frame_id: `frame-${seq}`,
    workflow_id,
    sequence: seq,
    step_type: 'gather',
    input_hash: HASH_64,
    output_hash: HASH_64,
    invariant_satisfied: true,
  })
}

describe('WorkflowEngine.recordFrame: non-matching workflow_id (L64 arm 1)', () => {
  it('does not increment replay_frame_count for non-matching workflow_id', () => {
    const { engine: e1 } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-A',
      workflow_type: 'research',
      agent_id: 'agent-1',
      sequence: 1,
    })
    const { engine: e2 } = e1.startWorkflow({
      workflow_id: 'wf-B',
      workflow_type: 'refactor',
      agent_id: 'agent-2',
      sequence: 2,
    })
    // Record frame for wf-A → wf-B's replay_frame_count stays 0 (arm 1: workflow_id !== match)
    const e3 = e2.recordFrame('wf-A', makeWfFrame('wf-A', 3))
    const execB = e3.executions.find(e => e.workflow_id === 'wf-B')
    expect(execB?.replay_frame_count).toBe(0)
  })
})

// ─── Core Tier: classifyPathTier with T3/T4/T5 paths ─────────

import { classifyPathTier } from '../../src/core/tier.js'

describe('classifyPathTier: T3/T4/T5 path classifications (L82, L84 arm 0)', () => {
  it('classifies docs/research/ as T3', () => {
    const tier = classifyPathTier('docs/research/spectral-theory.md')
    expect(tier).toBe(3)
  })

  it('classifies docs/vision/ as T4', () => {
    const tier = classifyPathTier('docs/vision/planetary-coordination.md')
    expect(tier).toBe(4)
  })

  it('classifies docs/cycles/ as T5', () => {
    const tier = classifyPathTier('docs/cycles/worldbuilding.md')
    expect(tier).toBe(5)
  })
})

// ─── Hoeffding: empiricalMean n=0 and normalQuantile p<0.5 ──

import { ConfidenceSequence, computeMinSampleSize } from '../../src/gate/hoeffding.js'

describe('ConfidenceSequence.empiricalMean: returns 0 when n=0 (L93 arm 1)', () => {
  it('empiricalMean is 0 for empty sequence', () => {
    const seq = new ConfidenceSequence()
    expect(seq.empiricalMean).toBe(0)
  })
})

describe('computeMinSampleSize: normalQuantile with p<0.5 (L193/194 arm 1)', () => {
  it('computes min sample size with targetPower < 0.5 (triggers sign=-1 arm)', () => {
    // targetPower=0.3 → normalQuantile(0.3) where p<0.5 → sign=-1, q=1-p (arm 1)
    const n = computeMinSampleSize(0.3, 0.5, 0.05)
    expect(n).toBeGreaterThan(0)
    expect(Number.isInteger(n)).toBe(true)
  })
})

// ─── Frame Lineage: non-monotone sequence (L179 arm 0) ────────

import {
  certifyLineage,
  GENESIS_TOPOLOGY_HASH,
  LINEAGE_SCHEMA_VERSION,
} from '../../src/frame/lineage.js'
import { hashValue } from '../../src/core/hashing.js'
import type { SequenceNumber } from '../../src/core/types.js'
import type { LineageEntry } from '../../src/frame/lineage.js'

describe('certifyLineage: non-monotone sequence → is_valid=false (L179 arm 0)', () => {
  it('returns is_valid=false when sequence is non-monotone', async () => {
    // Build two entries with decreasing sequence (violates monotonicity)
    const h1 = await hashValue({ entry: 1 }) as SHA256Hex
    const h2 = await hashValue({ entry: 2 }) as SHA256Hex
    const lh1 = await hashValue({ topology_hash: h1, previous_topology_hash: GENESIS_TOPOLOGY_HASH, sequence: 5n }) as SHA256Hex
    const lh2 = await hashValue({ topology_hash: h2, previous_topology_hash: h1, sequence: 3n }) as SHA256Hex

    const entries: LineageEntry[] = [
      Object.freeze({
        topology_hash: h1,
        previous_topology_hash: GENESIS_TOPOLOGY_HASH,
        sequence: 5n as SequenceNumber,
        lineage_hash: lh1,
        schema_version: LINEAGE_SCHEMA_VERSION,
        is_replay_reconstructable: true as const,
      }),
      Object.freeze({
        topology_hash: h2,
        previous_topology_hash: h1,
        sequence: 3n as SequenceNumber,  // ← 3 < 5 violates monotonicity (L179 arm 0)
        lineage_hash: lh2,
        schema_version: LINEAGE_SCHEMA_VERSION,
        is_replay_reconstructable: true as const,
      }),
    ]

    const cert = await certifyLineage(entries)
    expect(cert.is_valid).toBe(false)
  })
})

// ─── Skill Import: empty domain affinity and import errors ──

import { assignDomainAffinity, importSkillsFromManifests } from '../../src/skill-harness/import.js'
import type { RawSkillManifest } from '../../src/skill-harness/types.js'

describe('assignDomainAffinity: no keywords → returns ["operations"] (L48 arm 0)', () => {
  it('returns ["operations"] when no domain keywords match', () => {
    const domains = assignDomainAffinity('My Cool Thing', 'Helps with stuff generally')
    expect(domains).toEqual(['operations'])
  })
})

describe('importSkillsFromManifests: handles catalog registration errors', () => {
  it('rejects duplicate skill_id via SkillCatalogError (L115 arm 0)', async () => {
    // Two manifests with same name → same derived skill_id → catalog.register throws SkillCatalogError
    const manifests: RawSkillManifest[] = [
      {
        source: 'test',
        path: 'skills/audit-verifier/SKILL.md',
        content: '---\nname: Audit Verifier\ndescription: does audit and verify hash integrity for compliance governance\n---\nAudits everything.',
      },
      {
        source: 'test',
        path: 'skills/audit-verifier-2/SKILL.md',
        content: '---\nname: Audit Verifier\ndescription: another audit verify compliance governance hash skill\n---\nDuplicate name.',
      },
    ]
    const result = await importSkillsFromManifests(manifests)
    expect(result.rejected).toHaveLength(1)
  })

  it('admits a valid manifest correctly', async () => {
    const manifests: RawSkillManifest[] = [
      {
        source: 'test',
        path: 'skills/git-committer/SKILL.md',
        content: '---\nname: Git Committer\ndescription: creates git commits and manages version control branches for deployment\n---\nCommits code.',
      },
    ]
    const result = await importSkillsFromManifests(manifests)
    expect(result.admitted.length).toBeGreaterThan(0)
  })
})

// ─── Ledger Persistence: SyntaxError on invalid JSON (L242 arm 1) ─

import { deserializeChain } from '../../src/ledger/persistence.js'
import { LedgerPersistenceError } from '../../src/ledger/persistence.js'

describe('deserializeChain: SyntaxError wrapped in LedgerPersistenceError (L242 arm 0)', () => {
  it('throws LedgerPersistenceError when JSON is invalid', async () => {
    // Invalid JSON → deserializeSnapshot catches SyntaxError → wraps as LedgerPersistenceError('Invalid JSON: ...')
    // → deserializeChain re-throws (arm 0: instanceof LedgerPersistenceError)
    await expect(deserializeChain('{invalid json')).rejects.toThrow(LedgerPersistenceError)
  })

  it('error message mentions invalid JSON', async () => {
    await expect(deserializeChain('not-json-at-all')).rejects.toThrow(/Invalid JSON/)
  })
})
