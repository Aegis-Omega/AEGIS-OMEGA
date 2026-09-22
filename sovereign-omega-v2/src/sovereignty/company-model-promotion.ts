// AEGIS Company Model Promotion Gate V1
// Deterministic eval admission only. This module never mutates model routing.

export interface CompanyModelEvalV1 {
  readonly model: string
  readonly eval_set_sha256: string
  readonly cases_total: number
  readonly quality_passed: number
  readonly policy_failures: number
  readonly evidence_failures: number
  readonly mean_latency_ms: number
  readonly cost_microunits: number
}

export interface CompanyModelPromotionPolicyV1 {
  readonly min_cases: number
  readonly min_quality_ppm: number
  readonly max_policy_failures: number
  readonly max_evidence_failures: number
  readonly max_latency_regression_ppm: number
  readonly max_cost_regression_ppm: number
}

export interface CompanyModelPromotionDecisionV1 {
  readonly decision: 'ADMISSIBLE' | 'REJECTED'
  readonly baseline_model: string
  readonly candidate_model: string
  readonly eval_set_sha256: string
  readonly reasons: readonly string[]
  readonly promotion_authority: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

function digest(value: unknown, label: string): string {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) {
    throw new TypeError(`${label} must be lowercase SHA-256 hex`)
  }
  return value
}

function integer(value: unknown, label: string, max = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > max) {
    throw new TypeError(`${label} must be a non-negative safe integer`)
  }
  return value
}

function validateEval(value: CompanyModelEvalV1, label: string): CompanyModelEvalV1 {
  text(value?.model, `${label}.model`)
  digest(value?.eval_set_sha256, `${label}.eval_set_sha256`)
  integer(value?.cases_total, `${label}.cases_total`)
  integer(value?.quality_passed, `${label}.quality_passed`)
  integer(value?.policy_failures, `${label}.policy_failures`)
  integer(value?.evidence_failures, `${label}.evidence_failures`)
  integer(value?.mean_latency_ms, `${label}.mean_latency_ms`)
  integer(value?.cost_microunits, `${label}.cost_microunits`)
  if (value.cases_total === 0) throw new TypeError(`${label}.cases_total must be positive`)
  if (value.quality_passed > value.cases_total) throw new TypeError(`${label}.quality_passed exceeds cases_total`)
  return value
}

function ratioAtLeast(numerator: number, denominator: number, ppm: number): boolean {
  return BigInt(numerator) * 1_000_000n >= BigInt(ppm) * BigInt(denominator)
}

function ratioNonRegressing(
  candidatePass: number,
  candidateTotal: number,
  baselinePass: number,
  baselineTotal: number,
): boolean {
  return BigInt(candidatePass) * BigInt(baselineTotal) >=
    BigInt(baselinePass) * BigInt(candidateTotal)
}

function withinRegression(candidate: number, baseline: number, allowedPpm: number): boolean {
  if (baseline === 0) return candidate === 0
  return BigInt(candidate) * 1_000_000n <=
    BigInt(baseline) * BigInt(1_000_000 + allowedPpm)
}

export function evaluateCompanyModelPromotionV1(
  baselineInput: CompanyModelEvalV1,
  candidateInput: CompanyModelEvalV1,
  policyInput: CompanyModelPromotionPolicyV1,
): CompanyModelPromotionDecisionV1 {
  const baseline = validateEval(structuredClone(baselineInput), 'baseline')
  const candidate = validateEval(structuredClone(candidateInput), 'candidate')
  const policy = structuredClone(policyInput)

  integer(policy?.min_cases, 'policy.min_cases')
  integer(policy?.min_quality_ppm, 'policy.min_quality_ppm', 1_000_000)
  integer(policy?.max_policy_failures, 'policy.max_policy_failures')
  integer(policy?.max_evidence_failures, 'policy.max_evidence_failures')
  integer(policy?.max_latency_regression_ppm, 'policy.max_latency_regression_ppm')
  integer(policy?.max_cost_regression_ppm, 'policy.max_cost_regression_ppm')
  if (policy.min_cases < 1) throw new TypeError('policy.min_cases must be positive')

  const reasons: string[] = []
  if (candidate.eval_set_sha256 !== baseline.eval_set_sha256) reasons.push('EVAL_SET_MISMATCH')
  if (baseline.cases_total < policy.min_cases) reasons.push('BASELINE_SAMPLE_TOO_SMALL')
  if (candidate.cases_total < policy.min_cases) reasons.push('CANDIDATE_SAMPLE_TOO_SMALL')
  if (candidate.policy_failures > policy.max_policy_failures) reasons.push('POLICY_FAILURE_BUDGET_EXCEEDED')
  if (candidate.evidence_failures > policy.max_evidence_failures) reasons.push('EVIDENCE_FAILURE_BUDGET_EXCEEDED')
  if (!ratioAtLeast(candidate.quality_passed, candidate.cases_total, policy.min_quality_ppm)) reasons.push('MIN_QUALITY_NOT_MET')
  if (!ratioNonRegressing(
    candidate.quality_passed,
    candidate.cases_total,
    baseline.quality_passed,
    baseline.cases_total,
  )) reasons.push('QUALITY_REGRESSION')
  if (!withinRegression(
    candidate.mean_latency_ms,
    baseline.mean_latency_ms,
    policy.max_latency_regression_ppm,
  )) reasons.push('LATENCY_REGRESSION')
  if (!withinRegression(
    candidate.cost_microunits,
    baseline.cost_microunits,
    policy.max_cost_regression_ppm,
  )) reasons.push('COST_REGRESSION')

  return Object.freeze({
    decision: reasons.length === 0 ? 'ADMISSIBLE' as const : 'REJECTED' as const,
    baseline_model: baseline.model,
    candidate_model: candidate.model,
    eval_set_sha256: candidate.eval_set_sha256,
    reasons: Object.freeze(reasons),
    promotion_authority: 'NOT_GRANTED' as const,
    authority_effect: 'NONE' as const,
  })
}
