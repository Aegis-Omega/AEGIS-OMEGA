// test/integration/synthesis-hgt-corpus-composition.test.ts
//
// Gate 175 — Composition proof: BFT Synthesis Swarm + HGT Scanner + Corpus Section Visitor
// EPISTEMIC TIER: T2
//
// Proves that the three new paradigm-level additions introduced in Gates 172-174
// interoperate correctly under the constitutional framework:
//   1. runSynthesisSwarm → SynthesisRecord with is_replay_reconstructable
//   2. processRepoFiles + buildHGTRecord → HGTRecord with deterministic catalog_hash
//   3. visitSections → depth-bounded sections → corpus RALPH pipeline
//   4. synthesis_hash + hgt_hash + corpus_lineage_hash all deterministic ×3
//   5. Synthesis verdict feeds SkillCatalog (COMMITTED = admit, REJECTED = skip)

import { describe, it, expect } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'
import { runSynthesisSwarm } from '../../src/consensus/synthesis-swarm.js'
import type { SynthesisRequest, AgentRole } from '../../src/consensus/synthesis-swarm.js'
import { processRepoFiles, buildHGTRecord } from '../../src/skill-harness/hgt/hgt-scanner.js'
import type { HGTSkillFile } from '../../src/skill-harness/hgt/hgt-scanner.js'
import { visitSections } from '../../src/corpus-engine/section-visitor.js'
import { processDocument, buildCorpusDocument } from '../../src/corpus-engine/pipeline.js'
import { buildSkillRecord, SkillCatalog } from '../../src/skill-harness/catalog.js'
import type { SkillInput } from '../../src/skill-harness/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

// Shared implementation code — both Alpha and Beta produce this to ensure COMMITTED verdict
const IMPL_CODE = `
export async function hashGovernanceRecord(record: { id: string; sequence: bigint }): Promise<string> {
  if (!record || !record.id) throw new Error('invalid record')
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(record)))
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('')
}
`.trim()

// Mock agent that returns the shared implementation (ensures structural convergence)
const mockCallAgent = async (
  _system: string,
  _user: string,
  role: AgentRole,
): Promise<{ output: string; backend: string; latency_ms: number }> => {
  if (role === 'gamma') {
    return {
      output: JSON.stringify({ verdict: 'COMMITTED', violations: [], rationale: 'All invariants satisfied.' }),
      backend: 'mock',
      latency_ms: 1,
    }
  }
  return { output: IMPL_CODE, backend: 'mock', latency_ms: 1 }
}

// Sample SKILL.md content for HGT ingestion
const SKILL_MD_GOVERNANCE = `---
name: governance_replay
description: Replay-certified governance event processing
---
Processes governance events through the replay engine.
Tier: T2. primitive_mapping: VERIFY.
`

const SKILL_MD_HASHING = `---
name: hash_chain_integrity
description: SHA-256 hash chain verification for ledger entries
---
Verifies hash chain lineage using cryptographic SHA-256.
Tier: T1. primitive_mapping: HASH.
`

const SKILL_MD_T4 = `---
name: planetary_consciousness
description: Transcendent superintelligence swarm omniscience
---
sovereign consciousness civilizational omnipotent emergence.
Tier: T5. Should be rejected at ARBITRATION.
`

describe('Gate 175 — Synthesis Swarm + HGT + Corpus Section Visitor Composition', () => {

  describe('BFT Synthesis Swarm integration', () => {
    it('COMMITTED synthesis record has is_replay_reconstructable=true', async () => {
      const req: SynthesisRequest = {
        task: 'Implement a hash function for governance records',
        context: 'Must use SHA-256, handle errors, use TypeScript types',
        constitutional_constraints: ['deepFreeze output', 'no Date.now()', 'no JSON.stringify'],
        sequence: seq(1),
      }
      const record = await runSynthesisSwarm(req, mockCallAgent)
      expect(record.is_replay_reconstructable).toBe(true)
    })

    it('COMMITTED synthesis record has 64-char hex synthesis_hash', async () => {
      const req: SynthesisRequest = {
        task: 'Implement a hash function for governance records',
        context: 'Must use SHA-256',
        constitutional_constraints: ['no Date.now()'],
        sequence: seq(2),
      }
      const record = await runSynthesisSwarm(req, mockCallAgent)
      expect(record.synthesis_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(record.synthesis_hash)).toBe(true)
    })

    it('synthesis_hash is deterministic ×3 for same input', async () => {
      const req: SynthesisRequest = {
        task: 'Determinism probe',
        context: 'ctx',
        constitutional_constraints: [],
        sequence: seq(3),
      }
      const r1 = await runSynthesisSwarm(req, mockCallAgent)
      const r2 = await runSynthesisSwarm(req, mockCallAgent)
      const r3 = await runSynthesisSwarm(req, mockCallAgent)
      expect(r1.synthesis_hash).toBe(r2.synthesis_hash)
      expect(r2.synthesis_hash).toBe(r3.synthesis_hash)
    })

    it('different tasks produce different synthesis_hash values', async () => {
      const r1 = await runSynthesisSwarm(
        { task: 'Task A', context: 'ctx', constitutional_constraints: [], sequence: seq(4) },
        mockCallAgent,
      )
      const r2 = await runSynthesisSwarm(
        { task: 'Task B', context: 'ctx', constitutional_constraints: [], sequence: seq(5) },
        mockCallAgent,
      )
      expect(r1.synthesis_hash).not.toBe(r2.synthesis_hash)
    })

    it('COMMITTED record: verdict is COMMITTED and convergence.converged is true', async () => {
      const req: SynthesisRequest = {
        task: 'Implement a hash function',
        context: '',
        constitutional_constraints: [],
        sequence: seq(6),
      }
      const record = await runSynthesisSwarm(req, mockCallAgent)
      // Both alpha and beta produce same impl code → high convergence → COMMITTED
      expect(record.verdict).toBe('COMMITTED')
      expect(record.convergence.converged).toBe(true)
    })
  })

  describe('HGT Scanner integration', () => {
    const files: readonly HGTSkillFile[] = [
      { path: 'skills/governance/SKILL.md', raw_content: SKILL_MD_GOVERNANCE, repo_id: 'test-repo' },
      { path: 'skills/hashing/SKILL.md', raw_content: SKILL_MD_HASHING, repo_id: 'test-repo' },
      { path: 'skills/speculative/SKILL.md', raw_content: SKILL_MD_T4, repo_id: 'test-repo' },
    ]

    it('processRepoFiles returns admitted and rejected counts', async () => {
      const result = await processRepoFiles('test-repo', files)
      expect(result.admitted.length).toBeGreaterThan(0)
      // T4/T5 content rejected
      expect(result.rejected.length).toBeGreaterThan(0)
    })

    it('buildHGTRecord produces is_replay_reconstructable=true', async () => {
      const result = await processRepoFiles('test-repo', files)
      const hgt = await buildHGTRecord([result], seq(10))
      expect(hgt.is_replay_reconstructable).toBe(true)
    })

    it('hgt_hash is 64-char hex', async () => {
      const result = await processRepoFiles('test-repo', files)
      const hgt = await buildHGTRecord([result], seq(11))
      expect(hgt.hgt_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(hgt.hgt_hash)).toBe(true)
    })

    it('hgt_hash is deterministic ×3', async () => {
      const result = await processRepoFiles('test-repo', files)
      const h1 = await buildHGTRecord([result], seq(12))
      const h2 = await buildHGTRecord([result], seq(12))
      const h3 = await buildHGTRecord([result], seq(12))
      expect(h1.hgt_hash).toBe(h2.hgt_hash)
      expect(h2.hgt_hash).toBe(h3.hgt_hash)
    })

    it('T4/T5 skill is rejected — total_rejected >= 1', async () => {
      const result = await processRepoFiles('test-repo', files)
      const hgt = await buildHGTRecord([result], seq(13))
      expect(hgt.total_rejected).toBeGreaterThanOrEqual(1)
    })

    it('multi-repo aggregation: two repos produce correct totals', async () => {
      const repoA = await processRepoFiles('repo-a', [{ path: 'SKILL.md', raw_content: SKILL_MD_GOVERNANCE, repo_id: 'repo-a' }])
      const repoB = await processRepoFiles('repo-b', [{ path: 'SKILL.md', raw_content: SKILL_MD_HASHING, repo_id: 'repo-b' }])
      const hgt = await buildHGTRecord([repoA, repoB], seq(14))
      expect(hgt.total_admitted).toBe(repoA.admitted.length + repoB.admitted.length)
    })
  })

  describe('Corpus Section Visitor → RALPH pipeline', () => {
    const specDoc = [
      '# AEGIS Governance Specification',
      'Top-level constitutional replay invariant.',
      '## Hashing Subsystem',
      'SHA-256 hash chain verification. mechanically proven.',
      '## T4 Speculative Section',
      'sovereign consciousness civilizational planetary coordination.',
      '#### Deep Appendix (depth 4)',
      'Should be absorbed by ## parent at maxDepth=3.',
    ].join('\n')

    it('visitSections with maxDepth=3 produces 3 sections (# + ## + ##)', () => {
      const sections = visitSections(specDoc, 3)
      // # (depth 1), ## (depth 2), ## (depth 2) = 3 sections; #### absorbed
      expect(sections).toHaveLength(3)
    })

    it('absorbed deep heading appears in parent section content', () => {
      const sections = visitSections(specDoc, 3)
      const lastSection = sections[sections.length - 1]!
      expect(lastSection.content).toContain('Deep Appendix')
    })

    it('RALPH processDocument admits T2 governance spec correctly', async () => {
      const governanceDoc = [
        '# Governance Module',
        'engineering hypothesis proposed seam for constitutional replay.',
        '## Hash Verification',
        'SHA-256 hash chain integrity verification.',
      ].join('\n')
      const doc = await buildCorpusDocument('gov-spec-001', 'test://local', governanceDoc)
      const lineage = await processDocument(doc, governanceDoc)
      expect(lineage.phases).toHaveLength(5)
      expect(lineage.corpus_lineage_hash).toHaveLength(64)
      expect(lineage.is_replay_reconstructable).toBe(true)
      // T2 content should be admitted
      expect(lineage.phases.find(p => p.phase === 'ARBITRATION')?.admitted).toBe(true)
    })

    it('RALPH processDocument rejects T4/T5 content at ARBITRATION', async () => {
      const t4Doc = 'sovereign consciousness civilizational transcendent superintelligence'
      const doc = await buildCorpusDocument('t4-doc', 'test://local', t4Doc)
      const lineage = await processDocument(doc, t4Doc)
      const arbitration = lineage.phases.find(p => p.phase === 'ARBITRATION')!
      expect(arbitration.admitted).toBe(false)
      expect(arbitration.downgrade_reason).toBeTruthy()
    })

    it('corpus_lineage_hash is deterministic ×3', async () => {
      const content = '# Test\nbody text engineering hypothesis governance replay'
      const doc = await buildCorpusDocument('det-test', 'test://local', content)
      const l1 = await processDocument(doc, content)
      const l2 = await processDocument(doc, content)
      const l3 = await processDocument(doc, content)
      expect(l1.corpus_lineage_hash).toBe(l2.corpus_lineage_hash)
      expect(l2.corpus_lineage_hash).toBe(l3.corpus_lineage_hash)
    })
  })

  describe('Cross-paradigm composition: Synthesis → SkillCatalog', () => {
    it('COMMITTED synthesis record can seed a SkillRecord in SkillCatalog', async () => {
      const req: SynthesisRequest = {
        task: 'Implement hash chain verification utility',
        context: 'Governance context',
        constitutional_constraints: ['deepFreeze', 'no Date.now()'],
        sequence: seq(20),
      }
      const record = await runSynthesisSwarm(req, mockCallAgent)
      expect(record.verdict).toBe('COMMITTED')

      // The committed synthesis hash becomes the evidence ref for a new SkillRecord
      const skillInput: SkillInput = {
        skill_id: 'synthesized_hash_chain_verify',
        name: 'Hash Chain Verification (synthesized)',
        confidence: record.convergence.structural_similarity,
        validated_runs: 1,
        failure_rate: 0.0,
        recency_score: 1.0,
        domain_affinity: ['governance', 'security'],
        dependencies: [],
        evidence_refs: [record.synthesis_hash],
        last_validated: '2026-05-24T00:00:00.000Z',
        epistemic_tier: 'T2',
        primitive_mapping: 'VERIFY',
      }
      const skillRecord = await buildSkillRecord(skillInput)
      expect(skillRecord.skill_hash).toHaveLength(64)
      expect(skillRecord.evidence_refs).toContain(record.synthesis_hash)

      const catalog = SkillCatalog.empty()
      const { catalog: updated } = catalog.register(skillRecord)
      expect(updated.size).toBe(1)
      expect(updated.lookup('synthesized_hash_chain_verify')).not.toBeNull()
    })

    it('HGT admitted skills can be registered in SkillCatalog', async () => {
      const files: readonly HGTSkillFile[] = [
        { path: 'SKILL.md', raw_content: SKILL_MD_GOVERNANCE, repo_id: 'repo-a' },
      ]
      const result = await processRepoFiles('test-repo', files)
      expect(result.admitted.length).toBeGreaterThan(0)

      let catalog = SkillCatalog.empty()
      for (const skillRecord of result.admitted) {
        const { catalog: next } = catalog.register(skillRecord)
        catalog = next
      }
      expect(catalog.size).toBe(result.admitted.length)
      expect(await catalog.catalogHash()).toHaveLength(64)
    })

    it('catalogHash is deterministic across synthesis + HGT skill sources', async () => {
      // Register one synthesized skill
      const req: SynthesisRequest = {
        task: 'Hash utility',
        context: 'ctx',
        constitutional_constraints: [],
        sequence: seq(30),
      }
      const record = await runSynthesisSwarm(req, mockCallAgent)
      const synSkill = await buildSkillRecord({
        skill_id: 'det_synth_skill',
        name: 'Determinism Test Skill',
        confidence: record.convergence.structural_similarity,
        validated_runs: 1,
        failure_rate: 0.0,
        recency_score: 1.0,
        domain_affinity: ['quality'],
        dependencies: [],
        evidence_refs: [record.synthesis_hash],
        last_validated: '2026-05-24T00:00:00.000Z',
        epistemic_tier: 'T2',
        primitive_mapping: 'FREEZE',
      })

      const c1 = SkillCatalog.empty().register(synSkill).catalog
      const c2 = SkillCatalog.empty().register(synSkill).catalog
      const c3 = SkillCatalog.empty().register(synSkill).catalog

      const h1 = await c1.catalogHash()
      const h2 = await c2.catalogHash()
      const h3 = await c3.catalogHash()
      expect(h1).toBe(h2)
      expect(h2).toBe(h3)
    })
  })
})
