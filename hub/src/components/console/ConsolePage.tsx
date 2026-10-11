/**
 * AEGIS Ω Operator Console — evidence-native workbench.
 * This route no longer emits synthetic agent events or simulated approvals.
 * It observes public API responses, marks their limits and lets the operator
 * prepare a documented request; it never sends an execution without a key.
 */
import { useState, type ReactNode, type ChangeEvent } from 'react'
import { PLATFORM_ORIGIN, useConsoleController, type ConsoleSnapshot } from '../../lib/platformConsole.js'
import '../operator-workbench.css'

type View = 'overview' | 'interfaces' | 'evidence'
type Mode = 'analysis' | 'gtm' | 'revenue' | 'retention'
const links = {
  api: '/docs#collaborate',
  runtime: '/runtime',
  lab: 'https://aegis-quantum-integrity-mobile.tarikskalic33.workers.dev/',
  repo: 'https://github.com/Aegis-Omega/AEGIS-OMEGA',
}

function Label({ children }: { children: ReactNode }) { return <span className="op-overline">{children}</span> }
function Stamp({kind,children}: {kind: 'observed' | 'unknown' | 'blocked';children: ReactNode}) {
  return <span className={'op-stamp op-stamp-'+kind}>{children}</span>
}
function Copyable({value,label}: {value:string;label:string}) {
  const [result,setResult]=useState('')
  return <button type="button" className="op-copy" onClick={()=>{void navigator.clipboard.writeText(value).then(()=>setResult('Copied')).catch(()=>setResult('Clipboard unavailable'))}} aria-label={label}>{result||'Copy'} <span aria-hidden="true">↗</span></button>
}
function DataLine({label,value,mono=false}: {label:string;value:string;mono?:boolean}) {
  return <div className="op-dataline"><span>{label}</span><strong className={mono?'op-monospace':''}>{value}</strong></div>
}
function Empty({title,body}: {title:string;body:string}) {return <div className="op-empty"><div className="op-empty-mark" aria-hidden="true">∅</div><strong>{title}</strong><p>{body}</p></div>}

function ExecutionComposer() {
  const [objective,setObjective]=useState('')
  const [mode,setMode]=useState<Mode>('analysis')
  const [infer,setInfer]=useState<'demo'|'live'>('demo')
  const payload = JSON.stringify({objective:objective.trim(),mode,live:infer==='live'},null,2)
  const eligible = objective.trim().length > 0 && objective.trim().length <= 700
  return <section className="op-panel op-composer" aria-labelledby="op-compose-label">
    <div className="op-panel-head"><div><Label>02 / INVOCATION CONTRACT</Label><h2 id="op-compose-label">Prepare a governed request</h2></div><Stamp kind="unknown">NOT EXECUTED</Stamp></div>
    <p className="op-muted">Draft the JSON body for the documented <code>POST /platform/collaborate</code> endpoint. This console does not make paid/provider calls or handle API keys.</p>
    <label className="op-fieldlabel" htmlFor="op-objective">Objective <span>{objective.length}/700</span></label>
    <textarea id="op-objective" className="op-input op-textarea" value={objective} maxLength={701} onChange={(e:ChangeEvent<HTMLTextAreaElement>)=>setObjective(e.currentTarget.value)} placeholder="Describe the objective and constraints. No secrets or personal data." rows={3}/>
    <div className="op-controls">
      <label className="op-fieldlabel" htmlFor="op-mode">Mode<select id="op-mode" className="op-input" value={mode} onChange={(e:ChangeEvent<HTMLSelectElement>)=>setMode(e.currentTarget.value as Mode)}><option value="analysis">Analysis</option><option value="gtm">Go-to-market</option><option value="revenue">Revenue</option><option value="retention">Retention</option></select></label>
      <label className="op-fieldlabel" htmlFor="op-infer">Request inference<select id="op-infer" className="op-input" value={infer} onChange={(e:ChangeEvent<HTMLSelectElement>)=>setInfer(e.currentTarget.value as 'demo'|'live')}><option value="demo">Demo request (live: false)</option><option value="live">Provider request (live: true)</option></select></label>
    </div>
    <div className="op-code-header"><span>REQUEST.JSON · LOCAL DRAFT</span>{eligible?<Copyable key={payload} value={payload} label="Copy request JSON"/>:<span className="op-low">Enter an objective</span>}</div>
    <pre className="op-code" aria-label="Documented request body">{eligible?payload:'{\n  "objective": "…",\n  "mode": "analysis",\n  "live": false\n}'}</pre>
    <div className="op-cta-row"><a className="op-action" href={links.api}>Read invocation contract <span aria-hidden="true">↗</span></a><span className="op-muted">Preparation ≠ execution · key never requested here</span></div>
  </section>
}

function Observation({snap,busy,refresh}: {snap:ConsoleSnapshot;busy:boolean;refresh:()=>Promise<void>}) {
  const observed=snap.source==='live'
  const checked = snap.checked_at ? new Date(snap.checked_at).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}) : 'Not yet checked'
  return <section className="op-panel op-observe" aria-labelledby="op-state-label">
    <div className="op-panel-head"><div><Label>01 / RUNTIME OBSERVATION</Label><h2 id="op-state-label">Trust is a measured state.</h2></div><Stamp kind={observed?'observed':'unknown'}>{observed?'API RESPONDED':'NO EVIDENCE'}</Stamp></div>
    <p className="op-muted">{snap.reason}</p>
    <div className="op-signal"><div className={'op-signal-bar '+(observed?'op-signal-live':'')} aria-hidden="true"/><div><span>Source</span><strong>{observed?'Remote / observed':'Unavailable / unknown'}</strong></div><div><span>Last probe</span><strong>{checked}</strong></div></div>
    <div className="op-data-rows">
      <DataLine label="Platform availability" value={observed?(snap.status.available?'REPORTED AVAILABLE':'REPORTED UNAVAILABLE'):'UNKNOWN'}/>
      <DataLine label="Contract" value={observed?'Reported v'+snap.status.contract_version:'NOT OBSERVED'}/>
      <DataLine label="Upstream event time" value={observed?(snap.upstream_at||'NOT REPORTED'):'UNKNOWN'} mono/>
      <DataLine label="Agent registry" value={observed?`${snap.status.total_agents} reported`:'UNKNOWN'}/>
      <DataLine label="Audit-chain verification" value={observed&&snap.status.chain_valid===false?'REPORTED INVALID':'NOT INDEPENDENTLY VERIFIED'}/>
    </div>
    <button className="op-reload" disabled={busy} onClick={()=>{void refresh()}} type="button" aria-busy={busy}>{busy?'Checking…':'Recheck connection'} <span aria-hidden="true">↻</span></button>
    <p className="op-footnote">A backend-reported chain verdict is not proof of independent cryptographic replay. No green authority state is inferred.</p>
  </section>
}

function Verification({snap}: {snap:ConsoleSnapshot}) {
  const observed=snap.source==='live'
  const json=JSON.stringify({schema:'AEGIS_OPERATOR_OBSERVATION_V1',generated_at:new Date().toISOString(),authority:'UNSIGNED_OBSERVATION_NOT_ADMISSION',source:snap.source,checked_at:snap.checked_at,reason:snap.reason,status:snap.status,calibration:snap.calibration,tools_observed:snap.tools_observed,checks:snap.checks,tools:snap.tools},null,2)
  function download(){const blob=new Blob([json],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='aegis-operator-observation.json';a.click();window.setTimeout(()=>URL.revokeObjectURL(url),2000)}
  return <div className="op-proof-layout">
    <section className="op-panel"><div className="op-panel-head"><div><Label>VERIFICATION / REASONS</Label><h2>Evidence ledger</h2></div><Stamp kind="unknown">NOT ADMITTED</Stamp></div><div className="op-checks">{snap.checks.map((check,i)=><div className="op-check" key={check.label}><span className="op-check-index">{String(i+1).padStart(2,'0')}</span><div><strong>{check.label}</strong><p>{check.reason}</p></div><span className={'op-check-verdict '+(check.ok?'op-check-observed':'')}>{check.ok?'OBSERVED':check.reason.includes('INVALID')?'REPORTED INVALID':check.reason.startsWith('NOT QUERIED')?'NOT QUERIED':'UNVERIFIED'}</span></div>)}</div></section>
    <section className="op-panel"><Label>EXPORT / LOCAL</Label><h2>Observation receipt</h2><p className="op-muted">Export exactly what this browser observed. The JSON is neither signed nor a production-attested evidence bundle.</p><div className="op-data-rows"><DataLine label="Source" value={observed?'public status only':'unavailable'}/><DataLine label="Checked at" value={snap.checked_at||'not checked'} mono/><DataLine label="Provider tools" value={snap.tools_observed?`${snap.tools.length} reported`:'NOT QUERIED — AUTH REQUIRED'}/></div><button className="op-action op-download" onClick={download}>Export unsigned observation <span aria-hidden="true">↓</span></button></section>
  </div>
}

function Interfaces({snap}: {snap:ConsoleSnapshot}) {
  const [query,setQuery]=useState('')
  const tools=snap.tools_observed?snap.tools.filter(t=>(t.api_name+' '+t.capabilities.join(' ')).toLowerCase().includes(query.trim().toLowerCase())):[]
  return <div className="op-proof-layout">
    <section className="op-panel"><div className="op-panel-head"><div><Label>REPORTED TOOL REGISTRY</Label><h2>Connected interfaces</h2></div><Stamp kind={snap.tools_observed?'observed':'unknown'}>{snap.tools_observed?'API OBSERVED':'NOT QUERIED'}</Stamp></div>
      {snap.tools_observed?<><label htmlFor="op-filter" className="op-fieldlabel">Filter by provider or capability</label><input id="op-filter" className="op-input" value={query} onChange={(e:ChangeEvent<HTMLInputElement>)=>setQuery(e.currentTarget.value)} placeholder="Find an endpoint…"/><div className="op-tool-list">{tools.length?tools.map((t,i)=><div className="op-tool" key={t.api_name+'-'+i}><span className="op-tool-symbol">↗</span><div><strong>{t.api_name}</strong><small>{t.capabilities.join(' · ')}</small></div><span>{t.tier_required}</span></div>):<Empty title="No matching interfaces" body="No reported tool matches the filter. This is not evidence that the provider is down."/>}</div></>:<Empty title="Registry unavailable" body="Tool registry requires authorized credentials. This public console does not request secrets or probe protected endpoints."/>}
    </section>
    <section className="op-panel"><Label>OPEN INSTRUMENTS</Label><h2>Go to the source</h2><p className="op-muted">Links are real destinations, not health checks or claims that the service will respond.</p><div className="op-destinations"><a href={links.lab} target="_blank" rel="noopener noreferrer"><span>01 / QUANTUM</span><strong>Quantum Integrity Lab</strong><small>Edge PSD arithmetic · physics replay archive</small><b>↗</b></a><a href={links.repo} target="_blank" rel="noopener noreferrer"><span>02 / CODE</span><strong>AEGIS source</strong><small>Commits · pull requests · build evidence</small><b>↗</b></a><a href={links.runtime}><span>03 / RUNTIME</span><strong>Constitutional mechanism</strong><small>Browser demonstrations · not signed receipts</small><b>→</b></a></div></section>
  </div>
}

export function ConsolePage(){
  const {snap,busy,refresh}=useConsoleController()
  const [view,setView]=useState<View>('overview')
  const live=snap.source==='live'
  return <div className="op-console">
    <div className="op-topline"><span>AEGIS Ω / OPERATOR SYSTEM</span><span className="op-line-right">CONTROL SURFACE 01 · <b>NO AUTONOMOUS EXECUTION</b></span></div>
    <header className="op-intro"><div><Label>NOUS / CONTROL ROOM</Label><h1>Operate by <em>evidence.</em></h1><p>Remote state when observed. Unknown when absent. A command surface that refuses to turn demonstrations into authority.</p></div><div className="op-intro-state"><span>PLATFORM TELEMETRY</span><strong className={live?'op-state-live':''}>{live?'OBSERVED':'UNKNOWN'}</strong><small>{live?'Reported data · not independently verified':'No authenticated live execution asserted'}</small></div></header>
    <nav className="op-tabs" aria-label="Operator workspace">
      {([['overview','01','Operate'],['interfaces','02','Interfaces'],['evidence','03','Evidence']] as const).map(([id,n,label])=><button key={id} type="button" onClick={()=>setView(id)} aria-current={view===id?'page':undefined} className={view===id?'op-tab-active':''}><span>{n}</span>{label}</button>)}
      <a href="/docs">Developer contract <span aria-hidden="true">↗</span></a>
    </nav>
    <div className="op-tab-body">
      {view==='overview'&&<div className="op-main-layout"><Observation snap={snap} busy={busy} refresh={refresh}/><ExecutionComposer/></div>}
      {view==='interfaces'&&<Interfaces snap={snap}/>}
      {view==='evidence'&&<Verification snap={snap}/>}
    </div>
    <footer className="op-bottomline"><span>UNSIGNED OPERATOR PROJECTION</span><span>DATA ≠ CLAIM · CLAIM ≠ PROOF · PROOF ≠ AUTHORITY</span></footer>
  </div>
}