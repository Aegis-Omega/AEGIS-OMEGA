/** AEGIS Ω — ResearchOS source atlas. No fabricated telemetry or hidden indexing. */
import { useState, useMemo } from 'react'
import './operator-workbench.css'
import './research-workbench.css'
import { SovereignField } from './SovereignField.js'
import { EvidenceFilament } from './EvidenceFilament.js'

type Area = 'all'|'formal'|'physics'|'biology'|'cognition'|'system'
type Source = {
  id:string;area:Exclude<Area,'all'>;index:string;title:string;
  kind:string;status:string;description:string;question:string;
  boundaries:string[];href?:string;action:string;
}
const SOURCES:Source[] = [
  {id:'formal-fork',area:'formal',index:'01',title:'Formal conjectures',kind:'SOURCE / LEAN',status:'PROOF SCOPE OPEN',description:'Forked formal mathematics, proof attempts and exact-head compilation evidence.',question:'Which theorem statement is closed without a large-window hypothesis?',boundaries:['A compiled lemma is not automatically an unconditional proof.','Read theorem statements and import closure at a precise commit.','A missing module is a build defect; it does not decide mathematical truth.'],href:'https://github.com/tarikskalic33/formal-conjectures',action:'Inspect theorem sources'},
  {id:'qgi-lab',area:'physics',index:'02',title:'Quantum integrity',kind:'LIVE / EDGE MATHEMATICS',status:'BATH NOT LIVE HERE',description:'Interactive PSD spectral masks alongside explicitly archival quantum-channel simulation results.',question:'Where does selective secularization lose complete positivity?',boundaries:['The edge service computes PSD masks, not live SciPy/Choi simulations.','Archived numerical experiments are not interval certificates.','Physical universality and novelty require independent work.'],href:'https://aegis-quantum-integrity-mobile.tarikskalic33.workers.dev/',action:'Open live PSD instrument'},
  {id:'qbp',area:'biology',index:'03',title:'Genomics · QBP',kind:'ARCHIVED / PRIVATE',status:'DATASET ACCESS RESTRICTED',description:'Bacterial genomics, controls, conformational fingerprints and recorded statistical receipts in the research archive.',question:'Do holdout species and negative controls reproduce the reported signal?',boundaries:['The underlying archived datasets are not exposed by this public site.','Reproducible measurements are separate from synthetic seed sequences.','No medical or drug-design claim is inferred from a predictor.'],action:'Public dataset access not configured'},
  {id:'calibration',area:'cognition',index:'04',title:'Cognitive calibration',kind:'ARCHIVED / PRIVATE',status:'GENERALIZATION UNVERIFIED',description:'Calibration experiments, discriminator studies and self-correction traces held in the research archive.',question:'Do confidence estimates transfer outside the training context?',boundaries:['Calibration artifacts are not live agent-state readings.','A test receipt requires source data, code and holdout definition.','Self-reported confidence is not measured performance.'],action:'Public dataset access not configured'},
  {id:'source',area:'system',index:'05',title:'Sovereign runtime source',kind:'CODE / PUBLIC',status:'EXACT-HEAD REVIEW REQUIRED',description:'AEGIS runtime, verification logic and branches. Read what the implementation does, not what a headline promises.',question:'What is admitted by the currently protected execution path?',boundaries:['Draft or unsigned changes are not production admission.','A successful Vite build does not establish runtime correctness.','Verification must bind claims to immutable head and receipts.'],href:'https://github.com/Aegis-Omega/AEGIS-OMEGA',action:'Browse code and checks'},
  {id:'docs',area:'system',index:'06',title:'Platform API contract',kind:'INTERFACE / DOCUMENTATION',status:'AVAILABILITY NOT TESTED',description:'Documented collaboration request shapes, status endpoints and authentication requirements.',question:'Which API contracts can be invoked with legitimate scoped credentials?',boundaries:['Documentation describes a contract, not the current provider health.','Live inference requires authorized credentials and may incur costs.','No credentials are requested or stored in this research atlas.'],href:'/docs',action:'Open developer contract'},
]
const TAGS:{id:Area;label:string}[]=[{id:'all',label:'All sources'},{id:'formal',label:'Mathematics'},{id:'physics',label:'Physics'},{id:'biology',label:'Biology'},{id:'cognition',label:'Cognition'},{id:'system',label:'Runtime'}]

export function ResearchWorkbench(){
  const [area,setArea]=useState<Area>('all')
  const [term,setTerm]=useState('')
  const [active,setActive]=useState(SOURCES[0]!.id)
  // One active renderer: data-bound source lineage OR the existing spatial source atlas.
  // An inactive SDF scene is unmounted, never kept as a second ambient GPU surface.
  const [perspective,setPerspective]=useState<'lineage'|'atlas'>('lineage')
  const shown=useMemo(()=>SOURCES.filter(x=>(area==='all'||x.area===area)&&`${x.title} ${x.kind} ${x.description} ${x.question}`.toLowerCase().includes(term.trim().toLowerCase())),[area,term])
  const detail=shown.find(x=>x.id===active)||shown[0]
  const [compareId,setCompareId]=useState<string|null>(null)
  const comparison=shown.find(x=>x.id===compareId)
  const compareDistinct=Boolean(detail&&comparison&&detail.id!==comparison.id)
  return <div className="rw-shell">
    <div className="rw-ruler"><span>AEGIS Ω / RESEARCHOS</span><span>CURATED SOURCE MAP · NOT A LIVE INDEX</span></div>
    <header className="rw-hero"><div><span className="rw-eyebrow">EVIDENCE FABRIC / 01</span><h1>Questions before <em>claims.</em></h1><p>One research surface across formal mathematics, physical simulation, genomics and cognitive evaluation. Every entry points to its actual access boundary.</p></div><div className="rw-side"><span>DISCOVERY PRINCIPLE</span><strong>Recover → Reproduce<br/>→ Challenge → Admit</strong><small>Access does not imply a verified result.</small></div></header>
    <div className="rw-toolstrip"><div className="rw-filters" aria-label="Research domain filters">{TAGS.map(t=><button type="button" key={t.id} onClick={()=>setArea(t.id)} aria-pressed={area===t.id}>{t.label}</button>)}</div><label className="rw-search"><span className="rw-search-symbol" aria-hidden="true">⌕</span><span className="sr-only">Search source index</span><input type="search" value={term} onChange={e=>setTerm(e.target.value)} placeholder="Search source or question"/></label></div>
    <section className="rw-perspective" aria-label="Research visualization perspective">
      <div className="rw-perspective-copy">
        <strong>Explore relationships. Inspect their limits.</strong>
        <span>Curated sources only; no live agent activity, inferred proof, or execution permission.</span>
      </div>
      <div className="rw-perspective-controls" role="group" aria-label="Choose evidence view">
        <button type="button" aria-pressed={perspective==='lineage'} onClick={()=>setPerspective('lineage')}>Evidence filament</button>
        <button type="button" aria-pressed={perspective==='atlas'} onClick={()=>setPerspective('atlas')}>Spatial atlas</button>
      </div>
    </section>
    {perspective==='lineage'
      ? <EvidenceFilament sources={shown} selectedId={detail?.id ?? null} onSelect={setActive} />
      : <SovereignField sources={shown} selectedId={detail?.id ?? null} onSelect={setActive} />}
    <div className="rw-body"><section className="rw-index" aria-label="Research source list"><div className="rw-column-title"><span>SOURCE REGISTER</span><span>{shown.length} ENTRIES</span></div>{shown.length===0?<div className="rw-zero">No matching source in this curated map. Nothing has been inferred.</div>:shown.map(s=><button className={'rw-entry '+(detail?.id===s.id?'rw-entry-active':'')} key={s.id} onClick={()=>setActive(s.id)} type="button" aria-pressed={detail?.id===s.id}><span className="rw-entry-n">{s.index}</span><div><small>{s.kind}</small><strong>{s.title}</strong><p>{s.description}</p></div><span className="rw-entry-arrow" aria-hidden="true">↗</span></button>)}</section>
    <section className="rw-inspector" aria-label="Selected research source">{detail?<><div className="rw-inspector-top"><span>RESEARCH RECORD / {detail.index}</span><span className="rw-inspector-status">{detail.status}</span></div><div className="rw-inspector-main"><span className="rw-eyebrow">{detail.area.toUpperCase()} / SOURCE INSPECTION</span><h2>{detail.title}</h2><p>{detail.description}</p><div className="rw-question"><small>THE OPEN QUESTION</small><strong>{detail.question}</strong></div><div className="rw-limits"><small>BOUNDARIES · DO NOT PROMOTE</small>{detail.boundaries.map((x,i)=><div key={i}><span>{String(i+1).padStart(2,'0')}</span><p>{x}</p></div>)}</div><div className="rw-open">{detail.href?<a href={detail.href} target={detail.href.startsWith('http')?'_blank':undefined} rel={detail.href.startsWith('http')?'noopener noreferrer':undefined}>{detail.action}<span aria-hidden="true">↗</span></a>:<span className="rw-not-published">{detail.action} · NOT PUBLIC</span>}</div></div></>:<div className="rw-zero">Select a published source to inspect its limits.</div>}</section></div>
    <section className="rw-compare" aria-labelledby="rw-compare-title">
      <header className="rw-compare-head"><div><span className="rw-eyebrow">EVIDENCE COMPARISON / SOURCE BOUNDED</span><h2 id="rw-compare-title">Compare the <em>unknowns.</em></h2><p>Two recorded research entries, side by side. This comparison makes no claim that one proves or depends on the other.</p></div>
        <label htmlFor="rw-compare-select">SECOND RECORD
          <select id="rw-compare-select" value={compareId??''} onChange={event=>setCompareId(event.target.value||null)}>
            <option value="">Choose a source</option>{shown.filter(x=>x.id!==detail?.id).map(x=><option key={x.id} value={x.id}>{x.title}</option>)}
          </select>
        </label>
      </header>
      {compareDistinct?<div className="rw-compare-grid">{[detail!,comparison!].map((record,index)=><article key={record.id} className="rw-compare-record">
        <span>{String(index+1).padStart(2,'0')} / {record.area.toUpperCase()} / {record.kind}</span>
        <h3>{record.title}</h3><div className="rw-compare-verdict"><small>REPORTED STATUS</small><strong>{record.status}</strong></div>
        <div className="rw-compare-question"><small>OPEN QUESTION</small><p>{record.question}</p></div>
        <div className="rw-compare-limits"><small>DECLARED BOUNDARIES · {record.boundaries.length}</small><ol>{record.boundaries.map((limit,i)=><li key={i}>{limit}</li>)}</ol></div>
        {record.href?<a href={record.href} target={record.href.startsWith('http')?'_blank':undefined} rel={record.href.startsWith('http')?'noopener noreferrer':undefined}>Inspect original source ↗</a>:<span className="rw-compare-private">SOURCE NOT PUBLIC</span>}
      </article>)}</div>:<div className="rw-compare-empty" role="status">{shown.length<2?'At least two visible source records are needed. Adjust filters to compare.':'Select a second visible source to compare its question, evidence boundaries and access.'}</div>}
      <p className="rw-compare-disclosure">Comparison uses the curated source register only. It does not infer dependency, verification, scientific equivalence, provider availability or execution authority.</p>
    </section>
    <section className="rw-gate"><div><span className="rw-eyebrow">NEXT ACTION / EVIDENCE GATE</span><h2>Bring a claim. Leave with a test.</h2><p>Start from real code or a reproducible experiment, not a synthesized achievement metric.</p></div><div className="rw-gate-actions"><a href="/console">Operator console <span aria-hidden="true">↗</span></a><a href="https://github.com/Aegis-Omega/AEGIS-OMEGA" target="_blank" rel="noopener noreferrer">Source repository <span aria-hidden="true">↗</span></a></div></section>
    <footer className="rw-footer">RESEARCHOS / CURATED ENTRYPOINTS <span>NO PRIVATE DATA IS EXPOSED · NO SCIENTIFIC PRIORITY CLAIM</span></footer>
  </div>
}