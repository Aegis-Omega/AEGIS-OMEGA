import { describe, expect, it } from 'vitest'
import {
  MCM_AUTHORITY_EFFECT,
  MCM_AUTHORITY_WEIGHT,
  MCM_MAY_GROUND_STATE_TRANSITION,
  MCM_OBSERVATION_TIER,
} from '../../src/metacognition/mycorrhizal-contracts.js'
import {
  ONE_BNA_SOURCE_SHA256,
  ONE_BNA_V3_BENCHMARK_DIGEST,
  ONE_BNA_V4_CROSS_RUNTIME_DIGEST,
} from '../../src/metacognition/mycorrhizal-1bna.js'
import {
  STRUCTURAL_METRIC_SCHEMA_DNA_GEOMETRY_V1,
  createStructuralWitnessRegistry,
  type StructuralWitnessInputV1,
} from '../../src/metacognition/mycorrhizal-structural-witness-registry.js'

const d = (c: string): string => c.repeat(64)

function oneBna(overrides: Partial<StructuralWitnessInputV1> = {}): StructuralWitnessInputV1 {
  return {
    structureIdentity: 'pdb:1BNA',
    sourceDigest: ONE_BNA_SOURCE_SHA256,
    benchmarkDigest: ONE_BNA_V3_BENCHMARK_DIGEST,
    crossRuntimeDigest: ONE_BNA_V4_CROSS_RUNTIME_DIGEST,
    metricSchema: STRUCTURAL_METRIC_SCHEMA_DNA_GEOMETRY_V1,
    evidenceOrigin: 'SOURCE_BOUND_STRUCTURE',
    ...overrides,
  }
}

function sourceBoundFixture(
  structureIdentity: string,
  sourceDigest: string,
  benchmarkDigest: string,
  crossRuntimeDigest: string,
  metricSchema: string = STRUCTURAL_METRIC_SCHEMA_DNA_GEOMETRY_V1,
): StructuralWitnessInputV1 {
  return {
    structureIdentity,
    sourceDigest,
    benchmarkDigest,
    crossRuntimeDigest,
    metricSchema,
    evidenceOrigin: 'SOURCE_BOUND_STRUCTURE',
  }
}

function syntheticFixture(structureIdentity: string, seed: string): StructuralWitnessInputV1 {
  return {
    structureIdentity,
    sourceDigest: d(seed),
    benchmarkDigest: d(seed === 'a' ? 'b' : 'c'),
    crossRuntimeDigest: d(seed === 'a' ? 'd' : 'e'),
    metricSchema: STRUCTURAL_METRIC_SCHEMA_DNA_GEOMETRY_V1,
    evidenceOrigin: 'SYNTHETIC_TEST_FIXTURE',
  }
}

describe('Mycorrhizal structural witness registry', () => {
  it('keeps the real 1BNA corpus at SINGLE_STRUCTURE_EVIDENCE with zero authority', async () => {
    const registry = await createStructuralWitnessRegistry([oneBna()])
    expect(registry.evidenceClass).toBe('SINGLE_STRUCTURE_EVIDENCE')
    expect(registry.crossStructureEvidenceEstablished).toBe(false)
    expect(registry.sourceBoundWitnessCount).toBe(1)
    expect(registry.distinctSourceDigestCount).toBe(1)
    expect(registry.distinctStructureIdentityCount).toBe(1)
    expect(registry.authorityEffect).toBe(MCM_AUTHORITY_EFFECT)
    expect(registry.observationTier).toBe(MCM_OBSERVATION_TIER)
    expect(registry.authorityWeight).toBe(MCM_AUTHORITY_WEIGHT)
    expect(registry.mayGroundStateTransition).toBe(MCM_MAY_GROUND_STATE_TRANSITION)
  })

  it('deduplicates byte-identical witness copies instead of counting them as replication', async () => {
    const witness = oneBna()
    const registry = await createStructuralWitnessRegistry([witness, { ...witness }])
    expect(registry.uniqueWitnessCount).toBe(1)
    expect(registry.sourceBoundWitnessCount).toBe(1)
    expect(registry.evidenceClass).toBe('SINGLE_STRUCTURE_EVIDENCE')
  })

  it('fails closed when one source digest is laundered as two structure identities', async () => {
    await expect(createStructuralWitnessRegistry([
      oneBna(),
      oneBna({ structureIdentity: 'pdb:FAKE_SECOND_STRUCTURE' }),
    ])).rejects.toThrow(/source digest.*multiple structure identities/i)
  })

  it('does not count a second benchmark of the same structure as cross-structure evidence', async () => {
    const registry = await createStructuralWitnessRegistry([
      oneBna(),
      oneBna({
        sourceDigest: d('1'),
        benchmarkDigest: d('2'),
        crossRuntimeDigest: d('3'),
      }),
    ])
    expect(registry.distinctSourceDigestCount).toBe(2)
    expect(registry.distinctStructureIdentityCount).toBe(1)
    expect(registry.evidenceClass).toBe('SINGLE_STRUCTURE_EVIDENCE')
    expect(registry.crossStructureEvidenceEstablished).toBe(false)
  })

  it('implementation logic marks two distinct source-bound structures cross-eligible only under one metric schema', async () => {
    const registry = await createStructuralWitnessRegistry([
      oneBna(),
      sourceBoundFixture('pdb:FIXTURE2', d('1'), d('2'), d('3')),
    ])
    expect(registry.distinctSourceDigestCount).toBe(2)
    expect(registry.distinctStructureIdentityCount).toBe(2)
    expect(registry.compatibleMetricSchema).toBe(STRUCTURAL_METRIC_SCHEMA_DNA_GEOMETRY_V1)
    expect(registry.evidenceClass).toBe('CROSS_STRUCTURE_EVIDENCE')
    expect(registry.crossStructureEvidenceEstablished).toBe(true)
  })

  it('incompatible metric schemas cannot establish cross-structure evidence', async () => {
    const registry = await createStructuralWitnessRegistry([
      oneBna(),
      sourceBoundFixture('pdb:FIXTURE2', d('1'), d('2'), d('3'), 'AEGIS_INCOMPATIBLE_METRICS_V1'),
    ])
    expect(registry.compatibleMetricSchema).toBeNull()
    expect(registry.evidenceClass).toBe('SINGLE_STRUCTURE_EVIDENCE')
    expect(registry.crossStructureEvidenceEstablished).toBe(false)
  })

  it('synthetic fixtures can exercise transition logic but never establish scientific cross-structure evidence', async () => {
    const registry = await createStructuralWitnessRegistry([
      oneBna(),
      syntheticFixture('fixture:alpha', 'a'),
      syntheticFixture('fixture:beta', 'b'),
    ])
    expect(registry.syntheticFixtureCount).toBe(2)
    expect(registry.sourceBoundWitnessCount).toBe(1)
    expect(registry.distinctStructureIdentityCount).toBe(1)
    expect(registry.evidenceClass).toBe('SINGLE_STRUCTURE_EVIDENCE')
    expect(registry.crossStructureEvidenceEstablished).toBe(false)
  })

  it('is order-invariant and binds registryRoot to the canonical unique witness set', async () => {
    const second = sourceBoundFixture('pdb:FIXTURE2', d('1'), d('2'), d('3'))
    const left = await createStructuralWitnessRegistry([oneBna(), second])
    const right = await createStructuralWitnessRegistry([second, oneBna(), oneBna()])
    expect(right.registryRoot).toBe(left.registryRoot)
    expect(right.witnessDigests).toEqual(left.witnessDigests)
  })
})
