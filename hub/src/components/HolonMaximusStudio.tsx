import { useMemo, useRef, useState, type ChangeEvent } from 'react'
import { SovereignMatter } from './SovereignMatter.js'
import {
  emptyHolonTrace, appendHolonEvent, verifyHolonTrace, selectedHolonBranches,
  MAX_HOLON_EVENTS, MAX_HOLON_TEXT,
  type HolonKind, type HolonRole, type HolonLens, type HolonTrace, type HolonDraft
} from '../lib/holonTrace.js'
import './holon-maximus.css'

const LENSES: readonly {id: HolonLens; label: string; description: string}[] = [
  {id:'imagination',label:'Imagine',description:'What if it could be different?'},
  {id:'structure',label:'Construct',description:'How might it actually work?'},
  {id:'critique',label:'Challenge',description:'Which assumption should be questioned?'}
]
const labels:Record<HolonKind,string> = {
  seed:'Seed',branch:'Direction',select:'Human choice',weave:'Synthesis',artifact:'Artifact'
}
const shorten=(s:string,n=70) => s.length>n?s.slice(0,n-1)+'…':s

function TraceGraph({trace}:{trace:HolonTrace}) {
  const shown=trace.events.slice(-12)
  const points=shown.map((e,i)=>({
    id:e.id,label:labels[e.kind],text:e.text,actor:e.actor,
    x:64+(i%4)*132,y:65+Math.floor(i/4)*118
  }))
  const index=new Map(points.map(p=>[p.id,p]))
  return <div className="hm-graph" role="group" aria-label="Recorded idea and decision relationships">
    <svg viewBox="0 0 530 344" role="img" aria-label={shown.length ? 'Graph of the latest '+shown.length+' actual trace events' : 'Empty trace; no activity has been invented'}>
      {shown.flatMap(e=>e.parents.filter(id=>index.has(id)).map(id=>{
        const p=index.get(id)!,q=index.get(e.id)!
        return <path key={id+e.id} d={'M'+p.x+' '+p.y+' Q'+((p.x+q.x)/2)+' '+(p.y+q.y)/2+' '+q.x+' '+q.y} fill="none" stroke="#6EA9C6" strokeOpacity=".52" strokeWidth="1.4"/>
      }))}
      {points.map(p=><g key={p.id}><circle cx={p.x} cy={p.y} r={p.actor==='human'?20:16} stroke={p.actor==='human'?'#B8E4EC':'#CDB995'} strokeWidth="1.2" fill="#0C2234"/><circle cx={p.x} cy={p.y} r="5" fill={p.actor==='human'?'#88BFD6':'#CAA87B'}/><text x={p.x} y={p.y+35} fill="#D9E8ED" fontSize="10" textAnchor="middle">{p.label}</text></g>)}
      {!shown.length&&<><circle cx="265" cy="165" r="63" fill="none" stroke="#4B7393" strokeWidth="1.1" strokeDasharray="2 9"/><circle cx="265" cy="165" r="33" fill="#13283C" stroke="#90B2C9" strokeWidth="1.6"/><text x="265" y="171" textAnchor="middle" fontSize="19" fill="#DCEEF2">Ω</text></>}
    </svg>
    <p>{shown.length ? 'Only recorded relationships are drawn. Not a map of thoughts or neural activity.' : 'Your first idea begins the structure. No simulated activity.'}</p>
  </div>
}

export function HolonMaximusStudio(){
  const [trace,setTrace]=useState<HolonTrace>(emptyHolonTrace)
  const [seed,setSeed]=useState('')
  const [branch,setBranch]=useState('')
  const [branchParent,setBranchParent]=useState('')
  const [lens,setLens]=useState<HolonLens>('imagination')
  const [source,setSource]=useState<'human'|'model'|'agent'>('human')
  const [weave,setWeave]=useState('')
  const [artifact,setArtifact]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [busy,setBusy]=useState(false)
  const busyRef=useRef(false)
  const seedEvent=trace.events.find(e=>e.kind==='seed')
  const branches=trace.events.filter(e=>e.kind==='branch')
  const selected=selectedHolonBranches(trace)
  const selectedIds=new Set(selected.map(e=>e.id))
  const choices=trace.events.filter(e=>e.kind==='select')
  const lastWeave=[...trace.events].reverse().find(e=>e.kind==='weave')
  const visibleParents=trace.events.filter(e=>['seed','branch','weave'].includes(e.kind))
  const capacity=trace.events.length<MAX_HOLON_EVENTS
  const humanDecisions=trace.events.filter(e=>e.actor==='human').length
  const lastHash=trace.events.at(-1)?.hash??'NOT RECORDED'
  const canWeave=choices.length>=2&&selected.length>=2
  const graphStats=useMemo(()=>({nodes:trace.events.length,links:trace.events.reduce((n,e)=>n+e.parents.length,0)}),[trace])

  async function append(kind:HolonKind,text:string,parents:string[],role:HolonRole='human',selectedLens:HolonLens='none',onSuccess?:()=>void){
    if(busyRef.current)return
    busyRef.current=true;setBusy(true);setError('');setNotice('')
    const draft:HolonDraft={
      id:crypto.randomUUID(),kind,actor:role,
      origin:role==='human'?'direct_human':'pasted_external',
      lens:selectedLens,text:text.trim(),parents,recorded_at:new Date().toISOString()
    }
    try {
      const next=await appendHolonEvent(trace,draft)
      setTrace(next)
      setNotice(labels[kind]+' recorded locally. Export your trace to keep it.')
      onSuccess?.()
    } catch(e){setError(e instanceof Error?e.message:'Cannot update trace')}
    finally{busyRef.current=false;setBusy(false)}
  }
  function exportTrace(){
    const raw=JSON.stringify(trace,null,2)
    const url=URL.createObjectURL(new Blob([raw],{type:'application/json'}))
    const a=document.createElement('a');a.href=url;a.download='aegis-holon-maximus-trace.json';a.click()
    window.setTimeout(()=>URL.revokeObjectURL(url),500)
    setNotice('JSON exported. Hash linkage is not a digital signature.')
  }
  async function importTrace(event:ChangeEvent<HTMLInputElement>){
    const file=event.target.files?.[0];event.target.value='';if(!file)return
    if(busyRef.current)return
    if(file.size>256_000){setError('Import limited to 256 KB');return}
    busyRef.current=true;setBusy(true);setError('');setNotice('')
    try{
      const parsed:unknown=JSON.parse(await file.text())
      const verified=await verifyHolonTrace(parsed)
      setTrace(verified);setNotice('Imported and checked '+verified.events.length+' events; source identity remains unverified.')
    }catch(e){setError(e instanceof Error?e.message:'Invalid JSON')}
    finally{busyRef.current=false;setBusy(false)}
  }
  return <article className="hm-root" aria-labelledby="hm-title">
    <header className="hm-intro">
      <div><span className="hm-overline">AEGIS Ω / HOLON MAXIMUS OPTIMUS / PRIVATE STUDY</span>
        <h1 id="hm-title">Make something <em>only you could imagine.</em></h1>
        <p>Start with one thought. Challenge it, shape it, choose what survives. The system keeps the creative lineage without pretending to be its author.</p>
        <div className="hm-claims"><span>Human-directed</span><span>No provider calls</span><span>Local session</span></div>
      </div>
      <div className="hm-art" aria-label="Authored 3D AEGIS Ω material study; illustration, not a scientific or operational measurement">
        <SovereignMatter sourceId="source" limitCount={0} conceptArt motionOverride={false}/>
      </div>
    </header>
    <div className="hm-bar">
      <span><b>{graphStats.nodes}</b> recorded events <span aria-hidden="true">·</span> <b>{graphStats.links}</b> documented links <span aria-hidden="true">·</span> <b>{humanDecisions}</b> human actions</span>
      <span>Memory: this tab only · export to preserve</span>
    </div>
    <div className="hm-layout">
      <section className="hm-primary" aria-label="Create and evolve an idea">
        <section className="hm-step" aria-labelledby="hm-seed-heading">
          <div className="hm-step-label">01 / SEED</div><h2 id="hm-seed-heading">Begin with your own thought.</h2>
          {seedEvent?<div className="hm-existing"><span>ORIGINAL IDEA / HUMAN</span><p>{seedEvent.text}</p></div>:
          <><label htmlFor="hm-seed">An idea, a question, a world, a feeling</label>
            <textarea id="hm-seed" value={seed} maxLength={MAX_HOLON_TEXT} onChange={e=>setSeed(e.target.value)} placeholder="What do you wish existed?" rows={3}/>
            <button className="hm-action" type="button" disabled={busy||!seed.trim()||!capacity} onClick={()=>void append('seed',seed,[], 'human','none',()=>setSeed(''))}>Create first holon →</button></>}
        </section>
        {seedEvent&&<section className="hm-step" aria-labelledby="hm-branch-heading">
          <div className="hm-step-label">02 / DIVERGE</div><h2 id="hm-branch-heading">Give the idea another dimension.</h2>
          <div className="hm-lenses" role="group" aria-label="Choose a thinking lens">{LENSES.map(l=>
            <button type="button" aria-pressed={lens===l.id} key={l.id} onClick={()=>setLens(l.id)} title={l.description}>{l.label}</button>)}</div>
          <div className="hm-gridtwo">
            <label htmlFor="hm-author">Where did this direction come from?
              <select id="hm-author" value={source} onChange={e=>setSource(e.target.value as 'human'|'model'|'agent')}>
                <option value="human">I thought of it</option><option value="model">Pasted from an LLM (unverified)</option><option value="agent">Pasted from an agent (unverified)</option>
              </select>
            </label>
            <label htmlFor="hm-parent">Extend which idea?
              <select id="hm-parent" value={branchParent||seedEvent.id} onChange={e=>setBranchParent(e.target.value)}>
                {visibleParents.map(e=><option key={e.id} value={e.id}>{labels[e.kind]} — {shorten(e.text,48)}</option>)}
              </select>
            </label>
          </div>
          {source!=='human'&&<p className="hm-warning">This is pasted external text. AEGIS has not contacted or authenticated any LLM or agent.</p>}
          <label htmlFor="hm-branch">Your next direction</label>
          <textarea id="hm-branch" value={branch} onChange={e=>setBranch(e.target.value)} maxLength={MAX_HOLON_TEXT} rows={3} placeholder="Explore a possibility, mechanism, challenge, or visual form…"/>
          <button className="hm-action" type="button" disabled={busy||!branch.trim()||!capacity} onClick={()=>void append('branch',branch,[branchParent||seedEvent.id],source,lens,()=>setBranch(''))}>Add direction →</button>
        </section>}
        {!!branches.length&&<section className="hm-step" aria-labelledby="hm-choose-heading">
          <div className="hm-step-label">03 / CHOOSE</div><h2 id="hm-choose-heading">Taste is a human decision.</h2>
          <p className="hm-helper">Choosing records your decision. A model suggestion never becomes an accepted direction automatically.</p>
          <div className="hm-branches">{branches.map(e=><div className="hm-branch" key={e.id}>
            <div className="hm-branch-head"><span>{e.actor==='human'?'HUMAN IDEA':'PASTED '+e.actor.toUpperCase()+' / UNVERIFIED'}</span><span>{e.lens}</span></div>
            <p>{e.text}</p>
            <button type="button" disabled={busy||selectedIds.has(e.id)||!capacity} onClick={()=>void append('select','Human selected: '+shorten(e.text,110),[e.id])}>{selectedIds.has(e.id)?'Chosen by human ✓':'Keep this direction +'}</button>
          </div>)}</div>
        </section>}
        {canWeave&&<section className="hm-step" aria-labelledby="hm-weave-heading">
          <div className="hm-step-label">04 / WEAVE</div><h2 id="hm-weave-heading">Combine what you chose.</h2>
          <p className="hm-helper">{selected.length} distinct directions selected. Weaving is a human-authored synthesis.</p>
          <label htmlFor="hm-weave">What emerges when these ideas meet?</label>
          <textarea id="hm-weave" value={weave} onChange={e=>setWeave(e.target.value)} rows={3} maxLength={MAX_HOLON_TEXT}/>
          <button className="hm-action" type="button" disabled={busy||!weave.trim()||!capacity} onClick={()=>void append('weave',weave,choices.slice(0,4).map(x=>x.id),'human','none',()=>setWeave(''))}>Record the synthesis →</button>
        </section>}
        {lastWeave&&<section className="hm-step" aria-labelledby="hm-artifact-heading">
          <div className="hm-step-label">05 / CRAFT</div><h2 id="hm-artifact-heading">Make an authored outcome.</h2>
          <label htmlFor="hm-artifact">Describe your artifact, prototype, manifesto or next experiment</label>
          <textarea id="hm-artifact" rows={3} maxLength={MAX_HOLON_TEXT} value={artifact} onChange={e=>setArtifact(e.target.value)}/>
          <button className="hm-action" type="button" disabled={busy||!artifact.trim()||!capacity} onClick={()=>void append('artifact',artifact,[lastWeave.id],'human','none',()=>setArtifact(''))}>Record artifact intent →</button>
          <p className="hm-helper">An intent record is not proof that an artifact was built or published.</p>
        </section>}
      </section>
      <aside className="hm-aside" aria-label="Holonic lineage and export">
        <div className="hm-evidence-title"><span>LIVE LOCAL TRACE / NOT MODEL TELEMETRY</span><h2>Every choice leaves a connection.</h2></div>
        <TraceGraph trace={trace}/>
        <div className="hm-ledger"><h3>Recorded events</h3>
          {trace.events.length===0?<p>No journal yet. Nothing was generated in your name.</p>:
            <ol>{trace.events.slice(-8).map(e=><li key={e.id}>
              <span>{String(e.seq).padStart(2,'0')} / {labels[e.kind]} / {e.actor==='human'?'HUMAN':'UNVERIFIED '+e.actor.toUpperCase()}</span>
              <p>{shorten(e.text,160)}</p>
            </li>)}</ol>}
        </div>
        <div className="hm-export">
          <h3>Your creative lineage</h3>
          <p>Export a portable JSON with parents, human decisions, origin labels and linked SHA-256 digests. Digests detect edits; they do not verify personal identity.</p>
          <code>LAST HASH: {shorten(lastHash,28)}</code>
          <button type="button" onClick={exportTrace}>Export JSON ↓</button>
          <label className="hm-import" htmlFor="hm-import-file">Import and verify JSON
            <input id="hm-import-file" type="file" accept=".json,application/json" onChange={e=>void importTrace(e)} disabled={busy}/>
          </label>
          <p className="hm-helper">Private, in-memory session. No automatic cloud sync, billing, model inference or persistent storage.</p>
        </div>
      </aside>
    </div>
    {error&&<p className="hm-feedback hm-error" role="alert">{error}</p>}
    {notice&&<p className="hm-feedback" role="status">{notice}</p>}
    <footer className="hm-footer">AEGIS Ω / HOLON MAXIMUS OPTIMUS <span>Human intent ≠ LLM proposal ≠ agent execution ≠ verifier receipt.</span></footer>
  </article>
}
