/**
 * AEGIS Ω public operator observation — source-bound, auth-sparing, fail closed.
 * Only GET /platform/status is documented as anonymously readable.
 * Protected calibration/tools are NOT fetched without a scoped credential.
 * An API-reported verdict is not an independently replayed proof.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export type HomeostasisZone = 'slack' | 'optimal' | 'stressed' | 'critical'
export type CalibrationRecommendation = 'EASE' | 'MAINTAIN' | 'TIGHTEN'
export type Tier = 'explorer' | 'operator' | 'sovereign'
export interface CalibrationStatus {
  homeostasis_zone: HomeostasisZone
  recommendation: CalibrationRecommendation
  fitness_mean: number
  fitness_variance: number
  hd_equivalent: number
  stagnation_rate: number
  window_size: number
  trend: 'rising' | 'falling' | 'stable'
  constitutional_factor_mean: number
}
export interface AgentTool { api_name: string; endpoint_url: string; capabilities: string[]; tier_required: Tier }
export interface PlatformStatus {
  version: string
  contract_version: string
  total_agents: number
  chain_valid: boolean | null
  audit_chain_hash: string | null
  available: boolean
}
export interface SystemCheck { label: string; ok: boolean; reason: string }
export interface ConsoleSnapshot {
  /** 'live' means a valid public API response, not verified inference, authority or telemetry. */
  source: 'live' | 'unavailable'
  reason: string
  checked_at: string | null
  upstream_at: string | null
  status: PlatformStatus
  /** Null explicitly represents unqueried protected calibration. */
  calibration: CalibrationStatus | null
  tools: AgentTool[]
  tools_observed: boolean
  checks: SystemCheck[]
}
const PLATFORM_URL = ((import.meta.env.VITE_PLATFORM_URL as string | undefined) || 'https://aegis-vertex.aegisomega.com').replace(/\/$/, '')
export const PLATFORM_ORIGIN = PLATFORM_URL
// Only a public, schema-bounded GET through the dedicated read-only edge observer.
export const PUBLIC_STATUS_GATEWAY = 'https://aegis-public-observation.tarikskalic33.workers.dev/api/status'
export const EMPTY_PLATFORM: PlatformStatus = {
  version: 'unknown', contract_version: 'unknown', total_agents: 0,
  chain_valid: null, audit_chain_hash: null, available: false,
}
export function deriveChecks(source:'live'|'unavailable', status:PlatformStatus):SystemCheck[]{
  const observed = source === 'live'
  const version = status.contract_version
  return [
    {label:'Public status endpoint',ok:observed,reason:observed?'HTTP response parsed and schema-checked; authenticity not independently attested':'UNKNOWN — no valid public status observation'},
    {label:'Contract version',ok:observed && version==='1.0.0',reason:!observed?'UNKNOWN — no contract observed':version==='1.0.0'?'REPORTED v1.0.0; compatible with documented hub schema':`REPORTED ${version}; verify against the server contract`},
    {label:'Audit-chain evidence',ok:false,reason:!observed?'UNKNOWN — no runtime receipt':status.chain_valid===false?'REPORTED INVALID — independent incident review required':status.chain_valid===true?'REPORTED VALID — not independently replayed':'UNKNOWN — remote edge provides no chain verdict'},
    {label:'Calibration',ok:false,reason:'NOT QUERIED — documented authenticated endpoint; no key supplied'},
    {label:'Provider tool catalog',ok:false,reason:'NOT QUERIED — documented authenticated endpoint; no key supplied'},
  ]
}
export const UNAVAILABLE_SNAPSHOT: ConsoleSnapshot = {
  source:'unavailable',reason:'Public status unreachable, unauthorized, or invalid; no synthetic fallback.',
  checked_at:null,upstream_at:null,status:EMPTY_PLATFORM,calibration:null,tools:[],tools_observed:false,
  checks:deriveChecks('unavailable',EMPTY_PLATFORM),
}
function isPlatformStatus(value:unknown):value is Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value))return false
  const s=value as Record<string,unknown>
  return typeof s.version==='string'&&s.version.length<=80 && typeof s.contract_version==='string'&&s.contract_version.length<=80
    && Number.isSafeInteger(s.total_agents)&& (s.total_agents as number)>=0 && (s.total_agents as number)<=100000
    && typeof s.available==='boolean'
    && (s.chain_valid==null||typeof s.chain_valid==='boolean')
    && (s.audit_chain_hash==null||typeof s.audit_chain_hash==='string'&&s.audit_chain_hash.length<=256)
}
function normalize(value:Record<string,unknown>):PlatformStatus{
  return {version:value.version as string,contract_version:value.contract_version as string,
    total_agents:value.total_agents as number,available:value.available as boolean,
    chain_valid:typeof value.chain_valid==='boolean'?value.chain_valid:null,
    audit_chain_hash:typeof value.audit_chain_hash==='string'?value.audit_chain_hash:null}
}
/** Anonymous public observation; NEVER probes key-protected endpoints. */
export async function fetchConsoleSnapshot(): Promise<ConsoleSnapshot> {
  const controller=new AbortController()
  const timeout=setTimeout(()=>controller.abort(),3200)
  const checked_at=new Date().toISOString()
  try{
    const response=await fetch(PUBLIC_STATUS_GATEWAY,{method:'GET',signal:controller.signal,credentials:'omit',cache:'no-store'})
    if(!response.ok) return {...UNAVAILABLE_SNAPSHOT,checked_at,reason:`Public observation gateway HTTP ${response.status}; protected endpoints not probed.`}
    const json:unknown=await response.json()
    const packet=json&&typeof json==='object'&&!Array.isArray(json)?json as Record<string,unknown>:null
    const gateway=packet?.gateway&&typeof packet.gateway==='object'&&!Array.isArray(packet.gateway)?packet.gateway as Record<string,unknown>:null
    const accepted=gateway?.schema==='AEGIS_PUBLIC_OBSERVATION_GATE_V1' && gateway.upstream===PLATFORM_ORIGIN
      && gateway.authority==='UNSIGNED_REMOTE_REPORT_NOT_INDEPENDENTLY_VERIFIED'
    const data=accepted?packet?.data:null
    if(!isPlatformStatus(data))return {...UNAVAILABLE_SNAPSHOT,checked_at,reason:'Public gateway origin, schema, or status payload invalid; nothing inferred.'}
    const status=normalize(data)
    const upstream_at=typeof packet?.timestamp==='string'&&Number.isFinite(Date.parse(packet.timestamp))?packet.timestamp:null
    return {source:'live',reason:'Public upstream status relayed through a read-only edge gateway. This is a reported observation, not signed attestation. Protected endpoints were not queried.',
      checked_at,upstream_at,status,calibration:null,tools:[],tools_observed:false,checks:deriveChecks('live',status)}
  }catch{
    return {...UNAVAILABLE_SNAPSHOT,checked_at,reason:'Read-only observation gateway request failed or timed out; protected endpoints not probed.'}
  }finally{clearTimeout(timeout)}
}
export function useConsoleController():{snap:ConsoleSnapshot;busy:boolean;refresh:()=>Promise<void>}{
  const [snap,setSnap]=useState<ConsoleSnapshot>(UNAVAILABLE_SNAPSHOT)
  const [busy,setBusy]=useState(true)
  const revision=useRef(0)
  const active=useRef(false)
  const refresh=useCallback(async()=>{
    const request=++revision.current
    if(!active.current)return
    setBusy(true)
    try{const s=await fetchConsoleSnapshot();if(active.current&&request===revision.current)setSnap(s)}
    finally{if(active.current&&request===revision.current)setBusy(false)}
  },[])
  useEffect(()=>{
    active.current=true;void refresh()
    const id=setInterval(()=>{void refresh()},30000)
    return ()=>{active.current=false;revision.current++;clearInterval(id)}
  },[refresh])
  return {snap,busy,refresh}
}
export function usePlatformConsole():ConsoleSnapshot{return useConsoleController().snap}