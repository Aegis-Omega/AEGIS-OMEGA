// ============================================================
// Autopoietic Vision — Ontology Admission Proof
// ~10 tests: all five T4/T5-vision concepts now have complete
//   constitutional mappings and pass admitAbstraction().
//
// This is the constitutional proof that the user's vision of
// an "autopoietic swarm of metacognitive chatbots" has been
// fully reduced to T0/T2 substrate via Gates 34–38.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'
import {
  buildOntologyRecord,
  admitAbstraction,
  type OntologyInput,
} from '../../src/constitutional/reduction.js'

// ─── Helper ────────────────────────────────────────────────

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

// ─── Five vision concepts — now with complete mappings ──────
//
// These five inputs correspond to Gates 34–38 respectively.
// Before those gates, admitAbstraction() would reject them
// because the constitutional substrate to ground the mappings
// did not exist. Now it does.

const CONCEPTS: OntologyInput[] = [
  {
    name: 'SwarmConvergenceProtocol',   // Gate 34 — "swarm"
    primitive_mapping: 'VERIFY',
    replay_mapping: 'LOCK',
    topology_mapping: 'CONSENSUS',
    epistemic_tier: 'T2',
    sequence: seq(34),
  },
  {
    name: 'SelfAttestationProtocol',    // Gate 35 — "autopoietic"
    primitive_mapping: 'HASH',
    replay_mapping: 'HARMONIZE',
    topology_mapping: 'DFA',
    epistemic_tier: 'T0',
    sequence: seq(35),
  },
  {
    name: 'GovernanceMirrorStream',     // Gate 36 — "metacognitive"
    primitive_mapping: 'CANONICALIZE',
    replay_mapping: 'PROPAGATE',
    topology_mapping: 'LINEAGE',
    epistemic_tier: 'T1',
    sequence: seq(36),
  },
  {
    name: 'CapabilityEvolutionProtocol', // Gate 37 — "all-capable/plug-and-play"
    primitive_mapping: 'SEQUENCE',
    replay_mapping: 'ASSESS',
    topology_mapping: 'DFA',
    epistemic_tier: 'T2',
    sequence: seq(37),
  },
  {
    name: 'AdaptiveLineage',            // Gate 38 — "harmoniously evolves"
    primitive_mapping: 'HASH',
    replay_mapping: 'HARMONIZE',
    topology_mapping: 'LINEAGE',
    epistemic_tier: 'T2',
    sequence: seq(38),
  },
]

// ─── Admission proof ───────────────────────────────────────

describe('autopoietic vision — constitutional admission', () => {
  it('all five concepts build valid OntologyRecords', async () => {
    for (const concept of CONCEPTS) {
      const record = await buildOntologyRecord(concept)
      expect(record.abstraction_id).toHaveLength(64)
      expect(record.is_replay_reconstructable).toBe(true)
    }
  })

  it('SwarmConvergenceProtocol (Gate 34) → ADMITTED', async () => {
    const record = await buildOntologyRecord(CONCEPTS[0]!)
    const result = await admitAbstraction([], record)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('SelfAttestationProtocol (Gate 35) → ADMITTED', async () => {
    const record = await buildOntologyRecord(CONCEPTS[1]!)
    const result = await admitAbstraction([], record)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('GovernanceMirrorStream (Gate 36) → ADMITTED', async () => {
    const record = await buildOntologyRecord(CONCEPTS[2]!)
    const result = await admitAbstraction([], record)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('CapabilityEvolutionProtocol (Gate 37) → ADMITTED', async () => {
    const record = await buildOntologyRecord(CONCEPTS[3]!)
    const result = await admitAbstraction([], record)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('AdaptiveLineage (Gate 38) → ADMITTED', async () => {
    const record = await buildOntologyRecord(CONCEPTS[4]!)
    const result = await admitAbstraction([], record)
    expect(result.verdict).toBe('ADMITTED')
  })

  it('all five chain into a registry without rejection', async () => {
    const existing = []
    for (const concept of CONCEPTS) {
      const record = await buildOntologyRecord(concept)
      const result = await admitAbstraction(existing, record)
      expect(result.verdict).toBe('ADMITTED')
      existing.push(record)
    }
    expect(existing).toHaveLength(5)
  })

  it('all five results are frozen and replay-reconstructable', async () => {
    for (const concept of CONCEPTS) {
      const record = await buildOntologyRecord(concept)
      const result = await admitAbstraction([], record)
      expect(Object.isFrozen(result)).toBe(true)
      expect(result.is_replay_reconstructable).toBe(true)
    }
  })
})
