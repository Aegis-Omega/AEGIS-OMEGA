// Cycles 41–50: Enhanced telemetry with SSE streaming, gate state, and holonic metrics.
const BRIDGE = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'
const POLL_MS = 5000

export interface GateTelemetry {
  gate_acceptance_rate: number
  gate_total_signals: number
  gate_window: number
  is_sealed: boolean
}

export interface TelemetrySnapshot {
  sequence: number
  epoch: number
  avg_vcg_error: number
  drift_index: number
  pgcs_passes: boolean
  failsafe_state: string
  corruption_count: number
  calibrator_passes_100k: boolean
  gate?: GateTelemetry
  // Extended Layer B metrics — emitted when TGCS/AFSE are wired into bridge
  afse_r2?: number
  tgcs_variance?: number
  holonic_scaling_score?: number
}

export interface RalphCycleStatus {
  cycle: number
  scale: string
  phase: string
  entropy: number
}

export type TelemetryState =
  | { status: 'offline' }
  | { status: 'online'; data: TelemetrySnapshot; streaming: boolean }
  | { status: 'error'; message: string }

type Listener = (s: TelemetryState) => void

let abortController: AbortController | null = null
const listeners = new Set<Listener>()
let currentState: TelemetryState = { status: 'offline' }

function notify(s: TelemetryState) {
  currentState = s
  for (const l of listeners) l(s)
}

async function fetchOnce(): Promise<void> {
  try {
    const res = await fetch(`${BRIDGE}/telemetry`, { signal: AbortSignal.timeout(4000) } as RequestInit)
    if (!res.ok) {
      notify({ status: 'error', message: `Bridge ${res.status}` })
      return
    }
    const data = (await res.json()) as TelemetrySnapshot
    notify({ status: 'online', data, streaming: false })
  } catch {
    notify({ status: 'offline' })
  }
}

// SSE streaming path — used when bridge supports /telemetry/stream
function connectSSE(signal: AbortSignal): void {
  const es = new EventSource(`${BRIDGE}/telemetry/stream`)
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data as string) as TelemetrySnapshot
      notify({ status: 'online', data, streaming: true })
    } catch { /* ignore malformed frames */ }
  }
  es.onerror = () => {
    es.close()
    notify({ status: 'offline' })
  }
  signal.addEventListener('abort', () => es.close(), { once: true })
}

async function loop(signal: AbortSignal): Promise<void> {
  // Try SSE first; fall back to polling if EventSource not supported
  if (typeof EventSource !== 'undefined') {
    connectSSE(signal)
    return
  }
  while (!signal.aborted) {
    await fetchOnce()
    await new Promise<void>(r => {
      const t = setTimeout(r, POLL_MS)
      signal.addEventListener('abort', () => { clearTimeout(t); r() }, { once: true })
    })
  }
}

export function subscribeTelemetry(listener: Listener): () => void {
  listeners.add(listener)
  listener(currentState)

  if (!abortController) {
    abortController = new AbortController()
    void loop(abortController.signal)
  }

  return () => {
    listeners.delete(listener)
    if (listeners.size === 0 && abortController) {
      abortController.abort()
      abortController = null
    }
  }
}

export function getCurrentTelemetry(): TelemetryState {
  return currentState
}
