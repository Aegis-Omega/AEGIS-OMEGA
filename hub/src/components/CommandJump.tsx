import { useEffect, useRef, useState } from 'react'

/** Fast local route switcher; no imaginary search indexing or network requests. */
const ROUTES = [
  { href:'/',label:'Overview',detail:'AEGIS command homepage' },
  { href:'/platform',label:'ResearchOS',detail:'Curated research sources' },
  { href:'/console',label:'Console',detail:'Observed operator state' },
  { href:'/runtime',label:'Runtime',detail:'Verification and system boundaries' },
  { href:'/compliance',label:'Governance',detail:'Control mappings and limits' },
  { href:'/docs',label:'Developers',detail:'API reference' },
  { href:'/tools',label:'Tools',detail:'Creator tools and access' },
  { href:'/pricing',label:'Access',detail:'Plans and provisioning' },
  { href:'/claim-sponsor',label:'Sponsor claim',detail:'Existing sponsor access process' },
] as const

export function CommandJump() {
  const [open,setOpen] = useState(false)
  const [query,setQuery] = useState('')
  const root=useRef<HTMLDivElement>(null)
  const input=useRef<HTMLInputElement>(null)
  useEffect(()=>{
    function onKey(e:KeyboardEvent){
      if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){
        e.preventDefault();setOpen(v=>!v)
      }
      if(e.key==='Escape')setOpen(false)
    }
    function onPointer(e:PointerEvent){
      if(e.target instanceof Node&&!root.current?.contains(e.target))setOpen(false)
    }
    document.addEventListener('keydown',onKey)
    document.addEventListener('pointerdown',onPointer)
    return()=>{document.removeEventListener('keydown',onKey);document.removeEventListener('pointerdown',onPointer)}
  },[])
  useEffect(()=>{if(open)input.current?.focus()},[open])
  const matches=ROUTES.filter(r=>(r.label+' '+r.detail).toLowerCase().includes(query.trim().toLowerCase()))
  return <div className="cc-jump" ref={root}>
    <button type="button" className="cc-jump-trigger" aria-controls="cc-jump-results" aria-expanded={open}
      onClick={()=>setOpen(v=>!v)}><span aria-hidden="true">⌕</span> Jump to a system page <kbd>⌘ K</kbd></button>
    {open&&<div className="cc-jump-panel" id="cc-jump-results" aria-label="Search published routes">
      <label htmlFor="cc-jump-query">FIND A ROUTE · LOCAL INDEX</label>
      <input id="cc-jump-query" ref={input} type="search" placeholder="Research, console, tools..."
        value={query} onChange={e=>setQuery(e.target.value)}/>
      <div className="cc-jump-results">
        {matches.length?matches.map(r=><a key={r.href} href={r.href}><b>{r.label}</b><span>{r.detail}</span><span aria-hidden="true">↗</span></a>)
          :<p>No matching published route. No results inferred.</p>}
      </div>
      <p className="cc-jump-foot">ONLY PUBLISHED PAGES · NO REPOSITORY SEARCH</p>
    </div>}
  </div>
}