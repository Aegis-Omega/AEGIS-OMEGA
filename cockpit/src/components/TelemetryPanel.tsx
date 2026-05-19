// Cycles 41–50: Full holonic telemetry dashboard with gate metrics and epoch health.
import { useState, useEffect } from 'react'
import { Activity, ChevronDown, ChevronUp, WifiOff, Zap, Shield, Radio } from 'lucide-react'
import { subscribeTelemetry, type TelemetryState } from '../lib/telemetry.js'

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

export function TelemetryPanel() {
  const [state, setState] = useState<TelemetryState>({ status: 'offline' })
  const [open, setOpen] = useState(true)

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
              </>
            )
          })()}
        </div>
      )}
    </div>
  )
}
