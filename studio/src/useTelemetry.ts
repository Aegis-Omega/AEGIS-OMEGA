import { useState, useEffect } from 'react'
import type { TelemetrySnapshot } from './types.js'

const BRIDGE_URL = 'http://localhost:7890'
const POLL_MS = 5000

export function useTelemetry() {
  const [snapshot, setSnapshot] = useState<TelemetrySnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const res = await fetch(`${BRIDGE_URL}/telemetry`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json() as TelemetrySnapshot
        if (active) { setSnapshot(data); setError(null) }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : 'bridge unreachable')
      }
    }
    void poll()
    const id = setInterval(() => void poll(), POLL_MS)
    return () => { active = false; clearInterval(id) }
  }, [])

  return { snapshot, error }
}
