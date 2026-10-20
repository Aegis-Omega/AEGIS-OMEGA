import { useMemo, useRef, useState, type CSSProperties, type PointerEvent } from 'react'
import { SovereignMatter } from './SovereignMatter.js'
import { fieldProjection, sourceSnapshot, type FieldSource } from '../lib/fieldTopology.js'
import './sovereign-field.css'

type Props = {
  sources: readonly FieldSource[]
  selectedId: string | null
  onSelect: (id: string) => void
}
type Lens = 'field' | 'lineage'

const NODE_LABELS: Record<string, string> = {
  'formal-fork':'FORMAL','qgi-lab':'QUANTUM',qbp:'GENOMICS',calibration:'COGNITION',source:'RUNTIME',docs:'API',
}
const AREAS: Record<string, string> = {
  formal: 'MATHEMATICS', physics: 'PHYSICS', biology: 'LIFE SCIENCES',
  cognition: 'COGNITION', system: 'RUNTIME',
}

export function SovereignField({ sources, selectedId, onSelect }: Props) {
  const [yaw, setYaw] = useState(-.18)
  const [lens, setLens] = useState<Lens>('field')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const drag = useRef<{ x: number; yaw: number } | null>(null)
  const currentId = useRef(selectedId)
  const field = useMemo(() => fieldProjection(sources, selectedId, yaw), [sources, selectedId, yaw])
  const selected = field.selection
  const boundaries = selected?.boundaries ?? []
  currentId.current = selected?.id ?? null
  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    // Inert SVG/core descendants are part of the orbit surface; controls are not.
    // Keep touch vertical scrolling native; orbit buttons remain keyboard/touch operable.
    if (event.pointerType === 'touch') return
    if (event.target instanceof Element && event.target.closest('button, a, input, select, textarea')) return
    drag.current = { x: event.clientX, yaw }
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    setYaw(Math.max(-3.14, Math.min(3.14, drag.current.yaw + (event.clientX - drag.current.x) / 235)))
  }
  const onPointerEnd = () => { drag.current = null }
  const copyRecord = async () => {
    if (!selected) return
    const key = selected.id
    setCopiedId(null)
    try {
      await navigator.clipboard.writeText(sourceSnapshot(selected))
      // Do not attribute completion to a different record following a slow clipboard write.
      if (currentId.current === key) setCopiedId(key)
    } catch { setCopiedId(null) }
  }
  return <section className="sf-root" aria-labelledby="sf-title" data-area={selected?.area ?? 'none'}>
    <header className="sf-head">
      <div className="sf-wordmark"><span className="sf-symbol" aria-hidden="true">Ω</span><span>AEGIS <b>FIELD</b><small>RESEARCH OPERATING SYSTEM / EXPERIMENTAL VIEW</small></span></div>
      <span className="sf-edition">EDITION 001 <span className="sf-divider">/</span> SOURCE ATLAS</span>
    </header>
    <div className="sf-titlebar">
      <div><span className="sf-kicker"><i /> RESEARCH, MADE NAVIGABLE</span>
        <h2 id="sf-title">Enter the <em>unknown.</em></h2>
        <p>Move through research by inspecting what is documented, what remains open, and where the evidence stops. Each node is a real entry in the current curated source register.</p>
      </div>
      <div className="sf-count"><span>REGISTERED SOURCES</span><strong>{String(sources.length).padStart(2, '0')}</strong><small>CURATED · NOT LIVE</small></div>
    </div>
    <div className="sf-workspace">
      <div className="sf-space" aria-label="Spatial research source navigation">
        <div className="sf-space-top"><span>01 <i /> THE ATLAS</span><div className="sf-lens" role="group" aria-label="Visual lens">
          <button type="button" aria-pressed={lens === 'field'} onClick={() => setLens('field')}>Spatial</button>
          <button type="button" aria-pressed={lens === 'lineage'} onClick={() => setLens('lineage')}>Lineage</button>
        </div></div>
        <div className={'sf-universe ' + (lens === 'lineage' ? 'sf-universe-lineage' : '')}>
          {selected && <SovereignMatter sourceId={selected.id} limitCount={selected.boundaries.length} viewYaw={yaw} motionOverride={false} conceptArt />}
          <div className="sf-coordinate sf-coordinate-top" aria-hidden="true">RELATIONAL COORDINATES <span>·</span> OBSERVED CATALOG</div>
          <div className="sf-coordinate sf-coordinate-bottom" aria-hidden="true">DRAG BACKGROUND TO ORBIT <span>·</span> NO SIMULATED TELEMETRY</div>
          <div className="sf-compact-list" aria-label="Accessible source navigator">
            {sources.map(source => <button type="button" key={source.id}
              aria-pressed={selected?.id === source.id} onClick={() => { onSelect(source.id); setCopiedId(null) }}>
              <span>{source.index}</span><strong>{source.title}</strong><span aria-hidden="true">↗</span>
            </button>)}
          </div>
          <div className="sf-orbit-region" onPointerDown={onPointerDown} onPointerMove={onPointerMove}
            onPointerUp={onPointerEnd} onPointerCancel={onPointerEnd}>
            <svg className="sf-engraving" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="sf-connection" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#d5ba89" stopOpacity=".26"/><stop offset="1" stopColor="#9ebaca" stopOpacity=".42"/></linearGradient>
              </defs>
              <ellipse cx="50" cy="50" rx="39" ry="31" stroke="#b2c9d2" strokeOpacity=".16" fill="none" strokeWidth=".13" />
              <ellipse cx="50" cy="50" rx="33" ry="39" stroke="#b2c9d2" strokeOpacity=".12" fill="none" strokeWidth=".12" />
              {(lens === 'field' ? field.points : boundaries.map((_,index) => {
                const angle = -Math.PI / 2 + index * Math.PI * 2 / Math.max(1, boundaries.length)
                return { id: String(index), x: 50 + Math.cos(angle) * 33, y: 50 + Math.sin(angle) * 33, active: true, depth: 0, scale: 1, index: String(index + 1).padStart(2, '0') }
              })).map(point => <g key={point.id}>
                <path d={`M 50 50 Q ${(50 + point.x) / 2} ${Math.min(point.y, 50) - 8} ${point.x} ${point.y}`}
                  stroke={point.active ? '#d6b980' : 'url(#sf-connection)'} strokeWidth={point.active ? '.33' : '.16'}
                  fill="none" strokeDasharray={point.active ? undefined : '1 1.9'} />
                <circle cx={point.x} cy={point.y} r={point.active ? 1.1 : .6} fill={point.active ? '#d1b47b' : '#829ca8'} />
              </g>)}
              <circle cx="50" cy="50" r="1.3" stroke="#d9bf90" strokeWidth=".2" fill="#12202b" />
            </svg>
            <div className="sf-core" aria-hidden="true"><span>{lens === 'field' ? 'Ω' : '?'}</span><small>{lens === 'field' ? 'THE INDEX' : 'OPEN'}</small></div>
            {lens === 'field' ? field.points.map(point => {
              const record = sources.find(source => source.id === point.id)
              if (!record) return null
              return <button type="button" key={point.id}
                className={'sf-node' + (point.active ? ' sf-node-active' : '')}
                style={{left:point.x + '%', top:point.y + '%', '--node-scale':point.scale} as CSSProperties}
                onClick={() => { onSelect(point.id); setCopiedId(null) }}
                aria-label={`Inspect ${record.title}`} aria-pressed={point.active}>
                <span className="sf-node-mark">{point.index}</span><span className="sf-node-label">{NODE_LABELS[record.id] ?? record.title}</span>
              </button>
            }) : boundaries.map((limit,index) => {
              const angle = -Math.PI / 2 + index * Math.PI * 2 / Math.max(1, boundaries.length)
              return <div key={index} className="sf-limit-node" style={{ left:(50 + Math.cos(angle) * 33) + '%',top:(50 + Math.sin(angle) * 33) + '%' }} title={limit}>
                <span>{String(index+1).padStart(2,'0')} / LIMIT</span><strong>{limit}</strong>
              </div>
            })}
          </div>
        </div>
        <div className="sf-space-bottom">
          <span>INDEX MEMBERSHIP ONLY · NOT A PROOF DEPENDENCY GRAPH</span>
          <div className="sf-camera" role="group" aria-label="Adjust three-dimensional viewing angle">
            <button type="button" onClick={() => setYaw(value => Math.max(-3.14, value - .28))} aria-label="Orbit left">←</button>
            <button type="button" onClick={() => setYaw(-.18)} aria-label="Reset view">Reset</button>
            <button type="button" onClick={() => setYaw(value => Math.min(3.14, value + .28))} aria-label="Orbit right">→</button>
          </div>
        </div>
      </div>
      <aside className="sf-detail" aria-live="polite" aria-atomic="false">
        {selected ? <>
          <div className="sf-detail-label"><span>02 <i/> ACTIVE INVESTIGATION</span><span className="sf-record-id">{selected.index} / {String(sources.length).padStart(2,'0')}</span></div>
          <div className="sf-domain">{AREAS[selected.area] ?? selected.area.toUpperCase()}</div>
          <h3>{selected.title}</h3>
          <p className="sf-description">{selected.description}</p>
          <div className="sf-verdict"><span>REPORTED STATUS</span><strong>{selected.status}</strong><small>Not independently verified on this page</small></div>
          <div className="sf-inquiry"><span>THE QUESTION</span><p>{selected.question}</p></div>
          <div className="sf-constraints"><span>DECLARED LIMITS <b>{String(selected.boundaries.length).padStart(2,'0')}</b></span>
            <ol>{selected.boundaries.map((limit,i) => <li key={i}>{limit}</li>)}</ol>
          </div>
          <div className="sf-actions">
            {selected.href ? <a href={selected.href} target={selected.href.startsWith('http') ? '_blank' : undefined}
              rel={selected.href.startsWith('http') ? 'noopener noreferrer' : undefined}>Open actual source <span aria-hidden="true">↗</span></a>
              : <span className="sf-private">SOURCE NOT PUBLIC <span aria-hidden="true">↗</span></span>}
            <button type="button" onClick={copyRecord}>{copiedId === selected.id ? 'Copied unsigned record' : 'Copy source record'}</button>
          </div>
        </> : <div className="sf-empty" role="status">No matching sources. Adjust the filters above. No record has been inferred.</div>}
      </aside>
    </div>
    <footer className="sf-footer"><span>AEGIS Ω / SOURCE TRANSPARENCY</span><p>The spatial arrangement is a navigational visualization of an existing curated register, not a quantitative scientific graph or a live runtime measurement.</p><span>NO CLAIMS PROMOTED</span></footer>
  </section>
}
