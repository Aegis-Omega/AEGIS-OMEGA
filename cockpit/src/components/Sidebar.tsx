import { Plus, Trash2 } from 'lucide-react'
import type { Session } from '../hooks/useSessions.js'
import type { Provider } from '../lib/agent.js'
import { TelemetryPanel } from './TelemetryPanel.js'

const PROVIDERS: { value: Provider; label: string; weight?: number; dot: string }[] = [
  { value: 'claude',    label: 'Claude',  weight: 618, dot: '#60A5FA' },
  { value: 'dashscope', label: 'Qwen',    weight: 191, dot: '#A78BFA' },
  { value: 'ollama',    label: 'Ollama',              dot: '#3F3F4A'  },
]

const COUNCIL = [
  { name: 'Claude',       role: 'Coordinator',      weight: '618', dot: '#60A5FA' },
  { name: 'Qwen',         role: 'Implementer',       weight: '191', dot: '#A78BFA' },
  { name: 'ChatGPT',      role: 'Adversarial audit', weight: '191', dot: '#34D399' },
  { name: 'Tarik Skalić', role: 'Guardian · veto',   weight: '∞',   dot: '#C8A96E' },
]

interface SidebarProps {
  sessions: Session[]
  activeId: string | null
  provider: Provider
  onNewChat: () => void
  onSelectSession: (id: string) => void
  onDeleteSession: (id: string) => void
  onProviderChange: (p: Provider) => void
}

function Dot({ color, size = 6 }: { color: string; size?: number }) {
  return (
    <span
      className="rounded-full shrink-0"
      style={{ width: size, height: size, background: color, display: 'inline-block' }}
    />
  )
}

export function Sidebar({
  sessions, activeId, provider,
  onNewChat, onSelectSession, onDeleteSession, onProviderChange,
}: SidebarProps) {
  return (
    <aside
      className="w-56 shrink-0 flex flex-col overflow-y-auto"
      style={{ borderRight: '1px solid #1E1E22', background: '#0C0C0E' }}
    >
      {/* Brand */}
      <div className="px-4 pt-5 pb-4" style={{ borderBottom: '1px solid #1E1E22' }}>
        <p className="font-mono font-semibold tracking-[0.2em] text-base" style={{ color: '#C8A96E' }}>
          AEGIS-Ω
        </p>
        <p className="font-mono text-xs mt-0.5 opacity-35" style={{ color: '#6B6B7A' }}>
          1/φ ≈ 0.6180 · E[S|F] = S
        </p>
      </div>

      {/* New session */}
      <div className="p-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all"
          style={{ color: '#6B6B7A' }}
          onMouseEnter={e => {
            const el = e.currentTarget
            el.style.background = '#141416'
            el.style.color = '#ECEAE3'
          }}
          onMouseLeave={e => {
            const el = e.currentTarget
            el.style.background = 'transparent'
            el.style.color = '#6B6B7A'
          }}
        >
          <Plus size={13} />
          New session
        </button>
      </div>

      {/* Sessions */}
      <nav className="px-2 pb-2 space-y-0.5 flex-1" style={{ borderBottom: '1px solid #1E1E22' }}>
        {sessions.length === 0 ? (
          <p className="text-center text-xs py-6 opacity-30" style={{ color: '#6B6B7A' }}>
            No sessions yet
          </p>
        ) : (
          sessions.map(s => (
            <div
              key={s.id}
              onClick={() => onSelectSession(s.id)}
              className="group flex items-center gap-1 px-3 py-2 rounded-lg cursor-pointer text-xs transition-colors"
              style={{
                background: s.id === activeId ? '#141416' : 'transparent',
                color: s.id === activeId ? '#ECEAE3' : '#6B6B7A',
              }}
              onMouseEnter={e => {
                if (s.id !== activeId) {
                  (e.currentTarget as HTMLElement).style.background = '#141416'
                  ;(e.currentTarget as HTMLElement).style.color = '#ECEAE3'
                }
              }}
              onMouseLeave={e => {
                if (s.id !== activeId) {
                  (e.currentTarget as HTMLElement).style.background = 'transparent'
                  ;(e.currentTarget as HTMLElement).style.color = '#6B6B7A'
                }
              }}
            >
              <span className="flex-1 truncate">{s.title}</span>
              <button
                onClick={e => { e.stopPropagation(); onDeleteSession(s.id) }}
                aria-label={`Delete ${s.title}`}
                className="opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: '#6B6B7A' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#F87171' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#6B6B7A' }}
              >
                <Trash2 size={11} />
              </button>
            </div>
          ))
        )}
      </nav>

      {/* Orchestration Alliance */}
      <div className="p-3" style={{ borderBottom: '1px solid #1E1E22' }}>
        <p className="font-mono text-xs uppercase tracking-widest opacity-35 px-1 mb-2.5" style={{ color: '#6B6B7A' }}>
          Alliance · 1000
        </p>
        <div className="space-y-0.5">
          {COUNCIL.map(agent => (
            <div key={agent.name} className="flex items-center gap-2 px-2 py-1.5 rounded-lg">
              <Dot color={agent.dot} size={6} />
              <span className="flex-1 text-xs truncate" style={{ color: '#ECEAE3' }}>{agent.name}</span>
              <span className="font-mono text-xs opacity-40" style={{ color: agent.dot }}>
                {agent.weight}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Telemetry (bridge status) */}
      <TelemetryPanel />

      {/* Inference route */}
      <div className="p-3 mt-auto" style={{ borderTop: '1px solid #1E1E22' }}>
        <p className="font-mono text-xs opacity-35 px-1 mb-2" style={{ color: '#6B6B7A' }}>
          Inference route
        </p>
        <div className="space-y-0.5">
          {PROVIDERS.map(p => (
            <button
              key={p.value}
              onClick={() => onProviderChange(p.value)}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-left transition-all"
              style={{
                background: provider === p.value ? '#141416' : 'transparent',
                color: provider === p.value ? '#ECEAE3' : '#6B6B7A',
                border: provider === p.value ? '1px solid #1E1E22' : '1px solid transparent',
              }}
            >
              <Dot color={provider === p.value ? p.dot : '#3F3F4A'} size={5} />
              <span className="flex-1">{p.label}</span>
              {p.weight !== undefined && (
                <span className="font-mono opacity-40">{p.weight}</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}
