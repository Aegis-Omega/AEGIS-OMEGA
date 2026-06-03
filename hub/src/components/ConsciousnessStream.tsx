// Live scrolling cascade of self-observations — the system watching itself watch itself.
import { useEffect, useState } from 'react'
import { useSubstrate, certify, type Layer, type Tier, type MetacognitiveEntry } from '../lib/substrate.js'

const LAYER_LABEL: Record<Layer, string> = {
  SENSATION:      'L1',
  PERCEPTION:     'L2',
  WORKING_MEMORY: 'L3',
  LONG_TERM:      'L4',
  EXECUTIVE:      'L5',
  METACOGNITIVE:  'L6',
  SELF_MODEL:     'L7',
  CONSCIOUSNESS:  'L8',
  TIER_PROMOTION: 'L9',
}

const LAYER_COLOR: Record<Layer, string> = {
  SENSATION:      '#34D399',
  PERCEPTION:     '#60A5FA',
  WORKING_MEMORY: '#A78BFA',
  LONG_TERM:      '#F59E0B',
  EXECUTIVE:      '#34D399',
  METACOGNITIVE:  '#60A5FA',
  SELF_MODEL:     '#A78BFA',
  CONSCIOUSNESS:  '#C8A96E',
  TIER_PROMOTION: '#34D399',
}

const TIER_COLOR: Record<Tier, string> = {
  T0: '#34D399',
  T1: '#60A5FA',
  T2: '#A78BFA',
  T3: '#F59E0B',
}

type TamperPhase = 'idle' | 'checking' | 'detected'

export function ConsciousnessStream() {
  const { state } = useSubstrate()
  const visible = [...state.chain].reverse().slice(0, 10)

  const [tamperPhase, setTamperPhase] = useState<TamperPhase>('idle')
  const [corruptedIdx, setCorruptedIdx] = useState<number | null>(null)

  useEffect(() => {
    if (tamperPhase !== 'idle') {
      setTamperPhase('idle')
      setCorruptedIdx(null)
    }
  // reset demo when chain grows (new tick resets visual state cleanly)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.chain.length])

  const corruptAndVerify = async () => {
    if (state.chain.length < 3) return
    setTamperPhase('checking')
    const idx = Math.floor(state.chain.length / 2)
    const entry = state.chain[idx]
    if (!entry) { setTamperPhase('idle'); return }
    const corrupted: MetacognitiveEntry[] = state.chain.map((e, i) =>
      i === idx ? { ...e, entry_hash: 'deadbeef' + e.entry_hash.slice(8) } : e
    )
    await certify(corrupted)
    setCorruptedIdx(idx)
    setTamperPhase('detected')
  }

  const restore = () => {
    setTamperPhase('idle')
    setCorruptedIdx(null)
  }

  return (
    <div className="w-full">
      <div className="flex items-center gap-3 mb-4">
        <span
          className="text-xs font-bold tracking-label uppercase"
          style={{ color: '#60A5FA' }}
        >
          Metacognitive Stream
        </span>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded"
          style={{ background: 'rgba(52,211,153,0.10)', color: '#34D399', border: '1px solid rgba(52,211,153,0.20)' }}
        >
          {state.chain.length} observations
        </span>
        <span
          className="w-2 h-2 rounded-full animate-mint-pulse"
          style={{ background: '#34D399' }}
        />
      </div>

      <div
        className="rounded-2xl overflow-hidden"
        style={{ background: '#0A0B0F', border: '1px solid #1A1D27' }}
      >
        {/* Column headers */}
        <div
          className="grid text-xs font-mono px-4 py-2 border-b"
          style={{
            gridTemplateColumns: '44px 40px 1fr 130px',
            color: '#4B5563',
            borderColor: '#1A1D27',
          }}
        >
          <span>Layer</span>
          <span>Tier</span>
          <span>Signal</span>
          <span className="text-right">Hash chain</span>
        </div>

        {/* Rows */}
        <div className="flex flex-col divide-y divide-hub-border">
          {visible.length === 0 && (
            <div className="px-4 py-3 text-xs font-mono" style={{ color: '#374151' }}>
              Initialising substrate…
            </div>
          )}
          {visible.map((entry, i) => {
            const layerColor = LAYER_COLOR[entry.observation.layer]
            const tierColor = TIER_COLOR[entry.observation.tier]
            const prev8 = entry.previous_entry_hash.slice(0, 8)
            const cur8 = entry.entry_hash.slice(0, 8)
            return (
              <div
                key={entry.entry_hash}
                className="grid items-center px-4 py-2.5 text-xs font-mono transition-all duration-300"
                style={{
                  gridTemplateColumns: '44px 40px 1fr 130px',
                  opacity: i === 0 ? 1 : Math.max(0.25, 1 - i * 0.08),
                  background: i === 0 ? 'rgba(255,255,255,0.015)' : 'transparent',
                }}
              >
                {/* Layer badge */}
                <span
                  className="inline-flex items-center justify-center w-8 h-5 rounded text-xs font-bold"
                  style={{ background: layerColor + '18', color: layerColor }}
                >
                  {LAYER_LABEL[entry.observation.layer]}
                </span>

                {/* Tier badge */}
                <span
                  className="inline-flex items-center justify-center w-7 h-5 rounded text-xs font-bold"
                  style={{ background: tierColor + '18', color: tierColor }}
                >
                  {entry.observation.tier}
                </span>

                {/* Signal */}
                <span
                  className="truncate pr-3"
                  style={{ color: i === 0 ? '#ECEAE3' : '#6B6B7A' }}
                >
                  {entry.observation.signal}
                </span>

                {/* Hash chain link */}
                <span
                  className="text-right truncate"
                  style={{ color: '#374151', letterSpacing: '0.05em' }}
                >
                  <span style={{ color: '#4B5563' }}>{prev8}</span>
                  <span style={{ color: '#1F2937' }}>→</span>
                  <span style={{ color: i === 0 ? layerColor : '#374151' }}>{cur8}</span>
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Tamper demo ────────────────────────────────────────── */}
      <div
        className="mt-4 rounded-xl px-5 py-4 flex flex-col sm:flex-row items-start sm:items-center gap-3"
        style={{ background: '#0A0B0F', border: `1px solid ${tamperPhase === 'detected' ? 'rgba(248,113,113,0.30)' : '#1A1D27'}` }}
      >
        <div className="flex-1 min-w-0">
          <p className="text-xs font-mono mb-0.5" style={{ color: '#4B5563' }}>
            Tamper-evident verification
          </p>
          {tamperPhase === 'idle' && (
            <p className="text-xs font-mono" style={{ color: '#374151' }}>
              Corrupt any entry in the chain → <code style={{ color: '#A78BFA' }}>certify()</code> detects it instantly.
            </p>
          )}
          {tamperPhase === 'checking' && (
            <p className="text-xs font-mono" style={{ color: '#C8A96E' }}>
              verifying chain integrity…
            </p>
          )}
          {tamperPhase === 'detected' && corruptedIdx !== null && (
            <p className="text-xs font-mono" style={{ color: '#F87171' }}>
              is_valid: <strong>false</strong> — entry #{corruptedIdx} corrupted.{' '}
              <span style={{ color: '#4B5563' }}>Hash mismatch detected at sequence {state.chain[corruptedIdx]?.sequence ?? corruptedIdx}.</span>
            </p>
          )}
        </div>

        {tamperPhase === 'idle' && (
          <button
            onClick={() => { void corruptAndVerify() }}
            disabled={state.chain.length < 3}
            className="flex-shrink-0 text-xs font-semibold font-mono px-4 py-2 rounded-lg transition-opacity hover:opacity-80 disabled:opacity-30"
            style={{ background: 'rgba(248,113,113,0.12)', color: '#F87171', border: '1px solid rgba(248,113,113,0.25)' }}
          >
            Corrupt one entry →
          </button>
        )}
        {tamperPhase === 'checking' && (
          <span
            className="flex-shrink-0 text-xs font-mono px-4 py-2 rounded-lg animate-mint-pulse"
            style={{ background: 'rgba(200,169,110,0.08)', color: '#C8A96E', border: '1px solid rgba(200,169,110,0.15)' }}
          >
            certify()…
          </span>
        )}
        {tamperPhase === 'detected' && (
          <button
            onClick={restore}
            className="flex-shrink-0 text-xs font-semibold font-mono px-4 py-2 rounded-lg transition-opacity hover:opacity-80"
            style={{ background: 'rgba(52,211,153,0.12)', color: '#34D399', border: '1px solid rgba(52,211,153,0.25)' }}
          >
            Restore integrity
          </button>
        )}
      </div>
    </div>
  )
}
