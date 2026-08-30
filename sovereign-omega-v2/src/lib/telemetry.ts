const BRIDGE = 'http://localhost:7890'
const POLL_MS = 5000

export interface TelemetrySnapshot {
  sequence: number
  epoch: number
  avg_vcg_error: number
  drift_index: number
  pgcs_passes: boolean
  failsafe_state: string
  corruption_count: number
  calibrator_passes_100k: boolean
}

export type TelemetryState =
  | { status: 'offline' }
  | { status: 'online'; data: TelemetrySnapshot }
  | { status: 'error'; message: string }

type Listener = (s: TelemetryState) => void

let abortController: AbortController | null = null
const listeners = new Set<Listener>()
let currentState: TelemetryState = { status: 'offline' }

function notify(s: TelemetryState): void {
  currentState = s
  for (const l of listeners) l(s)
}

async function fetchOnce(signal: AbortSignal): Promise<void> {
  try {
    const res = await fetch(`${BRIDGE}/telemetry`, { signal })
    if (!res.ok) { notify({ status: 'error', message: `Bridge ${res.status}` }); return }
    const data = (await res.json()) as TelemetrySnapshot
    notify({ status: 'online', data })
  } catch (err) {
    if ((err as Error).name === 'AbortError') return
    notify({ status: 'offline' })
  }
}

async function loop(signal: AbortSignal): Promise<void> {
  while (!signal.aborted) {
    await fetchOnce(signal)
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
