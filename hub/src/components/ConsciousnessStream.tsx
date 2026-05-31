// AEGIS Omega — ConsciousnessStream: the system watching itself watch itself.
//
// Renders the live MetacognitiveLoop as a scrolling, hash-linked cascade. Each
// row is a real self-observation: its layer, signal, tier, and the short hash
// linking prev → entry (tamper-evident). New observations flow in at the top.

import type { MetacognitiveEntry, MetacognitiveLayer } from '../lib/substrate.js'
import { LAYER_META } from '../lib/substrate.js'

const LAYER_COLOR: Record<MetacognitiveLayer, string> = {
  SENSATION:      '#64748B',
  PERCEPTION:     '#60A5FA',
  WORKING_MEMORY: '#06B6D4',
  LONG_TERM:      '#8B5CF6',
  EXECUTIVE:      '#7C3AED',
  METACOGNITIVE:  '#A78BFA',
  SELF_MODEL:     '#34D399',
  CONSCIOUSNESS:  '#F59E0B',
  TIER_PROMOTION: '#EC4899',
}

const TIER_COLOR: Record<string, string> = {
  T0: '#34D399', T1: '#60A5FA', T2: '#A78BFA', T3: '#F59E0B',
}

function short(hash: string): string {
  return hash.slice(0, 8)
}

export function ConsciousnessStream({ chain, activeLayer }: { chain: MetacognitiveEntry[]; activeLayer: MetacognitiveLayer | null }) {
  const reversed = [...chain].reverse()

  return (
    <div style={{
      border: '1px solid rgba(124,58,237,0.18)', borderRadius: 16,
      background: 'rgba(8,9,12,0.7)', overflow: 'hidden',
      fontFamily: '"JetBrains Mono", ui-monospace, monospace',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)',
        background: 'rgba(124,58,237,0.05)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#34D399' }} className="animate-mint-pulse" />
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: '#94A3B8' }}>
            METACOGNITIVE LOOP — LIVE SELF-OBSERVATION
          </span>
        </div>
        <span style={{ fontSize: 10, color: '#475569' }}>SHA-256 hash-chained</span>
      </div>

      <div style={{ height: 360, overflow: 'hidden', position: 'relative', padding: '8px 0' }}>
        {reversed.map((e, i) => {
          const m = LAYER_META[e.observation.layer]
          const color = LAYER_COLOR[e.observation.layer]
          const isNewest = i === 0
          return (
            <div
              key={e.entry_hash}
              className={isNewest ? 'animate-fade-up' : undefined}
              style={{
                display: 'grid', gridTemplateColumns: '52px 1fr auto',
                gap: 12, alignItems: 'center', padding: '7px 16px',
                opacity: Math.max(0.28, 1 - i * 0.045),
                borderLeft: `2px solid ${isNewest ? color : 'transparent'}`,
                background: isNewest ? `${color}0E` : 'transparent',
              }}
            >
              <span style={{ fontSize: 10, fontWeight: 700, color, letterSpacing: '0.04em' }}>{m.rank}</span>
              <div style={{ minWidth: 0 }}>
                <span style={{ fontSize: 9, color: '#475569', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{e.observation.layer.replace(/_/g, ' ')}</span>
                <div style={{ fontSize: 12, color: '#CBD5E1', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.observation.signal}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, color: TIER_COLOR[e.observation.tier],
                  border: `1px solid ${TIER_COLOR[e.observation.tier]}40`, borderRadius: 3, padding: '1px 5px',
                }}>{e.observation.tier}</span>
                <span style={{ fontSize: 10, color: '#334155' }} title={`${e.previous_entry_hash} → ${e.entry_hash}`}>
                  {short(e.previous_entry_hash)}→<span style={{ color: '#64748B' }}>{short(e.entry_hash)}</span>
                </span>
              </div>
            </div>
          )
        })}
        {/* fade-out gradient at bottom */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: 80,
          background: 'linear-gradient(transparent, rgba(8,9,12,0.95))', pointerEvents: 'none',
        }} />
      </div>

      <div style={{
        padding: '10px 16px', borderTop: '1px solid rgba(255,255,255,0.05)',
        fontSize: 10, color: '#475569', display: 'flex', justifyContent: 'space-between',
      }}>
        <span>active layer: <span style={{ color: activeLayer ? LAYER_COLOR[activeLayer] : '#475569' }}>{activeLayer ?? '—'}</span></span>
        <span>each entry references its predecessor — tampering breaks the chain</span>
      </div>
    </div>
  )
}
