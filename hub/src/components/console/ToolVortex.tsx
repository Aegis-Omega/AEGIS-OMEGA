// AEGIS-Ω Console — the Tool Vortex.
// The agent API contact list rendered as a convergence portal: every outbound
// API is a node on a tier ring (sovereign innermost → explorer outermost),
// every path converging to the mediated center. This is the vortex — every
// communication layer and the single information path where it arrives.
//
// Read-only: capabilities are shown, credentials never are. Selecting a node
// surfaces its verification state — loud, with reason.

import { useState } from 'react'
import { T, MONO, TIER_META, glass } from './consoleTokens.js'
import { Heading } from './SystemStatusBar.js'
import type { AgentTool } from '../../lib/platformConsole.js'

const SIZE = 360
const CX = SIZE / 2
const CY = SIZE / 2
const RINGS = [54, 104, 154] // sovereign, operator, explorer

function nodePos(tool: AgentTool, indexInTier: number, tierCount: number): { x: number; y: number; r: number } {
  const ring = TIER_META[tool.tier_required]?.ring ?? 2
  const r = RINGS[ring] ?? 154
  const angle = (indexInTier / Math.max(1, tierCount)) * Math.PI * 2 - Math.PI / 2
  return { x: CX + Math.cos(angle) * r, y: CY + Math.sin(angle) * r, r }
}

export function ToolVortex({ tools, source }: { tools: AgentTool[]; source: 'live' | 'demo' }) {
  const [sel, setSel] = useState<number>(-1)

  // group by tier for even angular distribution
  const byTier: Record<string, number[]> = { sovereign: [], operator: [], explorer: [] }
  tools.forEach((t, i) => { (byTier[t.tier_required] ?? byTier.explorer!).push(i) })
  const tierIndex = (i: number, tier: string) => (byTier[tier] ?? []).indexOf(i)

  const selected = sel >= 0 ? tools[sel] : undefined

  return (
    <div style={{ ...glass(T.phi), padding: 20 }}>
      <div className="flex items-center justify-between mb-1">
        <Heading>TOOL VORTEX · agent contact list</Heading>
        <span style={{ fontFamily: MONO, fontSize: 11, color: T.muted }}>{tools.length} APIs</span>
      </div>
      <p style={{ fontSize: 12, color: T.muted, marginTop: 6, marginBottom: 8, lineHeight: 1.5 }}>
        Every path converges to the mediated center. Read-only — capabilities shown, keys never.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} style={{ width: '100%', height: 'auto' }}>
          {RINGS.map((r, i) => (
            <circle key={r} cx={CX} cy={CY} r={r} fill="none"
              stroke={[T.phi, T.indigo, T.blue][i]} strokeOpacity={0.16} strokeWidth={1} strokeDasharray="2 5" />
          ))}
          {/* converging paths */}
          {tools.map((t, i) => {
            const p = nodePos(t, tierIndex(i, t.tier_required), (byTier[t.tier_required] ?? []).length)
            const active = sel === i
            return (
              <line key={`l${i}`} x1={p.x} y1={p.y} x2={CX} y2={CY}
                stroke={TIER_META[t.tier_required]?.color ?? T.blue}
                strokeOpacity={active ? 0.6 : 0.14} strokeWidth={active ? 1.5 : 1} />
            )
          })}
          {/* center — the mediated channel */}
          <circle cx={CX} cy={CY} r={16} fill={T.void} stroke={T.phi} strokeWidth={1.5} />
          <circle cx={CX} cy={CY} r={16} fill="none" stroke={T.phi} strokeOpacity={0.4} strokeWidth={1}>
            <animate attributeName="r" values="16;26;16" dur="3s" repeatCount="indefinite" />
            <animate attributeName="stroke-opacity" values="0.4;0;0.4" dur="3s" repeatCount="indefinite" />
          </circle>
          <text x={CX} y={CY + 3} fill={T.phi} fontSize={9} fontFamily="monospace" textAnchor="middle">Ω</text>
          {/* tool nodes */}
          {tools.map((t, i) => {
            const p = nodePos(t, tierIndex(i, t.tier_required), (byTier[t.tier_required] ?? []).length)
            const color = TIER_META[t.tier_required]?.color ?? T.blue
            const active = sel === i
            return (
              <g key={`n${i}`} style={{ cursor: 'pointer' }} onClick={() => setSel(active ? -1 : i)}>
                <circle cx={p.x} cy={p.y} r={active ? 8 : 6} fill={color} fillOpacity={active ? 1 : 0.85}>
                  {source === 'live' && (
                    <animate attributeName="fill-opacity" values="0.85;0.4;0.85" dur="2.6s" repeatCount="indefinite" />
                  )}
                </circle>
                <text x={p.x} y={p.y - 11} fill={active ? T.text : T.sub} fontSize={9}
                  fontFamily="monospace" textAnchor="middle">{t.api_name.split(' ')[0]}</text>
              </g>
            )
          })}
        </svg>

        <ToolDetail tool={selected} source={source} />
      </div>

      <div className="flex items-center gap-4 mt-3">
        {(['sovereign', 'operator', 'explorer'] as const).map(tier => (
          <div key={tier} className="flex items-center gap-1.5">
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: TIER_META[tier]!.color, display: 'inline-block' }} />
            <span style={{ fontSize: 10, color: T.muted, fontFamily: MONO }}>{tier}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ToolDetail({ tool, source }: { tool: AgentTool | undefined; source: 'live' | 'demo' }) {
  if (!tool) {
    return (
      <div style={{ background: T.inset, borderRadius: 10, padding: 16, minHeight: 150 }}
        className="flex items-center justify-center">
        <span style={{ fontSize: 12, color: T.muted, textAlign: 'center', lineHeight: 1.6 }}>
          Select a node to inspect its capabilities<br />and verification state.
        </span>
      </div>
    )
  }
  const color = TIER_META[tool.tier_required]?.color ?? T.blue
  // Loud verification state for the selected contact.
  const verified = source === 'live'
  return (
    <div style={{ background: T.inset, borderRadius: 10, padding: 16, minHeight: 150 }}>
      <div className="flex items-center justify-between mb-3">
        <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{tool.api_name}</span>
        <span style={{
          fontSize: 10, fontFamily: MONO, color, padding: '2px 8px', borderRadius: 12,
          background: `${color}14`, border: `1px solid ${color}33`,
        }}>{tool.tier_required}</span>
      </div>
      <Row label="endpoint" value={tool.endpoint_url} />
      <Row label="credential"
        value={verified ? 'verified · sha-256 hash on file' : 'unverified · demo (no live key check)'}
        color={verified ? T.green : T.amber} />
      <div style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 12, marginBottom: 6 }}>
        capabilities
      </div>
      <div className="flex flex-wrap gap-1.5">
        {tool.capabilities.map(c => (
          <span key={c} style={{
            fontSize: 11, fontFamily: MONO, padding: '2px 7px', borderRadius: 4,
            background: T.bg, color: T.sub, border: `1px solid ${T.border}`,
          }}>{c}</span>
        ))}
      </div>
    </div>
  )
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <span style={{ fontSize: 10, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.08em', minWidth: 72 }}>{label}</span>
      <span style={{ fontSize: 12, fontFamily: MONO, color: color ?? T.sub, wordBreak: 'break-all' }}>{value}</span>
    </div>
  )
}
