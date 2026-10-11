/** One state-driven, data-bound visual slice of the existing ResearchOS atlas. */
import { selectEvidenceFilament, type FilamentSource } from '../lib/evidenceFilament.js'
import { SovereignMatter } from './SovereignMatter.js'

type Props = {
  sources: readonly FilamentSource[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function EvidenceFilament({ sources, selectedId, onSelect }: Props) {
  const flow = selectEvidenceFilament(sources, selectedId)
  return <section className="ef-observatory" aria-labelledby="ef-title">
    <header className="ef-heading">
      <div><span className="rw-eyebrow">EVIDENCE FILAMENT / RESEARCHOS</span>
        <h2 id="ef-title">The shape of a <em>question.</em></h2>
        <p>Explore one recorded source, its open question and its declared limits. Every connection comes from this curated register.</p>
      </div>
      <span className="ef-mode">CURATED DATA · NOT LIVE TELEMETRY</span>
    </header>
    {flow ? <>
      <div className="ef-map ef-map-material">
        <SovereignMatter sourceId={flow.source.id} limitCount={flow.source.boundaries.length} />
        <svg className="ef-engraving" viewBox="0 0 1080 390" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
          <defs>
            <linearGradient id="ef-beam" x1="0" y1="0" x2="1" y2="1">
              <stop stopColor="#476782" stopOpacity=".3" />
              <stop offset=".52" stopColor="#a1c9ea" stopOpacity=".7" />
              <stop offset="1" stopColor="#c8a96e" stopOpacity=".4" />
            </linearGradient>
            <radialGradient id="ef-depth"><stop stopColor="#356fb8" stopOpacity=".18" /><stop offset="1" stopColor="#356fb8" stopOpacity="0" /></radialGradient>
          </defs>
          <ellipse cx="544" cy="192" rx="440" ry="180" fill="url(#ef-depth)" />
          <g className="ef-lattice" fill="none" stroke="#81add2" strokeOpacity=".14">
            <ellipse cx="530" cy="195" rx="490" ry="135" />
            <ellipse cx="530" cy="195" rx="378" ry="183" />
            <path d="M40 195H1040M530 12V378" strokeDasharray="3 8" />
          </g>
          <g fill="none" stroke="url(#ef-beam)" strokeWidth="1.5">
            <path d="M195 194 C305 194 290 194 408 194" />
            <path d="M195 194 260 118 410 194 260 271Z" strokeOpacity=".35" />
            {flow && flow.source.boundaries.map((limit, index) => {
              const count = flow.source.boundaries.length
              const y = count === 1 ? 194 : 80 + index * 228 / (count - 1)
              return <g key={index}>
                <path d={'M658 194 C740 194 752 ' + y + ' 862 ' + y} />
                <circle cx="862" cy={y} r="5" stroke="#b7d9ed" fill="#102840" />
              </g>
            })}
          </g>
          <g fill="#9fd9f6" stroke="#142b46" strokeWidth="4">
            <circle cx="195" cy="194" r="6" />
            <circle cx="408" cy="194" r="5" />
            <circle cx="658" cy="194" r="5" />

          </g>
        </svg>
        <div className="ef-flow" key={flow.source.id}>
          <article className="ef-station ef-source">
            <span className="ef-index">01 / SOURCE</span>
            <strong>{flow.source.title}</strong>
            <small>{flow.source.kind}</small>
          </article>
          <article className="ef-station ef-question">
            <span className="ef-index">02 / OPEN QUESTION</span>
            <strong>{flow.source.question}</strong>
            <small>Research question · not a proven conclusion</small>
          </article>
          <article className="ef-station ef-boundaries">
            <span className="ef-index">03 / DECLARED LIMITS</span>
            <strong>{flow.source.boundaries.length} recorded boundaries</strong>
            <ol>{flow.source.boundaries.map((limit, i) => <li key={i}>{limit}</li>)}</ol>
          </article>
        </div>
      </div>
      <div className="ef-pick" role="group" aria-label="Choose a research source for the visual flow">
        {sources.map(source => <button key={source.id} type="button" aria-pressed={source.id === flow.source.id} onClick={() => onSelect(source.id)}>
          <span>{source.index}</span>{source.title}
        </button>)}
      </div>
      <p className="ef-disclosure">Edges show recorded metadata relationships within this source atlas, not mathematical proof dependencies, independent verification, or provider availability. Current record: <strong>{flow.source.status}</strong>.</p>
    </> : <p className="ef-empty" role="status">No source matches these filters. No lineage or result has been inferred.</p>}
  </section>
}
