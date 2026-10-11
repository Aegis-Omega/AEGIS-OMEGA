import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react'
import { COMMAND_ROUTES, filterCommandRoutes, nextPaletteIndex } from '../lib/commandPaletteModel.js'

/** Published-route navigation only; no remote search, indexing or telemetry. */


export function CommandJump() {
  const [open,setOpen] = useState(false)
  const [query,setQuery] = useState('')
  const root=useRef<HTMLDivElement>(null)
  const trigger=useRef<HTMLButtonElement>(null)
  const input=useRef<HTMLInputElement>(null)
  const matches=filterCommandRoutes(query)

  useEffect(()=>{
    function onKey(e:KeyboardEvent){
      if((e.metaKey||e.ctrlKey)&&!e.altKey&&!e.repeat&&e.key.toLowerCase()==='k'){
        e.preventDefault()
        setOpen(value=>!value)
      }
      if(e.key==='Escape'&&open){
        e.preventDefault()
        setOpen(false)
        trigger.current?.focus()
      }
    }
    function onPointer(e:PointerEvent){
      if(e.target instanceof Node&&!root.current?.contains(e.target))setOpen(false)
    }
    function onFocus(e:FocusEvent){
      if(open&&e.target instanceof Node&&!root.current?.contains(e.target))setOpen(false)
    }
    document.addEventListener('keydown',onKey)
    document.addEventListener('pointerdown',onPointer)
    document.addEventListener('focusin',onFocus)
    return()=>{
      document.removeEventListener('keydown',onKey)
      document.removeEventListener('pointerdown',onPointer)
      document.removeEventListener('focusin',onFocus)
    }
  },[open])
  useEffect(()=>{if(open)input.current?.focus()},[open])

  const onSearchKeyDown=(event:ReactKeyboardEvent<HTMLInputElement>)=>{
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
      const links=Array.from(root.current?.querySelectorAll<HTMLAnchorElement>('.cc-jump-results a')??[])
      const next=nextPaletteIndex(-1,links.length,event.key)
      if(next>=0){event.preventDefault();links[next]?.focus()}
    }
    if(event.key==='Enter'&&matches.length>0){
      event.preventDefault()
      window.location.assign(matches[0].href)
    }
  }
  const onResultsKeyDown=(event:ReactKeyboardEvent<HTMLDivElement>)=>{
    if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return
    const links=Array.from(event.currentTarget.querySelectorAll<HTMLAnchorElement>('a'))
    if(links.length===0)return
    event.preventDefault()
    const index=links.indexOf(document.activeElement as HTMLAnchorElement)
    const next=nextPaletteIndex(index,links.length,event.key as 'ArrowDown'|'ArrowUp'|'Home'|'End')
    if(next<0)input.current?.focus()
    else links[next]?.focus()
  }

  return <div className="cc-jump" ref={root}>
    <button ref={trigger} type="button" className="cc-jump-trigger" aria-haspopup="true"
      aria-label="Search published AEGIS pages" aria-controls={open?'cc-jump-results':undefined}
      aria-expanded={open} onClick={()=>setOpen(value=>!value)}>
      <span aria-hidden="true">⌕</span> Jump to a system page <kbd aria-hidden="true">⌘ K</kbd>
    </button>
    {open&&<div className="cc-jump-panel" id="cc-jump-results" role="region" aria-label="Published route search">
      <label htmlFor="cc-jump-query">FIND A ROUTE · LOCAL INDEX</label>
      <input id="cc-jump-query" ref={input} type="search" autoComplete="off"
        placeholder="Research, console, tools..." value={query}
        onKeyDown={onSearchKeyDown} onChange={e=>setQuery(e.target.value)}/>
      <div className="cc-jump-results" onKeyDown={onResultsKeyDown} aria-label="Matching published pages">
        {matches.length?matches.map(r=><a key={r.href} href={r.href}>
          <b>{r.label}</b><span>{r.detail}</span><span aria-hidden="true">↗</span>
        </a>):<p role="status">No matching published route. No results inferred.</p>}
      </div>
      <p className="cc-jump-foot">ONLY PUBLISHED PAGES · NO REPOSITORY SEARCH</p>
    </div>}
  </div>
}
