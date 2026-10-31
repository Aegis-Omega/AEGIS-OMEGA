/**
 * AEGIS AWS read-only resource collector.
 *
 * The caller injects an allowlisted read-only API function. This module has no
 * credentials, no SDK import, no implicit network access, no mutation and no
 * assumption about Free Plan grants or remaining balance.
 */
import type { AwsApiObservationV1, AwsResourceReadsV1 } from './connected-resource-intake.js'

export type AwsReadOperationV1 =
  | 'GetCallerIdentity' | 'ListBuckets' | 'DescribeRegions' | 'GetCostAndUsage'
  | 'ListBillingViews' | 'DescribeBudgets' | 'GetFreeTierUsage'
export type AwsReadServiceV1 = 'sts' | 's3' | 'ec2' | 'ce' | 'billing' | 'budgets' | 'freetier'
export interface AwsReadRequestV1 {
  service_name: AwsReadServiceV1
  operation_name: AwsReadOperationV1
  region_name: string
  params: Record<string, unknown>
}
export type AwsReadCallV1 = (request: AwsReadRequestV1) => Promise<unknown>
export interface AwsCollectorOptionsV1 {
  region: string
  cost_period?: { start: string; end: string }
  /** Some Cost Explorer API requests are chargeable; disabled by default. */
  include_cost_explorer?: boolean
  /** Operator statement, never an authenticated provider balance. */
  operator_reported_credit_usd?: string | null
}

const REGION = /^[a-z]{2}(?:-gov)?-[a-z]+-\d+$/
const DAY = /^\d{4}-\d{2}-\d{2}$/
const ID = /^\d{12}$/
const ERROR_CODES = new Set([
  'NotSignedUp', 'OptInRequired', 'SubscriptionRequiredException', 'AccessDeniedException',
])
type JsonObject = Record<string, unknown>
const object = (x: unknown): JsonObject | null =>
  x !== null && typeof x === 'object' && !Array.isArray(x) ? x as JsonObject : null
const unknownRead = (): AwsApiObservationV1 => ({outcome:'UNKNOWN',error_code:null,count:null})

/** Drops untrusted text (including secrets, account IDs and ARNs) from errors. */
function codeFromError(error: unknown): string | null {
  const e = object(error)
  const nested = object(object(e?.response)?.Error)
  const raw = e?.code ?? e?.Code ?? nested?.Code ?? e?.name
  if (typeof raw === 'string' && ERROR_CODES.has(raw)) return raw
  const msg = typeof e?.message === 'string' ? e.message : ''
  for (const code of ERROR_CODES) {
    if (msg.includes('('+code+')')) return code
  }
  return null
}

async function observe(
  call: AwsReadCallV1, request: AwsReadRequestV1, arrayField: string,
): Promise<AwsApiObservationV1> {
  try {
    const raw = object(await call(request))
    if (!raw || !Array.isArray(raw[arrayField])) return unknownRead()
    // The injected reader must return all pages. Never certify a partial count.
    if ((typeof raw.NextToken === 'string' && raw.NextToken.length > 0) ||
        (typeof raw.nextToken === 'string' && raw.nextToken.length > 0)) return unknownRead()
    const count = (raw[arrayField] as unknown[]).length
    if (!Number.isSafeInteger(count)) return unknownRead()
    return {outcome:'SUCCESS',error_code:null,count}
  } catch (error) {
    return {outcome:'ERROR',error_code:codeFromError(error),count:null}
  }
}

async function observeIdentity(
  call: AwsReadCallV1,
): Promise<{observation:AwsApiObservationV1;accountId:string|null}> {
  try {
    const raw = object(await call({
      service_name:'sts',operation_name:'GetCallerIdentity',region_name:'us-east-1',params:{},
    }))
    const account = raw?.Account
    if (typeof account !== 'string' || !ID.test(account)) {
      return {observation:unknownRead(),accountId:null}
    }
    // Account id is transient. Never copy it into returned evidence or logs.
    return {observation:{outcome:'SUCCESS',error_code:null,count:null},accountId:account}
  } catch (error) {
    return {observation:{outcome:'ERROR',error_code:codeFromError(error),count:null},accountId:null}
  }
}

function validPeriod(period: {start:string;end:string} | undefined): period is {start:string;end:string} {
  if (!period || !DAY.test(period.start) || !DAY.test(period.end) || period.start >= period.end) {
    return false
  }
  for (const day of [period.start, period.end]) {
    const time = Date.parse(day+'T00:00:00Z')
    if (!Number.isFinite(time) || new Date(time).toISOString().slice(0,10) !== day) {
      return false
    }
  }
  return true
}

/** Returns sanitized, dynamic AWS observations for the existing AEGIS intake. */
export async function collectAwsResourceReadsV1(
  call: AwsReadCallV1, options: AwsCollectorOptionsV1,
): Promise<AwsResourceReadsV1> {
  if (typeof call !== 'function' || !options || !REGION.test(options.region)) {
    throw new TypeError('collector requires a read-only callback and valid region')
  }
  if (options.include_cost_explorer && !validPeriod(options.cost_period)) {
    throw new TypeError('cost_period required for explicit Cost Explorer read')
  }
  const identity = await observeIdentity(call)
  const req = (
    service_name: AwsReadServiceV1, operation_name: AwsReadOperationV1,
    params:Record<string,unknown> = {}, region_name = options.region,
  ): AwsReadRequestV1 => ({service_name,operation_name,params,region_name})
  // Only call Budgets when the live STS response provided a valid account ID.
  const budget = identity.accountId === null
    ? Promise.resolve(unknownRead())
    : observe(call,req('budgets','DescribeBudgets',
      {AccountId:identity.accountId},'us-east-1'),'Budgets')
  const ce = options.include_cost_explorer
    ? observe(call,req('ce','GetCostAndUsage',{
      TimePeriod:{Start:options.cost_period!.start,End:options.cost_period!.end},
      Granularity:'MONTHLY',Metrics:['UnblendedCost'],
    },'us-east-1'),'ResultsByTime')
    : Promise.resolve(unknownRead())
  const [s3,ec2,billing,budgets,freeTier,costExplorer] = await Promise.all([
    observe(call,req('s3','ListBuckets',{},'us-east-1'),'Buckets'),
    observe(call,req('ec2','DescribeRegions',{AllRegions:false}),'Regions'),
    observe(call,req('billing','ListBillingViews',{},'us-east-1'),'billingViews'),
    budget,
    observe(call,req('freetier','GetFreeTierUsage',{MaxResults:20},'us-east-1'),'freeTierUsages'),
    ce,
  ])
  return {
    sts:identity.observation,s3,ec2,cost_explorer:costExplorer,
    billing_views:billing,budgets,free_tier:freeTier,
    operator_reported_credit_usd:options.operator_reported_credit_usd ?? null,
  }
}
