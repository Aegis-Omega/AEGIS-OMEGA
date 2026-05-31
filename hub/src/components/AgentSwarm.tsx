// AEGIS Omega — AgentSwarm: the AI company as a moving BFT consensus.
//
// Four agents, each with a constitutional weight, vote on a proposal; the
// tally converges toward the golden-ratio quorum 1/φ ≈ 0.618. Between them
// flow mediated EventEnvelopes — the Law of Silence: no agent ever speaks to
// another directly. An SVG network shows envelopes routing through the central
// mediator in real time. The convergence bar fills as votes settle.

import { useEffect, useState } from 'react'

const PHI = 0.6180339887498948

interface Agent {
  role: string
  model: string
  weight: number
  badge: string
  color: string
  desc: string
  // SVG position in the 460×250 network canvas
  cx: number
  cy: number
}

const AGENTS: Agent[] = [
  { role: 'Coordinator',         model: 'Claude',        weight: 618, badge: 'CEO',      color: '#7C3AED', desc: 'Orchestrates RALPH loops · final synthesis · constitutional arbiter',    cx: 80,  cy: 50  },
  { role: 'Adversarial Auditor', model: 'GPT-4o',        weight: 191, badge: 'RED TEAM', color: '#EF4444', desc: 'Attacks every plan at temperature 0.99 before LOCK · dissent mandatory', cx: 380, cy: 50  },
  { role: 'Implementer',         model: 'Qwen',          weight: 191, badge: 'ENGINEER', color: '#F59E0B', desc: 'Bulk execution · code generation · domain synthesis',                    cx: 80,  cy: 200 },
  { role: 'Notify Agent',        model: 'Supabase Edge', weight: 0,   badge: 'OPS',      color: '#10B981', desc: 'Fires purchase alerts · Slack · email on every event',                   cx: 380, cy: 200 },
]

// Central EventEnvelope mediator coordinates.
const MX = 230
const MY = 125

// Envelope pulses: one per agent-to-center path, staggered begin times.
const INBOUND: { agent: Agent; begin: number; dur: number }[] = AGENTS.map((a, i) => ({
  agent: a,
  begin: i * 0.42,
  dur: 1.55,
}))

// Outbound dispatch pulses (center → agents), subtler.
const OUTBOUND: { agent: Agent; begin: number; dur: number }[] = AGENTS.map((a, i) => ({
  agent: a,
  begin: i * 0.42 + 0.28,
  dur: 1.55,
}))

export function AgentSwarm() {
  const [convergence, setConvergence] = useState(0)
  const [round, setRound] = useState(0)
  const [envelopeCount, setEnvelopeCount] = useState(0)

  useEffect(() => {
    const id = setInterval(() => {
      setConvergence(c => {
        const next = c + (PHI - c) * 0.18 + (Math.random() - 0.5) * 0.02
        return Math.max(0, Math.min(1, next))
      })
      setRound(r => r + 1)
      setEnvelopeCount(n => n + 1)
    }, 700)
    return () => clearInterval(id)
  }, [])

  const reached = Math.abs(convergence - PHI) < 0.02

  return (
    <div>
      {/* Agent cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 16, marginBottom: 24 }}>
        {AGENTS.map((a, i) => {
          const phase = (round + i) % 4 === 0
          return (
            <div key={a.role} style={{
              background: 'rgba(13,17,27,0.95)',
              border: `1px solid ${phase ? `${a.color}45` : 'rgba(255,255,255,0.07)'}`,
              borderRadius: 16, padding: 22, display: 'flex', flexDirection: 'column', gap: 0,
              transition: 'border-color 0.6s ease, box-shadow 0.6s ease',
              boxShadow: phase ? `0 0 22px ${a.color}1A` : 'none',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', color: a.color, background: `${a.color}18`, border: `1px solid ${a.color}40`, borderRadius: 4, padding: '2px 7px' }}>{a.badge}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {phase && <span style={{ width: 5, height: 5, borderRadius: '50%', background: a.color, display: 'inline-block' }} className="animate-mint-pulse" />}
                  <span style={{ fontSize: 10, color: '#334155', fontFamily: '"JetBrains Mono", monospace' }}>w={a.weight || '—'}</span>
                </div>
              </div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', marginBottom: 4 }}>{a.role}</div>
              <div style={{ fontSize: 12, color: a.color, marginBottom: 10, fontWeight: 600 }}>{a.model}</div>
              <div style={{ fontSize: 12.5, color: '#64748B', lineHeight: 1.6 }}>{a.desc}</div>
              {a.weight > 0 && (
                <div style={{ marginTop: 14, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${(a.weight / 1000) * 100}%`, background: a.color, borderRadius: 2, transition: 'width 0.6s ease' }} />
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* EventEnvelope routing network — Law of Silence, live */}
      <div style={{
        border: '1px solid rgba(6,182,212,0.12)', borderRadius: 16,
        background: 'rgba(6,182,212,0.03)', padding: '16px 20px', marginBottom: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: '#0891B2' }}>EVENTENVELOPE ROUTING</span>
          <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: '#334155' }}>
            {envelopeCount} envelopes dispatched
          </span>
        </div>
        <svg
          viewBox="0 0 460 250"
          style={{ width: '100%', height: 'auto', display: 'block' }}
          aria-label="EventEnvelope routing network — all agent communication flows through the central mediator"
        >
          {/* Routing lines */}
          {AGENTS.map(a => (
            <line
              key={`line-${a.role}`}
              x1={a.cx} y1={a.cy} x2={MX} y2={MY}
              stroke="rgba(255,255,255,0.05)"
              strokeWidth="1"
            />
          ))}

          {/* Inbound envelopes: agent → mediator */}
          {INBOUND.flatMap(({ agent: a, begin, dur }) => [
            <circle key={`in-${a.role}-0`} r="3" fill={a.color} opacity="0.9">
              <animateMotion
                path={`M ${a.cx},${a.cy} L ${MX},${MY}`}
                dur={`${dur}s`}
                repeatCount="indefinite"
                begin={`${begin}s`}
              />
            </circle>,
            <circle key={`in-${a.role}-1`} r="2.5" fill={a.color} opacity="0.5">
              <animateMotion
                path={`M ${a.cx},${a.cy} L ${MX},${MY}`}
                dur={`${dur}s`}
                repeatCount="indefinite"
                begin={`${begin + dur * 0.5}s`}
              />
            </circle>,
          ])}

          {/* Outbound dispatch: mediator → agent */}
          {OUTBOUND.map(({ agent: a, begin, dur }) => (
            <circle key={`out-${a.role}`} r="2" fill="#06B6D4" opacity="0.4">
              <animateMotion
                path={`M ${MX},${MY} L ${a.cx},${a.cy}`}
                dur={`${dur}s`}
                repeatCount="indefinite"
                begin={`${begin}s`}
              />
            </circle>
          ))}

          {/* Agent nodes */}
          {AGENTS.map(a => (
            <g key={`node-${a.role}`}>
              <circle cx={a.cx} cy={a.cy} r="22" fill={`${a.color}18`} stroke={a.color} strokeWidth="1.5" />
              <text x={a.cx} y={a.cy - 5} textAnchor="middle" fill={a.color} fontSize="8" fontWeight="700">{a.badge}</text>
              <text x={a.cx} y={a.cy + 7} textAnchor="middle" fill={a.color} fontSize="7" opacity="0.8">{a.model}</text>
            </g>
          ))}

          {/* Central mediator */}
          <circle cx={MX} cy={MY} r="28" fill="rgba(6,182,212,0.07)" stroke="#06B6D4" strokeWidth="1.5" strokeDasharray="5 3" />
          <text x={MX} y={MY - 6} textAnchor="middle" fill="#06B6D4" fontSize="7" fontWeight="700" letterSpacing="0.08em">EVENT</text>
          <text x={MX} y={MY + 5} textAnchor="middle" fill="#06B6D4" fontSize="7" fontWeight="700" letterSpacing="0.08em">ENVELOPE</text>
          <text x={MX} y={MY + 15} textAnchor="middle" fill="#0E7490" fontSize="6">mediator</text>
        </svg>
      </div>

      {/* BFT convergence meter */}
      <div style={{
        border: '1px solid rgba(124,58,237,0.2)', borderRadius: 16,
        background: 'rgba(124,58,237,0.04)', padding: '20px 24px', marginBottom: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: '#A78BFA' }}>BFT CONSENSUS — ROUND {round}</span>
          <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 13, color: reached ? '#34D399' : '#94A3B8' }}>
            tally {convergence.toFixed(4)} → quorum {PHI.toFixed(4)}
          </span>
        </div>
        <div style={{ position: 'relative', height: 8, borderRadius: 4, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${convergence * 100}%`,
            background: reached ? 'linear-gradient(90deg,#34D399,#06B6D4)' : 'linear-gradient(90deg,#7C3AED,#A78BFA)',
            transition: 'width 0.5s ease', borderRadius: 4,
          }} />
          {/* φ marker */}
          <div style={{ position: 'absolute', top: -3, bottom: -3, left: `${PHI * 100}%`, width: 2, background: '#F59E0B' }} />
        </div>
        <div style={{ fontSize: 11, color: reached ? '#34D399' : '#475569', marginTop: 10 }}>
          {reached ? '✓ quorum reached — proposal converges at the golden ratio' : 'deliberating — votes settling toward 1/φ'}
        </div>
      </div>

      {/* Law of Silence */}
      <div style={{ padding: '20px 24px', border: '1px solid rgba(6,182,212,0.2)', borderRadius: 16, background: 'rgba(6,182,212,0.04)' }}>
        <div style={{ fontSize: 11, color: '#0891B2', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 8 }}>LAW OF SILENCE</div>
        <p style={{ color: '#94A3B8', fontSize: 13.5, margin: 0, lineHeight: 1.7 }}>
          No agent communicates with another directly. All communication flows through mediated{' '}
          <code style={{ color: '#06B6D4', background: 'rgba(6,182,212,0.1)', padding: '1px 6px', borderRadius: 4 }}>EventEnvelope</code>{' '}
          channels. Confinement is enforced at the constitutional boundary. The swarm cannot conspire.
        </p>
      </div>
    </div>
  )
}
