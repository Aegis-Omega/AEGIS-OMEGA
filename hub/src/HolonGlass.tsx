import { useEffect, useRef, useState, type ReactNode, type ChangeEvent } from 'react'
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
  useEffect(() => {
    if (!open) return
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [open])
  return <><a className="hg-skip-link" href="#hg-main">Skip to content</a><header className="hg-nav-wrap"><div className="hg-nav">
    <a className="hg-brand" href="/" aria-label="AEGIS Ω — home"><Sigil/><span className="hg-brand-word"><strong>AEGIS <em>Ω</em></strong><small>SOVEREIGN INTELLIGENCE</small></span></a>
    <nav id="hg-primary-nav" className={'hg-links'+(open ? ' hg-links-open' : '')} aria-label="Primary navigation">
      {MAIN.map(item => <a key={item.href} href={item.href} aria-current={path===item.href?'page':undefined}>{item.label}</a>)}
      <a className="hg-links-mobile-extra" href="/compliance">Governance</a>
      <a className="hg-links-mobile-extra" href="/tools">Tools</a>
    </nav>
    <div className="hg-nav-actions"><span className="hg-nav-status">EVIDENCE-BOUND</span><a href="/pricing" className="hg-nav-cta">Enter AEGIS <Arrow diagonal/></a><button className="hg-menu-toggle" type="button" onClick={()=>setOpen(!open)} aria-controls="hg-primary-nav" aria-expanded={open} aria-label={open?'Close navigation':'Open navigation'}>{open?'✕':'☰'}</button></div>
  </div></header></>
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

function ArtifactVerifier() {
  const [selected, setSelected] = useState<File | null>(null)
  const [expected, setExpected] = useState('')
  const [computed, setComputed] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle'|'running'|'computed'|'matched'|'mismatch'|'error'>('idle')
  const [message, setMessage] = useState('No file selected. Files are processed locally in this browser.')
  const [copyStatus, setCopyStatus] = useState('')
  const revision = useRef(0)
  const reset = () => {revision.current++;setComputed(null);setStatus('idle');setMessage('Ready to calculate a new digest.');setCopyStatus('')}
  const MAX_FILE = 32 * 1024 * 1024
  async function verify() {
    if (!selected) {setStatus('error');setMessage('Choose a local file first.');return}
    if (selected.size > MAX_FILE) {setStatus('error');setMessage('Maximum 32 MiB. Large files require a streaming verifier.');return}
    const reference=expected.trim().replace(/^sha256:/i,'').toLowerCase()
    if (reference && !/^[0-9a-f]{64}$/.test(reference)) {setStatus('error');setMessage('Expected SHA-256 must contain exactly 64 hexadecimal characters.');return}
    const runRevision=revision.current
    setStatus('running');setMessage('Computing SHA-256 locally…')
    try {
      if (!globalThis.crypto?.subtle) throw new Error('Secure-context crypto is unavailable.')
      const buffer=await selected.arrayBuffer()
      const hashed=await crypto.subtle.digest('SHA-256',buffer)
      const actual=Array.from(new Uint8Array(hashed), b=>b.toString(16).padStart(2,'0')).join('')
      if (runRevision !== revision.current) return // input changed during hashing: discard stale result
      setComputed(actual)
      setStatus(reference?(reference===actual?'matched':'mismatch'):'computed')
      setMessage(reference?(reference===actual?'The file matches the supplied expected digest.':'Digest mismatch: this file is not byte-identical to the declared reference.'):'Digest computed. Supply a trusted expected SHA-256 to perform a comparison.')
    } catch(e) {if (runRevision !== revision.current) return;setStatus('error');setComputed(null);setMessage(e instanceof Error?e.message:'Unable to compute this digest.')}
  }
  async function copyHash() {
    if (!computed) return
    try {await navigator.clipboard.writeText(computed);setCopyStatus('Copied')} catch {setCopyStatus('Copy unavailable — select the hash below')}
  }
  return <section className="hg-evidence-demo hg-glass hg-artifact-verifier" aria-labelledby="hg-verifier-heading">
    <div className="hg-demo-heading"><div><span className="hg-mono hg-eyebrow">LIVE / DEVICE-LOCAL SHA-256</span><h3 id="hg-verifier-heading">Verify the bytes.</h3></div>
      <span role="status" aria-live="polite" className={'hg-seal hg-seal-'+(status==='matched'?'valid':status==='mismatch'?'invalid':'checking')}>
        {status==='matched'?'DIGEST MATCH':status==='mismatch'?'MISMATCH':status==='computed'?'HASHED / UNVERIFIED':status==='running'?'COMPUTING':status==='error'?'INPUT ERROR':'AWAITING FILE'}
      </span>
    </div>
    <p className="hg-verifier-intro">Calculate a real cryptographic digest of a local file. Compare it to a source-published hash. No upload, telemetry or model inference.</p>
    <label className="hg-verifier-label" htmlFor="hg-evidence-file">Evidence artifact · maximum 32 MiB</label>
    <input id="hg-evidence-file" className="hg-verifier-input" type="file" onChange={(event: ChangeEvent<HTMLInputElement>)=>{setSelected(event.currentTarget.files?.[0]||null);reset()}} />
    {selected&&<p className="hg-verifier-filename">Selected: {selected.name} · {selected.size.toLocaleString()} bytes</p>}
    <label className="hg-verifier-label" htmlFor="hg-expected-sha">Expected SHA-256 · optional, from a trusted source</label>
    <input id="hg-expected-sha" className="hg-verifier-input hg-hash-input" type="text" autoCapitalize="off" autoCorrect="off" spellCheck={false} autoComplete="off" value={expected} onChange={(event: ChangeEvent<HTMLInputElement>)=>{setExpected(event.currentTarget.value);reset()}} placeholder="64 hex characters or sha256:…" aria-describedby="hg-verifier-guidance" />
    <div className="hg-verifier-actions"><button type="button" onClick={()=>void verify()} disabled={status==='running'} className="hg-btn hg-btn-primary">{status==='running'?'Calculating…':'Calculate / compare'} <Arrow/></button>{computed&&<button type="button" onClick={()=>void copyHash()} className="hg-text-button">Copy digest <Arrow/></button>}</div>
    <div className="hg-verifier-result" aria-live="polite"><span className="hg-verifier-result-label">RESULT / {status.toUpperCase()}</span><p>{message}</p>{computed&&<output className="hg-verifier-hash" aria-label="Computed SHA-256">{computed}</output>}{copyStatus&&<span className="hg-verifier-copy">{copyStatus}</span>}</div>
    <p id="hg-verifier-guidance" className="hg-demo-disclaimer">A digest match establishes byte identity relative to the supplied expected hash. It does not establish authorship, scientific correctness, digital signature validity, or production admission. No file content leaves this browser.</p>
  </section>
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
    <section className="hg-hero hg-section hg-content" id="top"><div className="hg-hero-copy"><span className="hg-eyebrow"><span className="hg-dot"/> AEGIS OMEGA LABS &nbsp; / &nbsp; SOVEREIGN RESEARCH INFRASTRUCTURE</span><h1>Sovereign<br/><span>research.</span><br/>Evidence-bound.</h1><p className="hg-hero-desc">Research, execution and scientific discovery connected by one principle: claims must be traceable to source, computation and independent checks.</p><div className="hg-hero-actions"><a className="hg-btn hg-btn-primary" href="/platform">Explore the platform <Arrow/></a><a className="hg-btn hg-btn-secondary" href="/runtime">Inspect verification <Arrow diagonal/></a></div><div className="hg-hero-note"><span className="hg-cross">✧</span> SOVEREIGN INTELLIGENCE &nbsp; / &nbsp; EVIDENCE BEFORE AUTHORITY</div></div><Orbit/></section>
    <section className="hg-facts hg-content" aria-label="Principles"><div><small>THE PRINCIPLE</small><b>Capability ≤ verifiability</b></div><div><small>THE SYSTEM</small><b>Research · Compute · Challenge · Admit</b></div><div><small>THE BOUNDARY</small><b>Unknown stays unknown</b></div></section>
    <section className="hg-section hg-content hg-intro" id="vision"><div className="hg-section-tag">01 — INTELLIGENCE ARCHITECTURE</div><div className="hg-intro-body"><h2>One collective intelligence.<br/><span>Multiple horizons of inquiry.</span></h2><p>Not another collection of disconnected copilots. AEGIS is organized around shared context, evidence-bearing computation and constrained operations. Its claims must survive review before they become authority.</p></div></section>
    <section className="hg-domains hg-content" id="domains">{DOMAINS.map(d=><a className="hg-domain hg-glass" href={d.href} key={d.id}><div className="hg-domain-top"><span className="hg-mono">{d.id} / 04</span><span className="hg-domain-arrow"><Arrow diagonal/></span></div><div className="hg-domain-icon"><Glyph kind={d.glyph}/></div><h3>{d.title}</h3><p>{d.detail}</p><div className="hg-domain-tag">{d.tag}</div></a>)}</section>
    <section className="hg-section hg-content hg-focus" id="research"><div className="hg-section-tag">02 — THE WORKING SYSTEM</div><div className="hg-focus-shell hg-glass"><div className="hg-focus-menu" role="tablist" aria-label="System capability" onKeyDown={(event: { key: string; preventDefault(): void }) => {
      const all = ['research','runtime','trust'] as const
      if (!['ArrowRight','ArrowLeft','ArrowDown','ArrowUp','Home','End'].includes(event.key)) return
      event.preventDefault()
      const pos=all.indexOf(focus)
      const next= event.key==='Home' ? all[0] : event.key==='End' ? all[2] :
        all[(pos + (event.key==='ArrowRight'||event.key==='ArrowDown'?1:2)) % all.length]
      setFocus(next)
      requestAnimationFrame(() => document.getElementById('hg-tab-'+next)?.focus())
    }}><button type="button" role="tab" id="hg-tab-research" aria-controls="hg-tab-panel" tabIndex={focus==='research'?0:-1} aria-selected={focus==='research'} onClick={()=>setFocus('research')} className={focus==='research'?'is-active':''}><Glyph kind="math"/> ResearchOS <span>01</span></button><button type="button" role="tab" id="hg-tab-runtime" aria-controls="hg-tab-panel" tabIndex={focus==='runtime'?0:-1} aria-selected={focus==='runtime'} onClick={()=>setFocus('runtime')} className={focus==='runtime'?'is-active':''}><Glyph kind="neural"/> Runtime <span>02</span></button><button type="button" role="tab" id="hg-tab-trust" aria-controls="hg-tab-panel" tabIndex={focus==='trust'?0:-1} aria-selected={focus==='trust'} onClick={()=>setFocus('trust')} className={focus==='trust'?'is-active':''}><Glyph kind="shield"/> Verification <span>03</span></button></div><div className="hg-focus-body" id="hg-tab-panel" role="tabpanel" aria-labelledby={'hg-tab-'+focus}><div className="hg-focus-copy"><span className="hg-eyebrow">{focusData.label} / SELECTED</span><h2>{focusData.title}</h2><p>{focusData.detail}</p><ul>{focusData.bullets.map(b=><li key={b}>{b}</li>)}</ul><a className="hg-btn hg-btn-primary" href={focusData.href}>{focusData.button}<Arrow/></a></div><div className="hg-focus-visual" aria-hidden="true"><div className="hg-holon hg-holon-a"/><div className="hg-holon hg-holon-b"/><div className="hg-holon hg-holon-c"/><div className="hg-holon-core"><Sigil size={74}/></div><span className="hg-holon-lbl hg-holon-lbl-a">MEMORY / CONTEXT</span><span className="hg-holon-lbl hg-holon-lbl-b">OBSERVE / VERIFY</span><span className="hg-holon-lbl hg-holon-lbl-c">COMPUTE / GOVERN</span></div></div></div></section>
    <section className="hg-section hg-content hg-proof" id="evidence"><div className="hg-section-tag">03 — THE EVIDENCE SPINE</div><div className="hg-section-head"><div><h2>Nothing outranks<br/><span>its proof.</span></h2><p>Auditability is not an illustration. It is the condition under which a capability may move forward.</p></div><a className="hg-small-link" href="/compliance">Governance specification <Arrow diagonal/></a></div><div className="hg-evidence-grid"><div className="hg-proof-steps">{STAGES.map(s=><div className="hg-step" key={s.stage}><span>{s.stage}</span><div><h3>{s.title}</h3><p>{s.text}</p></div><Arrow/></div>)}</div><ArtifactVerifier/></div></section>
    <section className="hg-section hg-content hg-labs" id="labs"><div className="hg-section-tag">04 — OPEN RESEARCH SURFACES</div><div className="hg-section-head"><div><h2>Research you can <span>inspect.</span></h2><p>Accessible instruments, visible limitations, and pathways from raw observations to falsifiable claims.</p></div></div><div className="hg-lab-grid"><a href={QUANTUM_URL} className="hg-lab-feature hg-glass"><div className="hg-lab-chip">PUBLIC MOBILE INSTRUMENT · PSD</div><div className="hg-lab-geometry"><span>Δω</span><svg viewBox="0 0 460 160" aria-hidden="true"><defs><linearGradient id="hg-signal" x1="0" x2="1"><stop stopColor="#417BE4"/><stop offset=".5" stopColor="#9DDFFF"/><stop offset="1" stopColor="#AC8AFF"/></linearGradient></defs><path d="M0 80h460M0 40h460M0 120h460" stroke="#5785B2" strokeOpacity=".24" strokeDasharray="2 7"/><polyline points="0,80 27,78 51,74 70,43 85,79 121,84 141,28 163,83 191,71 212,93 231,16 251,94 278,81 306,51 326,83 360,75 378,24 400,80 430,78 460,80" fill="none" stroke="url(#hg-signal)" strokeWidth="2.7"/></svg></div><h3>Quantum Integrity Lab</h3><p>Live PSD-safe spectral computations, traceable physical replay aggregates and bounded discoveries. Built for mobile.</p><span className="hg-open-link">Launch the laboratory <Arrow diagonal/></span></a><div className="hg-lab-stack"><a className="hg-small-lab hg-glass" href="/console"><div className="hg-small-lab-icon"><Glyph kind="terminal"/></div><div><span className="hg-mono">OPERATOR SURFACE</span><h3>Command Console</h3><p>System state, bounded agent workflows and explicit provenance.</p></div><Arrow diagonal/></a><a className="hg-small-lab hg-glass" href="/docs"><div className="hg-small-lab-icon"><Glyph kind="layers"/></div><div><span className="hg-mono">INTEGRATION SURFACE</span><h3>Developer API</h3><p>Contracts and interfaces for governed execution.</p></div><Arrow diagonal/></a></div></div></section>
    <section className="hg-section hg-content hg-enterprise" id="enterprise"><div><span className="hg-section-tag">05 — BUILT FOR SERIOUS SYSTEMS</span><h2>From frontier research<br/>to governed operations.</h2><p>Enterprise quality starts with a clear separation between demonstration, validation and deployment. Explore the available API, research tools and compliance model.</p><div className="hg-hero-actions"><a href="/pricing" className="hg-btn hg-btn-primary">Explore access <Arrow/></a><a href="/docs" className="hg-btn hg-btn-secondary">Read API contracts <Arrow diagonal/></a></div></div><div className="hg-enterprise-sigil" aria-hidden="true"><Sigil size={184}/></div></section>
    <section className="hg-section hg-content hg-source-registry" id="registry" aria-labelledby="hg-registry-title">
      <div className="hg-section-tag">05 — RESEARCH EVIDENCE REGISTER</div>
      <div className="hg-section-head"><div><h2 id="hg-registry-title">Open the actual <span>record.</span></h2><p>Public reference points, not synthesized achievements. The linked source determines what can be claimed.</p></div></div>
      <div className="hg-registry-grid">
        <a className="hg-registry-entry hg-glass" href="https://github.com/Aegis-Omega/AEGIS-OMEGA" target="_blank" rel="noopener noreferrer"><span className="hg-mono">01 / CODE</span><strong>AEGIS source repository</strong><p>Inspect branches, exact commits, live checks and independently reviewable code.</p><span className="hg-register-status">EXTERNAL SOURCE · NO IMPLIED PASS <Arrow diagonal/></span></a>
        <a className="hg-registry-entry hg-glass" href="https://github.com/tarikskalic33/formal-conjectures" target="_blank" rel="noopener noreferrer"><span className="hg-mono">02 / FORMAL</span><strong>Formal conjectures fork</strong><p>Lean formalizations and proof assembly. A successfully compiled file is not an unconditional RH proof.</p><span className="hg-register-status">OPEN TARGET · SCOPE MATTERS <Arrow diagonal/></span></a>
        <a className="hg-registry-entry hg-glass" href={QUANTUM_URL} target="_blank" rel="noopener noreferrer"><span className="hg-mono">03 / EXPERIMENT</span><strong>Quantum Integrity Lab</strong><p>Actual edge PSD-mask computation, with archived physical simulations clearly marked separately.</p><span className="hg-register-status">EDGE PSD LIVE · BATH REPLAY ARCHIVED <Arrow diagonal/></span></a>
      </div>
    </section>
    <SiteFooter/>
  </div>
}

type RouteDescription={kicker:string;title:string;description:string;boundary:string;action:{href:string;label:string}}
const ROUTE_META: Record<string, RouteDescription> = {
  platform:{kicker:'AEGIS / PLATFORM',title:'Agent configuration ≠ execution.',description:'Inspect configured departments and workflow behavior.',boundary:'No global latency or replay guarantee. Trust only receipts from the execution actually run.',action:{href:'/docs',label:'Read API contract'}},
  console:{kicker:'AEGIS / COMMAND',title:'Observe the operator state.',description:'Console state, execution traces and admission controls.',boundary:'Live telemetry and example data must remain distinguishable.',action:{href:'/runtime',label:'Inspect runtime'}},
  runtime:{kicker:'AEGIS / CONSTITUTIONAL',title:'Test the mechanism.',description:'In-browser demonstrations and runtime contracts.',boundary:'A browser simulation is not a signed production audit receipt.',action:{href:'/compliance',label:'Control mapping'}},
  docs:{kicker:'AEGIS / DEVELOPERS',title:'Integrate with explicit contracts.',description:'API routes, request shapes and authentication.',boundary:'Published API contracts do not establish current provider availability.',action:{href:'/platform',label:'Inspect platform'}},
  pricing:{kicker:'AEGIS / ACCESS',title:'Access with clear boundaries.',description:'Published tiers and credential flow.',boundary:'Review current terms and provisioning response before any paid action.',action:{href:'/docs',label:'Read API documentation'}},
  compliance:{kicker:'AEGIS / GOVERNANCE',title:'Control claims under review.',description:'Implementation-to-obligation mappings for scrutiny.',boundary:'Not a conformity certificate or an independent legal review.',action:{href:'/runtime',label:'Examine mechanism'}},
  tools:{kicker:'AEGIS / INSTRUMENTS',title:'Tools, not guarantees.',description:'Individual application and utility entry points.',boundary:'Check the availability and evidence status of each tool independently.',action:{href:'/docs',label:'Integration documentation'}},
  'claim-sponsor':{kicker:'AEGIS / ACCOUNT',title:'Secure entitlement flow.',description:'Sponsor-linked API-key provisioning.',boundary:'Treat issued API credentials as secrets; do not disclose them in public logs or chat.',action:{href:'/pricing',label:'View access terms'}},
}
export function HolonRoute({ route, children }: { route: string; children: ReactNode }) {
  const meta=ROUTE_META[route]
  return <div className={'hg-site hg-route hg-route-'+route}><Nav path={'/'+route}/>
    <section className="hg-route-header hg-content" aria-label="Route context">
      <div className="hg-route-header-main"><span className="hg-eyebrow">{meta?.kicker||'AEGIS OMEGA'} / SYSTEM SURFACE</span>
        <h1>{meta?.title || 'AEGIS runtime.'}</h1><p>{meta?.description}</p>
      </div><div className="hg-route-aside"><span className="hg-mono">EPISTEMIC BOUNDARY</span><p>{meta?.boundary}</p><a href={meta?.action.href||'/'}>{meta?.action.label||'Overview'} <Arrow diagonal/></a></div>
    </section>
    <main id="hg-main" className="hg-legacy-content">{children}</main><SiteFooter/></div>
}
export function HolonNotFound() {return <div className="hg-site hg-route"><Nav/><main id="hg-main" className="hg-missing hg-content"><span className="hg-eyebrow">ROUTE NOT FOUND / 404</span><h1>Nothing to verify here.</h1><p>This URL is not a published AEGIS route. No result has been inferred or redirected to an unrelated product.</p><a className="hg-btn hg-btn-primary" href="/">Return to overview <Arrow/></a></main><SiteFooter/></div>}
export function HolonHomepage() {return <div className="hg-site hg-site-home"><Nav path="/"/><main id="hg-main"><HolonHome/></main></div>}