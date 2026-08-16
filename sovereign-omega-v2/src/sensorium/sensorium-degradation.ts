import type { ConsequenceClass } from '../api/frontier-inference-gateway.js'
import type { SensoriumObservationV1 } from './sensorium-observation.js'

export type SensoriumRecommendation = 'UNCHANGED' | 'DEGRADED' | 'SUSPENDED'
export type SensoriumDegradationReason =
  | 'OBSERVATION_QUALITY_DEGRADED'
  | 'OBSERVATION_QUALITY_SUSPENDED'
  | 'CAPACITY_PRESSURE_DEGRADED'
  | 'CAPACITY_PRESSURE_SUSPENDED'
  | 'RETENTION_DEGRADED'
  | 'RETENTION_SUSPENDED'

export interface SensoriumDegradationV1 {
  readonly schemaVersion: '1.0.0'
  readonly authorityEffect: 'OBSERVATION_ONLY'
  readonly observationDigest: string
  readonly recommendation: SensoriumRecommendation
  readonly reasonCodes: readonly SensoriumDegradationReason[]
  readonly maxConsequenceClass: ConsequenceClass | null
  readonly validForObservationSequence: number
  readonly validForParentStateRoot: string
  readonly validForTopologyDigest: string
}

export interface ConsequenceCap {
  readonly recommendation: SensoriumRecommendation
  readonly maxConsequenceClass: ConsequenceClass | null
}

const CONSEQUENCE_ORDER: readonly ConsequenceClass[] = ['D0', 'D1', 'D2', 'D3', 'D4']
const RECOMMENDATION_RANK: Readonly<Record<SensoriumRecommendation, number>> = {
  UNCHANGED: 0,
  DEGRADED: 1,
  SUSPENDED: 2,
}

function consequenceRank(value: ConsequenceClass): number {
  const rank = CONSEQUENCE_ORDER.indexOf(value)
  if (rank < 0) throw new Error(`unsupported consequence class: ${String(value)}`)
  return rank
}

function maxRecommendation(values: readonly SensoriumRecommendation[]): SensoriumRecommendation {
  return values.reduce<SensoriumRecommendation>((current, candidate) =>
    RECOMMENDATION_RANK[candidate] > RECOMMENDATION_RANK[current] ? candidate : current,
  'UNCHANGED')
}

export function recommendSensoriumDegradation(observation: SensoriumObservationV1): SensoriumDegradationV1 {
  const recommendations: SensoriumRecommendation[] = []
  const reasonCodes: SensoriumDegradationReason[] = []

  if (observation.observationQualityBps < 5000) {
    recommendations.push('SUSPENDED')
    reasonCodes.push('OBSERVATION_QUALITY_SUSPENDED')
  } else if (observation.observationQualityBps < 8000) {
    recommendations.push('DEGRADED')
    reasonCodes.push('OBSERVATION_QUALITY_DEGRADED')
  }

  if (observation.capacityPressureBps >= 9500) {
    recommendations.push('SUSPENDED')
    reasonCodes.push('CAPACITY_PRESSURE_SUSPENDED')
  } else if (observation.capacityPressureBps >= 8000) {
    recommendations.push('DEGRADED')
    reasonCodes.push('CAPACITY_PRESSURE_DEGRADED')
  }

  if (observation.predictedNextRetentionBps < 4000) {
    recommendations.push('SUSPENDED')
    reasonCodes.push('RETENTION_SUSPENDED')
  } else if (observation.predictedNextRetentionBps < 7000) {
    recommendations.push('DEGRADED')
    reasonCodes.push('RETENTION_DEGRADED')
  }

  const recommendation = maxRecommendation(recommendations)
  const maxConsequenceClass: ConsequenceClass | null = recommendation === 'SUSPENDED'
    ? 'D0'
    : recommendation === 'DEGRADED'
      ? 'D1'
      : null

  return Object.freeze({
    schemaVersion: '1.0.0',
    authorityEffect: 'OBSERVATION_ONLY',
    observationDigest: observation.observationDigest,
    recommendation,
    reasonCodes: Object.freeze([...reasonCodes].sort()),
    maxConsequenceClass,
    validForObservationSequence: observation.observationSequence,
    validForParentStateRoot: observation.expectedParentStateRoot,
    validForTopologyDigest: observation.topologyDigest,
  })
}

export function applyConsequenceCap(admittedClass: ConsequenceClass, degradation: ConsequenceCap): ConsequenceClass {
  const admittedRank = consequenceRank(admittedClass)
  const expectedCap: ConsequenceClass | null = degradation.recommendation === 'UNCHANGED'
    ? null
    : degradation.recommendation === 'DEGRADED'
      ? 'D1'
      : 'D0'
  if (degradation.maxConsequenceClass !== expectedCap) {
    throw new Error('sensorium degradation recommendation/cap mismatch')
  }
  if (expectedCap === null) return admittedClass
  const capRank = consequenceRank(expectedCap)
  return CONSEQUENCE_ORDER[Math.min(admittedRank, capRank)]!
}
