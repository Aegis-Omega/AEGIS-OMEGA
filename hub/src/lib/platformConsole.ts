// AEGIS Ω — runtime observation is not attestation.
// Public console never treats a fallback, a reported hash, or a claimed verdict
// as proof of independent replay. Nothing here authorizes execution.
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
  source: 'live' | 'demo'
  reason: string
  checked_at: string | null
  status: PlatformStatus
  calibration: CalibrationStatus
  tools: AgentTool[]
  checks: SystemCheck[]
}
const PLATFORM_URL = ((import.meta.env.VITE_PLATFORM_URL as string | undefined) || 'https://aegis-vertex.aegisomega.com').replace(/\/$/, '')
export const PLATFORM_ORIGIN = PLATFORM_URL
export const EMPTY_CALIBRATION: CalibrationStatus = {
  homeostasis_zone: 'slack', recommendation: 'MAINTAIN', fitness_mean: 0,
  fitness_variance: 0, hd_equivalent: 0, stagnation_rate: 0,
  window_size: 0, trend: 'stable', constitutional_factor_mean: 0,
}
export const EMPTY_PLATFORM: PlatformStatus = {
  version: 'unknown', contract_version: 'unknown', total_agents: 0,
  chain_valid: null, audit_chain_hash: null, available: false,
}
export function deriveChecks(source: 'live'|'demo', status: PlatformStatus, cal: CalibrationStatus): SystemCheck[] {
  const live = source === 'live'
  return [
    { label: 'Remote API observation', ok: live, reason: live ? 'HTTP payload received; not independent admission' : 'UNKNOWN — no complete remote observation' },
    { label: 'Schema version', ok: live && status.contract_version === '1.0.0', reason: !live ? 'UNKNOWN — not observed' : status.contract_version === '1.0.0' ? 'REPORTED v1.0.0; schema not independently audited' : `REPORTED mismatch: ${status.contract_version}` },
    { label: 'Audit-chain evidence', ok: false, reason: !live ? 'UNKNOWN — no runtime receipt' : status.chain_valid === false ? 'REPORTED INVALID — inspect signed evidence' : status.chain_valid === true ? 'REPORTED VALID — not independently replayed' : 'UNKNOWN — no chain verdict' },
    { label: 'Calibration data', ok: live && cal.window_size > 0, reason: live && cal.window_size > 0 ? `REPORTED ${cal.homeostasis_zone}; ${cal.window_size} observations` : 'UNKNOWN — no measured window' },
  ]
}
export const UNAVAILABLE_SNAPSHOT: ConsoleSnapshot = {
  source: 'demo',
  reason: 'Remote platform data unavailable. No demo substitute is presented as evidence.',
  checked_at: null,
  status: EMPTY_PLATFORM,
  calibration: EMPTY_CALIBRATION,
  tools: [],
  checks: deriveChecks('demo', EMPTY_PLATFORM, EMPTY_CALIBRATION),
}

async function fetchEnvelope<T>(path: string, signal: AbortSignal): Promise<T | null> {
  try {
    const response = await fetch(`${PLATFORM_URL}${path}`, { signal, method: 'GET', credentials: 'omit', cache: 'no-store' })
    if (!response.ok) return null
    const json: unknown = await response.json()
    if (!json || typeof json !== 'object' || !('data' in json)) return null
    return (json as {data: T}).data || null
  } catch { return null }
}
function isPlatformStatus(value: unknown): value is PlatformStatus {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  return typeof v.version === 'string' && typeof v.contract_version === 'string'
    && typeof v.total_agents === 'number' && Number.isFinite(v.total_agents)
    && typeof v.available === 'boolean'
    && (v.chain_valid === undefined || typeof v.chain_valid === 'boolean')
}
function isCalibration(value: unknown): value is CalibrationStatus {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  return typeof v.homeostasis_zone === 'string' && typeof v.recommendation === 'string'
    && typeof v.window_size === 'number' && Number.isFinite(v.window_size)
}
export async function fetchConsoleSnapshot(): Promise<ConsoleSnapshot> {
  const ctrl = new AbortController()
  const timeout = setTimeout(() => ctrl.abort(), 3200)
  try {
    const [status, cal, toolset] = await Promise.all([
      fetchEnvelope<unknown>('/platform/status', ctrl.signal),
      fetchEnvelope<unknown>('/platform/calibration', ctrl.signal),
      fetchEnvelope<unknown>('/platform/tools', ctrl.signal),
    ])
    const checked_at = new Date().toISOString()
    if (!isPlatformStatus(status) || !isCalibration(cal)) {
      return { ...UNAVAILABLE_SNAPSHOT, checked_at, reason: 'Required status or calibration response missing, invalid, unauthorized or blocked. No fallback telemetry.' }
    }
    const normalized: PlatformStatus = {
      ...status, chain_valid: typeof status.chain_valid === 'boolean' ? status.chain_valid : null,
      audit_chain_hash: typeof status.audit_chain_hash === 'string' ? status.audit_chain_hash : null,
    }
    const tools = toolset && typeof toolset === 'object' && 'tools' in toolset && Array.isArray(toolset.tools)
      ? (toolset.tools as AgentTool[]).filter(t => t && typeof t.api_name === 'string' && Array.isArray(t.capabilities)).slice(0, 80)
      : []
    return { source:'live', reason:'Remote API responded. Values are observed/reported, not independently certified.',
      checked_at, status:normalized, calibration:cal, tools, checks:deriveChecks('live', normalized, cal) }
  } finally { clearTimeout(timeout) }
}
export function useConsoleController(): {snap: ConsoleSnapshot; busy: boolean; refresh: ()=>Promise<void>} {
  const [snap, setSnap] = useState<ConsoleSnapshot>(UNAVAILABLE_SNAPSHOT)
  const [busy, setBusy] = useState(true)
  // All async results are bound to the latest request and current mount.
  const revision = useRef(0)
  const active = useRef(false)
  const refresh = useCallback(async () => {
    const request = ++revision.current
    if (!active.current) return
    setBusy(true)
    try {
      const next = await fetchConsoleSnapshot()
      if (active.current && request === revision.current) setSnap(next)
    } finally {
      if (active.current && request === revision.current) setBusy(false)
    }
  }, [])
  useEffect(() => {
    active.current = true
    void refresh()
    const timer = setInterval(() => { void refresh() }, 30000)
    return () => { active.current = false; revision.current++; clearInterval(timer) }
  }, [refresh])
  return {snap,busy,refresh}
}
// Compat for legacy consumers; new console uses controller with explicit reload.
export function usePlatformConsole(): ConsoleSnapshot {
  const {snap} = useConsoleController()
  return snap
}