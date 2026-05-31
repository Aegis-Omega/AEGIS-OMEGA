// AEGIS Omega — optional live bridge telemetry overlay
//
// EPISTEMIC TIER: T1 — observational projection of the running governance
// runtime. The Python bridge (python/bridge.py) serves these endpoints on
// localhost:7890 on the operator's machine. A deployed page can only reach it
// when VITE_BRIDGE_URL points at a publicly reachable proxy (the local Claude
// instance wires credentials separately). When unset or unreachable, every
// fetch fails fast and the UI falls back to the browser substrate — no hanging
// requests, no console noise beyond a single debug line.

export interface LiveTelemetry {
  sequence: number
  epoch: number
  avg_vcg_error: number
  drift_index: number
  corruption_count: number
  pgcs_passes: boolean
  failsafe_state: string
  gate_acceptance_rate: number
}

export interface LiveNode {
  t0_verdict: boolean
  corruption_count: number
  phi_threshold: number
  drift_risk: number
  constitutional_hash: string
}

export interface LiveResonance {
  is_resonant: boolean
  is_certified: boolean
  phi_convergent: boolean
  resonance_depth: number
  phi_headroom: number
}

export interface LiveBlock {
  block_height: number
  sequence: number
  state_root: string
  bft_quorum: number
  validator_weights: { coordinator: number; auditor_1: number; auditor_2: number }
  t0_verdict: boolean
  corruption_count: number
  drift_risk: number
  is_replay_reconstructable: boolean
  schema_version: string
}

export interface BridgeSnapshot {
  reachable: boolean
  telemetry?: LiveTelemetry
  node?: LiveNode
  resonance?: LiveResonance
  block?: LiveBlock
}

const BRIDGE_URL = (import.meta.env.VITE_BRIDGE_URL as string | undefined)?.replace(/\/$/, '')

async function getJson<T>(path: string, signal: AbortSignal): Promise<T | undefined> {
  if (!BRIDGE_URL) return undefined
  try {
    const res = await fetch(`${BRIDGE_URL}${path}`, { signal })
    if (!res.ok) return undefined
    return (await res.json()) as T
  } catch {
    return undefined
  }
}

// Single-shot fetch of all three endpoints. Aborts after 2s so the page never
// stalls waiting on an unreachable bridge.
export async function fetchBridgeSnapshot(): Promise<BridgeSnapshot> {
  if (!BRIDGE_URL) return { reachable: false }
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 2000)
  try {
    const [telemetry, node, resonance, block] = await Promise.all([
      getJson<LiveTelemetry>('/telemetry', ctrl.signal),
      getJson<LiveNode>('/node', ctrl.signal),
      getJson<LiveResonance>('/resonance', ctrl.signal),
      getJson<LiveBlock>('/block', ctrl.signal),
    ])
    const reachable = Boolean(telemetry || node || resonance || block)
    return { reachable, telemetry, node, resonance, block }
  } finally {
    clearTimeout(timer)
  }
}

export const bridgeConfigured = Boolean(BRIDGE_URL)
