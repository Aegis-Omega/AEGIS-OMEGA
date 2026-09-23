import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const ts = createRequire(import.meta.url)('typescript')
const source = readFileSync(
  new URL('../../src/sovereignty/company-model-promotion.ts', import.meta.url),
  'utf8',
)
const js = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const api = await import(
  'data:text/javascript;base64,' + Buffer.from(js).toString('base64'),
)

const digest = 'a'.repeat(64)
const baseline = {
  model: 'gpt-5.6-terra',
  eval_set_sha256: digest,
  cases_total: 100,
  quality_passed: 96,
  policy_failures: 0,
  evidence_failures: 0,
  mean_latency_ms: 1000,
  cost_microunits: 10000,
}
const candidate = {
  model: 'gpt-5.6-sol',
  eval_set_sha256: digest,
  cases_total: 100,
  quality_passed: 97,
  policy_failures: 0,
  evidence_failures: 0,
  mean_latency_ms: 1050,
  cost_microunits: 10500,
}
const policy = {
  min_cases: 100,
  min_quality_ppm: 950000,
  max_policy_failures: 0,
  max_evidence_failures: 0,
  max_latency_regression_ppm: 100000,
  max_cost_regression_ppm: 100000,
}

test('better candidate is admissible but receives no promotion authority', () => {
  const out = api.evaluateCompanyModelPromotionV1(baseline, candidate, policy)
  assert.equal(out.decision, 'ADMISSIBLE')
  assert.deepEqual(out.reasons, [])
  assert.equal(out.promotion_authority, 'NOT_GRANTED')
  assert.equal(out.authority_effect, 'NONE')
})

test('different eval set is rejected', () => {
  const out = api.evaluateCompanyModelPromotionV1(
    baseline,
    { ...candidate, eval_set_sha256: 'b'.repeat(64) },
    policy,
  )
  assert.ok(out.reasons.includes('EVAL_SET_MISMATCH'))
})

test('policy or evidence regression is rejected', () => {
  const out = api.evaluateCompanyModelPromotionV1(
    baseline,
    { ...candidate, policy_failures: 1, evidence_failures: 1 },
    policy,
  )
  assert.ok(out.reasons.includes('POLICY_FAILURE_BUDGET_EXCEEDED'))
  assert.ok(out.reasons.includes('EVIDENCE_FAILURE_BUDGET_EXCEEDED'))
})

test('quality regression is rejected even above absolute floor', () => {
  const out = api.evaluateCompanyModelPromotionV1(
    baseline,
    { ...candidate, quality_passed: 95 },
    policy,
  )
  assert.ok(out.reasons.includes('QUALITY_REGRESSION'))
})

test('latency and cost regression budgets are enforced exactly', () => {
  const out = api.evaluateCompanyModelPromotionV1(
    baseline,
    { ...candidate, mean_latency_ms: 1101, cost_microunits: 11001 },
    policy,
  )
  assert.ok(out.reasons.includes('LATENCY_REGRESSION'))
  assert.ok(out.reasons.includes('COST_REGRESSION'))
})

test('zero baseline metric fails closed against positive candidate regression', () => {
  const out = api.evaluateCompanyModelPromotionV1(
    { ...baseline, mean_latency_ms: 0, cost_microunits: 0 },
    { ...candidate, mean_latency_ms: 1, cost_microunits: 1 },
    policy,
  )
  assert.ok(out.reasons.includes('LATENCY_REGRESSION'))
  assert.ok(out.reasons.includes('COST_REGRESSION'))
})

test('invalid eval data and undersized samples fail closed', () => {
  assert.throws(() => api.evaluateCompanyModelPromotionV1(
    { ...baseline, quality_passed: 101 },
    candidate,
    policy,
  ))
  const out = api.evaluateCompanyModelPromotionV1(
    { ...baseline, cases_total: 99, quality_passed: 95 },
    { ...candidate, cases_total: 99, quality_passed: 96 },
    policy,
  )
  assert.ok(out.reasons.includes('BASELINE_SAMPLE_TOO_SMALL'))
  assert.ok(out.reasons.includes('CANDIDATE_SAMPLE_TOO_SMALL'))
})
