import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Copy, Check } from 'lucide-react'
import type { ChatMessage } from '../lib/agent.js'

interface MessageListProps {
  messages: ChatMessage[]
  streaming: boolean
  error: string | null
}

const INVARIANTS = [
  { eq: 'AdaptivePower(T) ≤ ReplayVerifiability(T)', tier: 'T0', color: '#34D399', desc: 'Root constitutional law — no adaptive action exceeds replay-certifiable bounds' },
  { eq: 'E[S̅ₜ₊₁|Fₜ] = S̅ₜ', tier: 'T0', color: '#34D399', desc: 'Martingale — governance state is a certified expectation, not a prediction' },
  { eq: '1/φ ≈ 0.6180339887', tier: 'T0', color: '#34D399', desc: 'BFT quorum · mutation rate ceiling · martingale suspension threshold' },
  { eq: 'Tajweed DFA', tier: 'T1', color: '#60A5FA', desc: 'Arabic phonological state machine — 1,400 years of empirical validation' },
  { eq: 'A-B-C-B′-A′ ring', tier: 'T1', color: '#60A5FA', desc: 'Chiastic symmetry isomorphic to constitutional governance at two scales' },
  { eq: '3-6-9 vortex', tier: 'T2', color: '#A78BFA', desc: 'Digital root triadic attractor — rank span classifier for the DAG lattice' },
]

const ALLIANCE = [
  { name: 'Claude', weight: 618, color: '#60A5FA', role: 'Coordinator' },
  { name: 'GPT-4o', weight: 191, color: '#34D399', role: 'Adversarial audit' },
  { name: 'Qwen', weight: 191, color: '#A78BFA', role: 'Implementation' },
]

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 px-6 select-none">
      {/* Wordmark */}
      <div className="text-center">
        <div className="flex items-baseline justify-center gap-3 mb-1">
          <span className="font-mono font-semibold tracking-[0.25em] text-2xl" style={{ color: '#C8A96E' }}>
            AEGIS-Ω
          </span>
          <span
            className="font-mono text-xs tracking-widest uppercase opacity-40"
            style={{ color: '#ECEAE3' }}
          >
            Constitutional Runtime
          </span>
        </div>
        <p className="text-xs font-mono opacity-30" style={{ color: '#6B6B7A' }}>
          Hash-certified · Replay-verifiable · Martingale-anchored
        </p>
      </div>

      {/* Invariants panel */}
      <div className="w-full max-w-lg">
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: '1px solid #1E1E22', background: '#141416' }}
        >
          <div
            className="px-4 py-2.5 flex items-center justify-between"
            style={{ borderBottom: '1px solid #1E1E22', background: '#0C0C0E' }}
          >
            <span className="font-mono text-xs tracking-widest uppercase opacity-50" style={{ color: '#6B6B7A' }}>
              Active invariants
            </span>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs" style={{ color: '#34D399', opacity: 0.7 }}>279 Rust</span>
              <span className="opacity-20" style={{ color: '#6B6B7A' }}>·</span>
              <span className="font-mono text-xs" style={{ color: '#60A5FA', opacity: 0.7 }}>2733 TS</span>
            </div>
          </div>
          <div>
            {INVARIANTS.map((inv, i) => (
              <div
                key={i}
                className="flex items-start gap-3 px-4 py-3 transition-colors cursor-default"
                style={{
                  borderBottom: i < INVARIANTS.length - 1 ? '1px solid rgba(30,30,34,0.6)' : 'none',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.02)'
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = 'transparent'
                }}
              >
                <span
                  className="font-mono text-xs shrink-0 mt-0.5 font-medium"
                  style={{ color: inv.color, opacity: 0.85, minWidth: '2rem' }}
                >
                  {inv.tier}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-xs" style={{ color: '#ECEAE3' }}>{inv.eq}</p>
                  <p className="text-xs mt-0.5 leading-relaxed" style={{ color: '#6B6B7A', opacity: 0.7 }}>
                    {inv.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Orchestration alliance */}
      <div
        className="w-full max-w-lg rounded-xl px-4 py-3 flex items-center justify-between"
        style={{ border: '1px solid #1E1E22', background: '#0C0C0E' }}
      >
        <div className="flex items-center gap-1 font-mono text-xs" style={{ color: '#6B6B7A' }}>
          <span className="opacity-50 mr-2">Alliance</span>
          {ALLIANCE.map((a, i) => (
            <span key={a.name} className="flex items-center gap-1">
              {i > 0 && <span className="opacity-20 mx-1">·</span>}
              <span style={{ color: a.color }}>{a.name}</span>
              <span className="opacity-40"> {a.weight}</span>
            </span>
          ))}
        </div>
        <span className="font-mono text-xs" style={{ color: '#C8A96E', opacity: 0.7 }}>
          ⌊1000/φ⌋ = 618
        </span>
      </div>

      <p className="font-mono text-xs opacity-20" style={{ color: '#6B6B7A' }}>
        Enter to send · Shift+Enter for newline
      </p>
    </div>
  )
}

function CopyBtn({ text, light }: { text: string; light?: boolean }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handleCopy}
      aria-label="Copy message"
      className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5"
      style={{ color: light ? 'rgba(255,255,255,0.6)' : '#6B6B7A' }}
    >
      {copied
        ? <Check size={13} style={{ color: light ? 'rgba(255,255,255,0.9)' : '#34D399' }} />
        : <Copy size={13} />}
    </button>
  )
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end items-start gap-2 group">
      <CopyBtn text={content} light />
      <div
        className="max-w-[72%] px-4 py-3 rounded-2xl rounded-br-sm text-sm leading-relaxed whitespace-pre-wrap"
        style={{ background: '#60A5FA', color: '#ffffff' }}
      >
        {content}
      </div>
    </div>
  )
}

function renderInline(text: string): ReactNode {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]*\]\([^)]*\))/g)
  if (tokens.length === 1) return text
  return (
    <>
      {tokens.map((t, i) => {
        if (t.startsWith('**') && t.endsWith('**') && t.length > 4)
          return <strong key={i} style={{ color: '#ECEAE3', fontWeight: 600 }}>{t.slice(2, -2)}</strong>
        if (t.startsWith('`') && t.endsWith('`') && t.length > 2)
          return (
            <code key={i} style={{
              background: '#1A1A1E', padding: '0.1em 0.4em', borderRadius: '4px',
              fontFamily: 'monospace', fontSize: '0.85em', color: '#C8A96E',
              border: '1px solid #2A2A2E',
            }}>
              {t.slice(1, -1)}
            </code>
          )
        const m = t.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
        if (m)
          return <a key={i} href={m[2]} target="_blank" rel="noopener noreferrer" style={{ color: '#60A5FA', textDecoration: 'underline' }}>{m[1]}</a>
        return t || null
      })}
    </>
  )
}

function MarkdownContent({ content }: { content: string }) {
  const nodes: ReactNode[] = []
  const lines = content.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) { codeLines.push(lines[i]); i++ }
      i++
      nodes.push(
        <div key={nodes.length} style={{ margin: '8px 0', borderRadius: '8px', overflow: 'hidden', border: '1px solid #1E1E22' }}>
          {lang && (
            <div style={{ background: '#0C0C0E', padding: '5px 14px', borderBottom: '1px solid #1E1E22', fontFamily: 'monospace', fontSize: '11px', color: '#6B6B7A' }}>
              {lang}
            </div>
          )}
          <pre style={{ background: '#0A0A0C', padding: '12px 14px', overflow: 'auto', margin: 0 }}>
            <code style={{ fontFamily: '"Fira Code","Cascadia Code","JetBrains Mono",monospace', fontSize: '12px', color: '#ECEAE3', whiteSpace: 'pre' }}>
              {codeLines.join('\n')}
            </code>
          </pre>
        </div>
      )
      continue
    }

    // Horizontal rule
    if (/^---+$/.test(line) || /^===+$/.test(line)) {
      nodes.push(<hr key={nodes.length} style={{ border: 'none', borderTop: '1px solid #1E1E22', margin: '10px 0' }} />)
      i++; continue
    }

    // Headers
    const h3m = line.match(/^### (.+)/); if (h3m) { nodes.push(<h3 key={nodes.length} style={{ color: '#ECEAE3', fontWeight: 600, fontSize: '0.9em', margin: '12px 0 3px' }}>{renderInline(h3m[1])}</h3>); i++; continue }
    const h2m = line.match(/^## (.+)/);  if (h2m) { nodes.push(<h2 key={nodes.length} style={{ color: '#ECEAE3', fontWeight: 600, fontSize: '1em',   margin: '14px 0 4px' }}>{renderInline(h2m[1])}</h2>); i++; continue }
    const h1m = line.match(/^# (.+)/);   if (h1m) { nodes.push(<h1 key={nodes.length} style={{ color: '#ECEAE3', fontWeight: 700, fontSize: '1.1em', margin: '14px 0 5px' }}>{renderInline(h1m[1])}</h1>); i++; continue }

    // Bullet list
    if (/^[-*+] /.test(line)) {
      const items: ReactNode[] = []
      while (i < lines.length && /^[-*+] /.test(lines[i])) {
        items.push(<li key={items.length} style={{ margin: '2px 0' }}>{renderInline(lines[i].replace(/^[-*+] /, ''))}</li>)
        i++
      }
      nodes.push(<ul key={nodes.length} style={{ margin: '6px 0', paddingLeft: '18px', listStyleType: 'disc' }}>{items}</ul>)
      continue
    }

    // Numbered list
    if (/^\d+\. /.test(line)) {
      const items: ReactNode[] = []
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(<li key={items.length} style={{ margin: '2px 0' }}>{renderInline(lines[i].replace(/^\d+\. /, ''))}</li>)
        i++
      }
      nodes.push(<ol key={nodes.length} style={{ margin: '6px 0', paddingLeft: '18px' }}>{items}</ol>)
      continue
    }

    // Blank line
    if (line.trim() === '') { i++; continue }

    // Paragraph — collect until next special block
    const paraLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].startsWith('#') &&
      !lines[i].startsWith('```') &&
      !/^[-*+] /.test(lines[i]) &&
      !/^\d+\. /.test(lines[i]) &&
      !/^---+$/.test(lines[i])
    ) { paraLines.push(lines[i]); i++ }
    if (paraLines.length > 0)
      nodes.push(<p key={nodes.length} style={{ margin: '3px 0 6px', lineHeight: '1.65' }}>{renderInline(paraLines.join(' '))}</p>)
  }

  return <>{nodes}</>
}

function AssistantBubble({ content, isStreaming }: { content: string; isStreaming: boolean }) {
  return (
    <div className="flex justify-start group">
      <div className="flex gap-3 max-w-[80%]">
        <div
          className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center font-mono text-xs font-semibold mt-0.5"
          style={{ background: '#1E1E22', color: '#C8A96E' }}
        >
          Ω
        </div>
        <div
          className="px-4 py-3 rounded-2xl rounded-bl-sm text-sm"
          style={{
            background: '#141416',
            border: '1px solid #1E1E22',
            color: '#ECEAE3',
            lineHeight: '1.65',
          }}
        >
          <MarkdownContent content={content} />
          {isStreaming && (
            <span
              className="inline-block w-1.5 h-4 ml-1 rounded-sm align-middle animate-pulse"
              style={{ background: '#C8A96E' }}
            />
          )}
        </div>
      </div>
      {!isStreaming && <CopyBtn text={content} />}
    </div>
  )
}

export function MessageList({ messages, streaming, error }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const visible = messages.filter(m => m.role !== 'system')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
      {visible.length === 0 && <EmptyState />}

      {visible.map((m, i) =>
        m.role === 'user' ? (
          <UserBubble key={i} content={m.content} />
        ) : (
          <AssistantBubble
            key={i}
            content={m.content}
            isStreaming={streaming && i === visible.length - 1}
          />
        )
      )}

      {error && (
        <div
          className="text-center text-xs px-4 py-2.5 rounded-lg mx-auto max-w-sm"
          style={{
            color: '#F87171',
            background: 'rgba(248,113,113,0.08)',
            border: '1px solid rgba(248,113,113,0.15)',
          }}
        >
          {error}
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
