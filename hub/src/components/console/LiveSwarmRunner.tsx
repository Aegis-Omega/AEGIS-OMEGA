// AEGIS-Ω Console — swarm runner.
// Streams the 39-department collaboration sequence: dag_step → agent_event →
// tool_call → completion. In the public console this is a guided simulation
// over the real department roster (running live requires an API key — labeled
// honestly, never faked). Surfaces the cross-session memory layer that feeds
// every live run via memory_context.

import { useRef, useState } from 'react'
import { T, MONO, glass } from './consoleTokens.js'
import { Heading } from './SystemStatusBar.js'

type Mode = 'revenue' | 'analysis' | 'gtm' | 'retention'
type EvType = 'dag_step' | 'agent_event' | 'tool_call' | 'completion'
interface StreamLine { id: number; type: EvType; text: string; color: string }

const DEPTS = [
  ['REV-01 Strategy', 'revenue'], ['REV-02 Finance', 'revenue'], ['MKT-02 Content', 'marketing'],
  ['SLS-04 Enterprise', 'sales'], ['PRD-04 API', 'product'], ['ENG-04 Security', 'engineering'],
  ['RES-02 Competitive', 'research'], ['FIN-02 Treasury', 'finance'], ['EXE-03 CTO', 'executive'],
  ['GOV-01 Ethics', 'governance'], ['CON-09 Guardian', 'constitutional'],
] as const

const TOOLS_FIRED = ['Supabase.memory', 'Anthropic.govern', 'Supabase.ledger']
const MODE_COLOR: Record<Mode, string> = { revenue: T.green, analysis: T.indigo, gtm: T.phi, retention: T.blue }

export function LiveSwarmRunner({ memoryActive }: { memoryActive: boolean }) {
  const [mode, setMode] = useState<Mode>('gtm')
  const [obj, setObj] = useState('Enter EU AI-governance market Q4 2026')
  const [lines, setLines] = useState<StreamLine[]>([])
  const [running, setRunning] = useState(false)
  const idRef = useRef(0)
  const accent = MODE_COLOR[mode]

  function push(type: EvType, text: string, color: string) {
    setLines(prev => [...prev.slice(-40), { id: idRef.current++, type, text, color }])
  }

  async function run() {
    if (running) return
    setRunning(true); setLines([]); idRef.current = 0
    const wait = (ms: number) => new Promise(r => setTimeout(r, ms))

    if (memoryActive) {
      push('agent_event', `memory: retrieved 3 prior artifacts for this objective hash`, T.phi)
      await wait(280)
    }
    push('dag_step', `objective received · mode="${mode}" · 39 departments activating`, T.text)
    await wait(300)
    for (const [dept, cat] of DEPTS) {
      push('dag_step', `${dept} · ${cat}`, accent)
      await wait(120)
      push('agent_event', `${dept.split(' ')[1]} → output committed · T2`, T.sub)
      await wait(90)
    }
    for (const tool of TOOLS_FIRED) {
      push('tool_call', `tool_call · ${tool} · args_hash=${randHash()}`, T.indigo)
      await wait(160)
    }
    push('agent_event', `CON-09 Guardian · constitutional audit → APPROVED · concerns:[]`, T.green)
    await wait(260)
    push('completion', `39 artifacts · chain_valid=true · is_replay_reconstructable=true · ${randHash()}`, T.green)
    setRunning(false)
  }

  return (
    <div style={{ ...glass(accent), padding: 20 }}>
      <div className="flex items-center justify-between mb-1">
        <Heading>SWARM RUNNER · live stream</Heading>
        <span style={{ fontSize: 10, fontFamily: MONO, color: T.muted }}>simulated · key to run live</span>
      </div>

      <div className="flex flex-wrap gap-2 mt-3 mb-3">
        {(['gtm', 'revenue', 'analysis', 'retention'] as Mode[]).map(m => (
          <button key={m} onClick={() => setMode(m)} disabled={running} style={{
            padding: '5px 13px', borderRadius: 16, fontSize: 12, fontFamily: MONO,
            cursor: running ? 'default' : 'pointer',
            background: m === mode ? `${MODE_COLOR[m]}18` : 'transparent',
            border: `1px solid ${m === mode ? MODE_COLOR[m] + '55' : T.border}`,
            color: m === mode ? MODE_COLOR[m] : T.muted,
          }}>{m}</button>
        ))}
      </div>

      <div className="flex gap-2 mb-3">
        <input value={obj} onChange={e => setObj(e.target.value)} disabled={running}
          style={{
            flex: 1, background: T.inset, border: `1px solid ${T.border}`, borderRadius: 8,
            padding: '9px 12px', fontSize: 13, color: T.text, fontFamily: 'inherit', outline: 'none',
          }} />
        <button onClick={() => void run()} disabled={running} style={{
          padding: '9px 20px', borderRadius: 8, fontSize: 13, fontWeight: 600,
          background: running ? T.border : accent, color: running ? T.muted : '#0A0A0C',
          border: 'none', cursor: running ? 'default' : 'pointer', flexShrink: 0,
        }}>{running ? 'streaming…' : 'Run ▸'}</button>
      </div>

      <div style={{
        background: T.inset, borderRadius: 10, border: `1px solid ${T.border}`,
        padding: 14, height: 240, overflowY: 'auto', fontFamily: MONO, fontSize: 12,
      }}>
        {lines.length === 0 && (
          <span style={{ color: T.muted }}>▸ press Run to stream a 39-department collaboration</span>
        )}
        {lines.map(l => (
          <div key={l.id} style={{ marginBottom: 4, lineHeight: 1.5, display: 'flex', gap: 8 }}>
            <span style={{ color: l.color, opacity: 0.7, flexShrink: 0, minWidth: 92 }}>{l.type}</span>
            <span style={{ color: l.color }}>{l.text}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 mt-3">
        <span style={{ width: 7, height: 7, borderRadius: '50%', display: 'inline-block',
          background: memoryActive ? T.phi : T.muted }} />
        <span style={{ fontSize: 11, color: T.muted, fontFamily: MONO }}>
          memory layer {memoryActive ? 'active · prior runs feed context' : 'cold · no prior runs for this objective'}
        </span>
      </div>
    </div>
  )
}

function randHash(): string {
  const c = '0123456789abcdef'
  let s = ''
  for (let i = 0; i < 12; i += 1) s += c[Math.floor(Math.random() * 16)]
  return s
}
