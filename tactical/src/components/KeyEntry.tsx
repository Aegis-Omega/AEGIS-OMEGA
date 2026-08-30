import { Key } from 'lucide-react'
import { useState } from 'react'

interface Props { onKey: (key: string) => void }

export function KeyEntry({ onKey }: Props) {
  const [val, setVal] = useState('')

  function submit() {
    const k = val.trim()
    if (!k) return
    onKey(k)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-aegis-bg p-4">
      <div className="w-full max-w-md bg-aegis-panel border border-aegis-border rounded p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="bg-aegis-accent/10 border border-aegis-accent/40 rounded p-3">
              <Key size={24} className="text-aegis-accent" />
            </div>
          </div>
          <h1 className="text-lg font-mono font-bold text-white tracking-widest">AEGIS-Ω</h1>
          <p className="text-xs font-mono text-aegis-text/60">TACTICAL OPERATIONS CENTER</p>
        </div>

        <div className="space-y-2">
          <label className="text-[10px] font-mono text-aegis-text/60 tracking-widest">API_KEY</label>
          <input
            type="password"
            className="w-full bg-aegis-bg border border-aegis-border rounded px-3 py-2 text-sm font-mono text-white placeholder-aegis-text/30 focus:outline-none focus:border-aegis-accent/60"
            placeholder="aegis_…"
            value={val}
            onChange={e => setVal(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            autoFocus
          />
          <p className="text-[10px] font-mono text-aegis-text/40">
            Dev mode: any <code className="text-aegis-dim">aegis_*</code> key works when bridge has no Supabase configured.
          </p>
        </div>

        <button
          type="button"
          onClick={submit}
          disabled={!val.trim()}
          className="w-full bg-aegis-accent/10 border border-aegis-accent/60 hover:bg-aegis-accent/20 disabled:opacity-30 text-aegis-accent text-xs font-mono font-bold rounded py-2 transition-colors glow-accent"
        >
          AUTHENTICATE
        </button>
      </div>
    </div>
  )
}
