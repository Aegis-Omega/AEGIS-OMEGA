import { useMemo, useState, type ReactNode } from 'react'
import type { TelemetrySnapshot } from '../types.js'

interface Props {
  snapshot: TelemetrySnapshot | null
}

type NodeStatus = 'input' | 'review' | 'unknown' | 'blocked'

interface HolonNode {
  id: string
  label: string
  ring: 'core' | 'inner' | 'outer'
  status: NodeStatus
  description: string
}

interface Point {
  x: number
  y: number
}

const CENTER: Point = { x: 300, y: 250 }
const STATUS_COLOR: Record<NodeStatus, string> = {
  input: '#60A5FA',
  review: '#C8A96E',
  unknown: '#52525B',
  blocked: '#F87171',
}

const INNER_ROLES = [
  ['I1', 'Interpreter', 'Maps the unverified input into display primitives.'],
  ['I2', 'Assessor', 'Displays local assessment without promoting evidence.'],
  ['I3', 'Lease guard', 'Lease verification is not connected to this surface.'],
  ['I4', 'Executor', 'Studio cannot execute or mutate canonical state.'],
  ['I5', 'Verifier', 'Receipt verification is not connected to this surface.'],
  ['I6', 'Committer', 'Studio cannot commit or mutate canonical state.'],
] as const

const OUTER_ROLES = [
  ['O1', 'Actor witness', 'Actor identity binding is unavailable.'],
  ['O2', 'Session witness', 'Session identity binding is unavailable.'],
  ['O3', 'Workspace witness', 'Workspace identity binding is unavailable.'],
  ['O4', 'Holon witness', 'Holon identity binding is unavailable.'],
  ['O5', 'Authority witness', 'Authority receipt evidence is unavailable.'],
  ['O6', 'Lease witness', 'Lease evidence is unavailable.'],
  ['O7', 'Fence witness', 'Fencing-token evidence is unavailable.'],
  ['O8', 'Expected-state witness', 'Expected state root is unavailable.'],
  ['O9', 'Observed-state witness', 'Observed state root is unavailable.'],
  ['O10', 'Action witness', 'Action digest is unavailable.'],
  ['O11', 'Result witness', 'Result digest is unavailable.'],
  ['O12', 'Trust-chain witness', 'Receipt and trust-chain resolution is unavailable.'],
] as const

function polarPoint(radius: number, index: number, total: number): Point {
  const angle = -Math.PI / 2 + (index / total) * Math.PI * 2
  return {
    x: CENTER.x + Math.cos(angle) * radius,
    y: CENTER.y + Math.sin(angle) * radius,
  }
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function formatNumber(value: unknown, digits = 4): string {
  return isFiniteNumber(value) ? value.toFixed(digits) : 'unavailable'
}

function formatInteger(value: unknown): string {
  return isFiniteNumber(value) ? Math.trunc(value).toLocaleString() : 'unavailable'
}

function Panel({
  number,
  title,
  subtitle,
  className = '',
  children,
}: {
  number: string
  title: string
  subtitle: string
  className?: string
  children: ReactNode
}) {
  return (
    <section
      className={`relative overflow-hidden rounded-2xl border border-aegis-border bg-aegis-deep/95 ${className}`}
    >
      <div className="flex items-start gap-3 border-b border-aegis-border/70 px-4 py-3">
        <span className="font-mono text-[10px] tracking-[0.18em] text-aegis-phi">{number}</span>
        <div>
          <h2 className="m-0 text-sm font-semibold tracking-wide text-aegis-text">{title}</h2>
          <p className="mt-1 text-[10px] leading-relaxed text-aegis-muted">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  )
}

function BoundaryBanner({ hasInput }: { hasInput: boolean }) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-aegis-T3/30 bg-aegis-T3/10 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-aegis-T3">
          Projection-only boundary
        </div>
        <p className="mt-1 text-xs text-aegis-text">
          Visual compilation is a read-only display. It cannot verify receipts, grant authority,
          mutate state, adjust runtime routes, or promote evidence.
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2 font-mono text-[9px] uppercase tracking-wider">
        <span className="rounded-full border border-aegis-T3/30 bg-aegis-bg px-2.5 py-1 text-aegis-T3">
          {hasInput ? 'unverified bridge input' : 'demo / no bridge input'}
        </span>
        <span className="rounded-full border border-aegis-T4/30 bg-aegis-bg px-2.5 py-1 text-aegis-T4">
          no authority
        </span>
        <span className="rounded-full border border-aegis-border-medium bg-aegis-bg px-2.5 py-1 text-aegis-muted">
          no receipt resolver
        </span>
      </div>
    </div>
  )
}

function TransitionEnvelope({ snapshot }: Props) {
  return (
    <Panel
      number="01"
      title="Current transition envelope"
      subtitle="What the display received, with unresolved provenance left explicit."
      className="min-h-[300px]"
    >
      <div className="grid grid-cols-[auto,1fr] gap-x-5 gap-y-3 p-4 font-mono text-[11px]">
        <span className="text-aegis-muted">formula_id</span>
        <span className="text-aegis-T3">UNRESOLVED</span>
        <span className="text-aegis-muted">transition_id</span>
        <span className="text-aegis-T3">UNRESOLVED</span>
        <span className="text-aegis-muted">trace_id</span>
        <span className="text-aegis-T3">UNRESOLVED</span>
        <span className="text-aegis-muted">input_source</span>
        <span className={snapshot ? 'text-aegis-T1' : 'text-aegis-disabled'}>
          {snapshot ? 'GET /telemetry · unverified' : 'none · demo boundary'}
        </span>
        <span className="text-aegis-muted">reported_epoch</span>
        <span className="text-aegis-text">{formatInteger(snapshot?.epoch_sequence)}</span>
        <span className="text-aegis-muted">state_roots</span>
        <span className="text-aegis-T4">unavailable</span>
      </div>
      <div className="mx-4 mb-4 rounded-xl border border-aegis-border bg-aegis-bg/70 p-3">
        <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-aegis-muted">
          Compilation status
        </p>
        <p className="mt-1 text-xs leading-relaxed text-aegis-secondary">
          Telemetry can populate visual pressure, but no formula event, identity binding, or signed
          transition envelope is available to authenticate it.
        </p>
      </div>
    </Panel>
  )
}

function buildNodes(hasInput: boolean): HolonNode[] {
  const inputStatus: NodeStatus = hasInput ? 'input' : 'unknown'
  const innerStatuses: readonly NodeStatus[] = [
    inputStatus, 'blocked', 'blocked', 'blocked', 'unknown', inputStatus,
  ]
  const outerStatuses: readonly NodeStatus[] = [
    inputStatus, 'unknown', 'unknown', 'blocked', 'blocked', 'unknown',
    'review', 'unknown', 'blocked', 'review', 'blocked', 'blocked',
  ]

  return [
    {
      id: 'C0',
      label: 'Envelope',
      ring: 'core',
      status: inputStatus,
      description: hasInput
        ? 'Contains unverified bridge telemetry for display only.'
        : 'No live input is present; the surface is in demo mode.',
    },
    ...INNER_ROLES.map(([id, label, description], index) => ({
      id,
      label,
      description,
      ring: 'inner' as const,
      status: innerStatuses[index] ?? 'unknown',
    })),
    ...OUTER_ROLES.map(([id, label, description], index) => ({
      id,
      label,
      description,
      ring: 'outer' as const,
      status: outerStatuses[index] ?? 'unknown',
    })),
  ]
}

function Holonogram({ snapshot }: Props) {
  const nodes = useMemo(() => buildNodes(snapshot !== null), [snapshot])
  const [selectedId, setSelectedId] = useState('C0')
  const selected = nodes.find((node) => node.id === selectedId) ?? nodes[0]!
  const inner = nodes.filter((node) => node.ring === 'inner')
  const outer = nodes.filter((node) => node.ring === 'outer')
  const points = new Map<string, Point>([
    ['C0', CENTER],
    ...inner.map((node, index) => [node.id, polarPoint(104, index, inner.length)] as const),
    ...outer.map((node, index) => [node.id, polarPoint(196, index, outer.length)] as const),
  ])

  return (
    <Panel
      number="02"
      title="19-node Holonñgram"
      subtitle="C0 envelope · six interpretive roles · twelve independent display witnesses."
      className="lg:row-span-2"
    >
      <div className="relative p-3">
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-70"
          style={{
            background:
              'radial-gradient(circle at 50% 46%, rgba(96,165,250,0.09), transparent 28%), radial-gradient(circle at 50% 46%, transparent 37%, rgba(200,169,110,0.05) 38%, transparent 39%)',
          }}
        />
        <svg
          viewBox="0 0 600 500"
          className="relative z-10 mx-auto block h-auto w-full max-w-[680px]"
          aria-label="Holonñgram projection lattice"
          role="img"
        >
          <circle cx={CENTER.x} cy={CENTER.y} r="104" fill="none" stroke="#27272D" strokeWidth="1" />
          <circle cx={CENTER.x} cy={CENTER.y} r="196" fill="none" stroke="#27272D" strokeWidth="1" />
          <circle cx={CENTER.x} cy={CENTER.y} r="226" fill="none" stroke="#17171A" strokeDasharray="3 8" />

          {inner.map((node) => {
            const point = points.get(node.id)!
            return (
              <line
                key={`core-${node.id}`}
                x1={CENTER.x}
                y1={CENTER.y}
                x2={point.x}
                y2={point.y}
                stroke={STATUS_COLOR[node.status]}
                strokeOpacity="0.24"
                strokeWidth="1.2"
              />
            )
          })}
          {outer.map((node, index) => {
            const point = points.get(node.id)!
            const parent = points.get(inner[index % inner.length]!.id)!
            return (
              <line
                key={`witness-${node.id}`}
                x1={parent.x}
                y1={parent.y}
                x2={point.x}
                y2={point.y}
                stroke={STATUS_COLOR[node.status]}
                strokeOpacity="0.18"
                strokeWidth="1"
              />
            )
          })}

          {nodes.map((node) => {
            const point = points.get(node.id)!
            const radius = node.ring === 'core' ? 35 : node.ring === 'inner' ? 23 : 17
            const selectedNode = node.id === selected.id
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-label={`${node.id} ${node.label}: ${node.description}`}
                onClick={() => setSelectedId(node.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') setSelectedId(node.id)
                }}
                className="cursor-pointer outline-none"
              >
                <title>{`${node.id} · ${node.label} · ${node.description}`}</title>
                {selectedNode && (
                  <circle
                    cx={point.x}
                    cy={point.y}
                    r={radius + 8}
                    fill="none"
                    stroke={STATUS_COLOR[node.status]}
                    strokeOpacity="0.45"
                    strokeWidth="1"
                  />
                )}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={radius}
                  fill="#0C0C0E"
                  stroke={STATUS_COLOR[node.status]}
                  strokeWidth={node.ring === 'core' ? 2.4 : 1.5}
                />
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={node.ring === 'core' ? 15 : 4}
                  fill={STATUS_COLOR[node.status]}
                  fillOpacity={node.status === 'unknown' ? 0.32 : 0.82}
                />
                <text
                  x={point.x}
                  y={point.y + (node.ring === 'core' ? 5 : 3)}
                  textAnchor="middle"
                  fill={node.ring === 'core' ? '#0A0A0C' : '#ECEAE3'}
                  fontSize={node.ring === 'outer' ? 8 : 10}
                  fontFamily="ui-monospace, monospace"
                  fontWeight="700"
                >
                  {node.id}
                </text>
              </g>
            )
          })}
        </svg>

        <div className="relative z-10 mx-2 -mt-2 rounded-xl border border-aegis-border bg-aegis-bg/85 p-3">
          <div className="flex items-center gap-2">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: STATUS_COLOR[selected.status] }}
            />
            <span className="font-mono text-[11px] text-aegis-text">
              {selected.id} · {selected.label}
            </span>
            <span className="ml-auto font-mono text-[9px] uppercase tracking-wider text-aegis-muted">
              {selected.status}
            </span>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-aegis-secondary">{selected.description}</p>
        </div>

        <div className="relative z-10 mt-3 flex flex-wrap justify-center gap-3 font-mono text-[9px] uppercase tracking-wider text-aegis-muted">
          {(Object.keys(STATUS_COLOR) as NodeStatus[]).map((status) => (
            <span key={status} className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATUS_COLOR[status] }} />
              {status}
            </span>
          ))}
        </div>
      </div>
    </Panel>
  )
}

function ExpectedActual({ snapshot }: Props) {
  const rows = [
    {
      label: 'PGCS report',
      expected: 'true',
      actual: snapshot ? String(snapshot.pgcs_passes) : 'unavailable',
      match: snapshot?.pgcs_passes === true,
    },
    {
      label: 'Corruption report',
      expected: '0',
      actual: snapshot ? formatInteger(snapshot.corruption_count) : 'unavailable',
      match: snapshot?.corruption_count === 0,
    },
    {
      label: 'Drift display guardrail',
      expected: '< 0.2000',
      actual: formatNumber(snapshot?.drift_index),
      match: isFiniteNumber(snapshot?.drift_index) && snapshot.drift_index < 0.2,
    },
    {
      label: 'VCG display guardrail',
      expected: '< 1.0000',
      actual: formatNumber(snapshot?.vcg_error),
      match: isFiniteNumber(snapshot?.vcg_error) && snapshot.vcg_error < 1,
    },
  ]

  return (
    <Panel
      number="03"
      title="Expected vs actual"
      subtitle="Local display comparisons only; these are not verified state-root deltas."
    >
      <div className="divide-y divide-aegis-border/60">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[1fr,auto,auto] items-center gap-4 px-4 py-3 text-[10px]">
            <span className="text-aegis-secondary">{row.label}</span>
            <span className="font-mono text-aegis-muted">{row.expected}</span>
            <span className={`font-mono ${snapshot ? (row.match ? 'text-aegis-T1' : 'text-aegis-T3') : 'text-aegis-disabled'}`}>
              {row.actual}
            </span>
          </div>
        ))}
      </div>
      <div className="border-t border-aegis-border bg-aegis-T3/5 px-4 py-2 font-mono text-[9px] text-aegis-T3">
        changed_fields and canonical root delta: UNAVAILABLE
      </div>
    </Panel>
  )
}

function FeedbackSignal({ snapshot }: Props) {
  const displayReview = snapshot === null ||
    snapshot.pgcs_passes !== true ||
    snapshot.corruption_count !== 0 ||
    !isFiniteNumber(snapshot.drift_index) ||
    snapshot.drift_index >= 0.2

  return (
    <Panel
      number="04"
      title="Feedback signal"
      subtitle="A visual attention cue, never a runtime instruction."
    >
      <div className="p-4">
        <div className={`rounded-xl border p-4 ${displayReview ? 'border-aegis-T3/30 bg-aegis-T3/10' : 'border-aegis-T1/30 bg-aegis-T1/10'}`}>
          <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-aegis-muted">
            display signal
          </div>
          <div className={`mt-2 text-xl font-semibold ${displayReview ? 'text-aegis-T3' : 'text-aegis-T1'}`}>
            {displayReview ? 'Review input' : 'Observe'}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-aegis-secondary">
            {snapshot
              ? 'Derived from unverified telemetry and local display guardrails.'
              : 'No bridge input is present; no feedback can be compiled.'}
          </p>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[9px]">
          <div className="rounded-lg border border-aegis-border bg-aegis-bg p-2.5">
            <span className="block text-aegis-muted">resonance_score</span>
            <span className="mt-1 block text-aegis-T4">not computed</span>
          </div>
          <div className="rounded-lg border border-aegis-border bg-aegis-bg p-2.5">
            <span className="block text-aegis-muted">value_delta</span>
            <span className="mt-1 block text-aegis-T4">not computed</span>
          </div>
        </div>
      </div>
    </Panel>
  )
}

function MiddlewareEdge() {
  return (
    <Panel
      number="05"
      title="Middleware graph edge"
      subtitle="Proposed visual routing with all runtime deltas disabled."
    >
      <div className="p-4">
        <div className="flex items-center gap-3">
          <div className="flex-1 rounded-xl border border-aegis-border bg-aegis-bg p-3 text-center">
            <div className="font-mono text-[9px] text-aegis-muted">I5</div>
            <div className="mt-1 text-xs text-aegis-secondary">Verifier</div>
          </div>
          <div className="flex min-w-20 flex-col items-center">
            <div className="font-mono text-[8px] uppercase tracking-wider text-aegis-T3">display only</div>
            <div className="my-1 h-px w-full bg-gradient-to-r from-aegis-T3/20 via-aegis-T3 to-aegis-T3/20" />
            <div className="font-mono text-[8px] text-aegis-muted">no write</div>
          </div>
          <div className="flex-1 rounded-xl border border-aegis-border bg-aegis-bg p-3 text-center">
            <div className="font-mono text-[9px] text-aegis-muted">I6</div>
            <div className="mt-1 text-xs text-aegis-secondary">Committer</div>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[9px]">
          <div className="rounded-lg border border-aegis-border px-3 py-2 text-aegis-muted">
            trust_delta <span className="float-right text-aegis-T4">not applied</span>
          </div>
          <div className="rounded-lg border border-aegis-border px-3 py-2 text-aegis-muted">
            risk_delta <span className="float-right text-aegis-T4">not applied</span>
          </div>
        </div>
      </div>
    </Panel>
  )
}

function ReceiptChain() {
  const rows = [
    ['Trust registry', 'not connected'],
    ['Parent receipt', 'unresolved'],
    ['Terminal receipt', 'unresolved'],
    ['Promotion state', 'prohibited'],
  ] as const

  return (
    <Panel
      number="06"
      title="Receipt chain"
      subtitle="The visual layer refuses to manufacture provenance from telemetry."
    >
      <div className="p-4">
        <div className="flex items-center gap-2 pb-4">
          {rows.map(([label], index) => (
            <div key={label} className="flex min-w-0 flex-1 items-center gap-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-aegis-T4/40 bg-aegis-T4/10 font-mono text-[9px] text-aegis-T4">
                {index + 1}
              </div>
              {index < rows.length - 1 && <div className="h-px min-w-2 flex-1 bg-aegis-border-medium" />}
            </div>
          ))}
        </div>
        <div className="divide-y divide-aegis-border/60 rounded-xl border border-aegis-border bg-aegis-bg">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between px-3 py-2.5 text-[10px]">
              <span className="text-aegis-muted">{label}</span>
              <span className="font-mono text-aegis-T4">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  )
}

function TimeHorizon({ snapshot }: Props) {
  const observedTime = isFiniteNumber(snapshot?.timestamp_ms)
    ? Math.trunc(snapshot.timestamp_ms).toLocaleString()
    : 'unavailable'

  return (
    <Panel
      number="07"
      title="Time-slice horizon"
      subtitle="One unverified observation; history and future remain deliberately empty."
    >
      <div className="p-4">
        <div className="relative grid grid-cols-3 gap-3 before:absolute before:left-[16%] before:right-[16%] before:top-4 before:h-px before:bg-aegis-border-medium">
          {[
            ['T-1', 'not provided', 'unknown'],
            ['T0', snapshot ? `epoch ${formatInteger(snapshot.epoch_sequence)}` : 'no input', snapshot ? 'input' : 'unknown'],
            ['T+1', 'not predicted', 'unknown'],
          ].map(([slice, value, status]) => (
            <div key={slice} className="relative z-10 text-center">
              <div
                className="mx-auto h-8 w-8 rounded-full border-2 bg-aegis-deep"
                style={{ borderColor: STATUS_COLOR[status as NodeStatus] }}
              />
              <div className="mt-2 font-mono text-[9px] text-aegis-muted">{slice}</div>
              <div className="mt-1 text-[10px] text-aegis-secondary">{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 rounded-xl border border-aegis-border bg-aegis-bg px-3 py-2.5 font-mono text-[9px]">
          <span className="text-aegis-muted">reported timestamp_ms</span>
          <span className="float-right text-aegis-secondary">{observedTime}</span>
        </div>
        <p className="mt-2 text-[9px] leading-relaxed text-aegis-T3">
          This is not trusted clock evidence and is not a receipt timeline.
        </p>
      </div>
    </Panel>
  )
}

export function HolonogramSurface({ snapshot }: Props) {
  return (
    <div className="min-h-full p-4 md:p-5">
      <div className="mx-auto max-w-[1500px] space-y-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-aegis-phi">
              Visual compiled feedback layer
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-aegis-text md:text-3xl">
              Holonñgram Compiler
            </h1>
            <p className="mt-2 max-w-3xl text-xs leading-relaxed text-aegis-muted">
              Mathematics as inspectable state pressure: envelope, lattice, comparison, feedback,
              route proposal, provenance boundary, and time horizon.
            </p>
          </div>
          <div className="font-mono text-[9px] uppercase tracking-wider text-aegis-muted">
            mathematics → trace → display → operator inspection
          </div>
        </div>

        <BoundaryBanner hasInput={snapshot !== null} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(320px,0.82fr)_minmax(520px,1.5fr)]">
          <TransitionEnvelope snapshot={snapshot} />
          <Holonogram snapshot={snapshot} />
          <ExpectedActual snapshot={snapshot} />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <FeedbackSignal snapshot={snapshot} />
          <MiddlewareEdge />
          <ReceiptChain />
          <TimeHorizon snapshot={snapshot} />
        </div>
      </div>
    </div>
  )
}
