/**
 * Source-bound Cloudflare account resource discovery.
 * Inventory only. Does not provision services, run models or grant quota.
 */
import { canonicalizeJCS } from '../core/canonicalize.js'
import { hashString, sha256Hex } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import type { CloudflareReadOnlyFetchV1 } from './cloudflare-account-collector.js'

const API_BASE = 'https://api.cloudflare.com/client/v4'
const ACCOUNT = /^[0-9a-fA-F]{32}$/
const GENERATION = /^(0|[1-9][0-9]*)$/

const SERVICES = [
  ['workers', '/workers/scripts'],
  ['d1', '/d1/database'],
  ['pages', '/pages/projects'],
  ['queues', '/queues'],
  ['vectorize', '/vectorize/v2/indexes'],
  ['ai_gateway', '/ai-gateway/gateways'],
  ['r2', '/r2/buckets'],
] as const

export type CloudflareServiceV1 = typeof SERVICES[number][0]
export type CloudflareServiceStateV1 = 'PRESENT' | 'EMPTY' | 'SETUP_REQUIRED' | 'UNKNOWN'
export interface CloudflareServiceEvidenceV1 {
  service: CloudflareServiceV1
  state: CloudflareServiceStateV1
  http_status: number
  observed_first_page_count: number | null
  total_count: number | null
}
export interface CloudflareDiscoveryV1 {
  schema: 'AEGIS_CLOUDFLARE_DISCOVERY_V1'
  account_fingerprint: SHA256Hex
  observation_generation: string
  services: readonly CloudflareServiceEvidenceV1[]
  routing_authority: 'NONE'
  cost_authority: 'NONE'
  free_quota_verified: false
  evidence_root: SHA256Hex
}
export interface CloudflareDiscoveryRequestV1 {
  account_id: string
  api_token: string
  observation_generation: string
  fetch_read?: CloudflareReadOnlyFetchV1
}

function object(v: unknown): Record<string, unknown> | null {
  return typeof v === 'object' && v !== null && !Array.isArray(v) ? v as Record<string,unknown> : null
}
function count(v: unknown): number | null {
  return typeof v === 'number' && Number.isSafeInteger(v) && v >= 0 ? v : null
}
function items(v: unknown): readonly unknown[] | null {
  if (Array.isArray(v)) return v
  const obj=object(v)
  for(const key of ['buckets', 'indexes', 'items', 'result'] as const) {
    if(Array.isArray(obj?.[key])) return obj[key] as readonly unknown[]
  }
  return null
}
/** Fail closed on HTTP failures, malformed objects and incomplete pagination. */
function classify(
  service: CloudflareServiceV1,
  status: number,
  response: unknown,
): CloudflareServiceEvidenceV1 {
  const base={service,http_status:status}
  const envelope=object(response)
  if (status === 403 && service === 'r2') {
    const errors=envelope?.errors
    if (Array.isArray(errors) && errors.some(e => object(e)?.code === 10042)) {
      return {...base,state:'SETUP_REQUIRED',observed_first_page_count:null,total_count:null}
    }
  }
  if (status !== 200 || envelope?.success !== true) {
    return {...base,state:'UNKNOWN',observed_first_page_count:null,total_count:null}
  }
  const entries=items(envelope.result)
  if (!entries || entries.length>10000) {
    return {...base,state:'UNKNOWN',observed_first_page_count:null,total_count:null}
  }
  const info=object(envelope.result_info)
  const total=count(info?.total_count)
  // These endpoints list the first page. Empty from an authenticated 200
  // counts as EMPTY only if metadata does not contradict that result.
  if (total !== null && total < entries.length) {
    return {...base,state:'UNKNOWN',observed_first_page_count:null,total_count:null}
  }
  const seen=entries.length
  const state:CloudflareServiceStateV1=seen>0?'PRESENT':
    (total===null || total===0)?'EMPTY':'UNKNOWN'
  return {...base,state,observed_first_page_count:seen,total_count:total}
}
async function read(
  service:CloudflareServiceV1,
  path:string,
  account:string,
  token:string,
  fetcher:CloudflareReadOnlyFetchV1,
): Promise<CloudflareServiceEvidenceV1> {
  try {
    const response=await fetcher(`${API_BASE}/accounts/${account}${path}`,{
      method:'GET',
      headers:{Authorization:`Bearer ${token}`,Accept:'application/json'},
      redirect:'error',
      signal:AbortSignal.timeout(8000),
    })
    if(response.status!==200 && !(service==='r2' && response.status===403)) {
      return classify(service,response.status,null)
    }
    const json:unknown=await response.json()
    return classify(service,response.status,json)
  } catch {
    return classify(service,0,null)
  }
}
export async function discoverCloudflareAccountResourcesV1(
  options:CloudflareDiscoveryRequestV1,
):Promise<CloudflareDiscoveryV1> {
  if(!ACCOUNT.test(options.account_id)) throw new TypeError('account_id must be 32 hexadecimal characters')
  if(typeof options.api_token!=='string' || !options.api_token.trim() || /\s/.test(options.api_token)) {
    throw new TypeError('valid single-token credential required')
  }
  if(!GENERATION.test(options.observation_generation)) throw new TypeError('invalid observation_generation')
  const account=options.account_id.toLowerCase()
  const fetcher=options.fetch_read??fetch
  const services:CloudflareServiceEvidenceV1[]=[]
  for(const [service,path] of SERVICES) {
    services.push(await read(service,path,account,options.api_token,fetcher))
  }
  const account_fingerprint=await hashString('AEGIS_CF_DISCOVERY_ACCOUNT_V1:'+account)
  const body={
    schema:'AEGIS_CLOUDFLARE_DISCOVERY_V1' as const,
    account_fingerprint,
    observation_generation:options.observation_generation,
    services,
    routing_authority:'NONE' as const,
    cost_authority:'NONE' as const,
    free_quota_verified:false as const,
  }
  const evidence_root=await sha256Hex(canonicalizeJCS({domain:'AEGIS_CLOUDFLARE_DISCOVERY_V1',body}))
  return {...body,evidence_root}
}
