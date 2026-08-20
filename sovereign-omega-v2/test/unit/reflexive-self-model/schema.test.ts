import { readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, test } from 'vitest'

const schemaRoot = path.resolve(process.cwd(), '..', 'schemas', 'reflexive-self-model')
const load = (name: string): Record<string, any> =>
  JSON.parse(readFileSync(path.join(schemaRoot, name), 'utf8'))

function closedObjects(value: unknown, at = '$'): string[] {
  if (!value || typeof value !== 'object') return []
  const obj = value as Record<string, unknown>
  const errors: string[] = []
  if (obj.type === 'object' && obj.additionalProperties !== false) errors.push(`${at}:open`)
  for (const [key, child] of Object.entries(obj)) {
    errors.push(...closedObjects(child, `${at}.${key}`))
  }
  return errors
}

const cases = [
  ['self-model-snapshot-v1.schema.json', 'record_kind', 'SELF_MODEL_SNAPSHOT_V1', 'SELF_MODEL_EVIDENCE_ONLY'],
  ['self-prediction-v1.schema.json', 'record_kind', 'SELF_PREDICTION_V1', 'PREDICTION_EVIDENCE_ONLY'],
  ['self-observation-v1.schema.json', 'record_kind', 'SELF_OBSERVATION_V1', 'OBSERVATION_EVIDENCE_ONLY'],
  ['prediction-error-receipt-v1.schema.json', 'record_kind', 'PREDICTION_ERROR_RECEIPT_V1', 'CALIBRATION_EVIDENCE_ONLY'],
  ['self-model-update-proposal-v1.schema.json', 'record_kind', 'SELF_MODEL_UPDATE_PROPOSAL_V1', 'UPDATE_PROPOSAL_ONLY'],
  ['reflexive-cycle-receipt-v1.schema.json', 'record_kind', 'REFLEXIVE_CYCLE_RECEIPT_V1', 'REFLEXIVE_EVIDENCE_ONLY'],
] as const

const forbidden = [
  'permit', 'execute', 'effect', 'admission', 'capability_grant',
  'policy_mutation', 'tier_promotion', 'consciousness_proved',
]

describe('REFLEXIVE_SELF_MODEL_V1 schemas', () => {
  test.each(cases)('%s is a closed nominal Draft 2020-12 evidence contract', (file, kindField, kind, authority) => {
    const schema = load(file)
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema')
    expect(schema.type).toBe('object')
    expect(schema.additionalProperties).toBe(false)
    expect(closedObjects(schema)).toEqual([])
    expect(schema.properties[kindField].const).toBe(kind)
    expect(schema.properties.authority.const).toBe(authority)
    for (const field of forbidden) expect(schema.properties[field]).toBeUndefined()
  })

  test('prediction schema fixes the five V1 clause kinds and exact 0..10000 bps bounds', () => {
    const schema = load('self-prediction-v1.schema.json')
    const clauses = schema.properties.clauses.items
    const kinds = clauses.oneOf.map((entry: any) => entry.properties.kind.const)
    expect(new Set(kinds)).toEqual(new Set([
      'BOOLEAN', 'EXACT_STRING', 'SHA256_DIGEST', 'INTEGER_RANGE', 'BPS_INTERVAL',
    ]))
    for (const entry of clauses.oneOf) {
      expect(entry.properties.weight_bps.minimum).toBe(0)
      expect(entry.properties.weight_bps.maximum).toBe(10000)
      expect(entry.properties.confidence_bps.minimum).toBe(0)
      expect(entry.properties.confidence_bps.maximum).toBe(10000)
    }
  })

  test('observation schema keeps provider reports distinct from verified receipt modalities', () => {
    const schema = load('self-observation-v1.schema.json')
    expect(new Set(schema.properties.source_modality.enum)).toEqual(new Set([
      'RUNTIME_TELEMETRY', 'LEDGER_STATE', 'TEST_RESULT', 'FORMAL_VERIFIER_RECEIPT',
      'WORLD_OBSERVATION_RECEIPT', 'PROVIDER_REPORT',
    ]))
    expect(new Set(schema.properties.epistemic_status.enum)).toEqual(new Set(['CANDIDATE', 'VERIFIED']))
  })

  test('update proposal schema cannot encode promotion or mutation actions', () => {
    const schema = load('self-model-update-proposal-v1.schema.json')
    expect(new Set(schema.properties.action.enum)).toEqual(new Set([
      'HOLD', 'DEMOTE_CONFIDENCE', 'RAISE_UNCERTAINTY', 'MARK_CONTRADICTION', 'REQUEST_REVIEW',
    ]))
  })

  test('cycle receipt schema keeps reflexive evidence non-authoritative', () => {
    const schema = load('reflexive-cycle-receipt-v1.schema.json')
    expect(new Set(schema.properties.cycle_status.enum)).toEqual(new Set([
      'CYCLE_CLOSED', 'UNSCORABLE_POSTDICTION', 'UNSCORABLE_STALE_BINDING',
      'UNSCORABLE_UNVERIFIED_OUTCOME', 'CONTRADICTION_DETECTED', 'TAMPER_DETECTED',
      'VERIFIER_UNAVAILABLE',
    ]))
    expect(schema.properties.authority.const).toBe('REFLEXIVE_EVIDENCE_ONLY')
  })
})
