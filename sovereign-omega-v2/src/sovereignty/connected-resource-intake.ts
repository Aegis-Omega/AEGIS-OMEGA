/**
 * AEGIS Ω connected-resource intake (read-only, no admission authority).
 *
 * Provider data are externally acquired read-only API results; this function
 * neither fetches credentials nor grants execution / free-quota entitlement.
 * A SHA-256 receipt is an integrity checksum, NOT provider authentication.
 */
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'

export interface ConnectedApiReadV1 {
  status: number
  success: boolean
  result: unknown
}

/** Sanitized AWS API metadata, not AWS-signed entitlement proof. */
export interface AwsApiObservationV1 {
  outcome: 'SUCCESS' | 'ERROR' | 'UNKNOWN'
  error_code: string | null
  count: number | null
}
export interface AwsResourceReadsV1 {
  sts: AwsApiObservationV1 | null
  s3: AwsApiObservationV1 | null
  ec2: AwsApiObservationV1 | null
  cost_explorer: AwsApiObservationV1 | null
  billing_views: AwsApiObservationV1 | null
  budgets: AwsApiObservationV1 | null
  free_tier: AwsApiObservationV1 | null
  operator_reported_credit_usd: string | null
  /** Derived from STS ARN; raw ARN/account are never returned or hashed. */
  principal_kind?: 'ROOT' | 'IAM_PRINCIPAL' | 'UNKNOWN'
}
export interface AwsResourceInventoryV1 {
  identity: 'OBSERVED' | 'UNKNOWN'
  s3: 'API_SUCCESS' | 'NOT_SIGNED_UP' | 'UNKNOWN'
  s3_bucket_count: number | null
  ec2: 'API_SUCCESS' | 'OPT_IN_REQUIRED' | 'UNKNOWN'
  ec2_region_count: number | null
  cost_explorer: 'API_SUCCESS' | 'SUBSCRIPTION_REQUIRED' | 'UNKNOWN'
  billing_views_count: number | null
  budgets_count: number | null
  free_tier_usage_count: number | null
  operator_reported_credit_usd: string | null
  principal_kind?: 'ROOT' | 'IAM_PRINCIPAL' | 'UNKNOWN'
  remaining_credit_verified: 'UNKNOWN'
  effective_hard_budget_stop: 'UNKNOWN'
  paid_aws_workloads: 'HOLD'
  provider_attestation: 'NOT_ESTABLISHED'
}

export interface ConnectedResourceReadsV1 {
  observation_generation: string
  cloudflare: {
    ai_gateway_credit_balance: ConnectedApiReadV1 | null
    ai_gateway_topup_config: ConnectedApiReadV1 | null
    worker_account_settings: ConnectedApiReadV1 | null
    worker_scripts: ConnectedApiReadV1 | null
  }
  hugging_face: {
    account_plan: 'FREE' | 'PRO' | 'UNKNOWN'
    jobs_total: number | null
  }
  aws?: AwsResourceReadsV1
}
export interface ConnectedResourceInventoryV1 {
  schema: 'AEGIS_CONNECTED_RESOURCE_INVENTORY_V1'
  observation_generation: string
  cloudflare: {
    ai_gateway_prepaid: 'ZERO_CONFIRMED' | 'POSITIVE_NOT_FREE' | 'UNKNOWN'
    ai_gateway_auto_topup: 'OFF_CONFIRMED' | 'POSSIBLE' | 'UNKNOWN'
    worker_script_count: number | null
    worker_usage_model: 'STANDARD' | 'UNKNOWN'
    workers_ai_free_quota: 'UNKNOWN'
  }
  hugging_face: {
    plan: 'FREE' | 'PRO' | 'UNKNOWN'
    jobs_total: number | null
    free_gpu_quota: 'UNKNOWN'
  }
  aws?: AwsResourceInventoryV1
  zero_spend_admission: 'HOLD'
  authority_effect: 'NONE'
  integrity_root: SHA256Hex
}
function record(x: unknown): Record<string, unknown> | null {
  return x !== null && typeof x === 'object' && !Array.isArray(x)
    ? x as Record<string, unknown> : null
}
function usable(read: ConnectedApiReadV1 | null): unknown {
  return read && read.status === 200 && read.success === true ? read.result : null
}
function validNonnegativeCount(n: unknown): n is number {
  return typeof n === 'number' && Number.isSafeInteger(n) && n >= 0
}

const AWS_ERROR_CODES = new Set(['NotSignedUp','OptInRequired','SubscriptionRequiredException','AccessDeniedException'])
function awsObservation(x: AwsApiObservationV1 | null): AwsApiObservationV1 {
  if (x === null) return {outcome:'UNKNOWN',error_code:null,count:null}
  if (!x || !(['SUCCESS','ERROR','UNKNOWN'] as string[]).includes(x.outcome)) {
    throw new TypeError('invalid AWS observation outcome')
  }
  if (x.count !== null && !validNonnegativeCount(x.count)) {
    throw new TypeError('AWS observation count must be nonnegative safe integer or null')
  }
  // Unknown error codes and unexpected fields are discarded, never hashed.
  const safeCode=x.outcome==='ERROR' && typeof x.error_code==='string' && AWS_ERROR_CODES.has(x.error_code)
    ? x.error_code : null
  return {outcome:x.outcome,error_code:safeCode,count:x.count}
}
function awsApiStatus<T extends string>(
  read:AwsApiObservationV1, code:string, status:T,
): 'API_SUCCESS' | T | 'UNKNOWN' {
  if(read.outcome==='SUCCESS') return 'API_SUCCESS'
  if(read.outcome==='ERROR' && read.error_code===code) return status
  return 'UNKNOWN'
}
function awsCount(read:AwsApiObservationV1):number|null {
  return read.outcome==='SUCCESS' ? read.count : null
}
function observeAws(reads:AwsResourceReadsV1):AwsResourceInventoryV1 {
  if(!reads || typeof reads!=='object') throw new TypeError('missing AWS observations')
  const sts=awsObservation(reads.sts)
  const s3=awsObservation(reads.s3)
  const ec2=awsObservation(reads.ec2)
  const ce=awsObservation(reads.cost_explorer)
  const billing=awsObservation(reads.billing_views)
  const budgets=awsObservation(reads.budgets)
  const free=awsObservation(reads.free_tier)
  const reported=reads.operator_reported_credit_usd
  if (reads.principal_kind !== undefined && !(['ROOT','IAM_PRINCIPAL','UNKNOWN'] as string[]).includes(reads.principal_kind)) {
    throw new TypeError('invalid AWS principal_kind')
  }
  if(reported!==null && (typeof reported!=='string' || reported.length>24 ||
    !/^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$/.test(reported))) {
    throw new TypeError('operator_reported_credit_usd must be unsigned decimal or null')
  }
  return {
    identity:sts.outcome==='SUCCESS'?'OBSERVED':'UNKNOWN',
    s3:awsApiStatus(s3,'NotSignedUp','NOT_SIGNED_UP'),
    s3_bucket_count:awsCount(s3),
    ec2:awsApiStatus(ec2,'OptInRequired','OPT_IN_REQUIRED'),
    ec2_region_count:awsCount(ec2),
    cost_explorer:awsApiStatus(ce,'SubscriptionRequiredException','SUBSCRIPTION_REQUIRED'),
    billing_views_count:awsCount(billing),
    budgets_count:awsCount(budgets),
    free_tier_usage_count:awsCount(free),
    operator_reported_credit_usd:reported,
    ...(reads.principal_kind === undefined ? {} : {principal_kind:reads.principal_kind}),
    // Credit and hard overage ceilings cannot be inferred from read-only API metadata.
    remaining_credit_verified:'UNKNOWN',
    effective_hard_budget_stop:'UNKNOWN',
    paid_aws_workloads:'HOLD',
    provider_attestation:'NOT_ESTABLISHED',
  }
}

export async function observeConnectedResourcesV1(reads: ConnectedResourceReadsV1): Promise<ConnectedResourceInventoryV1> {
  if (!/^(0|[1-9][0-9]*)$/.test(reads.observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }
  const credit = record(usable(reads.cloudflare.ai_gateway_credit_balance))
  const topup = record(usable(reads.cloudflare.ai_gateway_topup_config))
  const workerSettings = record(usable(reads.cloudflare.worker_account_settings))
  const scripts = usable(reads.cloudflare.worker_scripts)
  const balance = credit?.balance

  // Credit is AI Gateway prepaid credit ONLY, never Workers AI free quota.
  const prepaid = typeof balance === 'number' && Number.isFinite(balance) && balance >= 0
    ? balance === 0 ? 'ZERO_CONFIRMED' as const : 'POSITIVE_NOT_FREE' as const
    : 'UNKNOWN' as const
  const threshold = topup?.threshold
  const amount = topup?.amount
  const autoTopup = typeof threshold === 'number' && typeof amount === 'number'
    && Number.isFinite(threshold) && Number.isFinite(amount) && threshold >= 0 && amount >= 0
    ? threshold === 0 && amount === 0 ? 'OFF_CONFIRMED' as const : 'POSSIBLE' as const
    : 'UNKNOWN' as const
  // Cloudflare returns script objects with an id; sanitized connector exports
  // may instead contain bare script names. Neither is proof of a free quota.
  const scriptCount = Array.isArray(scripts)
    && scripts.every(x => (typeof x === 'string' && x.length > 0)
      || (typeof record(x)?.id === 'string' && (record(x)?.id as string).length > 0))
    ? scripts.length : null
  const model = workerSettings?.default_usage_model === 'standard' ? 'STANDARD' as const : 'UNKNOWN' as const

  if (!['FREE', 'PRO', 'UNKNOWN'].includes(reads.hugging_face.account_plan)) {
    throw new TypeError('invalid Hugging Face account plan')
  }
  if (reads.hugging_face.jobs_total !== null && !validNonnegativeCount(reads.hugging_face.jobs_total)) {
    throw new TypeError('jobs_total must be a nonnegative safe integer or null')
  }

  const body = {
    schema: 'AEGIS_CONNECTED_RESOURCE_INVENTORY_V1' as const,
    observation_generation: reads.observation_generation,
    cloudflare: {
      ai_gateway_prepaid: prepaid,
      ai_gateway_auto_topup: autoTopup,
      worker_script_count: scriptCount,
      worker_usage_model: model,
      workers_ai_free_quota: 'UNKNOWN' as const,
    },
    hugging_face: {
      plan: reads.hugging_face.account_plan,
      jobs_total: reads.hugging_face.jobs_total,
      free_gpu_quota: 'UNKNOWN' as const,
    },
    ...(reads.aws === undefined ? {} : {aws:observeAws(reads.aws)}),
    // Zero jobs, a live Worker and zero prepaid credit are not free-quota proof.
    zero_spend_admission: 'HOLD' as const,
    authority_effect: 'NONE' as const,
  }
  const integrity_root = await sha256Hex(canonicalizeJCS({domain:'AEGIS_CONNECTED_RESOURCE_INVENTORY_V1', body}))
  return {...body, integrity_root}
}
