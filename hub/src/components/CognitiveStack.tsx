// AEGIS Omega — CognitiveStack: the seven-layer reasoning organ (L1–L7).
//
// The metacognitive protocol the automaton executes at every action boundary,
// rendered as a living column. The layer currently firing in the substrate
// pulses — you watch cognition move up and down the stack in real time.

import type { MetacognitiveLayer } from '../lib/substrate.js'
import { useSubstrate } from '../lib/useSubstrate.js'

const STACK: { layer: MetacognitiveLayer; rank: string; human: string; mechanism: string; color: string }[] = [
  { layer: 'SELF_MODEL',     rank: 'L7', human: 'Self-model',         mechanism: 'Hash-verified autonode · frozen-file integrity · t0_verdict', color: '#34D399' },
  { layer: 'METACOGNITIVE',  rank: 'L6', human: 'Metacognition',      mechanism: 'Tier re-classification · error-pattern recognition · retrospective', color: '#A78BFA' },
  { layer: 'EXECUTIVE',      rank: 'L5', human: 'Executive Function', mechanism: 'RALPH loop · gate sequence · martingale gate', color: '#7C3AED' },
  { layer: 'LONG_TERM',      rank: 'L4', human: 'Long-term Memory',   mechanism: 'AdaptiveLineage chain · invariants · git lineage', color: '#8B5CF6' },
  { layer: 'WORKING_MEMORY', rank: 'L3', human: 'Working Memory',     mechanism: 'Current gate · active RALPH phase · loaded skills', color: '#06B6D4' },
  { layer: 'PERCEPTION',     rank: 'L2', human: 'Perception',         mechanism: 'Verified + tier-classified signal · verify-hashes result', color: '#60A5FA' },
  { layer: 'SENSATION',      rank: 'L1', human: 'Sensation',          mechanism: 'Raw signal · test output · diff · error message', color: '#64748B' },
]

export function CognitiveStack() {
  const { activeLayer } = useSubstrate()
  // CONSCIOUSNESS / TIER_PROMOTION map onto L6↻L7 — light the top two when they fire.
  const isActive = (layer: MetacognitiveLayer) =>
    activeLayer === layer ||
    (activeLayer === 'CONSCIOUSNESS' && (layer === 'METACOGNITIVE' || layer === 'SELF_MODEL')) ||
    (activeLayer === 'TIER_PROMOTION' && layer === 'METACOGNITIVE')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {STACK.map(row => {
        const active = isActive(row.layer)
        return (
          <div key={row.layer} style={{
            display: 'grid', gridTemplateColumns: '44px 1fr', gap: 14, alignItems: 'center',
            padding: '14px 18px', borderRadius: 12,
            border: `1px solid ${active ? `${row.color}55` : 'rgba(255,255,255,0.05)'}`,
            background: active ? `${row.color}12` : 'rgba(255,255,255,0.015)',
            transition: 'all 0.5s ease', position: 'relative',
            boxShadow: active ? `0 0 24px ${row.color}22` : 'none',
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 800, color: active ? '#0B0F19' : row.color,
              background: active ? row.color : `${row.color}1A`,
              transition: 'all 0.5s ease',
            }}>{row.rank}</div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 15, fontWeight: 700, color: '#F1F5F9' }}>{row.human}</span>
                {active && <span style={{ width: 6, height: 6, borderRadius: '50%', background: row.color }} className="animate-mint-pulse" />}
              </div>
              <div style={{ fontSize: 12.5, color: '#64748B', marginTop: 2, lineHeight: 1.5 }}>{row.mechanism}</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
