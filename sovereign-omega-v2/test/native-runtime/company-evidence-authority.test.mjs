import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const ts = createRequire(import.meta.url)('typescript')
const source = readFileSync(
  new URL('../../src/sovereignty/company-evidence-authority.ts', import.meta.url),
  'utf8',
)
const js = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const policy = await import(
  'data:text/javascript;base64,' + Buffer.from(js).toString('base64')
)

test('absent collection path cannot become numeric zero', () => {
  const result = policy.admitMetricEvidenceV1({
    metric: 'visits',
    source_authority: 'PROVIDER_ATTESTATION',
    instrumentation_state: 'VERIFIED',
    collection_state: 'ABSENT',
    observed_value: 0,
  })
  assert.equal(result.measurement_state, 'NOT_MEASURED')
  assert.equal(result.admitted_value, null)
  assert.equal(result.numeric_claim_admitted, false)
})

test('unknown stream identity remains NOT_VERIFIED', () => {
  const result = policy.admitMetricEvidenceV1({
    metric: 'sessions',
    source_authority: 'PROVIDER_ATTESTATION',
    instrumentation_state: 'UNKNOWN',
    collection_state: 'UNKNOWN',
    observed_value: 0,
  })
  assert.equal(result.measurement_state, 'NOT_VERIFIED')
  assert.equal(result.admitted_value, null)
})

test('verified provider metric stays provider-attested rather than direct', () => {
  const result = policy.admitMetricEvidenceV1({
    metric: 'video_count',
    source_authority: 'PROVIDER_ATTESTATION',
    instrumentation_state: 'VERIFIED',
    collection_state: 'VERIFIED',
    observed_value: 0,
  })
  assert.equal(result.measurement_state, 'MEASURED')
  assert.equal(result.admitted_value, 0)
  assert.equal(result.source_authority, 'PROVIDER_ATTESTATION')
  assert.match(result.reason, /provider-attested/)
})

test('verified direct observation admits numeric zero', () => {
  const result = policy.admitMetricEvidenceV1({
    metric: 'reply_count',
    source_authority: 'DIRECT_OBSERVATION',
    instrumentation_state: 'VERIFIED',
    collection_state: 'VERIFIED',
    observed_value: 0,
  })
  assert.equal(result.measurement_state, 'MEASURED')
  assert.equal(result.admitted_value, 0)
  assert.equal(result.numeric_claim_admitted, true)
})
