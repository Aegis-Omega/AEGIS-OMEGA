// Gate 240 — Anthropic Admin API org status panel.
// Polls /org on the bridge (30s interval). Bridge caches the Admin API response for 60s.
// Renders silently absent when bridge is offline or key is unset.
import { useState, useEffect } from 'react'
import { Building2 } from 'lucide-react'

const BRIDGE = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

interface OrgStatus {
  available: boolean
  reason?: string
  org_id?: string
  org_name?: string
  active_key_count?: number
  workspace_count?: number
}

function useOrgStatus() {
  const [data, setData] = useState<OrgStatus | null>(null)
  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const res = await fetch(`${BRIDGE}/org`, { signal: AbortSignal.timeout(6000) } as RequestInit)
        if (res.ok && active) setData((await res.json()) as OrgStatus)
      } catch { /* bridge offline */ }
    }
    void poll()
    const id = setInterval(() => { void poll() }, 30_000)
    return () => { active = false; clearInterval(id) }
  }, [])
  return data
}

export function OrgPanel() {
  const org = useOrgStatus()
  if (org == null) return null

  return (
    <div className="border-t border-aegis-border pt-1 space-y-0.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 text-xs text-aegis-muted font-medium">
          <Building2 size={10} />
          <span>Org</span>
        </div>
        <span
          className="text-xs font-mono px-1 rounded"
          style={{
            color: org.available ? '#34D399' : '#6B6B7A',
            background: org.available ? 'rgba(52,211,153,0.1)' : 'rgba(107,107,122,0.1)',
          }}
        >
          {org.available ? 'CONNECTED' : 'NO KEY'}
        </span>
      </div>

      {org.available && org.org_name != null && (
        <div className="flex items-center justify-between text-xs py-0.5">
          <span className="text-aegis-muted">name</span>
          <span className="font-mono text-aegis-text truncate max-w-[110px]">{org.org_name}</span>
        </div>
      )}

      {org.available && (
        <>
          <div className="flex items-center justify-between text-xs py-0.5">
            <span className="text-aegis-muted">active keys</span>
            <span className="font-mono text-aegis-text">{org.active_key_count ?? '—'}</span>
          </div>
          <div className="flex items-center justify-between text-xs py-0.5">
            <span className="text-aegis-muted">workspaces</span>
            <span className="font-mono text-aegis-text">{org.workspace_count ?? '—'}</span>
          </div>
          {org.org_id != null && (
            <div className="flex items-center justify-between text-xs py-0.5">
              <span className="text-aegis-muted">org_id</span>
              <span className="font-mono text-aegis-muted">{org.org_id.slice(0, 8)}…</span>
            </div>
          )}
        </>
      )}
    </div>
  )
}
