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
    // Zero jobs, a live Worker and zero prepaid credit are not free-quota proof.
    zero_spend_admission: 'HOLD' as const,
    authority_effect: 'NONE' as const,
  }
  const integrity_root = await sha256Hex(canonicalizeJCS({domain:'AEGIS_CONNECTED_RESOURCE_INVENTORY_V1', body}))
  return {...body, integrity_root}
}
