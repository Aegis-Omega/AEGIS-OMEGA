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
  Globe, Gauge,
} from 'lucide-react'
import { subscribeLiveState, type LiveState, type CoherenceData, type PipelineData, type DriftData } from './lib/bridge.js'

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
  | 'coherence-tower'
  | 'audit-trail'
  | 'chord-network'
  | 'agent-registry'
  | 'skill-certification'
  | 'compliance'
  | 'governance-events'
  | 'self-certification'
  | 'pipeline-drift'

const SURFACES: Array<{ id: SurfaceId; label: string; icon: React.ElementType; tier: string }> = [
  { id: 'constitutional-health', label: 'Constitutional Health',  icon: Shield,      tier: 'T0' },
  { id: 'coherence-tower',       label: 'Coherence Tower',       icon: Layers,      tier: 'T1' },
  { id: 'audit-trail',           label: 'Audit Trail',           icon: FileText,    tier: 'T1' },
  { id: 'chord-network',         label: 'Chord Network',         icon: Radio,       tier: 'T2' },
  { id: 'agent-registry',        label: 'Agent Registry',        icon: Users,       tier: 'T2' },
  { id: 'skill-certification',   label: 'Skill Certification',   icon: Activity,    tier: 'T2' },
  { id: 'compliance',            label: 'EU AI Act Compliance',  icon: Globe,       tier: 'T1' },
  { id: 'governance-events',     label: 'Governance Events',     icon: GitBranch,   tier: 'T2' },
  { id: 'self-certification',    label: 'Self-Certification',    icon: Shield,      tier: 'T1' },
  { id: 'pipeline-drift',        label: 'Pipeline & Drift',      icon: Gauge,       tier: 'T2' },
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

// ─── Coherence Tower Surface ─────────────────────────────────────────────

const LEVEL_LABELS = [
  { key: 'l0_ralph_frame',        label: 'L0 — RALPH Frame',       desc: 'sequence_monotone: RALPH loop is valid', weight: 1 },
  { key: 'l1_mutation_authority', label: 'L1 — Mutation Authority', desc: 'No D2+ divergence: authority preserved', weight: 1 },
  { key: 'l2_resonance',          label: 'L2 — Resonance',          desc: 'φ-convergent ∧ ring-valid ∧ seq-monotone', weight: 2 },
  { key: 'l3_chord_unity',        label: 'L3 — Chord Unity',        desc: 'Network UNIFIED ∧ all peers below φ',    weight: 3 },
  { key: 'l4_autopoietic',        label: 'L4 — Autopoietic',        desc: 'Self-certification Certified (closure)',  weight: 5 },
] as const

function CoherenceTowerSurface({ coherence }: { coherence: CoherenceData | null }) {
  if (!coherence) return <Offline />

  const gsColor = coherence.global_section_exists ? T.T0 : T.error
  const scoreBar = coherence.coherence_score

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Coherence Tower</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Gates 227–229 — Moduli tower global section. Does the constitutional state
          simultaneously trivialize all 5 obstruction levels?
        </p>
      </div>

      {/* Global section banner */}
      <div className="rounded-lg p-4 flex items-center gap-4"
        style={{
          background: `${gsColor}08`,
          border: `1px solid ${gsColor}30`,
        }}>
        <div className="text-center px-3">
          {coherence.global_section_exists
            ? <CheckCircle size={28} style={{ color: T.T0 }} />
            : <AlertTriangle size={28} style={{ color: T.error }} />}
        </div>
        <div className="flex-1">
          <div className="font-mono font-bold mb-1" style={{ color: gsColor }}>
            GLOBAL SECTION: {coherence.global_section_exists ? 'EXISTS' : 'DOES NOT EXIST'}
          </div>
          <div className="text-sm" style={{ color: T.muted }}>
            {coherence.satisfied_count}/5 levels satisfied · epoch {coherence.epoch}
            {coherence.first_obstruction != null && (
              <> · First obstruction: L{coherence.first_obstruction}</>
            )}
          </div>
        </div>
        <div className="text-right font-mono">
          <div className="text-2xl font-bold" style={{ color: gsColor }}>
            {(coherence.coherence_score * 100).toFixed(1)}%
          </div>
          <div className="text-2xs" style={{ color: T.muted }}>coherence score</div>
        </div>
      </div>

      {/* Score bar */}
      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span style={{ color: T.muted }}>Fibonacci-weighted coherence</span>
          <span className="font-mono" style={{ color: gsColor }}>
            {scoreBar.toFixed(4)} / 1.0
          </span>
        </div>
        <div className="h-2 rounded-full" style={{ background: T.border }}>
          <div className="h-full rounded-full transition-all"
            style={{
              width: `${scoreBar * 100}%`,
              background: scoreBar === 1.0 ? T.T0 : scoreBar > 0.5 ? T.phi : T.error,
            }} />
        </div>
      </div>

      {/* Level tower */}
      <div className="space-y-2">
        <div className="text-sm font-medium mb-3" style={{ color: T.secondary }}>
          Obstruction Levels (L0→L4, Fibonacci weights 1:1:2:3:5)
        </div>
        {LEVEL_LABELS.map(({ key, label, desc, weight }) => {
          const ok = coherence.levels[key]
          const levelColor = ok ? T.T0 : T.error
          const isFail = !ok && (coherence.first_obstruction === LEVEL_LABELS.indexOf({ key, label, desc, weight } as never))
          return (
            <div key={key}
              className="flex items-center gap-3 rounded-lg px-4 py-3"
              style={{
                background: isFail ? `${T.error}08` : T.surface,
                border: `1px solid ${isFail ? T.error + '30' : T.border}`,
              }}>
              <div className="flex-shrink-0 w-5 h-5 rounded flex items-center justify-center"
                style={{ background: `${levelColor}15` }}>
                {ok
                  ? <CheckCircle size={12} style={{ color: T.T0 }} />
                  : <AlertTriangle size={12} style={{ color: T.error }} />}
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium" style={{ color: ok ? T.text : T.muted }}>
                  {label}
                </div>
                <div className="text-2xs font-mono mt-0.5" style={{ color: T.muted }}>{desc}</div>
              </div>
              <div className="text-right">
                <div className="text-xs font-mono" style={{ color: T.phi }}>w={weight}/12</div>
                <div className="text-2xs font-mono" style={{ color: ok ? T.T0 : T.error }}>
                  {ok ? 'SATISFIED' : 'BLOCKED'}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Frame hex */}
      <div className="rounded-lg p-3 font-mono text-xs" style={{ background: T.card, border: `1px solid ${T.border}` }}>
        <span style={{ color: T.muted }}>frame_hex: </span>
        <span style={{ color: T.T2 }}>{coherence.frame_hex}</span>
        <span style={{ color: T.border }}> · 16-byte CoherenceFrame (Gate 228 encoding)</span>
      </div>
    </div>
  )
}

// ─── Agent Registry Surface ───────────────────────────────────────────────

type AgentStatus = 'active' | 'quarantined' | 'suspended'

interface AgentRecord {
  agent_id: string
  agent_type: string
  epistemic_tier: string
  loop_count: number
  fibonacci_interval: number
  status: AgentStatus
  entropy_ratio: number
  last_loop_hash: string
}

const SEED_AGENTS: AgentRecord[] = [
  { agent_id: 'agt-001', agent_type: 'ResonanceMonitorAgent',      epistemic_tier: 'T1', loop_count: 47,  fibonacci_interval: 89, status: 'active',      entropy_ratio: 0.38, last_loop_hash: 'a3f9b2c1' },
  { agent_id: 'agt-002', agent_type: 'ChordNetworkAgent',          epistemic_tier: 'T2', loop_count: 23,  fibonacci_interval: 55, status: 'active',      entropy_ratio: 0.41, last_loop_hash: 'd7e4f819' },
  { agent_id: 'agt-003', agent_type: 'SelfCertificationAgent',     epistemic_tier: 'T1', loop_count: 89,  fibonacci_interval: 89, status: 'active',      entropy_ratio: 0.29, last_loop_hash: 'f2a1c3e5' },
  { agent_id: 'agt-004', agent_type: 'EntropySuppressionAgent',    epistemic_tier: 'T2', loop_count: 12,  fibonacci_interval: 21, status: 'active',      entropy_ratio: 0.55, last_loop_hash: 'b8d3a7c2' },
  { agent_id: 'agt-005', agent_type: 'ArbitrationAgent',           epistemic_tier: 'T2', loop_count: 6,   fibonacci_interval: 8,  status: 'active',      entropy_ratio: 0.31, last_loop_hash: 'e9c4f012' },
  { agent_id: 'agt-006', agent_type: 'TelemetryAnalysisAgent',     epistemic_tier: 'T2', loop_count: 134, fibonacci_interval: 89, status: 'active',      entropy_ratio: 0.44, last_loop_hash: '7a3d9b1f' },
  { agent_id: 'agt-007', agent_type: 'ConstitutionalGuardianAgent', epistemic_tier: 'T1', loop_count: 3,   fibonacci_interval: 3,  status: 'quarantined', entropy_ratio: 0.68, last_loop_hash: 'c5f8a2b4' },
  { agent_id: 'agt-008', agent_type: 'FederationRelayAgent',       epistemic_tier: 'T2', loop_count: 0,   fibonacci_interval: 1,  status: 'suspended',   entropy_ratio: 0.0,  last_loop_hash: '00000000' },
]

function AgentRegistrySurface() {
  const statusColor = (s: AgentStatus) =>
    s === 'active' ? T.T0 : s === 'quarantined' ? T.warn : T.muted

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Agent Registry</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          RALPH-paced agent swarm · Fibonacci interval scheduling · 1/φ entropy-bounded mutation authority
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Active Agents',     value: SEED_AGENTS.filter(a => a.status === 'active').length,      color: T.T0  },
          { label: 'Quarantined',       value: SEED_AGENTS.filter(a => a.status === 'quarantined').length, color: T.warn },
          { label: 'Suspended',         value: SEED_AGENTS.filter(a => a.status === 'suspended').length,   color: T.muted },
        ].map(m => (
          <div key={m.label} className="rounded-lg p-4 text-center"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="text-2xl font-mono font-bold" style={{ color: m.color }}>{m.value}</div>
            <div className="text-xs mt-1" style={{ color: T.muted }}>{m.label}</div>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ borderBottom: `1px solid ${T.border}` }}>
              {['Agent ID', 'Type', 'Tier', 'Loops', 'Fib-Interval', 'Entropy%', 'Status', 'Last Hash'].map(h => (
                <th key={h} className="text-left px-3 py-2 font-medium" style={{ color: T.muted }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SEED_AGENTS.map(a => (
              <tr key={a.agent_id} style={{ borderBottom: `1px solid ${T.border}20` }}>
                <td className="px-3 py-2.5 font-mono" style={{ color: T.T2 }}>{a.agent_id}</td>
                <td className="px-3 py-2.5" style={{ color: T.text }}>{a.agent_type}</td>
                <td className="px-3 py-2.5 font-mono"
                  style={{ color: a.epistemic_tier === 'T1' ? T.T1 : T.T2 }}>{a.epistemic_tier}</td>
                <td className="px-3 py-2.5 font-mono text-right" style={{ color: T.secondary }}>{a.loop_count}</td>
                <td className="px-3 py-2.5 font-mono text-right" style={{ color: T.phi }}>F={a.fibonacci_interval}</td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <div className="flex-1 h-1 rounded-full" style={{ background: T.border }}>
                      <div className="h-full rounded-full"
                        style={{
                          width: `${a.entropy_ratio * 100}%`,
                          background: a.entropy_ratio > 0.618 ? T.error : a.entropy_ratio > 0.5 ? T.warn : T.T0,
                        }} />
                    </div>
                    <span style={{ color: a.entropy_ratio > 0.618 ? T.error : T.secondary }}>
                      {(a.entropy_ratio * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <span className="text-2xs font-mono px-1.5 py-0.5 rounded"
                    style={{ background: `${statusColor(a.status)}15`, color: statusColor(a.status) }}>
                    {a.status.toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-2.5 font-mono" style={{ color: T.border }}>{a.last_loop_hash}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg p-3 font-mono text-xs" style={{ background: T.card, border: `1px solid ${T.phiDeep}` }}>
        <span style={{ color: T.muted }}>Mutation ceiling: </span>
        <span style={{ color: T.phi }}>MUTATION_RATE_LIMIT = (√5−1)/2 ≈ 0.6180339887</span>
        <span style={{ color: T.border }}> · Entropy ratio above this threshold triggers authority suspension</span>
      </div>
    </div>
  )
}

// ─── Audit Trail Surface ──────────────────────────────────────────────────

interface AuditEntry {
  seq: number
  timestamp: string
  event_type: string
  agent_id: string
  verdict: 'APPROVED' | 'REJECTED' | 'SUSPENDED' | 'CERTIFIED'
  audit_hash: string
  tier: string
}

const AUDIT_LOG: AuditEntry[] = [
  { seq: 2789, timestamp: '05:47:12.341', event_type: 'SELF_CERTIFICATION',   agent_id: 'agt-003', verdict: 'CERTIFIED',  audit_hash: 'a3f9b2c1d8e4', tier: 'T1' },
  { seq: 2788, timestamp: '05:47:07.219', event_type: 'CAPABILITY_EVOLUTION', agent_id: 'agt-004', verdict: 'APPROVED',   audit_hash: 'b7c2f4a1e9d3', tier: 'T2' },
  { seq: 2787, timestamp: '05:47:02.108', event_type: 'TOPOLOGY_TRANSITION',  agent_id: 'agt-001', verdict: 'APPROVED',   audit_hash: 'c1d4a8f2b3e7', tier: 'T1' },
  { seq: 2786, timestamp: '05:46:55.443', event_type: 'QUARANTINE_TRIGGER',   agent_id: 'agt-007', verdict: 'SUSPENDED',  audit_hash: 'd5e9b1f4c2a8', tier: 'T2' },
  { seq: 2785, timestamp: '05:46:49.887', event_type: 'CAPABILITY_EVOLUTION', agent_id: 'agt-004', verdict: 'REJECTED',   audit_hash: 'e2f8c7a3b1d5', tier: 'T2' },
  { seq: 2784, timestamp: '05:46:44.012', event_type: 'CHORD_RESONANCE',      agent_id: 'agt-002', verdict: 'APPROVED',   audit_hash: 'f4a1d9c3b7e2', tier: 'T2' },
  { seq: 2783, timestamp: '05:46:38.774', event_type: 'MARTINGALE_CHECK',     agent_id: 'agt-003', verdict: 'CERTIFIED',  audit_hash: 'a9c3e1f7b4d2', tier: 'T1' },
  { seq: 2782, timestamp: '05:46:33.219', event_type: 'TOPOLOGY_TRANSITION',  agent_id: 'agt-001', verdict: 'APPROVED',   audit_hash: 'b2d8f1c4e9a3', tier: 'T1' },
]

function AuditTrailSurface() {
  const verdictColor = (v: AuditEntry['verdict']) => ({
    APPROVED: T.T0, REJECTED: T.error, SUSPENDED: T.warn, CERTIFIED: T.T1,
  })[v]

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Audit Trail</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          EU AI Act Article 12 · SHA-256 hash-chained event log · All decisions replay-certifiable
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total Events', value: '2789', color: T.secondary },
          { label: 'Approved',     value: AUDIT_LOG.filter(e => e.verdict === 'APPROVED').length.toString(),   color: T.T0   },
          { label: 'Rejected',     value: AUDIT_LOG.filter(e => e.verdict === 'REJECTED').length.toString(),   color: T.error },
          { label: 'Certified',    value: AUDIT_LOG.filter(e => e.verdict === 'CERTIFIED').length.toString(),  color: T.T1   },
        ].map(m => (
          <div key={m.label} className="rounded-lg p-3 text-center"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="text-xl font-mono font-bold" style={{ color: m.color }}>{m.value}</div>
            <div className="text-2xs mt-0.5" style={{ color: T.muted }}>{m.label}</div>
          </div>
        ))}
      </div>

      <div className="space-y-1">
        <div className="grid gap-1 text-2xs font-mono px-3 mb-1"
          style={{
            gridTemplateColumns: '3rem 7rem 1fr 4rem 5rem 6rem',
            color: T.muted,
          }}>
          <span>SEQ</span><span>TIME</span><span>EVENT TYPE</span>
          <span>TIER</span><span>AGENT</span><span>HASH</span>
        </div>
        {AUDIT_LOG.map(e => (
          <div key={e.seq}
            className="grid gap-1 text-xs rounded px-3 py-2 items-center"
            style={{
              gridTemplateColumns: '3rem 7rem 1fr 4rem 5rem 6rem',
              background: T.surface, border: `1px solid ${T.border}`,
            }}>
            <span className="font-mono" style={{ color: T.muted }}>{e.seq}</span>
            <span className="font-mono text-2xs" style={{ color: T.secondary }}>{e.timestamp}</span>
            <div className="flex items-center gap-2">
              <span style={{ color: T.text }}>{e.event_type}</span>
              <span className="text-2xs font-mono px-1 rounded"
                style={{ background: `${verdictColor(e.verdict)}15`, color: verdictColor(e.verdict) }}>
                {e.verdict}
              </span>
            </div>
            <span className="font-mono text-2xs" style={{
              color: e.tier === 'T1' ? T.T1 : T.T2
            }}>{e.tier}</span>
            <span className="font-mono text-2xs" style={{ color: T.muted }}>{e.agent_id}</span>
            <span className="font-mono text-2xs" style={{ color: T.border }}>{e.audit_hash}</span>
          </div>
        ))}
      </div>

      <div className="text-xs font-mono px-3" style={{ color: T.border }}>
        ↑ Showing latest 8 of 2789 entries · Hash-chained · SHA-256 · is_replay_reconstructable: true
      </div>
    </div>
  )
}

// ─── Governance Events Surface ────────────────────────────────────────────

interface GovEvent {
  id: string; kind: string; source: string; sequence: number
  payload_preview: string; epoch: number; tier: string
}

const GOV_EVENTS: GovEvent[] = [
  { id: 'ev-2789', kind: 'TOPOLOGY_TRANSITION',  source: 'replay-engine',   sequence: 2789, payload_preview: 'topology_hash=a3f9…→b7c2…', epoch: 47, tier: 'T1' },
  { id: 'ev-2788', kind: 'CAPABILITY_EVOLUTION', source: 'capsule-vm',      sequence: 2788, payload_preview: 'EMIT_EVENT cap APPROVED on agt-004', epoch: 47, tier: 'T2' },
  { id: 'ev-2787', kind: 'SWARM_CONVERGENCE',    source: 'consensus-swarm', sequence: 2787, payload_preview: 'quorum_hash=d5e9… peer_count=5', epoch: 47, tier: 'T2' },
  { id: 'ev-2786', kind: 'MARTINGALE_SUSPEND',   source: 'martingale',      sequence: 2786, payload_preview: 'entropy_bounded=false adaptive_ratio=0.682', epoch: 47, tier: 'T1' },
  { id: 'ev-2785', kind: 'SKILL_VALIDATED',      source: 'skill-harness',   sequence: 2785, payload_preview: 'skill_id=resonance_synthesis confidence=0.91', epoch: 47, tier: 'T2' },
  { id: 'ev-2784', kind: 'CHORD_RESONANCE',      source: 'chord-network',   sequence: 2784, payload_preview: 'verdict=UNIFIED quorum_triadic=true', epoch: 47, tier: 'T2' },
]

const KIND_COLORS: Record<string, string> = {
  TOPOLOGY_TRANSITION: T.T1,
  CAPABILITY_EVOLUTION: T.T2,
  SWARM_CONVERGENCE: T.phi,
  MARTINGALE_SUSPEND: T.error,
  SKILL_VALIDATED: T.T0,
  CHORD_RESONANCE: T.phi,
}

function GovernanceEventsSurface() {
  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Governance Events</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Live EventEnvelope stream · Law of Silence: all agent communication is mediated · Append-only
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Current Epoch', value: 47, color: T.phi },
          { label: 'Sequence',      value: 2789, color: T.T1 },
          { label: 'Active Agents', value: 6, color: T.T0 },
        ].map(m => (
          <div key={m.label} className="rounded-lg p-4 text-center"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="text-2xl font-mono font-bold" style={{ color: m.color }}>{m.value}</div>
            <div className="text-xs mt-1" style={{ color: T.muted }}>{m.label}</div>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        {GOV_EVENTS.map(e => {
          const kindColor = KIND_COLORS[e.kind] ?? T.secondary
          return (
            <div key={e.id} className="rounded-lg px-4 py-3"
              style={{ background: T.surface, border: `1px solid ${T.border}` }}>
              <div className="flex items-center gap-3 mb-1.5">
                <span className="text-xs font-mono font-semibold" style={{ color: kindColor }}>
                  {e.kind}
                </span>
                <span className="text-2xs font-mono" style={{ color: T.border }}>seq:{e.sequence}</span>
                <span className="text-2xs font-mono" style={{ color: T.border }}>epoch:{e.epoch}</span>
                <span className="flex-1" />
                <span className="text-2xs font-mono" style={{ color: T.muted }}>←{e.source}</span>
                <span className="text-2xs font-mono px-1 rounded"
                  style={{ background: `${e.tier === 'T1' ? T.T1 : T.T2}15`,
                           color: e.tier === 'T1' ? T.T1 : T.T2 }}>{e.tier}</span>
              </div>
              <div className="text-xs font-mono" style={{ color: T.muted }}>{e.payload_preview}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Skill Certification Surface ──────────────────────────────────────────

interface SkillRecord {
  skill_id: string; name: string; confidence: number; validated_runs: number
  failure_rate: number; epistemic_tier: string; domain: string; status: 'certified' | 'provisional' | 'uncertified'
}

const SKILLS: SkillRecord[] = [
  { skill_id: 'resonance_synthesis',   name: 'Resonance Synthesis',     confidence: 0.91, validated_runs: 134, failure_rate: 0.02, epistemic_tier: 'T1', domain: 'constitutional', status: 'certified'    },
  { skill_id: 'chord_classification',  name: 'Chord Classification',    confidence: 0.87, validated_runs: 89,  failure_rate: 0.04, epistemic_tier: 'T2', domain: 'network',        status: 'certified'    },
  { skill_id: 'entropy_suppression',   name: 'Entropy Suppression',     confidence: 0.79, validated_runs: 47,  failure_rate: 0.07, epistemic_tier: 'T2', domain: 'governance',     status: 'provisional'  },
  { skill_id: 'martingale_audit',      name: 'Martingale Audit',        confidence: 0.95, validated_runs: 213, failure_rate: 0.01, epistemic_tier: 'T1', domain: 'constitutional', status: 'certified'    },
  { skill_id: 'federation_relay',      name: 'Federation Relay',        confidence: 0.42, validated_runs: 8,   failure_rate: 0.25, epistemic_tier: 'T2', domain: 'network',        status: 'uncertified'  },
  { skill_id: 'eu_compliance_check',   name: 'EU Compliance Check',     confidence: 0.98, validated_runs: 312, failure_rate: 0.00, epistemic_tier: 'T1', domain: 'compliance',     status: 'certified'    },
]

function SkillCertificationSurface() {
  const statusColor = (s: SkillRecord['status']) =>
    s === 'certified' ? T.T0 : s === 'provisional' ? T.warn : T.error

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Skill Certification</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Skill Harness Phase 1 · Probabilistic competency objects · Event-sourced confidence scoring
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Certified',    value: SKILLS.filter(s => s.status === 'certified').length,    color: T.T0   },
          { label: 'Provisional',  value: SKILLS.filter(s => s.status === 'provisional').length,  color: T.warn },
          { label: 'Uncertified',  value: SKILLS.filter(s => s.status === 'uncertified').length,  color: T.error },
        ].map(m => (
          <div key={m.label} className="rounded-lg p-4 text-center"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="text-2xl font-mono font-bold" style={{ color: m.color }}>{m.value}</div>
            <div className="text-xs mt-1" style={{ color: T.muted }}>{m.label}</div>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        {SKILLS.map(s => (
          <div key={s.skill_id} className="rounded-lg px-4 py-3"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-medium text-sm flex-1" style={{ color: T.text }}>{s.name}</span>
              <span className="text-2xs font-mono px-1 rounded"
                style={{ background: `${s.epistemic_tier === 'T1' ? T.T1 : T.T2}15`,
                         color: s.epistemic_tier === 'T1' ? T.T1 : T.T2 }}>{s.epistemic_tier}</span>
              <span className="text-2xs font-mono" style={{ color: T.muted }}>{s.domain}</span>
              <span className="text-xs font-mono font-semibold px-1.5 py-0.5 rounded"
                style={{ background: `${statusColor(s.status)}10`, color: statusColor(s.status) }}>
                {s.status.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <div className="flex justify-between text-2xs mb-0.5">
                  <span style={{ color: T.muted }}>confidence</span>
                  <span style={{ color: T.secondary }}>{(s.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1 rounded-full" style={{ background: T.border }}>
                  <div className="h-full rounded-full transition-all"
                    style={{
                      width: `${s.confidence * 100}%`,
                      background: s.confidence >= 0.8 ? T.T0 : s.confidence >= 0.6 ? T.warn : T.error,
                    }} />
                </div>
              </div>
              <div className="text-2xs font-mono text-right" style={{ color: T.muted }}>
                <div>{s.validated_runs} runs</div>
                <div style={{ color: s.failure_rate > 0.1 ? T.error : T.muted }}>
                  {(s.failure_rate * 100).toFixed(0)}% fail
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Pipeline & Drift Surface ─────────────────────────────────────────────

const DRIFT_COLORS: Record<string, string> = {
  D0: '#34D399', D1: '#60A5FA', D2: '#C8A96E', D3: '#F59E0B', D4: '#F87171',
}

function PipelineDriftSurface({
  pipeline, drift,
}: { pipeline: PipelineData | null; drift: DriftData | null }) {
  if (!pipeline && !drift) return <Offline />
  const dClass = drift?.current_drift_class ?? pipeline?.drift_class ?? 'D0'
  const dColor = DRIFT_COLORS[dClass] ?? '#A1A1AA'
  const mutOk = pipeline?.mutation_authority_active ?? drift?.mutation_authority_active ?? true
  const entropyPct = pipeline ? pipeline.entropy_balance / 10000 : 1
  const driftRisk = pipeline?.drift_risk ?? drift?.drift_risk ?? 0

  return (
    <div className="p-6 space-y-5">
      <div>
        <h2 className="text-lg font-semibold mb-1" style={{ color: T.text }}>Pipeline & Drift</h2>
        <p className="text-sm" style={{ color: T.muted }}>
          Gates 235–236 — GovernancePipeline field-scale status · DriftHistory D0–D4 · Entropy budget ledger
        </p>
      </div>

      {/* Mutation authority banner */}
      <div className="rounded-lg p-4 flex items-center gap-4"
        style={{
          background: mutOk ? 'rgba(52,211,153,0.06)' : 'rgba(248,113,113,0.06)',
          border: `1px solid ${mutOk ? 'rgba(52,211,153,0.25)' : 'rgba(248,113,113,0.25)'}`,
        }}>
        {mutOk
          ? <CheckCircle size={28} style={{ color: T.T0 }} />
          : <AlertTriangle size={28} style={{ color: T.error }} />}
        <div>
          <div className="font-semibold mb-0.5" style={{ color: mutOk ? T.T0 : T.error }}>
            MUTATION AUTHORITY: {mutOk ? 'ACTIVE' : 'SUSPENDED'}
          </div>
          <div className="text-sm" style={{ color: T.muted }}>
            {mutOk
              ? `Drift ${dClass} < D2 · Entropy sufficient · Adaptive events permitted`
              : `Drift ${dClass} ≥ D2 or entropy exhausted · Adaptive events BLOCKED`}
          </div>
        </div>
        <div className="ml-auto font-mono text-2xl font-bold" style={{ color: dColor }}>{dClass}</div>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Drift Class',   value: dClass,                                          color: dColor },
          { label: 'Entropy',       value: pipeline ? pipeline.entropy_balance : '—',        color: entropyPct > 0.5 ? T.T0 : T.warn },
          { label: 'Cycle Count',   value: pipeline?.cycle_count ?? '—',                    color: T.secondary },
          { label: 'Drift Risk',    value: `${(driftRisk * 100).toFixed(2)}%`,              color: driftRisk < 0.618 ? T.T0 : T.error },
        ].map(m => (
          <div key={m.label} className="rounded-lg p-3 text-center"
            style={{ background: T.surface, border: `1px solid ${T.border}` }}>
            <div className="text-xl font-mono font-semibold" style={{ color: m.color }}>{String(m.value)}</div>
            <div className="text-2xs mt-0.5" style={{ color: T.muted }}>{m.label}</div>
          </div>
        ))}
      </div>

      {/* Entropy bar */}
      {pipeline && (
        <div>
          <div className="flex justify-between text-xs mb-1.5">
            <span style={{ color: T.muted }}>Entropy budget (ADAPTIVE_COST=10 · REPLAY_GAIN=7)</span>
            <span className="font-mono" style={{ color: entropyPct > 0.5 ? T.T0 : T.warn }}>
              {pipeline.entropy_balance} / 10000
            </span>
          </div>
          <div className="h-2 rounded-full" style={{ background: T.border }}>
            <div className="h-full rounded-full transition-all"
              style={{
                width: `${entropyPct * 100}%`,
                background: entropyPct > 0.5 ? T.T0 : entropyPct > 0.2 ? T.warn : T.error,
              }} />
          </div>
          <div className="flex justify-between text-2xs mt-1 font-mono">
            <span style={{ color: T.muted }}>before: {pipeline.entropy_balance_before}</span>
            <span style={{ color: pipeline.replay_replenished ? T.T0 : T.muted }}>
              replay_replenished: {pipeline.replay_replenished ? 'YES' : 'NO'}
            </span>
            <span style={{ color: T.muted }}>after: {pipeline.entropy_balance_after}</span>
          </div>
        </div>
      )}

      {/* D0–D4 drift class table */}
      <div>
        <div className="text-sm font-medium mb-3" style={{ color: T.secondary }}>
          Drift Severity Classification (D0→D4)
        </div>
        <div className="space-y-1.5">
          {(['D0', 'D1', 'D2', 'D3', 'D4'] as const).map(dc => {
            const isActive = dClass === dc
            const dcColor = DRIFT_COLORS[dc]
            const desc = dc === 'D0' ? 'Observational — coefficient changed, invariants intact'
              : dc === 'D1' ? 'Serializer drift — phi_headroom sign changed'
              : dc === 'D2' ? 'Topology mismatch — ring_valid or seq_monotone flipped (authority BLOCKED)'
              : dc === 'D3' ? 'Ownership inconsistency — vortex_family changed'
              : 'Constitutional invalidity — phi_convergent=false OR depth=0'
            return (
              <div key={dc}
                className="flex items-center gap-3 rounded-lg px-4 py-2.5"
                style={{
                  background: isActive ? `${dcColor}12` : T.surface,
                  border: `1px solid ${isActive ? dcColor + '40' : T.border}`,
                }}>
                <span className="font-mono font-bold w-6 text-center" style={{ color: dcColor }}>{dc}</span>
                <span className="flex-1 text-sm" style={{ color: isActive ? T.text : T.muted }}>{desc}</span>
                {isActive && (
                  <span className="text-2xs font-mono px-1.5 py-0.5 rounded"
                    style={{ background: `${dcColor}20`, color: dcColor }}>CURRENT</span>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Drift history summary */}
      {drift && (
        <div className="rounded-lg p-4 font-mono text-xs space-y-2"
          style={{ background: T.card, border: `1px solid ${T.border}` }}>
          <div className="text-sm font-semibold mb-2" style={{ color: T.secondary }}>
            DriftHistory — Gate 235
          </div>
          {[
            ['worst_class', drift.worst_drift_class, DRIFT_COLORS[drift.worst_drift_class]],
            ['authority_suspended_count', drift.authority_suspended_count, drift.authority_suspended_count > 0 ? T.warn : T.T0],
            ['coefficient_delta', drift.coefficient_delta.toFixed(6), drift.coefficient_delta > 0 ? T.error : T.T0],
            ['current_record_hash', drift.current_record_hash + '…', T.border],
          ].map(([label, val, color]) => (
            <div key={String(label)} className="flex gap-2">
              <span style={{ color: T.muted }}>{String(label)}:</span>
              <span style={{ color: String(color) }}>{String(val)}</span>
            </div>
          ))}
        </div>
      )}
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
    node: null, network: null, resonance: null, telemetry: null, coherence: null,
    pipeline: null, drift: null,
  })

  useEffect(() => subscribeLiveState(setLiveState), [])

  const renderSurface = useCallback(() => {
    switch (surface) {
      case 'constitutional-health': return <ConstitutionalHealthSurface state={liveState} />
      case 'coherence-tower':       return <CoherenceTowerSurface coherence={liveState.coherence} />
      case 'chord-network':         return <ChordNetworkSurface state={liveState} />
      case 'self-certification':    return <SelfCertificationSurface state={liveState} />
      case 'compliance':            return <ComplianceSurface />
      case 'agent-registry':        return <AgentRegistrySurface />
      case 'audit-trail':           return <AuditTrailSurface />
      case 'governance-events':     return <GovernanceEventsSurface />
      case 'skill-certification':   return <SkillCertificationSurface />
      case 'pipeline-drift':        return <PipelineDriftSurface pipeline={liveState.pipeline} drift={liveState.drift} />
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
              <div>Gates 1–236 complete</div>
              <div>475 Rust tests</div>
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
