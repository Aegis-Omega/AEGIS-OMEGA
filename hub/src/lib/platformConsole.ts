// AEGIS-Ω Console — live platform data layer.
// EPISTEMIC TIER: T1 — observational projection of the /platform/* API.
//
// Fetches /platform/status, /platform/calibration, /platform/tools with a hard
// 2s abort. When the bridge is unreachable, falls back to a curated demo
// snapshot — never a blank. Every state carries its REASON (loud, not silent):
// the operator always knows whether they're seeing live data or demo, and why.

import { useEffect, useState } from 'react'

// ── Mirrored contract shapes (source of truth: @shared/lib/platform-contract) ──

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

export interface AgentTool {
  api_name: string
  endpoint_url: string
  capabilities: string[]
  tier_required: Tier
}

export interface PlatformStatus {
  version: string
  contract_version: string
  total_agents: number
  chain_valid: boolean | null
  audit_chain_hash: string | null
  available: boolean
}

// A single legible verification line — the loud-failure primitive.
export interface SystemCheck {
  label: string
  ok: boolean
  reason: string
}

export interface ConsoleSnapshot {
  source: 'live' | 'demo'
  reason: string
  status: PlatformStatus
  calibration: CalibrationStatus
  tools: AgentTool[]
  checks: SystemCheck[]
}

const PLATFORM_URL =
  ((import.meta.env.VITE_PLATFORM_URL as string | undefined) ??
    'https://aegis-vertex.aegisomega.com').replace(/\/$/, '')

// ── Demo snapshot — curated, believable, premium. Used when bridge unreachable ──

const DEMO_TOOLS: AgentTool[] = [
  { api_name: 'Anthropic Claude', endpoint_url: 'api.anthropic.com',  capabilities: ['inference', 'governed-call', 'streaming'], tier_required: 'sovereign' },
  { api_name: 'DashScope Qwen',   endpoint_url: 'dashscope.aliyuncs', capabilities: ['inference', 'fallback'],                  tier_required: 'operator' },
  { api_name: 'Supabase',         endpoint_url: 'supabase.co',        capabilities: ['ledger', 'key-store', 'memory'],         tier_required: 'operator' },
  { api_name: 'Stripe',           endpoint_url: 'api.stripe.com',     capabilities: ['provision', 'webhook-verify'],           tier_required: 'operator' },
  { api_name: 'Resend',           endpoint_url: 'api.resend.com',     capabilities: ['key-delivery'],                          tier_required: 'explorer' },
  { api_name: 'GitHub',           endpoint_url: 'api.github.com',     capabilities: ['sponsors', 'webhook-verify'],            tier_required: 'explorer' },
]

const DEMO_SNAPSHOT: ConsoleSnapshot = {
  source: 'demo',
  reason: 'bridge unreachable — showing representative demo state',
  status: {
    version: '1.0.0', contract_version: '1.0.0', total_agents: 39,
    chain_valid: null, audit_chain_hash: null,
    available: false,
  },
  calibration: {
    homeostasis_zone: 'optimal', recommendation: 'MAINTAIN',
    fitness_mean: 0.612, fitness_variance: 0.014, hd_equivalent: 0.118,
    stagnation_rate: 0.0, window_size: 10, trend: 'rising', constitutional_factor_mean: 0.94,
  },
  tools: DEMO_TOOLS,
  checks: [],
}

// ── Loud verification: derive a legible check list from the live/demo state ────

export function deriveChecks(
  source: 'live' | 'demo',
  status: PlatformStatus,
  cal: CalibrationStatus,
): SystemCheck[] {
  const live = source === 'live'
  const chainClaim = !live ? 'UNKNOWN — demonstration data'
    : status.chain_valid === true ? 'REPORTED_VALID — no independently verified receipt'
    : status.chain_valid === false ? 'REPORTED_INVALID — investigate backend evidence'
    : 'UNKNOWN — backend supplied no chain verdict'
  return [
    { label: 'Platform reachable', ok: live,
      reason: live ? 'HTTP transport observed; not a governance verdict' : 'unreachable — demo only' },
    { label: 'Contract version', ok: live && status.contract_version === '1.0.0',
      reason: live ? `backend reports ${status.contract_version}` : 'UNKNOWN — demo only' },
    { label: 'Independent chain verification', ok: false, reason: chainClaim },
    { label: 'Homeostasis observation', ok: false,
      reason: live ? `REPORTED_ONLY — ${cal.homeostasis_zone} · ${cal.recommendation}` : 'UNKNOWN — not measured' },
    { label: 'Stagnation observation', ok: false,
      reason: live && Number.isFinite(cal.stagnation_rate)
        ? `REPORTED_ONLY — ${Math.round(cal.stagnation_rate * 100)}%` : 'UNKNOWN — not measured' },
    { label: 'Constitutional factor observation', ok: false,
      reason: live && Number.isFinite(cal.constitutional_factor_mean)
        ? `REPORTED_ONLY — mean ${cal.constitutional_factor_mean.toFixed(2)}` : 'UNKNOWN — not measured' },
  ]
}

async function getData<T>(path: string, signal: AbortSignal): Promise<T | undefined> {
  try {
    const res = await fetch(`${PLATFORM_URL}${path}`, { signal })
    if (!res.ok) return undefined
    const env = (await res.json()) as { data?: T }
    return env.data
  } catch {
    return undefined
  }
}

export async function fetchConsoleSnapshot(): Promise<ConsoleSnapshot> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 2000)
  try {
    const [status, calibration, toolsEnv] = await Promise.all([
      getData<PlatformStatus>('/platform/status', ctrl.signal),
      getData<CalibrationStatus>('/platform/calibration', ctrl.signal),
      getData<{ tools: AgentTool[] }>('/platform/tools', ctrl.signal),
    ])
    if (!status || !calibration) {
      return { ...DEMO_SNAPSHOT, checks: deriveChecks('demo', DEMO_SNAPSHOT.status, DEMO_SNAPSHOT.calibration) }
    }
    const tools = toolsEnv?.tools?.length ? toolsEnv.tools : DEMO_TOOLS
    // Normalize missing/ambiguous provenance to UNKNOWN, not false.
    const normalizedStatus: PlatformStatus = {
      ...status,
      chain_valid: status.chain_valid === true ? true : status.chain_valid === false ? false : null,
      audit_chain_hash: typeof status.audit_chain_hash === 'string' && /^[a-f0-9]{64}$/i.test(status.audit_chain_hash)
        ? status.audit_chain_hash : null,
    }
    return {
      source: 'live', reason: 'backend responded; verification not established',
      status: normalizedStatus, calibration, tools,
      checks: deriveChecks('live', normalizedStatus, calibration),
    }
  } finally {
    clearTimeout(timer)
  }
}

// React hook — single fetch on mount, then poll every 8s. Always returns a
// usable snapshot (demo until the first live response lands).
export function usePlatformConsole(): ConsoleSnapshot {
  const [snap, setSnap] = useState<ConsoleSnapshot>({
    ...DEMO_SNAPSHOT,
    checks: deriveChecks('demo', DEMO_SNAPSHOT.status, DEMO_SNAPSHOT.calibration),
  })
  useEffect(() => {
    let cancelled = false
    async function poll() {
      const s = await fetchConsoleSnapshot()
      if (!cancelled) setSnap(s)
    }
    void poll()
    const id = setInterval(() => { void poll() }, 8000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])
  return snap
}
