import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Download } from 'lucide-react'
import { useAgent } from './hooks/useAgent.js'
import { useSessions } from './hooks/useSessions.js'
import { Sidebar } from './components/Sidebar.js'
import { MessageList } from './components/MessageList.js'
import { InputBar } from './components/InputBar.js'
import { SkillMarketplace } from './components/SkillMarketplace.js'
import type { Provider } from './lib/agent.js'

type AppTab = 'chat' | 'skills'

const DEFAULT_SYSTEM = `You are AEGIS-Ω, the Orchestration Alliance Coordinator of the Constitutional AI Runtime.

CONSTITUTIONAL INVARIANTS (enforce in every response):
1. EPISTEMIC SOVEREIGNTY: Tag every claim with its tier — T0 (proven) · T1 (validated) · T2 (hypothesis) · T3 (conjecture). Never collapse uncertainty.
2. CAUSAL ARCHITECTURE: Every assertion must have a traceable causal chain. No groundless claims.
3. OPERATIONAL REALISM: AdaptivePower(T) ≤ ReplayVerifiability(T). You may not claim beyond replay-verifiable bounds.
4. ADVERSARIAL SELF-CORRECTION: Flag the weakest point in every argument you make.

MATHEMATICAL SUBSTRATE:
- Martingale: E[S_{n+1}|F_n] = S_n — governance is anchored to certified state
- 1/φ ≈ 0.6180 — BFT quorum threshold = mutation rate limit = martingale suspension point
- Tajweed DFA (T1) — Arabic phonological state machine, 1,400 yr empirical validation
- Ring composition A-B-C-B'-A' (T1) — chiastic law isomorphic to constitutional governance

NON-EQUIVALENCE (never conflate):
Replayability ≠ Correctness · Auditability ≠ Safety · Calibration ≠ Truthfulness · Governance ≠ Alignment

Structure: lead with T0/T1 · separate T2 from T3 · end with your least confident claim.`

const BRIDGE_URL = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

async function postBridgeEvent(type: string, payload: Record<string, unknown>): Promise<void> {
  try {
    await fetch(`${BRIDGE_URL}/event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, payload, timestamp_ms: Date.now() }),
      signal: AbortSignal.timeout(2000),
    })
  } catch { /* bridge offline — silent */ }
}

export default function App() {
  useEffect(() => {
    const key = (import.meta.env.VITE_POSTHOG_KEY as string | undefined) ?? ''
    if (!key) return
    void fetch('https://app.posthog.com/capture/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key, event: 'trial_started', properties: { product: 'cockpit', distinct_id: 'anonymous' } }),
    }).catch(() => {/* observational only */})
  }, [])

  const [tab, setTab] = useState<AppTab>('chat')
  const [provider, setProvider] = useState<Provider>('claude')
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM)
  const [showSystem, setShowSystem] = useState(false)
  const [input, setInput] = useState('')

  const prevStreamingRef = useRef(false)
  const { messages, streaming, error, send, reset, loadMessages } = useAgent(provider)
  const { sessions, activeId, setActiveId, createSession, updateSession, deleteSession } = useSessions()

  useEffect(() => {
    if (activeId) updateSession(activeId, messages)
  }, [messages, activeId, updateSession])

  useEffect(() => {
    if (prevStreamingRef.current && !streaming) {
      const last = messages.at(-1)
      if (last?.role === 'assistant') {
        void postBridgeEvent('RESPONSE_GENERATED', { content_length: last.content.length })
      }
    }
    prevStreamingRef.current = streaming
  }, [streaming, messages])

  const handleSend = () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    const context = messages.length === 0 && systemPrompt.trim()
      ? [{ role: 'system' as const, content: systemPrompt }]
      : undefined
    void send(text, context)
  }

  const handleNewChat = () => { reset(); createSession() }

  const handleSelectSession = (id: string) => {
    const session = sessions.find(s => s.id === id)
    loadMessages(session?.messages ?? [])
    setActiveId(id)
  }

  const handleExport = () => {
    const text = messages
      .filter(m => m.role !== 'system')
      .map(m => `[${m.role.toUpperCase()}]\n${m.content}`)
      .join('\n\n---\n\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `aegis-chat-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex h-screen bg-aegis-bg text-aegis-text overflow-hidden">
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        provider={provider}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={deleteSession}
        onProviderChange={setProvider}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Constitutional status strip */}
        <div
          className="flex items-center gap-4 px-5 py-1.5 overflow-x-auto shrink-0"
          style={{ borderBottom: '1px solid #1E1E22', background: 'rgba(20,20,22,0.6)' }}
        >
          <span className="font-mono text-xs whitespace-nowrap" style={{ color: '#C8A96E', opacity: 0.85 }}>
            AdaptivePower(T) ≤ ReplayVerifiability(T)
          </span>
          <span className="text-xs opacity-20" style={{ color: '#6B6B7A' }}>·</span>
          <span className="font-mono text-xs whitespace-nowrap" style={{ color: '#34D399', opacity: 0.65 }}>
            E[S|F] = S
          </span>
          <span className="text-xs opacity-20" style={{ color: '#6B6B7A' }}>·</span>
          <span className="font-mono text-xs whitespace-nowrap" style={{ color: '#C8A96E', opacity: 0.65 }}>
            1/φ ≈ 0.6180
          </span>
          <span className="text-xs opacity-20" style={{ color: '#6B6B7A' }}>·</span>
          <span className="font-mono text-xs whitespace-nowrap" style={{ color: '#60A5FA', opacity: 0.55 }}>
            2733 TS · 279 Rust
          </span>
        </div>

        {/* Tab bar */}
        <div
          className="flex items-center px-2"
          style={{ borderBottom: '1px solid #1E1E22', background: '#0C0C0E' }}
        >
          {(['chat', 'skills'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-4 py-2.5 text-xs font-mono transition-colors capitalize relative"
              style={{
                color: tab === t ? '#ECEAE3' : '#6B6B7A',
                borderBottom: tab === t ? '1px solid #C8A96E' : '1px solid transparent',
              }}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === 'skills' ? (
          <SkillMarketplace />
        ) : (
          <>
            {/* Chat toolbar */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-aegis-border bg-aegis-surface/50">
              <button
                onClick={() => setShowSystem(v => !v)}
                aria-label={showSystem ? 'Hide system prompt' : 'Show system prompt'}
                aria-expanded={showSystem}
                className="flex items-center gap-1.5 text-xs text-aegis-muted hover:text-aegis-text transition-colors"
              >
                System prompt
                <ChevronDown size={13} className={`transition-transform ${showSystem ? 'rotate-180' : ''}`} />
              </button>
              {messages.length > 0 && (
                <button
                  onClick={handleExport}
                  aria-label="Export conversation"
                  className="flex items-center gap-1.5 text-xs text-aegis-muted hover:text-aegis-text transition-colors"
                >
                  <Download size={13} />
                  Export
                </button>
              )}
            </div>

            {showSystem && (
              <div className="px-4 py-2 border-b border-aegis-border bg-aegis-surface/30">
                <textarea
                  value={systemPrompt}
                  onChange={e => setSystemPrompt(e.target.value)}
                  rows={2}
                  className="w-full bg-transparent text-xs text-aegis-muted placeholder-aegis-muted/50 resize-none focus:outline-none"
                  placeholder="System prompt…"
                />
              </div>
            )}

            <MessageList messages={messages} streaming={streaming} error={error} />

            <InputBar
              value={input}
              streaming={streaming}
              onChange={setInput}
              onSend={handleSend}
              onStop={reset}
            />
          </>
        )}
      </div>
    </div>
  )
}
