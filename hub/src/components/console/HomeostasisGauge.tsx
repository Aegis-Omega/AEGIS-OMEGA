// AEGIS-Ω Console — homeostasis gauge.
// Visualizes the HPA-axis hormetic curve from /platform/calibration.
// The fitness_mean rides the curve: slack → optimal → stressed → critical.
// HD-equivalent (fitness stdev) is the spread = the hallucination-delta proxy.

import { T, MONO, ZONE_META, REC_META, glass } from './consoleTokens.js'
import { Heading } from './SystemStatusBar.js'
import type { CalibrationStatus } from '../../lib/platformConsole.js'

const W = 460
const H = 150

// Hormetic curve: rises to the optimal band, then falls into breakdown.
// y is inverted (SVG): lower y = higher productivity.
function curveY(x: number): number {
  const peak = 0.5 // optimal center
  const dist = Math.abs(x - peak)
  const productivity = Math.max(0, 1 - Math.pow(dist * 2.1, 2))
  return H - 28 - productivity * (H - 56)
}

function buildPath(): string {
  let d = ''
  for (let i = 0; i <= 100; i += 1) {
    const x = i / 100
    const px = 8 + x * (W - 16)
    const py = curveY(x)
    d += `${i === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)} `
  }
  return d
}

const ZONE_BANDS: { from: number; to: number; zone: keyof typeof ZONE_META }[] = [
  { from: 0.0,  to: 0.30, zone: 'slack' },
  { from: 0.30, to: 0.70, zone: 'optimal' },
  { from: 0.70, to: 0.90, zone: 'stressed' },
  { from: 0.90, to: 1.0,  zone: 'critical' },
]

export function HomeostasisGauge({ cal }: { cal: CalibrationStatus }) {
  const meta = ZONE_META[cal.homeostasis_zone] ?? ZONE_META.optimal!
  const rec = REC_META[cal.recommendation] ?? REC_META.MAINTAIN!
  const markerX = 8 + cal.fitness_mean * (W - 16)
  const markerY = curveY(cal.fitness_mean)
  const trendGlyph = cal.trend === 'rising' ? '↑' : cal.trend === 'falling' ? '↓' : '→'

  return (
    <div style={{ ...glass(meta.color), padding: 20 }}>
      <div className="flex items-center justify-between mb-1">
        <Heading>HOMEOSTASIS · HPA axis</Heading>
        <span style={{
          fontFamily: MONO, fontSize: 11, color: meta.color,
          padding: '3px 10px', borderRadius: 20,
          background: `${meta.color}14`, border: `1px solid ${meta.color}35`,
        }}>{meta.label}</span>
      </div>
      <p style={{ fontSize: 12, color: T.muted, marginTop: 6, marginBottom: 14 }}>{meta.band}</p>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
        {ZONE_BANDS.map(b => (
          <rect key={b.zone} x={8 + b.from * (W - 16)} y={6}
            width={(b.to - b.from) * (W - 16)} height={H - 30}
            fill={ZONE_META[b.zone]!.color} opacity={cal.homeostasis_zone === b.zone ? 0.10 : 0.03} />
        ))}
        <path d={buildPath()} fill="none" stroke={T.muted} strokeWidth={1.5} opacity={0.5} />
        {/* live marker */}
        <line x1={markerX} y1={markerY} x2={markerX} y2={H - 24} stroke={meta.color} strokeWidth={1} opacity={0.4} strokeDasharray="2 3" />
        <circle cx={markerX} cy={markerY} r={6} fill={meta.color}>
          <animate attributeName="r" values="6;9;6" dur="2.4s" repeatCount="indefinite" />
        </circle>
        <circle cx={markerX} cy={markerY} r={3} fill={T.void} />
        {ZONE_BANDS.map(b => (
          <text key={b.zone} x={8 + ((b.from + b.to) / 2) * (W - 16)} y={H - 8}
            fill={ZONE_META[b.zone]!.color} fontSize={9} fontFamily="monospace"
            textAnchor="middle" opacity={cal.homeostasis_zone === b.zone ? 0.9 : 0.4}>
            {ZONE_META[b.zone]!.label}
          </text>
        ))}
      </svg>

      <div className="grid grid-cols-4 gap-2 mt-3">
        <Metric label="fitness μ" value={cal.fitness_mean.toFixed(3)} color={meta.color} />
        <Metric label="HD-equiv" value={cal.hd_equivalent.toFixed(3)} color={cal.hd_equivalent < 0.2 ? T.green : T.amber} />
        <Metric label="trend" value={`${trendGlyph} ${cal.trend}`} color={T.sub} />
        <Metric label="action" value={`${rec.glyph} ${cal.recommendation}`} color={rec.color} />
      </div>
      <p style={{ fontSize: 11, color: T.muted, marginTop: 12, lineHeight: 1.5, fontFamily: MONO }}>
        HD-equivalent = stdev(fitness) over {cal.window_size} cycles. Spread = unreliability.
      </p>
    </div>
  )
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: T.inset, borderRadius: 8, padding: '8px 10px' }}>
      <div style={{ fontSize: 9, color: T.muted, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
      <div style={{ fontFamily: MONO, fontSize: 13, color, marginTop: 2 }}>{value}</div>
    </div>
  )
}
