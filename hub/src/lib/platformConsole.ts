// AEGIS-Ω Console — read-only platform telemetry.
// Fail-closed: no demo telemetry, synthetic metrics or fabricated tools.
import { useEffect, useState } from 'react'
import { toConsoleSnapshot, unknownSnapshot } from './platformContract.js'
import type { ConsoleSnapshot } from './platformContract.js'
export type {
  HomeostasisZone, CalibrationRecommendation, Tier, CalibrationStatus,
  AgentTool, PlatformStatus, SystemCheck, ConsoleSnapshot,
} from './platformContract.js'

const PLATFORM_URL =
  ((import.meta.env.VITE_PLATFORM_URL as string | undefined) ??
    'https://aegis-vertex.aegisomega.com').replace(/\/$/, '')

async function getData(path: string, signal: AbortSignal): Promise<unknown> {
  try {
    const res = await fetch(`${PLATFORM_URL}${path}`, { signal })
    if (!res.ok) return undefined
    const raw: unknown = await res.json()
    if (raw !== null && typeof raw === 'object' && !Array.isArray(raw) && 'data' in raw) {
      return raw.data
    }
    return undefined
  } catch {
    return undefined
  }
}

export async function fetchConsoleSnapshot(): Promise<ConsoleSnapshot> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 2000)
  try {
    const [status, calibration, tools] = await Promise.all([
      getData('/platform/status', ctrl.signal),
      getData('/platform/calibration', ctrl.signal),
      getData('/platform/tools', ctrl.signal),
    ])
    return toConsoleSnapshot(status, calibration, tools)
  } catch {
    return unknownSnapshot('Platform request failed')
  } finally {
    clearTimeout(timer)
  }
}

export function usePlatformConsole(): ConsoleSnapshot {
  const [snap, setSnap] = useState<ConsoleSnapshot>(() => unknownSnapshot('Awaiting first verified API response'))
  useEffect(() => {
    let cancelled = false
    async function poll() {
      const next = await fetchConsoleSnapshot()
      if (!cancelled) setSnap(next)
    }
    void poll()
    const interval = setInterval(() => { void poll() }, 8000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])
  return snap
}
