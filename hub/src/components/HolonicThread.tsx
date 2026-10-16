import { useMemo, useState } from 'react'
import type { HolonTrace, HolonEvent } from '../lib/holonTrace.js'
import { buildHolonicThread, HOLON_THREAD_WIDTH, HOLON_THREAD_HEIGHT } from '../lib/holonThread.js'
import './holonic-thread.css'

const typeLabel:Record<HolonEvent['kind'],string>={
  seed:'Original spark',branch:'Exploration',select:'Human choice',
  weave:'Synthesis',artifact:'Artifact intention'
}
const originLabel=(e:HolonEvent)=>e.actor==='human'?'Human-authored':
  e.actor==='model'?'Pasted LLM suggestion · unverified':'Pasted agent content · unverified'

/**
 * Deliberate 3D projection of real creative decisions. This is not live inference,
 * a neural scan, a source signature, or an authenticated identity record.
 * Full-text accessible mobile list is the equivalent of the spatial artwork.
 */
export function HolonicThread({trace}:{trace:HolonTrace}){
  const [yaw,setYaw]=useState(0)
  const [focusId,setFocusId]=useState<string|null>(null)
  const [windowEnd,setWindowEnd]=useState<number|null>(null)
  const effectiveEnd=windowEnd===null?trace.events.length:Math.min(windowEnd,trace.events.length)
  const thread=useMemo(()=>buildHolonicThread(trace,yaw,effectiveEnd),[trace,yaw,effectiveEnd])
  const focus=trace.events.find(e=>e.id===focusId)??trace.events[thread.windowEnd-1]??null
  const allById=useMemo(()=>new Map(trace.events.map(e=>[e.id,e])),[trace])
  const activeId=focus?.id??null
  const sequence=thread.points.map(p=>allById.get(p.id)!).filter(Boolean)
  const selectedLinked=new Set<string>(focus?[focus.id,...focus.parents]:[])
  const selectedStrands=new Set(thread.strands.filter(e=>e.from===activeId||e.to===activeId).map(e=>e.key))
  return <section className="ht-root" aria-labelledby="ht-title">
    <div className="ht-head">
      <div className="ht-heading"><span className="ht-eyebrow">AEGIS Ω / HOLONIC THREAD / RECORD-BOUND</span>
        <h2 id="ht-title">The thread of becoming.</h2>
        <p>A thread exists only when a creative event names its source. Turn the space to inspect a different perspective; the record itself never changes.</p>
      </div>
      <div className="ht-metrics" aria-label="Thread rendering scope">
        <span><b>{thread.points.length}</b> visible events</span>
        <span><b>{thread.strands.length}</b> visible source links</span>
        {thread.hiddenEvents>0&&<span>{thread.hiddenBefore} earlier · {thread.hiddenAfter} later events outside this window</span>}
        {thread.hiddenStrands>0&&<span>{thread.hiddenStrands} links outside this window</span>}
      </div>
    </div>
    <div className="ht-composition">
      <div className="ht-scene">
        <div className="ht-timeline" role="group" aria-label="Navigate recorded creative history">
          <button type="button" onClick={()=>{setWindowEnd(Math.max(1,effectiveEnd-12));setFocusId(null)}} disabled={effectiveEnd<=1} aria-label="View earlier recorded events">← Earlier</button>
          <span>{trace.events.length?"Events "+(thread.windowStart+1)+"–"+thread.windowEnd+" / "+trace.events.length:"No events"}</span>
          <button type="button" onClick={()=>{setWindowEnd(effectiveEnd>=trace.events.length-12?null:Math.min(trace.events.length,effectiveEnd+12));setFocusId(null)}} disabled={effectiveEnd>=trace.events.length} aria-label="View later recorded events">Later →</button>
          <button type="button" onClick={()=>{setWindowEnd(null);setFocusId(null)}} disabled={effectiveEnd===trace.events.length} aria-label="View latest recorded events">Latest</button>
        </div>
        <div className="ht-tools" role="group" aria-label="Adjust spatial thread perspective">
          <button type="button" onClick={()=>setYaw(v=>Math.max(-.72,Math.round((v-.18)*100)/100))} disabled={!thread.points.length||yaw<=-.72} aria-label="Turn perspective left">←</button>
          <button type="button" onClick={()=>setYaw(0)} disabled={!thread.points.length||yaw===0} aria-label="Center perspective">Center</button>
          <button type="button" onClick={()=>setYaw(v=>Math.min(.72,Math.round((v+.18)*100)/100))} disabled={!thread.points.length||yaw>=.72} aria-label="Turn perspective right">→</button>
        </div>
        <div className="ht-stage" aria-label="Interactive 3D-projected creative lineage">
          <svg className="ht-threads" viewBox={'0 0 '+HOLON_THREAD_WIDTH+' '+HOLON_THREAD_HEIGHT} preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id="ht-thread-iridescence" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stopColor="#6696B7"/>
                <stop offset=".48" stopColor="#D5E3D6"/>
                <stop offset="1" stopColor="#CAAA84"/>
              </linearGradient>
            </defs>
            {thread.strands.map(edge=><g key={edge.key} className={'ht-strand '+(selectedStrands.has(edge.key)?'ht-strand-focus':'')}>
              <path d={edge.d} className="ht-strand-shadow"/>
              <path d={edge.d} className="ht-strand-body"/>
              <path d={edge.d} className="ht-strand-highlight"/>
            </g>)}
          </svg>
          {thread.points.map(p=><button type="button" key={p.id}
            className={'ht-node ht-node-'+p.actor+(activeId===p.id?' ht-node-active':'')+(selectedLinked.has(p.id)?' ht-node-linked':'')}
            style={{left:(p.px/HOLON_THREAD_WIDTH*100)+'%',top:(p.py/HOLON_THREAD_HEIGHT*100)+'%'}}
            onClick={()=>setFocusId(p.id)}
            aria-pressed={activeId===p.id}
            aria-label={'Event '+p.seq+', '+typeLabel[p.kind]+', '+originLabel(allById.get(p.id)!)}
            title={'#'+p.seq+' · '+typeLabel[p.kind]}>
            <span className="ht-node-core" aria-hidden="true"/>
            <span className="ht-node-index" aria-hidden="true">{String(p.seq).padStart(2,'0')}</span>
          </button>)}
          {thread.points.length===0&&<p className="ht-zero">No thread yet. One human-created idea is enough to begin.</p>}
        </div>
        <ol className="ht-mobile-list" aria-label="Recent recorded creative events">
          {sequence.map(e=><li key={e.id}><button type="button" onClick={()=>setFocusId(e.id)} aria-pressed={activeId===e.id}>
            <span>{String(e.seq).padStart(2,'0')} / {typeLabel[e.kind]}</span>
            <strong>{e.text}</strong>
            <small>{originLabel(e)}</small>
          </button></li>)}
        </ol>
        <div className="ht-key" aria-label="Origin legend"><span><i className="ht-key-human"/> Human</span><span><i className="ht-key-model"/> Pasted LLM</span><span><i className="ht-key-agent"/> Pasted agent content</span></div>
        <p className="ht-caution">An authored spatial projection, not a visualization of consciousness, proof, or agent telemetry. Links show only recorded source IDs. No background animation.</p>
      </div>
      <aside className="ht-inspector" aria-label="Selected thread record">
        <span className="ht-inspector-kicker">CREATIVE ORIGIN / INSPECTION</span>
        {focus?<>
          <span className="ht-inspector-count">EVENT {String(focus.seq).padStart(2,'0')} / {trace.events.length}</span>
          <h3>{typeLabel[focus.kind]}</h3>
          <div className="ht-actor">{originLabel(focus)}</div>
          <p className="ht-content">{focus.text}</p>
          <dl className="ht-provenance">
            <div><dt>Recorded by</dt><dd>{focus.actor==='human'?'Human event':focus.actor+' (pasted, unverified)'}</dd></div>
            <div><dt>Time recorded</dt><dd>{focus.recorded_at}</dd></div>
            <div><dt>Source links</dt><dd>{focus.parents.length?focus.parents.map(id=>allById.get(id)?'#'+allById.get(id)!.seq:'Unknown').join(' · '):'Original event'}</dd></div>
            <div><dt>Event digest</dt><dd className="ht-digest">{focus.hash}</dd></div>
          </dl>
          <p className="ht-boundary">A hash can detect changes to the exported record. It does not certify authorship or verify an external model.</p>
        </>:<><h3>No record selected</h3><p className="ht-content">Create an idea to begin an inspectable lineage. Nothing will be invented on your behalf.</p></>}
      </aside>
    </div>
  </section>
}
