import { useState, useEffect } from 'react'
import { isConstitutionallySound, type AutonodeDescriptor } from '../../../packages/shared/lib/autonode.js'

interface AutonodeStatusProps {
  bridgeUrl: string
}

function useAutonodeDescriptor(bridgeUrl: string) {
  const [data, setData] = useState<AutonodeDescriptor | null>(null)
  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const res = await fetch(`${bridgeUrl}/node`, { signal: AbortSignal.timeout(3000) } as RequestInit)
        if (res.ok && active) setData((await res.json()) as AutonodeDescriptor)
      } catch { /* bridge offline */ }
    }
    void poll()
    const id = setInterval(() => { void poll() }, 10000)
    return () => { active = false; clearInterval(id) }
  }, [bridgeUrl])
  return data
}

export function AutonodeStatus({ bridgeUrl }: AutonodeStatusProps) {
  const node = useAutonodeDescriptor(bridgeUrl)
  if (node == null) return null

  const sound = isConstitutionallySound(node)

  return (
    <div className="border-t border-aegis-border pt-1 space-y-0.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-aegis-muted font-medium">Autonode</span>
        <span
          className="text-xs font-mono px-1 rounded"
          style={{
            color: sound ? '#34D399' : '#F87171',
            background: sound ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)',
          }}
        >
          {sound ? 'T0 PASS' : 'T0 FAIL'}
        </span>
      </div>

      <div className="flex items-center justify-between text-xs py-0.5">
        <span className="text-aegis-muted">node_id</span>
        <span className="font-mono text-aegis-text">{node.node_id.slice(0, 8)}…</span>
      </div>

      <div className="flex items-center justify-between text-xs py-0.5">
        <span className="text-aegis-muted">const. hash</span>
        <span className="font-mono text-aegis-muted">{node.constitutional_hash.slice(0, 12)}…</span>
      </div>

      <div className="flex items-center justify-between text-xs py-0.5">
        <span className="text-aegis-muted">epoch</span>
        <span className="font-mono text-aegis-text">{node.epoch}</span>
      </div>
    </div>
  )
}
