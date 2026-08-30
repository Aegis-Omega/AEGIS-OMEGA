import { useState, useEffect } from 'react'
import type { TelemetryState, TelemetrySnapshot } from '../lib/telemetry.js'
import { subscribeTelemetry } from '../lib/telemetry.js'

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full mr-2 ${ok ? 'bg-omega-glow animate-pulse-dot' : 'bg-omega-alert'}`}
    />
  )
}

interface MetricProps {
  label: string
  value: string
  alert?: boolean
}

function Metric({ label, value, alert }: MetricProps) {
  const valueClass = alert === true ? 'text-omega-alert' : 'text-omega-glow'
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-omega-border last:border-0">
      <span className="text-omega-muted text-xs">{label}</span>
      <span className={`text-xs font-bold ${valueClass}`}>{value}</span>
    </div>
  )
}

function rows(data: TelemetrySnapshot): MetricProps[] {
  return [
    { label: 'Sequence',       value: String(data.sequence) },
    { label: 'Epoch',          value: String(data.epoch) },
    {
      label: 'Avg VCG Error',
      value: data.avg_vcg_error.toFixed(4),
      alert: data.avg_vcg_error > 0.35,
    },
    {
      label: 'Drift Index',
      value: data.drift_index.toFixed(4),
      alert: data.drift_index > 0.1,
    },
    {
      label: 'PGCS',
      value: data.pgcs_passes ? 'PASS' : 'FAIL',
      alert: !data.pgcs_passes,
    },
    {
      label: 'Failsafe State',
      value: data.failsafe_state,
      alert: data.failsafe_state !== 'nominal',
    },
    {
      label: 'Corruption Count',
      value: String(data.corruption_count),
      alert: data.corruption_count !== 0,
    },
    {
      label: 'Calibrator 100k',
      value: data.calibrator_passes_100k ? 'PASS' : 'FAIL',
      alert: !data.calibrator_passes_100k,
    },
  ]
}

export function BridgePanel() {
  const [state, setState] = useState<TelemetryState>({ status: 'offline' })
  useEffect(() => subscribeTelemetry(setState), [])

  const isOnline = state.status === 'online'
  const data = isOnline ? state.data : null

  return (
    <section className="bg-omega-surface border border-omega-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-omega-text text-sm font-bold tracking-wider uppercase">Python Bridge</h2>
        <div className="flex items-center text-xs">
          <StatusDot ok={isOnline} />
          <span className={isOnline ? 'text-omega-glow' : 'text-omega-muted'}>
            {isOnline ? 'Online · :7890' : 'Offline'}
          </span>
        </div>
      </div>
      {state.status === 'error' && (
        <p className="text-omega-alert text-xs mb-3">{state.message}</p>
      )}
      {data
        ? rows(data).map(m => <Metric key={m.label} {...m} />)
        : Array.from({ length: 8 }, (_, i) => (
            <Metric key={i} label="—" value="—" />
          ))}
      {!isOnline && (
        <p className="text-omega-muted text-xs mt-4">
          Start: <code className="text-omega-glow">python python/bridge.py</code>
        </p>
      )}
    </section>
  )
}
