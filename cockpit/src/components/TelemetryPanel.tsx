// Cycles 41–50: Full holonic telemetry dashboard with gate metrics and epoch health.
// Gate 222: Resonance Monitor — phi_headroom bar + 4-pip depth indicator.
// Gate 224: Chord Network — UNIFIED/CLUSTERED/SPLIT verdict with peer chord display.
import { useState, useEffect } from 'react'
import { Activity, ChevronDown, ChevronUp, WifiOff, Zap, Shield, Radio } from 'lucide-react'
import { subscribeTelemetry, type TelemetryState } from '../lib/telemetry.js'
import { AutonodeStatus } from './AutonodeStatus.js'
import { fetchNetworkResonance, type NetworkResonanceReport, type NetworkVerdict, type NetworkPeer } from '../../../packages/shared/lib/autonode.js'

const BRIDGE = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

interface ResonanceData {
  is_resonant: boolean
  is_certified: boolean
  phi_convergent: boolean
  vortex_family: string
  ring_valid: boolean
  sequence_monotone: boolean
  resonance_depth: number
  resonance_coefficient: number
  phi_headroom: number
  divergence_risk: number
}

function useResonance() {
  const [data, setData] = useState<ResonanceData | null>(null)
  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const res = await fetch(`${BRIDGE}/resonance`, { signal: AbortSignal.timeout(3000) } as RequestInit)
        if (res.ok && active) setData((await res.json()) as ResonanceData)
      } catch { /* bridge offline */ }
    }
    void poll()
    const id = setInterval(() => { void poll() }, 5000)
    return () => { active = false; clearInterval(id) }
  }, [])
  return data
}

function StatusDot({ ok, pulse }: { ok: boolean; pulse?: boolean }) {
  return (
    <span
      className={`inline-block w-1.5 h-1.5 rounded-full ${ok ? 'bg-green-400' : 'bg-red-400'} ${pulse && ok ? 'animate-pulse' : ''}`}
    />
  )
}

function Indicator({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center justify-between text-xs py-0.5">
      <span className="text-aegis-muted">{label}</span>
      <StatusDot ok={ok} />
    </div>
  )
}

function Metric({ label, value, dim }: { label: string; value: string; dim?: boolean }) {
  return (
    <div className="flex items-center justify-between text-xs py-0.5">
      <span className="text-aegis-muted">{label}</span>
      <span className={`font-mono ${dim ? 'text-aegis-muted' : 'text-aegis-text'}`}>{value}</span>
    </div>
  )
}

function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div className="w-12 h-1.5 bg-aegis-border rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

interface BlockData {
  block_height: number
  state_root: string
  t0_verdict: boolean
  drift_risk: number
  is_replay_reconstructable: boolean
}

function useBlock() {
  const [data, setData] = useState<BlockData | null>(null)
  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const res = await fetch(`${BRIDGE}/block`, { signal: AbortSignal.timeout(3000) } as RequestInit)
        if (res.ok && active) setData((await res.json()) as BlockData)
      } catch { /* bridge offline */ }
    }
    void poll()
    const id = setInterval(() => { void poll() }, 5000)
    return () => { active = false; clearInterval(id) }
  }, [])
  return data
}

function useNetworkResonance(): NetworkResonanceReport | null {
  const [data, setData] = useState<NetworkResonanceReport | null>(null)
  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const report = await fetchNetworkResonance(BRIDGE)
        if (active) setData(report)
      } catch { /* bridge offline — stay null */ }
    }
    void poll()
    const id = setInterval(() => void poll(), 10_000)
    return () => { active = false; clearInterval(id) }
  }, [])
  return data
}

const VERDICT_COLOR: Record<NetworkVerdict, string> = {
  UNIFIED:   '#34D399',
  CLUSTERED: '#C8A96E',
  SPLIT:     '#F87171',
}

export function TelemetryPanel() {
  const [state, setState] = useState<TelemetryState>({ status: 'offline' })
  const [open, setOpen] = useState(true)
  const resonance = useResonance()
  const block = useBlock()
  const network = useNetworkResonance()

  useEffect(() => subscribeTelemetry(setState), [])

  const streaming = state.status === 'online' && state.streaming

  return (
    <div className="border-t border-aegis-border">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-aegis-muted hover:text-aegis-text transition-colors"
        aria-label="Toggle runtime telemetry panel"
      >
        <div className="flex items-center gap-1.5">
          <Activity size={12} />
          <span className="font-medium">Runtime</span>
          {state.status === 'online' && <StatusDot ok pulse />}
          {state.status === 'offline' && <span className="w-1.5 h-1.5 rounded-full bg-gray-600 inline-block" />}
          {streaming && <Radio size={10} className="text-green-400" aria-label="Live SSE stream" />}
        </div>
        {open ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-2">
          {state.status === 'offline' && (
            <div className="flex items-center gap-1.5 text-xs text-aegis-muted py-1">
              <WifiOff size={12} />
              <span>Runtime offline — start bridge.py</span>
            </div>
          )}

          {state.status === 'error' && (
            <div className="text-xs text-red-400 py-1">{state.message}</div>
          )}

          {state.status === 'online' && (() => {
            const d = state.data
            const healthy = d.pgcs_passes && d.corruption_count === 0 && d.calibrator_passes_100k
            const failState = d.failsafe_state
            return (
              <>
                {/* System health summary */}
                <div className={`rounded px-2 py-1 text-xs font-medium flex items-center gap-1.5 ${healthy ? 'bg-green-900/30 text-green-300' : 'bg-red-900/30 text-red-300'}`}>
                  {healthy ? <Zap size={11} /> : <Shield size={11} />}
                  {healthy ? 'All systems nominal' : 'Attention required'}
                </div>

                {/* Core indicators */}
                <div className="space-y-0.5">
                  <Indicator ok={d.pgcs_passes} label="PGCS (disk I/O=0)" />
                  <Indicator ok={failState === 'active' || failState === 'nominal'} label={`Failsafe — ${failState}`} />
                  <Indicator ok={d.corruption_count === 0} label="Epoch integrity" />
                  <Indicator ok={d.calibrator_passes_100k} label="Calibrator 100k" />
                </div>

                {/* Gate metrics */}
                {d.gate != null && (
                  <div className="border-t border-aegis-border pt-1 space-y-0.5">
                    <div className="text-xs text-aegis-muted font-medium mb-0.5">Gate</div>
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">Accept rate</span>
                      <div className="flex items-center gap-1.5">
                        <MiniBar value={d.gate.gate_acceptance_rate} max={1} color="bg-blue-400" />
                        <span className="font-mono text-aegis-text">{(d.gate.gate_acceptance_rate * 100).toFixed(1)}%</span>
                      </div>
                    </div>
                    <Metric label="Total signals" value={String(d.gate.gate_total_signals)} />
                    <Indicator ok={d.gate.is_sealed} label="Router sealed" />
                  </div>
                )}

                {/* Calibration metrics */}
                <div className="border-t border-aegis-border pt-1 space-y-0.5">
                  <div className="text-xs text-aegis-muted font-medium mb-0.5">Calibration</div>
                  <div className="flex items-center justify-between text-xs py-0.5">
                    <span className="text-aegis-muted">VCG error</span>
                    <div className="flex items-center gap-1.5">
                      <MiniBar value={d.avg_vcg_error} max={1} color={d.avg_vcg_error < 0.1 ? 'bg-green-400' : 'bg-yellow-400'} />
                      <span className="font-mono text-aegis-text">{d.avg_vcg_error.toFixed(4)}</span>
                    </div>
                  </div>
                  <Metric label="Drift index D" value={d.drift_index.toFixed(6)} dim={d.drift_index === 0} />
                  <Metric label="Epoch" value={String(d.epoch)} />
                  <Metric label="Sequence" value={d.sequence.toLocaleString()} dim />
                </div>

                {/* Layer B extended metrics — shown when TGCS/AFSE bridge wired */}
                {(d.afse_r2 != null || d.holonic_scaling_score != null) && (
                  <div className="border-t border-aegis-border pt-1 space-y-0.5">
                    <div className="text-xs text-aegis-muted font-medium mb-0.5">Layer B</div>
                    {d.afse_r2 != null && (
                      <div className="flex items-center justify-between text-xs py-0.5">
                        <span className="text-aegis-muted">AFSE R²</span>
                        <div className="flex items-center gap-1.5">
                          <MiniBar value={d.afse_r2} max={1} color={d.afse_r2 >= 0.98 ? 'bg-green-400' : 'bg-yellow-400'} />
                          <span className="font-mono text-aegis-text">{d.afse_r2.toFixed(4)}</span>
                        </div>
                      </div>
                    )}
                    {d.tgcs_variance != null && (
                      <Metric label="TGCS σ²" value={d.tgcs_variance.toFixed(6)} dim={d.tgcs_variance === 0} />
                    )}
                    {d.holonic_scaling_score != null && (
                      <Metric label="Holonic scale" value={d.holonic_scaling_score.toFixed(4)} />
                    )}
                  </div>
                )}

                {/* Autonode — T0 verdict gate + constitutional hash */}
                <AutonodeStatus bridgeUrl={BRIDGE} />

                {/* Block — distributed ledger state root */}
                {block != null && (
                  <div className="border-t border-aegis-border pt-1 space-y-0.5">
                    <div className="text-xs text-aegis-muted font-medium mb-0.5">Block</div>
                    <Metric label="Height" value={String(block.block_height)} />
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">State root</span>
                      <span className="font-mono text-aegis-muted">…{block.state_root.slice(-8)}</span>
                    </div>
                    <Indicator ok={block.t0_verdict} label="T0 verdict" />
                    <Indicator ok={block.is_replay_reconstructable} label="Replay OK" />
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">Drift risk</span>
                      <div className="flex items-center gap-1.5">
                        <MiniBar value={block.drift_risk} max={1} color={block.drift_risk < 0.618 ? 'bg-green-400' : 'bg-red-400'} />
                        <span className="font-mono text-aegis-muted">{block.drift_risk.toFixed(3)}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Gate 222 — Resonance Monitor */}
                {resonance != null && (
                  <div className="border-t border-aegis-border pt-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-aegis-muted font-medium">Resonance</span>
                      <span
                        className="text-xs font-mono px-1 rounded"
                        style={{
                          color: resonance.is_certified ? '#34D399' : resonance.is_resonant ? '#C8A96E' : '#F87171',
                          background: resonance.is_certified ? 'rgba(52,211,153,0.1)' : resonance.is_resonant ? 'rgba(200,169,110,0.1)' : 'rgba(248,113,113,0.1)',
                        }}
                      >
                        {resonance.is_certified ? 'CERTIFIED' : resonance.is_resonant ? 'RESONANT' : 'BREACH'}
                      </span>
                    </div>

                    {/* 4-pip depth indicator */}
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">Depth</span>
                      <div className="flex items-center gap-1">
                        {[0, 1, 2, 3].map(i => (
                          <span
                            key={i}
                            className="inline-block w-2 h-2 rounded-sm"
                            style={{
                              background: i < resonance.resonance_depth
                                ? (resonance.resonance_depth === 4 ? '#34D399' : '#C8A96E')
                                : '#1E1E22',
                            }}
                          />
                        ))}
                        <span className="font-mono text-aegis-muted ml-1">{resonance.resonance_depth}/4</span>
                      </div>
                    </div>

                    {/* φ-headroom progress bar */}
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">φ-headroom</span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-aegis-border rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${Math.max(0, Math.min(100, (resonance.phi_headroom / 0.618) * 100))}%`,
                              background: resonance.phi_convergent ? '#34D399' : '#F87171',
                            }}
                          />
                        </div>
                        <span className="font-mono text-aegis-muted">{resonance.phi_headroom.toFixed(3)}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">Coefficient</span>
                      <span className="font-mono" style={{ color: resonance.is_certified ? '#34D399' : '#6B6B7A' }}>
                        {resonance.resonance_coefficient.toFixed(3)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">Vortex</span>
                      <span className="font-mono" style={{ color: resonance.vortex_family === 'Triadic' ? '#C8A96E' : '#6B6B7A' }}>
                        {resonance.vortex_family}
                      </span>
                    </div>
                  </div>
                )}

                {/* Gate 224 — Chord Network: multi-peer UNIFIED/CLUSTERED/SPLIT */}
                {network != null && (
                  <div className="border-t border-aegis-border pt-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-aegis-muted font-medium">Network</span>
                      <span
                        className="text-xs font-mono px-1 rounded"
                        style={{
                          color: VERDICT_COLOR[network.verdict],
                          background: `${VERDICT_COLOR[network.verdict]}1A`,
                        }}
                      >
                        {network.verdict}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">Peers</span>
                      <span className="font-mono text-aegis-muted">
                        {network.below_phi_count}✓ {network.above_phi_count > 0 ? `${network.above_phi_count}✗ ` : ''}
                        {network.triadic_count}△
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs py-0.5">
                      <span className="text-aegis-muted">Quorum △</span>
                      <span className="font-mono" style={{ color: network.quorum_triadic ? '#34D399' : '#6B6B7A' }}>
                        {network.quorum_triadic ? 'YES' : 'NO'} ({network.triadic_count}/{network.peer_count})
                      </span>
                    </div>
                    <div className="flex gap-0.5 pt-0.5">
                      {network.peers.slice(0, 5).map((p: NetworkPeer) => (
                        <div
                          key={p.node_id}
                          title={`${p.node_id}\nchord: ${p.chord_hex}\ndrift: ${p.drift_risk}`}
                          className="flex-1 h-1.5 rounded-sm"
                          style={{
                            background: p.chord_bytes[3] === 0 ? '#34D399'
                                      : p.chord_bytes[3] === 1 ? '#C8A96E'
                                      : '#F87171',
                          }}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )
          })()}
        </div>
      )}
    </div>
  )
}
