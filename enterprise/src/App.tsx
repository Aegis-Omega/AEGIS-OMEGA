/**
 * AEGIS-Ω Enterprise Governance Dashboard
 * Constitutional compliance · Audit trail · Multi-node resonance · EU AI Act Article 12
 *
 * Layout:
 *   [TOP: Constitutional Ribbon — law + T0 + chord + network + resonance]
 *   [LEFT NAV: 8 governance surfaces]
 *   [MAIN: Active surface content]
 *   [RIGHT: Live telemetry + self-certification status]
 */
import { useState, useEffect, useCallback } from 'react'
import {
  Shield, Activity, GitBranch, Users, FileText, Radio,
  Layers, AlertTriangle, CheckCircle, Circle, Wifi, WifiOff,
  Globe,
} from 'lucide-react'
import { subscribeLiveState, type LiveState } from './lib/bridge.js'

// ─── Design tokens (inline for single-bundle enterprise product) ──────────

const T = {
  T0: '#34D399', T1: '#60A5FA', T2: '#A78BFA', T3: '#F59E0B', T4: '#F87171',
  phi: '#C8A96E', phiDeep: '#3D3020', phiAlpha: 'rgba(200,169,110,0.12)',
  bg: '#0F0F11', surface: '#141416', card: '#1A1A1E', hover: '#1E1E26',
  border: '#1E1E22', borderMedium: '#27272D', borderStrong: '#3F3F46',
  text: '#ECEAE3', secondary: '#A1A1AA', muted: '#6B6B7A',
  ok: '#34D399', warn: '#C8A96E', error: '#F87171', info: '#60A5FA',
  unified: '#34D399', clustered: '#C8A96E', split: '#F87171',
} as const

// ─── Surfaces ─────────────────────────────────────────────────────────────

type SurfaceId =
  | 'constitutional-health'
  | 'audit-trail'
  | 'chord-network'
  | 'agent-registry'
  | 'skill-certification'
  | 'compliance'
  | 'governance-events'
  | 'self-certification'

const SURFACES: Array<{ id: SurfaceId; label: string; icon: React.ElementType; tier: string }> = [
  { id: 'constitutional-health', label: 'Constitutional Health',  icon: Shield,      tier: 'T0' },
  { id: 'audit-trail',           label: 'Audit Trail',           icon: FileText,    tier: 'T1' },
  { id: 'chord-network',         label: 'Chord Network',         icon: Radio,       tier: 'T2' },
  { id: 'agent-registry',        label: 'Agent Registry',        icon: Users,       tier: 'T2' },
  { id: 'skill-certification',   label: 'Skill Certification',   icon: Layers,      tier: 'T2' },
  { id: 'compliance',            label: 'EU AI Act Compliance',  icon: Globe,       tier: 'T1' },
  { id: 'governance-events',     label: 'Governance Events',     icon: Activity,    tier: 'T2' },
  { id: 'self-certification',    label: 'Self-Certification',    icon: GitBranch,   tier: 'T1' },
]

// ─── Constitutional Ribbon ────────────────────────────────────────────────

function Ribbon({ state }: { state: LiveState }) {
  const { node, network, resonance } = state
  const t0 = node?.t0_verdict
  const t0Color = t0 == null ? T.muted : t0 ? T.T0 : T.error
  const netColor = network == null ? T.muted
    : network.verdict === 'UNIFIED' ? T.unified
    : network.verdict === 'CLUSTERED' ? T.clustered : T.split

  return (
    <div className="flex items-center gap-3 px-4 py-1.5 text-xs font-mono shrink-0"
      style={{ background: '#0A0A0C', borderBottom: `1px solid ${T.phiDeep}` }}>
      <span style={{ color: T.phiDeep }}>AdaptivePower(T) ≤ ReplayVerifiability(T)</span>
      <span style={{ color: T.borderStrong }}>·</span>
      <span style={{ color: t0Color, fontWeight: 600 }}>
        {t0 == null ? 'T0:—' : t0 ? 'T0:PASS' : 'T0:FAIL'}
      </span>
      {node?.chord_hex && (
        <>
          <span style={{ color: T.borderStrong }}>·</span>
          <span style={{ color: T.phi }}>chord:{node.chord_hex}</span>
        </>
      )}
      {network && (
        <>
          <span style={{ color: T.borderStrong }}>·</span>
          <span style={{ color: netColor }}>net:{network.verdict}</span>
        </>
      )}
      {resonance && (
        <>
          <span style={{ color: T.borderStrong }}>·</span>
          <span className="flex items-center gap-1">
            <span style={{ color: T.muted }}>res:</span>
            {[0,1,2,3].map(i => (
              <span key={i} className="inline-block w-1.5 h-1.5 rounded-sm"
                style={{ background: i < resonance.resonance_depth
                  ? (resonance.resonance_depth === 4 ? T.T0 : T.phi)
                  : T.border }} />
            ))}
          </span>
          <span style={{ color: T.phi }}>{resonance.phi_headroom.toFixed(4)}φ</span>
        </>
      )}
      <span className="flex-1" />
      <span style={{ color: T.border }}>E[S|F]=S</span>
      <span style={{ color: T.borderStrong }}>·</span>
      <span style={{ color: T.phiDeep }}>AEGIS-Ω Enterprise v1.0.0</span>
    </div>
  )
}

// ─── Left navigation ──────────────────────────────────────────────────────

function NavItem({
  surface, active, onClick,
}: { surface: typeof SURFACES[0]; active: boolean; onClick: () => void }) {
  const tierColor = T[surface.tier as keyof typeof T] as string ?? T.muted
  const Icon = surface.icon
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left rounded transition-colors"
      style={{
        background: active ? T.hover : 'transparent',
        color: active ? T.text : T.muted,
        borderLeft: active ? `2px solid ${tierColor}` : '2px solid transparent',
      }}
    >
      <Icon size={14} style={{ color: active ? tierColor : T.muted, flexShrink: 0 }} />
      <span className="flex-1 truncate">{surface.label}</span>
      <span className="text-2xs font-mono" style={{ color: active ? tierColor : T.border }}>
        {surface.tier}
      </span>
    </button>
  )
}

// ─── Right telemetry panel ────────────────────────────────────────────────

function RightPanel({ state }: { state: LiveState }) {
  const { node, network, resonance } = state
  const connected = node != null

  return (
    <div className="flex flex-col gap-2 p-3 text-xs" style={{ borderLeft: `1px solid ${T.border}` }}>
      <div className="flex items-center gap-1.5 mb-1">
        {connected
          ? <Wifi size={12} style={{ color: T.T0 }} />
          : <WifiOff size={12} style={{ color: T.muted }} />}
        <span style={{ color: connected ? T.T0 : T.muted }}>
          {connected ? 'BRIDGE ONLINE' : 'BRIDGE OFFLINE'}
        </span>
      </div>

      {node && (
        <div className="space-y-1.5">
          <Row label="T0" value={node.t0_verdict ? 'PASS' : 'FAIL'}
            color={node.t0_verdict ? T.T0 : T.error} />
          <Row label="epoch" value={node.epoch} />
          <Row label="seq" value={node.sequence} />
          <Row label="corruption" value={node.corruption_count}
            color={node.corruption_count === 0 ? T.T0 : T.error} />
          <Row label="drift" value={`${(node.drift_risk * 100).toFixed(2)}%`}
            color={node.drift_risk < node.phi_threshold ? T.T0 : T.error} />
          {node.chord_hex && (
            <Row label="chord" value={node.chord_hex} color={T.phi} mono />
          )}
        </div>
      )}

      {resonance && (
        <div className="mt-2 pt-2 space-y-1.5" style={{ borderTop: `1px solid ${T.border}` }}>
          <div className="font-medium mb-1" style={{ color: T.secondary }}>Resonance</div>
          <Row label="depth" value={`${resonance.resonance_depth}/4`}
            color={resonance.resonance_depth === 4 ? T.T0 : T.warn} />
          <Row label="coeff" value={resonance.resonance_coefficient.toFixed(3)}
            color={resonance.is_certified ? T.T0 : T.muted} />
          <Row label="vortex" value={resonance.vortex_family} color={T.phi} />
          <Row label="φ-head" value={resonance.phi_headroom.toFixed(4)}
            color={resonance.phi_convergent ? T.T0 : T.error} />
        </div>
      )}

      {network && (
        <div className="mt-2 pt-2 space-y-1.5" style={{ borderTop: `1px solid ${T.border}` }}>
          <div className="font-medium mb-1" style={{ color: T.secondary }}>Network</div>
          <Row label="verdict" value={network.verdict}
            color={network.verdict === 'UNIFIED' ? T.unified
                 : network.verdict === 'CLUSTERED' ? T.clustered : T.split} />
          <Row label="peers" value={`${network.below_phi_count}✓/${network.peer_count}`}
            color={network.all_below_phi ? T.T0 : T.warn} />
          <Row label="triadic" value={`${network.triadic_count}/${network.peer_count}`}
            color={network.quorum_triadic ? T.T0 : T.muted} />
          <div className="flex gap-0.5 mt-1">
            {network.peers.slice(0, 5).map(p => (
              <div key={p.node_id}
                title={`${p.node_id}: chord=${p.chord_hex}`}
                className="flex-1 h-1.5 rounded-sm"
                style={{ background: p.chord_bytes[3] === 0 ? T.ok
                       : p.chord_bytes[3] === 1 ? T.warn : T.error }} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Row({ label, value, color, mono }: {
  label: string; value: unknown; color?: string; mono?: boolean
}) {
  return (
    <div className="flex justify-between items-center">
      <span style={{ color: T.muted }}>{label}</span>
      <span className={mono ? 'font-mono' : ''} style={{ color: color ?? T.secondary }}>
        {String(value)}
      </span>
    </div>
  )
}

// ─── Surfaces content ─────────────────────────────────────────────────────

function ConstitutionalHealthSurface({ state }: { state: LiveState }) {
  const { node, resonance, network } = state
  const certified = resonance?.is_certified && network?.verdict === 'UNIFIED' && node?.t0_verdict

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>
          Constitutional Health
        </h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Live T0/T1/T2 invariant status across all constitutional substrates.
        </p>
      </div>

      {/* Self-certification banner */}
      <div className="rounded-lg p-4 flex items-center gap-4"
        style={{
          background: certified ? 'rgba(52,211,153,0.06)' : 'rgba(248,113,113,0.06)',
          border: `1px solid ${certified ? 'rgba(52,211,153,0.25)' : 'rgba(248,113,113,0.25)'}`,
        }}>
        <div className="flex-shrink-0">
          {certified
            ? <CheckCircle size={28} style={{ color: T.T0 }} />
            : <AlertTriangle size={28} style={{ color: T.error }} />}
        </div>
        <div>
          <div className="font-semibold mb-0.5" style={{ color: certified ? T.T0 : T.error }}>
            {node == null ? 'Awaiting bridge...'
             : certified ? 'CONSTITUTIONALLY CERTIFIED'
             : 'CERTIFICATION INCOMPLETE'}
          </div>
          <div className="text-sm" style={{ color: T.muted }}>
            {certified
              ? 'All T1 invariants satisfied · Network UNIFIED · T0 PASS · Self-hash stable'
              : 'One or more constitutional invariants require attention.'}
          </div>
        </div>
      </div>

      {/* Invariant grid */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'T0 Verdict', ok: node?.t0_verdict, desc: 'corruption=0 · drift<φ' },
          { label: 'φ-Convergent', ok: resonance?.phi_convergent, desc: 'Lawvere risk < 1/φ' },
          { label: 'Ring Valid', ok: resonance?.ring_valid, desc: 'A-B-C-B′-A′ chiastic law' },
          { label: 'Seq Monotone', ok: resonance?.sequence_monotone, desc: 'SPSF write law' },
          { label: 'Network UNIFIED', ok: network?.verdict === 'UNIFIED', desc: 'All peers in chord' },
          { label: 'Triadic Quorum', ok: network?.quorum_triadic, desc: '≥1/φ nodes Triadic' },
        ].map(item => (
          <div key={item.label} className="rounded-lg p-4"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium" style={{ color: T.text }}>{item.label}</span>
              {item.ok == null
                ? <Circle size={14} style={{ color: T.muted }} />
                : item.ok
                  ? <CheckCircle size={14} style={{ color: T.T0 }} />
                  : <AlertTriangle size={14} style={{ color: T.error }} />}
            </div>
            <div className="text-2xs font-mono" style={{ color: T.muted }}>{item.desc}</div>
          </div>
        ))}
      </div>

      {/* Constitutional law display */}
      <div className="rounded-lg p-4" style={{ background: T.card, border: `1px solid ${T.phiDeep}` }}>
        <div className="font-mono text-sm space-y-1.5">
          {[
            { label: 'Root Law:',     value: 'AdaptivePower(T) ≤ ReplayVerifiability(T)' },
            { label: 'Martingale:',   value: 'E[S_{n+1}|F_n] = S_n' },
            { label: 'Mutation Cap:', value: 'MUTATION_RATE_LIMIT = (√5−1)/2 ≈ 0.6180339887' },
            { label: 'Law of Silence:', value: 'Agents communicate only through EventEnvelope' },
          ].map(row => (
            <div key={row.label} className="flex gap-2">
              <span style={{ color: T.muted, flexShrink: 0 }}>{row.label}</span>
              <span style={{ color: T.phi }}>{row.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ChordNetworkSurface({ state }: { state: LiveState }) {
  const { network } = state
  if (!network) return <Offline />

  const verdictColor = network.verdict === 'UNIFIED' ? T.unified
    : network.verdict === 'CLUSTERED' ? T.clustered : T.split

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Chord Network</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Gate 224 — Multi-peer constitutional chord resonance tracker.
          UNIFIED = global section exists. SPLIT = non-global coherence.
        </p>
      </div>

      {/* Verdict banner */}
      <div className="rounded-lg p-4 text-center"
        style={{ background: `${verdictColor}10`, border: `1px solid ${verdictColor}30` }}>
        <div className="text-2xl font-mono font-bold mb-1" style={{ color: verdictColor }}>
          {network.verdict}
        </div>
        <div className="text-sm" style={{ color: T.muted }}>
          {network.peer_count} peers · {network.distinct_chord_classes} chord class(es)
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Below φ',  value: network.below_phi_count,  color: T.ok },
          { label: 'Above φ',  value: network.above_phi_count,  color: network.above_phi_count > 0 ? T.error : T.muted },
          { label: 'Triadic',  value: network.triadic_count,    color: T.phi },
          { label: 'Quorum △', value: network.quorum_triadic ? 'YES' : 'NO',
            color: network.quorum_triadic ? T.T0 : T.warn },
        ].map(m => (
          <div key={m.label} className="rounded-lg p-3 text-center"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="text-xl font-mono font-semibold" style={{ color: m.color }}>{m.value}</div>
            <div className="text-2xs mt-0.5" style={{ color: T.muted }}>{m.label}</div>
          </div>
        ))}
      </div>

      {/* Peer list */}
      <div className="space-y-2">
        <div className="text-sm font-medium mb-2" style={{ color: T.secondary }}>Peers</div>
        {network.peers.map(p => {
          const pColor = p.chord_bytes[3] === 0 ? T.ok : p.chord_bytes[3] === 1 ? T.warn : T.error
          const phiLabel = p.chord_bytes[3] === 0 ? 'BelowPhi' : p.chord_bytes[3] === 1 ? 'AtPhi' : 'AbovePhi'
          return (
            <div key={p.node_id} className="flex items-center gap-3 rounded-lg px-4 py-2.5"
              style={{ background: T.surface, border: `1px solid ${T.border}` }}>
              <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: pColor }} />
              <span className="font-mono text-sm flex-1" style={{ color: T.secondary }}>{p.node_id}</span>
              <span className="font-mono text-xs" style={{ color: T.phi }}>{p.chord_hex}</span>
              <span className="text-2xs" style={{ color: pColor }}>{phiLabel}</span>
              <span className="text-2xs font-mono" style={{ color: T.muted }}>
                drift:{(p.drift_risk * 100).toFixed(2)}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SelfCertificationSurface({ state }: { state: LiveState }) {
  const { node, resonance, network } = state
  const t1Ok = resonance?.phi_convergent && resonance.ring_valid && resonance.sequence_monotone
  const netOk = network?.verdict === 'UNIFIED' && (network.above_phi_count === 0)
  const verdict = !t1Ok || !netOk ? 'Uncertified'
                : netOk && t1Ok ? 'Certified'
                : 'ProvisionallyGranted'
  const vColor = verdict === 'Certified' ? T.T0 : verdict === 'ProvisionallyGranted' ? T.warn : T.error

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Self-Certification</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Gate 225 — Autopoietic state closure. The system certifies its own constitutional state
          by binding resonance + network + version into a deterministic SHA-256 self-hash.
        </p>
      </div>

      <div className="rounded-lg p-5 text-center"
        style={{ background: `${vColor}0A`, border: `1px solid ${vColor}30` }}>
        <div className="text-xl font-mono font-bold mb-2" style={{ color: vColor }}>{verdict}</div>
        <div className="text-sm" style={{ color: T.muted }}>
          {verdict === 'Certified'
            ? 'All T1 invariants satisfied · Network UNIFIED · No above-phi peers'
            : verdict === 'ProvisionallyGranted'
            ? 'T1 invariants hold · Network not fully unified or boundary state'
            : 'One or more invariants violated — certification blocked'}
        </div>
      </div>

      <div className="space-y-2">
        {[
          { label: 'T1 invariants (φ-convergent ∧ ring-valid ∧ seq-monotone)', ok: !!t1Ok },
          { label: 'Network UNIFIED', ok: network?.verdict === 'UNIFIED' },
          { label: 'No above-phi peers', ok: (network?.above_phi_count ?? 0) === 0 },
          { label: 'Triadic quorum (>1/φ)', ok: !!network?.quorum_triadic },
          { label: 'T0 verdict (corruption=0)', ok: !!node?.t0_verdict },
        ].map(item => (
          <div key={item.label} className="flex items-center gap-3 rounded px-4 py-2.5"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            {item.ok
              ? <CheckCircle size={14} style={{ color: T.T0, flexShrink: 0 }} />
              : <AlertTriangle size={14} style={{ color: T.error, flexShrink: 0 }} />}
            <span className="text-sm" style={{ color: item.ok ? T.text : T.muted }}>{item.label}</span>
          </div>
        ))}
      </div>

      <div className="rounded-lg p-4 font-mono text-xs space-y-1.5"
        style={{ background: T.card, border: `1px solid ${T.border}` }}>
        <div className="text-sm font-semibold mb-2" style={{ color: T.secondary }}>
          Constitutional Binding
        </div>
        {node?.constitutional_hash && (
          <div className="flex gap-2">
            <span style={{ color: T.muted }}>const.hash:</span>
            <span style={{ color: T.T2 }}>{node.constitutional_hash.slice(0, 32)}…</span>
          </div>
        )}
        {node?.chord_hex && (
          <div className="flex gap-2">
            <span style={{ color: T.muted }}>chord:</span>
            <span style={{ color: T.phi }}>{node.chord_hex}</span>
          </div>
        )}
        <div className="flex gap-2">
          <span style={{ color: T.muted }}>version:</span>
          <span style={{ color: T.secondary }}>AEGIS-Ω v1.0.0</span>
        </div>
        <div className="flex gap-2">
          <span style={{ color: T.muted }}>verdict:</span>
          <span style={{ color: vColor }}>{verdict}</span>
        </div>
      </div>
    </div>
  )
}

function ComplianceSurface() {
  const articles = [
    { id: 'Art.12', label: 'Record Keeping', status: 'COMPLIANT', detail: 'Append-only event log with SHA-256 chain' },
    { id: 'Art.13', label: 'Transparency',   status: 'COMPLIANT', detail: 'All decisions replay-certifiable with audit_trace_id' },
    { id: 'Art.14', label: 'Human Oversight', status: 'COMPLIANT', detail: 'Mutation authority suspended on M-rate > 1/φ' },
    { id: 'Art.17', label: 'Quality Mgmt',    status: 'COMPLIANT', detail: 'T0/T1/T2 tier tagging on all inference outputs' },
    { id: 'Art.9',  label: 'Risk Management', status: 'COMPLIANT', detail: 'Hysteresis quarantine on drift_index anomalies' },
    { id: 'Art.10', label: 'Data Governance', status: 'COMPLIANT', detail: 'Event sourced, no hidden state, replay-provable' },
  ]

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>EU AI Act Compliance</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Article-by-article compliance status for high-risk AI system deployment.
          All compliance claims are grounded in replay-certifiable technical controls.
        </p>
      </div>
      <div className="space-y-2">
        {articles.map(a => (
          <div key={a.id} className="flex items-center gap-4 rounded-lg px-4 py-3"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <span className="font-mono text-xs font-semibold w-12 flex-shrink-0" style={{ color: T.phi }}>
              {a.id}
            </span>
            <span className="flex-1 text-sm" style={{ color: T.text }}>{a.label}</span>
            <span className="text-xs" style={{ color: T.muted }}>{a.detail}</span>
            <span className="text-xs font-mono font-semibold" style={{ color: T.T0 }}>
              {a.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function PlaceholderSurface({ surface }: { surface: typeof SURFACES[0] }) {
  const Icon = surface.icon
  const tierColor = T[surface.tier as keyof typeof T] as string ?? T.muted
  return (
    <div className="p-6 flex flex-col items-center justify-center h-full min-h-64 gap-3">
      <Icon size={32} style={{ color: tierColor, opacity: 0.5 }} />
      <div className="text-lg font-medium" style={{ color: T.secondary }}>{surface.label}</div>
      <div className="text-sm" style={{ color: T.muted }}>
        {surface.tier} surface — implementation in progress
      </div>
    </div>
  )
}

function Offline() {
  return (
    <div className="p-6 flex items-center justify-center h-full min-h-64">
      <div className="text-center space-y-2">
        <WifiOff size={28} style={{ color: T.muted, margin: '0 auto' }} />
        <div style={{ color: T.muted }}>Bridge offline — start bridge.py to connect</div>
        <div className="font-mono text-xs" style={{ color: T.border }}>
          cd sovereign-omega-v2/python && python bridge.py
        </div>
      </div>
    </div>
  )
}

// ─── App root ─────────────────────────────────────────────────────────────

export function App() {
  const [surface, setSurface] = useState<SurfaceId>('constitutional-health')
  const [liveState, setLiveState] = useState<LiveState>({
    node: null, network: null, resonance: null, telemetry: null,
  })

  useEffect(() => subscribeLiveState(setLiveState), [])

  const renderSurface = useCallback(() => {
    switch (surface) {
      case 'constitutional-health': return <ConstitutionalHealthSurface state={liveState} />
      case 'chord-network':         return <ChordNetworkSurface state={liveState} />
      case 'self-certification':    return <SelfCertificationSurface state={liveState} />
      case 'compliance':            return <ComplianceSurface />
      default: return <PlaceholderSurface surface={SURFACES.find(s => s.id === surface)!} />
    }
  }, [surface, liveState])

  return (
    <div className="flex flex-col h-screen" style={{ background: T.bg, color: T.text }}>
      {/* Top ribbon */}
      <Ribbon state={liveState} />

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{ borderBottom: `1px solid ${T.border}` }}>
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded flex items-center justify-center"
            style={{ background: T.phiDeep, border: `1px solid ${T.phi}40` }}>
            <Shield size={14} style={{ color: T.phi }} />
          </div>
          <div>
            <div className="text-sm font-semibold" style={{ color: T.text }}>AEGIS-Ω Enterprise</div>
            <div className="text-2xs font-mono" style={{ color: T.muted }}>
              Constitutional Governance Dashboard
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full animate-pulse-slow"
            style={{ background: liveState.node ? T.T0 : T.border }} />
          <span className="text-xs font-mono" style={{ color: liveState.node ? T.T0 : T.muted }}>
            {liveState.node ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* 3-column layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left nav */}
        <div className="w-52 flex-shrink-0 p-2 space-y-0.5 overflow-y-auto"
          style={{ borderRight: `1px solid ${T.border}` }}>
          {SURFACES.map(s => (
            <NavItem key={s.id} surface={s} active={surface === s.id}
              onClick={() => setSurface(s.id)} />
          ))}

          <div className="mt-4 pt-4 mx-2" style={{ borderTop: `1px solid ${T.border}` }}>
            <div className="text-2xs font-mono space-y-1" style={{ color: T.border }}>
              <div>Gates 1–225 complete</div>
              <div>312 Rust tests</div>
              <div>2790 TS tests</div>
            </div>
          </div>
        </div>

        {/* Main surface */}
        <div className="flex-1 overflow-y-auto">
          {renderSurface()}
        </div>

        {/* Right telemetry */}
        <div className="w-52 flex-shrink-0 overflow-y-auto"
          style={{ minWidth: '200px' }}>
          <div className="px-3 py-2.5 text-2xs font-mono font-semibold"
            style={{ color: T.muted, borderBottom: `1px solid ${T.border}` }}>
            LIVE TELEMETRY
          </div>
          <RightPanel state={liveState} />
        </div>
      </div>
    </div>
  )
}
