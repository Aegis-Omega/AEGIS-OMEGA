import { useEffect, useState } from 'react'

const BRIDGE = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

export interface BridgeHealth {
  online: boolean
  version?: string
  chain_valid?: boolean
  total_agents?: number
  contract_version?: string
  t0_verdict?: boolean
  corruption_count?: number
}

export function useBridgeStatus(): BridgeHealth {
  const [health, setHealth] = useState<BridgeHealth>({ online: false })

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        const [statusRes, nodeRes] = await Promise.all([
          fetch(`${BRIDGE}/platform/status`, { signal: AbortSignal.timeout(3000) }),
          fetch(`${BRIDGE}/node`,            { signal: AbortSignal.timeout(3000) }),
        ])
        if (cancelled) return

        const status = statusRes.ok
          ? (await statusRes.json() as { data: Record<string, unknown> }).data
          : {}
        const node = nodeRes.ok
          ? await nodeRes.json() as Record<string, unknown>
          : {}

        setHealth({
          online:           true,
          version:          status['version'] as string | undefined,
          chain_valid:      status['chain_valid'] as boolean | undefined,
          total_agents:     status['total_agents'] as number | undefined,
          contract_version: status['contract_version'] as string | undefined,
          t0_verdict:       node['t0_verdict'] as boolean | undefined,
          corruption_count: node['corruption_count'] as number | undefined,
        })
      } catch {
        if (!cancelled) setHealth({ online: false })
      }
    }

    void check()
    const id = setInterval(() => void check(), 10_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  return health
}
