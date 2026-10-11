import { useEffect, useState, type ReactNode } from 'react'
import './holon-glass.css'

/**
 * AEGIS Ω | HOLON GLASS — one optical / navigational system for the hub.
 * Public presentation layer only. Existing operator, payments, console, tools and
 * runtime components are rendered unmodified on their respective routes.
 */

const MAIN = [
  { href: '/', label: 'Overview' },
  { href: '/platform', label: 'Platform' },
  { href: '/console', label: 'Command' },
  { href: '/runtime', label: 'Runtime' },
  { href: '/docs', label: 'Developers' },
  { href: '/pricing', label: 'Access' },
]
const QUANTUM_URL = 'https://aegis-quantum-integrity-mobile.tarikskalic33.workers.dev/'

function Sigil({ size = 37 }: { size?: number }) {
  return <svg role="img" aria-label="AEGIS Omega" width={size} height={size} viewBox="0 0 64 64" fill="none">
    <defs><linearGradient id="hg-mark" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#E8F8FF"/><stop offset=".5" stopColor="#82BFFF"/><stop offset="1" stopColor="#6282FF"/></linearGradient></defs>
    <path d="M32 6 56 51H44L32 26 20 51H8L32 6Z" stroke="url(#hg-mark)" strokeWidth="2" fill="url(#hg-mark)" fillOpacity=".14"/>
    <path d="M19 45h26M32 26v24M17 53h30" stroke="url(#hg-mark)" strokeWidth="1.4" opacity=".85"/>
    <circle cx="32" cy="26" r="2.4" fill="#C3E9FF"/><path d="M2 57h60" stroke="#4A8BC7" strokeOpacity=".35"/>
  </svg>
}
function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <svg width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" viewBox="0 0 24 24"><path d={diagonal ? 'M5 19 19 5M8 5h11v11' : 'M4 12h16m-7-7 7 7-7 7'}/></svg>
}
function Glyph({ kind }: { kind: string }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.35, strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const }
  return <svg viewBox="0 0 32 32" width="23" height="23" aria-hidden="true" {...common}>
    {kind === 'neural' && <><path d="M5 16 13 6l12 5-3 15-13-2Z M5 16l12 1 8-6M17 17l5 9M13 6l4 11"/><circle cx="5" cy="16" r="2"/><circle cx="13" cy="6" r="2"/><circle cx="25" cy="11" r="2"/><circle cx="22" cy="26" r="2"/></>}
    {kind === 'math' && <><path d="M4 24 11 10l6 13 7-17 4 12M4 27h24"/><circle cx="11" cy="10" r="2"/></>}
    {kind === 'dna' && <><path d="M9 3c19 7-11 19 9 26M23 3C4 10 34 22 14 29M10 8h12M8 14h16M9 20h14M12 26h8"/></>}
    {kind === 'shield' && <><path d="M16 3 27 8v8c0 8-6 12-11 14C11 28 5 24 5 16V8L16 3Z M10 17l4 4 8-9"/></>}
    {kind === 'terminal' && <><path d="M4 8h24v17H4Z M8 12l5 4-5 4M16 21h7"/></>}
    {kind === 'layers' && <><path d="m16 3 13 7-13 7L3 10 16 3Zm-13 13 13 7 13-7M3 22l13 7 13-7"/></>}
  </svg>
}

function Nav({ path = '/' }: { path?: string }) {
  const [open, setOpen] = useState(false)
  useEffect(() => { setOpen(false) }, [path])
  return <header className="hg-nav-wrap"><div className="hg-nav">
    <a className="hg-brand" href="/" aria-label="AEGIS Ω — home"><Sigil/><span className="hg-brand-word"><strong>AEGIS <em>Ω</em></strong><small>SOVEREIGN INTELLIGENCE</small></span></a>
    <nav className={'hg-links'+(open ? ' hg-links-open' : '')} aria-label="Primary navigation">
      {MAIN.map(item => <a key={item.href} href={item.href} aria-current={path===item.href?'page':undefined}>{item.label}</a>)}
      <a className="hg-links-mobile-extra" href="/compliance">Governance</a>
      <a className="hg-links-mobile-extra" href="/tools">Tools</a>
    </nav>
    <div className="hg-nav-actions"><span className="hg-nav-status"><i/> EVIDENCE FIRST</span><a href="/pricing" className="hg-nav-cta">Enter AEGIS <Arrow diagonal/></a><button className="hg-menu-toggle" type="button" onClick={()=>setOpen(!open)} aria-expanded={open} aria-label={open?'Close navigation':'Open navigation'}>{open?'✕':'☰'}</button></div>
  </div></header>
}

function Orbit() {
  return <div className="hg-orbit" aria-hidden="true">
    <div className="hg-orbit-glow"/><div className="hg-orbit-grid"/>
    <svg viewBox="0 0 580 580" className="hg-orbit-svg"><defs>
      <linearGradient id="hg-curve" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#476EFA"/><stop offset=".37" stopColor="#C5F2FF"/><stop offset=".69" stopColor="#61A6F4"/><stop offset="1" stopColor="#AC81FE"/></linearGradient>
      <radialGradient id="hg-core"><stop stopColor="#ACDAFF" stopOpacity=".5"/><stop offset=".4" stopColor="#16589C" stopOpacity=".28"/><stop offset="1" stopColor="#060D1B" stopOpacity="0"/></radialGradient>
      <filter id="hg-glow"><feGaussianBlur stdDeviation="5"/></filter>
    </defs>
    <circle cx="290" cy="290" r="242" fill="url(#hg-core)"/>
    {[83,133,184,232].map((r,i)=><circle key={r} cx="290" cy="290" r={r} fill="none" stroke="#72A8EC" strokeWidth=".9" strokeOpacity={.26-i*.025} strokeDasharray={i%2?'2 11':undefined}/>)}
    <g className="hg-orbit-turn hg-orbit-turn-a"><ellipse cx="290" cy="290" rx="238" ry="93" stroke="url(#hg-curve)" strokeWidth="1.8"/><ellipse cx="290" cy="290" rx="223" ry="129" stroke="#6FBEF9" strokeOpacity=".42" strokeWidth="1"/></g>
    <g className="hg-orbit-turn hg-orbit-turn-b"><ellipse cx="290" cy="290" rx="252" ry="89" stroke="url(#hg-curve)" strokeWidth="1.25" transform="rotate(60 290 290)"/><ellipse cx="290" cy="290" rx="238" ry="123" stroke="#97B6FF" strokeOpacity=".45" strokeWidth=".8" transform="rotate(-42 290 290)"/></g>
    <g stroke="#74B7EF" strokeOpacity=".4" strokeWidth=".9"><path d="M92 331 176 171 320 223 461 152M92 331l148 103 80-211 103 177M176 171l64 263 221-282"/></g>
    <path d="M92 331 176 171 320 223 461 152" stroke="#8BCDFD" strokeWidth="5" opacity=".55" filter="url(#hg-glow)"/>
    <g fill="#BAE9FF" stroke="#448FEC" strokeWidth="1">{[[92,331],[176,171],[320,223],[461,152],[240,434],[423,400]].map(([x,y],i)=><circle key={i} cx={x} cy={y} r={i%2?5:4}/>)}</g>
    <g className="hg-orbit-center"><path d="M290 205 360 341H334l-44-86-44 86h-26z" fill="#86C5FE" fillOpacity=".12" stroke="url(#hg-curve)" strokeWidth="2.1"/><path d="M249 322h82" stroke="#AEDFFF" strokeWidth="2"/><circle cx="290" cy="287" r="11" fill="#D5F4FF" opacity=".8" filter="url(#hg-glow)"/></g>
    <g stroke="#8BBDE9" strokeOpacity=".35"><path d="M290 12v43M290 528v39M12 290h43M525 290h43"/></g>
    </svg>
    <div className="hg-orbit-caption hg-caption-top">HOLON / ∞<br/>MULTISCALE COHERENCE</div><div className="hg-orbit-caption hg-caption-bottom">MATHEMATICS · BIOLOGY · INTELLIGENCE</div>
  </div>
}

const DOMAINS = [
  { id: '01', glyph: 'neural', title: 'Sovereign runtime', detail: 'Authority-bounded execution, governed agents and a verifiable decision trail.', tag: 'SYSTEM / GOVERNANCE', href: '/runtime' },
  { id: '02', glyph: 'math', title: 'Frontier mathematics', detail: 'Formal conjectures, falsifiable propositions and proof-producing research.', tag: 'SCIENCE / FORMAL', href: 'https://github.com/tarikskalic33/formal-conjectures' },
  { id: '03', glyph: 'dna', title: 'Computational biology', detail: 'Genomic, structural and spectral research with explicit source provenance.', tag: 'SCIENCE / GENOMICS', href: 'https://github.com/Aegis-Omega/AEGIS-OMEGA' },
  { id: '04', glyph: 'shield', title: 'Verification systems', detail: 'Replay, cryptographic lineage and epistemic admission boundaries.', tag: 'EVIDENCE / AUDIT', href: '/compliance' },
]

const STAGES = [
  { stage: '01', title: 'Acquire', text: 'Original sources, datasets, model assumptions and head-bound code. No synthetic source substitution.' },
  { stage: '02', title: 'Compute', text: 'Reproducible experiments in a declared runtime. Failures remain first-class results.' },
  { stage: '03', title: 'Challenge', text: 'Independent verification, adversarial counterexamples and negative controls.' },
  { stage: '04', title: 'Admit', text: 'Capability advances only as far as verified evidence permits. Unverified claims stay blocked.' },
]

async function digest(s: string): Promise<string> {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))
  return Array.from(new Uint8Array(d)).map(v=>v.toString(16).padStart(2,'0')).join('')
}

function EvidenceDemo() {
  const [corrupted, setCorrupted] = useState(false)
  const [hash, setHash] = useState<string|null>(null)
  const [status, setStatus] = useState<'checking'|'valid'|'invalid'|'unavailable'>('checking')
  useEffect(()=>{
    let active=true
    setStatus('checking')
    const records=['genesis:source-bound','experiment:bounded-replay','decision:pending-verification']
    async function run(){
      try {
        let h='0'.repeat(64)
        for(let i=0;i<records.length;i++)h=await digest(h+'|'+i+'|'+records[i])
        const expected=h
        h='0'.repeat(64)
        for(let i=0;i<records.length;i++){const value=corrupted&&i===1?'experiment:modified-after-seal':records[i];h=await digest(h+'|'+i+'|'+value)}
        if(active){setHash(h);setStatus(h===expected?'valid':'invalid')}
      } catch{if(active){setStatus('unavailable');setHash(null)}}
    }
    void run();return()=>{active=false}
  },[corrupted])
  return <div className="hg-evidence-demo hg-glass">
    <div className="hg-demo-heading"><div><span className="hg-mono hg-eyebrow">IN-BROWSER DEMONSTRATION / SHA-256</span><h3>Truth leaves a trace.</h3></div><span className={'hg-seal hg-seal-'+status}>{status==='valid'?'CHAIN INTACT':status==='invalid'?'CHAIN BROKEN':status.toUpperCase()}</span></div>
    <div className="hg-ledger">
      {['SOURCE / GENESIS','COMPUTE / REPLAY','VERDICT / BOUNDARY'].map((name,i)=><div className="hg-ledger-row" key={name}><span className="hg-ledger-num">0{i}</span><span>{name}</span><span className={corrupted&&i===1?'hg-corrupt':''}>{corrupted&&i===1?'MODIFIED INPUT':'RECORDED'}</span></div>)}
    </div>
    <div className="hg-ledger-foot"><div><small>Computed chain head</small><code>{hash?hash.slice(0,19)+'…':'—'}</code></div><button type="button" className="hg-text-button" onClick={()=>setCorrupted(v=>!v)}>{corrupted?'Restore record':'Tamper with record'} <Arrow/></button></div>
    <p className="hg-demo-disclaimer">Independent local sample; not a production runtime receipt. Tampering recomputes the SHA-256 chain and changes the verification verdict.</p>
  </div>
}

function SiteFooter() {
  return <footer className="hg-footer"><div className="hg-footer-top"><div className="hg-footer-brand"><Sigil size={33}/><div><b>AEGIS Ω</b><span>INTELLIGENCE · RESEARCH · VERIFICATION</span></div></div><div className="hg-footer-nav"><a href="/platform">Platform</a><a href="/docs">Developers</a><a href="/compliance">Governance</a><a href="/tools">Tools</a><a href="/pricing">Access</a></div></div><div className="hg-footer-bottom"><span>© 2026 AEGIS Omega Labs · A sovereign research initiative</span><span>VERIFIABILITY &gt; ASSERTION &nbsp; · &nbsp; NO CLAIM BEYOND EVIDENCE</span></div></footer>
}

export function HolonHome() {
  const [focus,setFocus] = useState<'research'|'runtime'|'trust'>('research')
  const focusData = {
    research: { label:'RESEARCH OS', title:'Explore the unknown. Preserve the proof.', detail:'Unify mathematics, genomics, scientific simulation and independent evaluation without mixing hypothesis with established result.', bullets:['Evidence-native experiments','Cross-domain research atlas','Reproducible scientific artifacts'],href:QUANTUM_URL,button:'Open Quantum Integrity Lab' },
    runtime: { label:'SOVEREIGN RUNTIME', title:'Capability without uncontrolled authority.', detail:'Coordinate model-assisted work with constitutional gates and explicit limits on actions, identity, provenance and deployment.',bullets:['Agentic execution envelopes','Separation of capability and authority','Inspectable runtime boundaries'],href:'/console',button:'Inspect command console' },
    trust: { label:'PROOF SYSTEM', title:'Trust is an executable condition.',detail:'Treat artifacts, independent checks, negative controls and exact-head verification as the record—not polished claims of autonomous success.',bullets:['Tamper-evident records','Epistemic tier separation','Fail-closed admission'],href:'/runtime',button:'Explore the runtime' },
  }[focus]
  return <div className="hg-home">
    <section className="hg-hero hg-section hg-content" id="top"><div className="hg-hero-copy"><span className="hg-eyebrow"><span className="hg-dot"/> AEGIS OMEGA LABS &nbsp; / &nbsp; SOVEREIGN RESEARCH INFRASTRUCTURE</span><h1>Frontier<br/><span>intelligence.</span><br/>Verified.</h1><p className="hg-hero-desc">A unified cognitive and scientific operating system where research, computation and autonomous execution are constrained by their evidence.</p><div className="hg-hero-actions"><a className="hg-btn hg-btn-primary" href="/platform">Explore the platform <Arrow/></a><a className="hg-btn hg-btn-secondary" href="/runtime">Inspect verification <Arrow diagonal/></a></div><div className="hg-hero-note"><span className="hg-cross">✧</span> SOVEREIGN INTELLIGENCE &nbsp; / &nbsp; EVIDENCE BEFORE AUTHORITY</div></div><Orbit/></section>
    <section className="hg-facts hg-content" aria-label="Principles"><div><small>THE PRINCIPLE</small><b>Capability ≤ verifiability</b></div><div><small>THE SYSTEM</small><b>Research · Compute · Challenge · Admit</b></div><div><small>THE BOUNDARY</small><b>Unknown stays unknown</b></div></section>
    <section className="hg-section hg-content hg-intro" id="vision"><div className="hg-section-tag">01 — INTELLIGENCE ARCHITECTURE</div><div className="hg-intro-body"><h2>One collective intelligence.<br/><span>Multiple horizons of inquiry.</span></h2><p>Not another collection of disconnected copilots. AEGIS is organized around shared context, evidence-bearing computation and constrained operations. Its claims must survive review before they become authority.</p></div></section>
    <section className="hg-domains hg-content" id="domains">{DOMAINS.map(d=><a className="hg-domain hg-glass" href={d.href} key={d.id}><div className="hg-domain-top"><span className="hg-mono">{d.id} / 04</span><span className="hg-domain-arrow"><Arrow diagonal/></span></div><div className="hg-domain-icon"><Glyph kind={d.glyph}/></div><h3>{d.title}</h3><p>{d.detail}</p><div className="hg-domain-tag">{d.tag}</div></a>)}</section>
    <section className="hg-section hg-content hg-focus" id="research"><div className="hg-section-tag">02 — THE WORKING SYSTEM</div><div className="hg-focus-shell hg-glass"><div className="hg-focus-menu" role="tablist" aria-label="System capability"><button type="button" role="tab" aria-selected={focus==='research'} onClick={()=>setFocus('research')} className={focus==='research'?'is-active':''}><Glyph kind="math"/> ResearchOS <span>01</span></button><button type="button" role="tab" aria-selected={focus==='runtime'} onClick={()=>setFocus('runtime')} className={focus==='runtime'?'is-active':''}><Glyph kind="neural"/> Runtime <span>02</span></button><button type="button" role="tab" aria-selected={focus==='trust'} onClick={()=>setFocus('trust')} className={focus==='trust'?'is-active':''}><Glyph kind="shield"/> Verification <span>03</span></button></div><div className="hg-focus-body" role="tabpanel"><div className="hg-focus-copy"><span className="hg-eyebrow">{focusData.label} / SELECTED</span><h2>{focusData.title}</h2><p>{focusData.detail}</p><ul>{focusData.bullets.map(b=><li key={b}>{b}</li>)}</ul><a className="hg-btn hg-btn-primary" href={focusData.href}>{focusData.button}<Arrow/></a></div><div className="hg-focus-visual" aria-hidden="true"><div className="hg-holon hg-holon-a"/><div className="hg-holon hg-holon-b"/><div className="hg-holon hg-holon-c"/><div className="hg-holon-core"><Sigil size={74}/></div><span className="hg-holon-lbl hg-holon-lbl-a">MEMORY / CONTEXT</span><span className="hg-holon-lbl hg-holon-lbl-b">OBSERVE / VERIFY</span><span className="hg-holon-lbl hg-holon-lbl-c">COMPUTE / GOVERN</span></div></div></div></section>
    <section className="hg-section hg-content hg-proof" id="evidence"><div className="hg-section-tag">03 — THE EVIDENCE SPINE</div><div className="hg-section-head"><div><h2>Nothing outranks<br/><span>its proof.</span></h2><p>Auditability is not an illustration. It is the condition under which a capability may move forward.</p></div><a className="hg-small-link" href="/compliance">Governance specification <Arrow diagonal/></a></div><div className="hg-evidence-grid"><div className="hg-proof-steps">{STAGES.map(s=><div className="hg-step" key={s.stage}><span>{s.stage}</span><div><h3>{s.title}</h3><p>{s.text}</p></div><Arrow/></div>)}</div><EvidenceDemo/></div></section>
    <section className="hg-section hg-content hg-labs" id="labs"><div className="hg-section-tag">04 — OPEN RESEARCH SURFACES</div><div className="hg-section-head"><div><h2>Research you can <span>inspect.</span></h2><p>Accessible instruments, visible limitations, and pathways from raw observations to falsifiable claims.</p></div></div><div className="hg-lab-grid"><a href={QUANTUM_URL} className="hg-lab-feature hg-glass"><div className="hg-lab-chip">PUBLIC MOBILE INSTRUMENT · PSD</div><div className="hg-lab-geometry"><span>Δω</span><svg viewBox="0 0 460 160" aria-hidden="true"><defs><linearGradient id="hg-signal" x1="0" x2="1"><stop stopColor="#417BE4"/><stop offset=".5" stopColor="#9DDFFF"/><stop offset="1" stopColor="#AC8AFF"/></linearGradient></defs><path d="M0 80h460M0 40h460M0 120h460" stroke="#5785B2" strokeOpacity=".24" strokeDasharray="2 7"/><polyline points="0,80 27,78 51,74 70,43 85,79 121,84 141,28 163,83 191,71 212,93 231,16 251,94 278,81 306,51 326,83 360,75 378,24 400,80 430,78 460,80" fill="none" stroke="url(#hg-signal)" strokeWidth="2.7"/></svg></div><h3>Quantum Integrity Lab</h3><p>Live PSD-safe spectral computations, traceable physical replay aggregates and bounded discoveries. Built for mobile.</p><span className="hg-open-link">Launch the laboratory <Arrow diagonal/></span></a><div className="hg-lab-stack"><a className="hg-small-lab hg-glass" href="/console"><div className="hg-small-lab-icon"><Glyph kind="terminal"/></div><div><span className="hg-mono">OPERATOR SURFACE</span><h3>Command Console</h3><p>System state, bounded agent workflows and explicit provenance.</p></div><Arrow diagonal/></a><a className="hg-small-lab hg-glass" href="/docs"><div className="hg-small-lab-icon"><Glyph kind="layers"/></div><div><span className="hg-mono">INTEGRATION SURFACE</span><h3>Developer API</h3><p>Contracts and interfaces for governed execution.</p></div><Arrow diagonal/></a></div></div></section>
    <section className="hg-section hg-content hg-enterprise" id="enterprise"><div><span className="hg-section-tag">05 — BUILT FOR SERIOUS SYSTEMS</span><h2>From frontier research<br/>to governed operations.</h2><p>Enterprise quality starts with a clear separation between demonstration, validation and deployment. Explore the available API, research tools and compliance model.</p><div className="hg-hero-actions"><a href="/pricing" className="hg-btn hg-btn-primary">Explore access <Arrow/></a><a href="/docs" className="hg-btn hg-btn-secondary">Read API contracts <Arrow diagonal/></a></div></div><div className="hg-enterprise-sigil" aria-hidden="true"><Sigil size={184}/></div></section>
    <SiteFooter/>
  </div>
}

const ROUTE_META: Record<string, {kicker:string;title:string;description:string}> = {
  platform:{kicker:'AEGIS / PLATFORM',title:'Sovereign execution.',description:'Agents, orchestration and bounded capabilities.'},
  console:{kicker:'AEGIS / COMMAND',title:'Operator console.',description:'Inspectable system state and constrained execution.'},
  runtime:{kicker:'AEGIS / CONSTITUTIONAL',title:'Runtime integrity.',description:'Interactive verification in a declared scope.'},
  docs:{kicker:'AEGIS / DEVELOPERS',title:'API reference.',description:'Contracts, authorization and integrations.'},
  pricing:{kicker:'AEGIS / ACCESS',title:'Access & deployment.',description:'Explicit plans, credentials and terms.'},
  compliance:{kicker:'AEGIS / GOVERNANCE',title:'Verification & policy.',description:'Evidence, accountability and regulatory boundaries.'},
  tools:{kicker:'AEGIS / INSTRUMENTS',title:'Tools & applications.',description:'Purpose-built computational interfaces.'},
  'claim-sponsor':{kicker:'AEGIS / ACCOUNT',title:'Sponsor entitlement.',description:'Secure access provisioning.'},
}
export function HolonRoute({ route, children }: { route: string; children: ReactNode }) {
  const meta=ROUTE_META[route]
  return <div className={'hg-site hg-route hg-route-'+route}><Nav path={'/'+route}/><div className="hg-route-overline hg-content"><span className="hg-eyebrow">{meta?.kicker||'AEGIS OMEGA'}</span><span className="hg-route-context">{meta?.description||''}</span></div><main className="hg-legacy-content">{children}</main><SiteFooter/></div>
}
export function HolonHomepage() {return <div className="hg-site hg-site-home"><Nav path="/"/><main><HolonHome/></main></div>}