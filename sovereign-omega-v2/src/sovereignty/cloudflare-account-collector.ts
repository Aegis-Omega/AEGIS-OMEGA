/**
 * Read-only Cloudflare account observation for AEGIS Ω Resource Mesh.
 * No inference, signup, billed operation, write or provider authority.
 * Output is an account-scoped CHECKSUM, never a provider-signed attestation.
 */
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex, hashString } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import {
  observeConnectedResourcesV1,
  type ConnectedApiReadV1,
  type ConnectedResourceInventoryV1,
} from './connected-resource-intake.js'

const API_BASE = 'https://api.cloudflare.com/client/v4'
const ACCOUNT_PATTERN = /^[0-9a-fA-F]{32}$/
const GENERATION_PATTERN = /^(0|[1-9][0-9]*)$/

const READ_PATHS = {
  ai_gateway_credit_balance: '/ai-gateway/billing/credit-balance',
  ai_gateway_topup_config: '/ai-gateway/billing/topup/config',
  worker_account_settings: '/workers/account-settings',
  worker_scripts: '/workers/scripts',
} as const

export type CloudflareReadOnlyFetchV1 = (
  url: string,
  init: RequestInit,
) => Promise<Pick<Response, 'status' | 'json'>>

export interface CloudflareAccountCollectorOptionsV1 {
  account_id: string
  api_token: string
  observation_generation: string
  fetch_read?: CloudflareReadOnlyFetchV1
}

export interface CloudflareAccountCollectorReceiptV1 {
  schema: 'AEGIS_CLOUDFLARE_ACCOUNT_COLLECTOR_V1'
  provider: 'cloudflare'
  account_fingerprint: SHA256Hex
  methods: readonly ['GET']
  endpoints: readonly string[]
  inventory: ConnectedResourceInventoryV1
  collector_root: SHA256Hex
  authority_effect: 'NONE'
}

function object(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown> : null
}

/**
 * Strip upstream payloads before they can be cached, emitted, or hashed.
 * Failures are represented by status only. No raw provider errors are returned.
 */
function sanitizeRead(
  key: keyof typeof READ_PATHS,
  status: number,
  apiResponse: unknown,
): ConnectedApiReadV1 {
  const envelope = object(apiResponse)
  const success = status === 200 && envelope?.success === true
  const result = success ? envelope?.result : null
  if (key === 'ai_gateway_credit_balance') {
    const x = object(result)
    return {status, success, result: {balance: x?.balance ?? null}}
  }
  if (key === 'ai_gateway_topup_config') {
    const x = object(result)
    return {status, success, result: {threshold: x?.threshold ?? null, amount: x?.amount ?? null}}
  }
  if (key === 'worker_account_settings') {
    const x = object(result)
    return {status, success, result: {default_usage_model: x?.default_usage_model ?? null}}
  }
  const scripts = Array.isArray(result) && result.length <= 10000
    ? result.map(item => {
      if (typeof item === 'string') return item
      const id = object(item)?.id
      return typeof id === 'string' ? {id} : null
    })
    : null
  return {status, success, result: scripts}
}

async function readEndpoint(
  path: string,
  key: keyof typeof READ_PATHS,
  account: string,
  token: string,
  fetcher: CloudflareReadOnlyFetchV1,
): Promise<ConnectedApiReadV1> {
  try {
    const response = await fetcher(`${API_BASE}/accounts/${account}${path}`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
      },
      redirect: 'error',
      signal: AbortSignal.timeout(8000),
    })
    if (response.status !== 200) return {status: response.status,success:false,result:null}
    // Failed JSON parse also fails closed; never log the response body.
    const body: unknown = await response.json()
    return sanitizeRead(key, response.status, body)
  } catch {
    return {status:0,success:false,result:null}
  }
}

/** Execute exactly four bounded GETs; no supplied URL or HTTP method is accepted. */
export async function collectCloudflareAccountResourcesV1(
  options: CloudflareAccountCollectorOptionsV1,
): Promise<CloudflareAccountCollectorReceiptV1> {
  if (!ACCOUNT_PATTERN.test(options.account_id)) {
    throw new TypeError('Cloudflare account id must be 32 hex characters')
  }
  if (typeof options.api_token !== 'string' || !options.api_token.trim()
      || /\s/.test(options.api_token)) {
    throw new TypeError('a non-empty single-token API credential is required')
  }
  if (!GENERATION_PATTERN.test(options.observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }
  const account = options.account_id.toLowerCase()
  const fetcher = options.fetch_read ?? fetch
  // Execute sequentially to avoid unnecessary API burst/rate-limit pressure.
  const credit = await readEndpoint(READ_PATHS.ai_gateway_credit_balance, 'ai_gateway_credit_balance', account, options.api_token, fetcher)
  const topup = await readEndpoint(READ_PATHS.ai_gateway_topup_config, 'ai_gateway_topup_config', account, options.api_token, fetcher)
  const settings = await readEndpoint(READ_PATHS.worker_account_settings, 'worker_account_settings', account, options.api_token, fetcher)
  const scripts = await readEndpoint(READ_PATHS.worker_scripts, 'worker_scripts', account, options.api_token, fetcher)

  const inventory = await observeConnectedResourcesV1({
    observation_generation: options.observation_generation,
    cloudflare: {
      ai_gateway_credit_balance: credit,
      ai_gateway_topup_config: topup,
      worker_account_settings: settings,
      worker_scripts: scripts,
    },
    // An absent HF account read is UNKNOWN; empty job lists do not confer GPU quota.
    hugging_face: {account_plan:'UNKNOWN', jobs_total:null},
  })
  const account_fingerprint = await hashString('AEGIS_CF_ACCOUNT_V1:' + account)
  const payload = {
    schema: 'AEGIS_CLOUDFLARE_ACCOUNT_COLLECTOR_V1' as const,
    provider: 'cloudflare' as const,
    account_fingerprint,
    methods: ['GET'] as const,
    endpoints: Object.values(READ_PATHS),
    inventory,
    authority_effect: 'NONE' as const,
  }
  const collector_root = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_CLOUDFLARE_COLLECTOR_V1',
    payload,
  }))
  return {...payload, collector_root}
}
