import {
  McmContractError,
  assertMcmDigest,
  type McmNodeObservationInputV1,
} from './mycorrhizal-contracts.js'

export const ONE_BNA_SOURCE_SHA256 =
  'df42f1506792f191b957227b061360652adcf6f813eb69d9ec553067ea584670' as const
export const ONE_BNA_V3_BENCHMARK_DIGEST =
  '0d23a1449c4110c11fe99809df1fd9bb55216d8b14eee75cdcff81f21f794276' as const
export const ONE_BNA_V4_CROSS_RUNTIME_DIGEST =
  'f8197fa4ee9d37fd81bd4f3d1d9391d8eff153aefc3d0ff5e0ecce2ade1d053a' as const

export const ONE_BNA_MCM_PROFILE_V1 = Object.freeze({
  calibrationBps: 6500,
  evidenceSupportBps: 9000,
  evidenceFreshnessBps: 8000,
  resourcePressureBps: 1000,
  contradictionPressureBps: 0,
  verificationDemandBps: 7500,
} as const)

export interface OneBnaMcmEvidenceBindingV1 {
  readonly sourceSha256: string
  readonly v3BenchmarkDigest: string
  readonly v4CrossRuntimeDigest: string
  readonly hotspotDigest?: string
  readonly nodeIdentityDigest: string
  readonly sensoriumObservationDigest: string
  readonly observationSequence: number
  readonly expectedParentStateRoot: string
  readonly topologyDigest: string
}

const FORBIDDEN_PROMOTION_KEYS = Object.freeze([
  'biologicalMechanismEstablished',
  'standard3dnaVerified',
  'authorityEffect',
  'observationTier',
  'authorityWeight',
  'mayGroundStateTransition',
  'admission',
  'effectReceipt',
  'providerInvocation',
  'leaseGrant',
  'fencingToken',
] as const)

function rejectPromotionFields(binding: OneBnaMcmEvidenceBindingV1): void {
  const record = binding as unknown as Record<string, unknown>
  for (const key of FORBIDDEN_PROMOTION_KEYS) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      throw new McmContractError(`1BNA evidence binding forbids promotion field ${key}`)
    }
  }
}

function assertExact1BnaEvidence(binding: OneBnaMcmEvidenceBindingV1): void {
  if (binding.sourceSha256 !== ONE_BNA_SOURCE_SHA256) {
    throw new McmContractError('1BNA source SHA-256 mismatch')
  }
  if (binding.v3BenchmarkDigest !== ONE_BNA_V3_BENCHMARK_DIGEST) {
    throw new McmContractError('1BNA V3 benchmark digest mismatch')
  }
  if (binding.v4CrossRuntimeDigest !== ONE_BNA_V4_CROSS_RUNTIME_DIGEST) {
    throw new McmContractError('1BNA V4 cross-runtime digest mismatch')
  }
  if (binding.hotspotDigest !== undefined) {
    assertMcmDigest('1BNA hotspotDigest', binding.hotspotDigest)
  }
}

function assertMcmBindingContext(binding: OneBnaMcmEvidenceBindingV1): void {
  assertMcmDigest('nodeIdentityDigest', binding.nodeIdentityDigest)
  assertMcmDigest('sensoriumObservationDigest', binding.sensoriumObservationDigest)
  assertMcmDigest('expectedParentStateRoot', binding.expectedParentStateRoot)
  assertMcmDigest('topologyDigest', binding.topologyDigest)
  if (!Number.isSafeInteger(binding.observationSequence) || binding.observationSequence < 0) {
    throw new McmContractError('observationSequence must be a non-negative safe integer')
  }
}

export function create1BnaMcmObservationInput(
  binding: OneBnaMcmEvidenceBindingV1,
): McmNodeObservationInputV1 {
  rejectPromotionFields(binding)
  assertExact1BnaEvidence(binding)
  assertMcmBindingContext(binding)

  const evidenceReferences = [
    `1bna:benchmark-v3:sha256:${ONE_BNA_V3_BENCHMARK_DIGEST}`,
    `1bna:cross-runtime-v4:sha256:${ONE_BNA_V4_CROSS_RUNTIME_DIGEST}`,
    `1bna:pdb:sha256:${ONE_BNA_SOURCE_SHA256}`,
  ]
  if (binding.hotspotDigest !== undefined) {
    evidenceReferences.push(`1bna:hotspot:sha256:${binding.hotspotDigest}`)
  }
  evidenceReferences.sort()

  return Object.freeze({
    nodeIdentityDigest: binding.nodeIdentityDigest,
    sensoriumObservationDigest: binding.sensoriumObservationDigest,
    observationSequence: binding.observationSequence,
    expectedParentStateRoot: binding.expectedParentStateRoot,
    topologyDigest: binding.topologyDigest,
    ...ONE_BNA_MCM_PROFILE_V1,
    evidenceReferences: Object.freeze(evidenceReferences),
  })
}
