import { hashValue } from '../core/hashing.js'
import {
  MCM_AUTHORITY_EFFECT,
  MCM_AUTHORITY_WEIGHT,
  MCM_MAY_GROUND_STATE_TRANSITION,
  MCM_OBSERVATION_TIER,
  McmContractError,
  assertMcmDigest,
} from './mycorrhizal-contracts.js'

export const STRUCTURAL_WITNESS_SCHEMA_VERSION = '1.0.0' as const
export const STRUCTURAL_METRIC_SCHEMA_DNA_GEOMETRY_V1 = 'AEGIS_DNA_GEOMETRY_METRICS_V1' as const

export type StructuralWitnessEvidenceOriginV1 =
  | 'SOURCE_BOUND_STRUCTURE'
  | 'SYNTHETIC_TEST_FIXTURE'

export type StructuralEvidenceClassV1 =
  | 'SINGLE_STRUCTURE_EVIDENCE'
  | 'CROSS_STRUCTURE_EVIDENCE'

export interface StructuralWitnessInputV1 {
  readonly structureIdentity: string
  readonly sourceDigest: string
  readonly benchmarkDigest: string
  readonly crossRuntimeDigest: string
  readonly metricSchema: string
  readonly evidenceOrigin: StructuralWitnessEvidenceOriginV1
}

interface CanonicalStructuralWitnessV1 extends StructuralWitnessInputV1 {
  readonly schemaVersion: typeof STRUCTURAL_WITNESS_SCHEMA_VERSION
  readonly witnessDigest: string
}

export interface StructuralWitnessRegistryV1 {
  readonly schemaVersion: typeof STRUCTURAL_WITNESS_SCHEMA_VERSION
  readonly authorityEffect: typeof MCM_AUTHORITY_EFFECT
  readonly observationTier: typeof MCM_OBSERVATION_TIER
  readonly authorityWeight: typeof MCM_AUTHORITY_WEIGHT
  readonly mayGroundStateTransition: typeof MCM_MAY_GROUND_STATE_TRANSITION
  readonly evidenceClass: StructuralEvidenceClassV1
  readonly crossStructureEvidenceEstablished: boolean
  readonly uniqueWitnessCount: number
  readonly sourceBoundWitnessCount: number
  readonly syntheticFixtureCount: number
  readonly distinctSourceDigestCount: number
  readonly distinctStructureIdentityCount: number
  readonly compatibleMetricSchema: string | null
  readonly witnessDigests: readonly string[]
  readonly registryRoot: string
}

const FORBIDDEN_PROMOTION_KEYS = Object.freeze([
  'authorityEffect',
  'observationTier',
  'authorityWeight',
  'mayGroundStateTransition',
  'biologicalMechanismEstablished',
  'standard3dnaVerified',
  'admission',
  'effectReceipt',
] as const)

function assertCanonicalLabel(name: string, value: string): void {
  if (typeof value !== 'string' || value.length === 0 || value.trim() !== value) {
    throw new McmContractError(`${name} must be a non-empty canonical string`)
  }
}

function validateWitnessInput(input: StructuralWitnessInputV1): void {
  const record = input as unknown as Record<string, unknown>
  for (const key of FORBIDDEN_PROMOTION_KEYS) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      throw new McmContractError(`structural witness forbids promotion field ${key}`)
    }
  }

  assertCanonicalLabel('structureIdentity', input.structureIdentity)
  assertCanonicalLabel('metricSchema', input.metricSchema)
  assertMcmDigest('sourceDigest', input.sourceDigest)
  assertMcmDigest('benchmarkDigest', input.benchmarkDigest)
  assertMcmDigest('crossRuntimeDigest', input.crossRuntimeDigest)

  if (input.evidenceOrigin !== 'SOURCE_BOUND_STRUCTURE' &&
      input.evidenceOrigin !== 'SYNTHETIC_TEST_FIXTURE') {
    throw new McmContractError('evidenceOrigin must be SOURCE_BOUND_STRUCTURE or SYNTHETIC_TEST_FIXTURE')
  }
}

async function canonicalWitness(input: StructuralWitnessInputV1): Promise<CanonicalStructuralWitnessV1> {
  validateWitnessInput(input)
  const payload = Object.freeze({
    schemaVersion: STRUCTURAL_WITNESS_SCHEMA_VERSION,
    structureIdentity: input.structureIdentity,
    sourceDigest: input.sourceDigest,
    benchmarkDigest: input.benchmarkDigest,
    crossRuntimeDigest: input.crossRuntimeDigest,
    metricSchema: input.metricSchema,
    evidenceOrigin: input.evidenceOrigin,
  })
  const witnessDigest = await hashValue(payload)
  return Object.freeze({ ...payload, witnessDigest })
}

function assertNoSourceIdentityLaundering(witnesses: readonly CanonicalStructuralWitnessV1[]): void {
  const sourceToIdentity = new Map<string, string>()
  for (const witness of witnesses) {
    const prior = sourceToIdentity.get(witness.sourceDigest)
    if (prior !== undefined && prior !== witness.structureIdentity) {
      throw new McmContractError('source digest cannot map to multiple structure identities')
    }
    sourceToIdentity.set(witness.sourceDigest, witness.structureIdentity)
  }
}

export async function createStructuralWitnessRegistry(
  inputs: readonly StructuralWitnessInputV1[],
): Promise<StructuralWitnessRegistryV1> {
  if (inputs.length < 1) {
    throw new McmContractError('structural witness registry requires at least one witness')
  }

  const hashed = await Promise.all(inputs.map(canonicalWitness))
  const uniqueByDigest = new Map<string, CanonicalStructuralWitnessV1>()
  for (const witness of hashed) {
    uniqueByDigest.set(witness.witnessDigest, witness)
  }
  const unique = [...uniqueByDigest.values()].sort((a, b) =>
    a.witnessDigest.localeCompare(b.witnessDigest))

  assertNoSourceIdentityLaundering(unique)

  const sourceBound = unique.filter(witness => witness.evidenceOrigin === 'SOURCE_BOUND_STRUCTURE')
  const syntheticFixtureCount = unique.length - sourceBound.length
  if (sourceBound.length < 1) {
    throw new McmContractError('structural witness registry requires at least one source-bound structure')
  }

  const distinctSourceDigestCount = new Set(sourceBound.map(witness => witness.sourceDigest)).size
  const distinctStructureIdentityCount = new Set(sourceBound.map(witness => witness.structureIdentity)).size
  const metricSchemas = [...new Set(sourceBound.map(witness => witness.metricSchema))].sort()
  const compatibleMetricSchema = metricSchemas.length === 1 ? metricSchemas[0]! : null

  const crossStructureEvidenceEstablished =
    distinctSourceDigestCount >= 2 &&
    distinctStructureIdentityCount >= 2 &&
    compatibleMetricSchema !== null
  const evidenceClass: StructuralEvidenceClassV1 = crossStructureEvidenceEstablished
    ? 'CROSS_STRUCTURE_EVIDENCE'
    : 'SINGLE_STRUCTURE_EVIDENCE'
  const witnessDigests = Object.freeze(unique.map(witness => witness.witnessDigest))

  const registryPayload = Object.freeze({
    schemaVersion: STRUCTURAL_WITNESS_SCHEMA_VERSION,
    authorityEffect: MCM_AUTHORITY_EFFECT,
    observationTier: MCM_OBSERVATION_TIER,
    authorityWeight: MCM_AUTHORITY_WEIGHT,
    mayGroundStateTransition: MCM_MAY_GROUND_STATE_TRANSITION,
    evidenceClass,
    crossStructureEvidenceEstablished,
    uniqueWitnessCount: unique.length,
    sourceBoundWitnessCount: sourceBound.length,
    syntheticFixtureCount,
    distinctSourceDigestCount,
    distinctStructureIdentityCount,
    compatibleMetricSchema,
    witnessDigests,
  })
  const registryRoot = await hashValue(registryPayload)

  return Object.freeze({ ...registryPayload, registryRoot })
}
