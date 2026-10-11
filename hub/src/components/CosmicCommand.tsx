import { useState } from 'react'
import './cosmic-command.css'

/** AEGIS Ω cinematic navigation, with operational links and no invented telemetry. */
const NODES = [
  { label:'RESEARCH',href:'/platform',x:'54%',y:'13%',n:'01' },
  { label:'CONSOLE',href:'/console',x:'82%',y:'30%',n:'02' },
  { label:'RUNTIME',href:'/runtime',x:'77%',y:'75%',n:'03' },
  { label:'VERIFY',href:'/compliance',x:'23%',y:'74%',n:'04' },
  { label:'DEVELOP',href:'/docs',x:'11%',y:'37%',n:'05' },
] as const
const STARS = Array.from({length:90},(_,i)=>({
  x:(i*97+Math.floor(i/5)*17)%1000, y:(i*67+Math.floor(i/3)*41)%560,
  r:i%13===0?1.6:i%4===0?.8:.4, opacity:i%7===0?.78:.23+(i%4)*.08,
}))

export function CosmicCommand() {
  const [mode,setMode] = useState<'atlas'|'evidence'>('atlas')
  return <div className="cc-system" id="top">
    <section className="cc-hero" aria-labelledby="cc-headline">
      <div className="cc-copy">
        <div className="cc-eyebrow"><span className="cc-pulse"/> AEGIS OMEGA / RESEARCH INFRASTRUCTURE</div>
        <h1 id="cc-headline">Beyond the<br/><em>known.</em></h1>
        <p>One intelligence fabric for research, governed execution and inspectable evidence. Explore the source. Challenge the claim. Keep authority bounded.</p>
        <div className="cc-hero-actions">
          <a className="cc-cta cc-cta-primary" href="/platform">Open research <span aria-hidden="true">↗</span></a>
          <a className="cc-cta cc-cta-secondary" href="/console">Enter command <span aria-hidden="true">→</span></a>
        </div>
        <div className="cc-axiom">RESEARCH <span>→</span> CHALLENGE <span>→</span> VERIFY <span>→</span> ADMIT</div>
      </div>
      <div className="cc-space" aria-label="Navigation through AEGIS research and operational areas">
        <span className="cc-space-note cc-note-top">SOVEREIGN FIELD / 001<br/>SPATIAL DIRECTORY</span>
        <svg viewBox="0 0 1000 560" className="cc-celestial" role="img" aria-label="Decorative planetary research scene. Conceptual, not scientific or runtime telemetry.">
          <defs>
            <radialGradient id="cc-aurora"><stop stopColor="#5faaf8" stopOpacity=".37"/><stop offset="1" stopColor="#070c24" stopOpacity="0"/></radialGradient>
            <radialGradient id="cc-world" fx="75%" fy="28%"><stop stopColor="#c6eeff"/><stop offset=".13" stopColor="#3e97ff"/><stop offset=".36" stopColor="#183f90"/><stop offset=".75" stopColor="#07132f"/><stop offset=".95" stopColor="#070c1e"/><stop offset="1" stopColor="#86b9ff"/></radialGradient>
            <linearGradient id="cc-orbit"><stop stopColor="#5278ff" stopOpacity="0"/><stop offset=".42" stopColor="#68d7ff"/><stop offset=".75" stopColor="#9d86ff"/><stop offset="1" stopColor="#3f6bff" stopOpacity=".12"/></linearGradient>
            <clipPath id="cc-world-clip"><circle cx="555" cy="281" r="190"/></clipPath>
          </defs>
          <g fill="#b8e8ff">{STARS.map((s,i)=><circle key={i} cx={s.x} cy={s.y} r={s.r} opacity={s.opacity}/>)}</g>
          <circle cx="555" cy="281" r="292" fill="url(#cc-aurora)"/>
          <circle cx="555" cy="281" r="195" fill="#0a2f79" stroke="#8ce2ff" strokeWidth="1.5"/>
          <circle cx="555" cy="281" r="190" fill="url(#cc-world)"/>
          <g clipPath="url(#cc-world-clip)" fill="none">
            <g stroke="#c8edff" strokeOpacity=".28"><ellipse cx="555" cy="281" rx="90" ry="190"/><ellipse cx="555" cy="281" rx="150" ry="190"/><path d="M346 282H764M354 221H756M350 348H760M383 164H728M380 398H733"/></g>
            <path d="m412 180 27-25 32 7 28-21 23 15-5 31 34 19-17 23-31 3-21 34-29-18-15-38z m139 121 22-26 38-6 32-31 33 18-9 30 25 30-11 44-32 11-17 45-40-13-5-40-32-24z m134-122 23-11 30 39-9 37-32-9z" fill="#85ccff" fillOpacity=".23" stroke="#a0deff" strokeOpacity=".31"/>
            <g fill="#c7efff"><circle cx="472" cy="201" r="2.6"/><circle cx="612" cy="292" r="2.3"/><circle cx="530" cy="340" r="2"/><circle cx="652" cy="218" r="1.6"/></g>
          </g>
          <g fill="none" stroke="url(#cc-orbit)" strokeWidth="1.6">
            <ellipse cx="555" cy="281" rx="306" ry="109" transform="rotate(-25 555 281)"/>
            <ellipse cx="555" cy="281" rx="284" ry="145" transform="rotate(39 555 281)"/>
            <ellipse cx="555" cy="281" rx="273" ry="219" transform="rotate(-66 555 281)" opacity=".6"/>
          </g>
          <circle cx="555" cy="281" r="72" fill="#040920" stroke="#8981ff" strokeWidth="2"/>
          <circle cx="555" cy="281" r="61" fill="none" stroke="#a7dfff" strokeOpacity=".48" strokeDasharray="2 8"/>
          <text x="555" y="311" textAnchor="middle" fill="#f0edff" fontSize="91" fontFamily="Georgia,serif">Ω</text>
        </svg>
        <div className="cc-map-nodes">{NODES.map(x=><a className="cc-map-node" href={x.href} style={{left:x.x,top:x.y}} key={x.n} aria-label={'Open '+x.label}>
          <span>{x.n}</span><b>{x.label}</b>
        </a>)}</div>
        <div className="cc-layer-picker" role="group" aria-label="Context view">
          <button type="button" onClick={()=>setMode('atlas')} aria-pressed={mode==='atlas'}>Atlas</button>
          <button type="button" onClick={()=>setMode('evidence')} aria-pressed={mode==='evidence'}>Evidence</button>
        </div>
        <div className="cc-mode-note" aria-live="polite">{mode==='atlas'?'Select a node to open its real destination.':'Evidence is confirmed inside source records, not by this illustration.'}</div>
        <span className="cc-space-note cc-note-bottom">CONCEPT ART / NO LIVE TELEMETRY</span>
      </div>
    </section>
  </div>
}