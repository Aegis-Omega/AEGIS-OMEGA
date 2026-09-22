import { useCallback, useEffect, useState } from 'react'

const BRIDGE = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

type RuntimeState = 'loading' | 'ready' | 'unavailable'
type ProbeState = 'idle' | 'running' | 'pass' | 'error'

interface RuntimeStatusPayload {
  state: string
  available: boolean
  scope: string
  network_authority: boolean
  persistent_state: boolean
  authority_effect: string
}

interface ArcProbePayload {
  schema: string
  operation: string
  output: number[][]
  authority_effect: string
}

interface Envelope<T> { data: T }

export interface ArchiveRuntimeView {
  state: RuntimeState
  declaredState: string
  scope: string
  authorityEffect: string
  networkAuthority: boolean
  persistentState: boolean
  error: string | null
  probeState: ProbeState
  probeOutput: number[][] | null
  runArcProbe: () => Promise<void>
}

export function useArchiveRuntime(apiKey: string): ArchiveRuntimeView {
  const [state, setState] = useState<RuntimeState>('loading')
  const [declaredState, setDeclaredState] = useState('UNKNOWN')
  const [scope, setScope] = useState('—')
  const [authorityEffect, setAuthorityEffect] = useState('NONE')
  const [networkAuthority, setNetworkAuthority] = useState(false)
  const [persistentState, setPersistentState] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [probeState, setProbeState] = useState<ProbeState>('idle')
  const [probeOutput, setProbeOutput] = useState<number[][] | null>(null)

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      try {
        const res = await fetch(`${BRIDGE}/platform/archive/runtime/status`, {
          signal: AbortSignal.timeout(3000),
        })
        if (!res.ok) throw new Error(`status ${res.status}`)
        const envelope = await res.json() as Envelope<RuntimeStatusPayload>
        const data = envelope.data
        if (!data || data.authority_effect !== 'NONE') {
          throw new Error('authority boundary mismatch')
        }
        if (cancelled) return
        setDeclaredState(data.state)
        setScope(data.scope)
        setAuthorityEffect(data.authority_effect)
        setNetworkAuthority(Boolean(data.network_authority))
        setPersistentState(Boolean(data.persistent_state))
        setState(data.available ? 'ready' : 'unavailable')
        setError(null)
      } catch (e) {
        if (cancelled) return
        setState('unavailable')
        setDeclaredState('INVALID_OR_STALE')
        setError(String(e))
      }
    }

    void refresh()
    const id = setInterval(() => void refresh(), 15_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const runArcProbe = useCallback(async () => {
    if (state !== 'ready' || probeState === 'running') return
    setProbeState('running')
    setProbeOutput(null)
    setError(null)

    const params = new URLSearchParams({
      op: '1',
      grid: JSON.stringify([[1, 2], [3, 4]]),
    })

    try {
      const res = await fetch(`${BRIDGE}/platform/archive/runtime/arc?${params.toString()}`, {
        method: 'GET',
        headers: { 'x-api-key': apiKey },
        signal: AbortSignal.timeout(5000),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ error: res.statusText })) as { error?: string }
        throw new Error(`${res.status}: ${detail.error ?? res.statusText}`)
      }
      const envelope = await res.json() as Envelope<ArcProbePayload>
      const data = envelope.data
      if (
        !data ||
        data.authority_effect !== 'NONE' ||
        data.operation !== 'ROT90' ||
        JSON.stringify(data.output) !== JSON.stringify([[2, 4], [1, 3]])
      ) {
        throw new Error('bounded ARC receipt mismatch')
      }
      setProbeOutput(data.output)
      setProbeState('pass')
    } catch (e) {
      setProbeState('error')
      setError(String(e))
    }
  }, [apiKey, probeState, state])

  return {
    state,
    declaredState,
    scope,
    authorityEffect,
    networkAuthority,
    persistentState,
    error,
    probeState,
    probeOutput,
    runArcProbe,
  }
}
