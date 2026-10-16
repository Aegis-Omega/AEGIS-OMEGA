/**
 * HOLONSKI KONAC / Holonic Thread v1
 * Deterministic 3D projection of REPORTED creative events only.
 * All coordinates and strands derive from the event DAG. The projection is
 * an artistic navigation aid, not measured cognition, provenance attestation,
 * a physical reconstruction, or an inference about the creator.
 */
import type { HolonEvent, HolonTrace, HolonRole } from './holonTrace.js'

export const HOLON_THREAD_WINDOW = 24
export const HOLON_THREAD_WIDTH = 800
export const HOLON_THREAD_HEIGHT = 470

export type ThreadPoint = Readonly<{
  id:string; seq:number; kind:HolonEvent['kind']; actor:HolonRole;
  px:number; py:number; depth:number; radius:number; text:string; parentCount:number
}>
export type ThreadStrand = Readonly<{
  key:string; from:string; to:string; actor:HolonRole; d:string; depth:number
}>
export type HolonicThread = Readonly<{
  points:readonly ThreadPoint[]; strands:readonly ThreadStrand[];
  hiddenEvents:number; hiddenStrands:number; totalStrands:number; yaw:number
}>

type WorldPoint = { x:number; y:number; z:number }
const clamp=(x:number,lo:number,hi:number)=>Math.max(lo,Math.min(hi,x))
const siblingOffset=(n:number)=>n===0?-.7:n===1?.7:(n%2===0?-1:1)*(.7+Math.floor(n/2)*.58)
const kindLift:Record<HolonEvent['kind'],number>={seed:0,branch:0,select:.14,weave:0,artifact:-.1}
const actorZ:Record<HolonRole,number>={human:.34,model:-.30,agent:-.47}

/** Pure layout; input must be verified separately by verifyHolonTrace. */
export function buildHolonicThread(trace:HolonTrace, requestedYaw=0):HolonicThread {
  if (!Number.isFinite(requestedYaw)) throw new Error('HOLON_THREAD_INVALID: non-finite camera yaw')
  const yaw=clamp(requestedYaw,-.72,.72)
  const events=trace.events
  const windowEvents=events.slice(-HOLON_THREAD_WINDOW)
  const hiddenEvents=events.length-windowEvents.length
  const world=new Map<string,WorldPoint>()
  const siblings=new Map<string,number>()
  // First derive the full ancestry in source order. This keeps layout stable
  // when the latest 24 are visible while earlier ancestors are omitted.
  for (const event of events) {
    const parents=event.parents.map(id=>world.get(id)).filter((p):p is WorldPoint=>p!==undefined)
    const average=parents.length ? parents.reduce((a,p)=>a+p.y,0)/parents.length : 0
    let lane=average
    if(event.kind==='branch'){
      const parent=event.parents[0]
      const nth=siblings.get(parent)??0
      siblings.set(parent,nth+1)
      lane=average*.61+siblingOffset(nth)
    } else if(event.kind==='select') lane=average*.90
    else if(event.kind==='weave') lane=average*.60
    else if(event.kind==='artifact') lane=average*.75
    world.set(event.id,{x:0,y:clamp(lane+kindLift[event.kind],-2.55,2.55),z:actorZ[event.actor]})
  }
  const n=windowEvents.length
  const projection=(event:HolonEvent):ThreadPoint=>{
    const p=world.get(event.id)!
    const index=windowEvents.findIndex(e=>e.id===event.id)
    const normalized=n===1?0:index/(Math.max(1,n-1))-.5
    const x=normalized*6.35
    const c=Math.cos(yaw),s=Math.sin(yaw)
    const rotatedX=x*c+p.z*s
    const rotatedZ=-x*s+p.z*c
    const perspective=clamp(5.2/(5.2-rotatedZ),.64,1.38)
    const px=clamp(HOLON_THREAD_WIDTH/2+rotatedX*92*perspective,18,HOLON_THREAD_WIDTH-18)
    const py=clamp(HOLON_THREAD_HEIGHT/2+p.y*67*perspective,26,HOLON_THREAD_HEIGHT-26)
    return {id:event.id,seq:event.seq,kind:event.kind,actor:event.actor,px,py,
      depth:rotatedZ,radius:clamp(10*perspective+(event.kind==='seed'?5:0),8,17),
      text:event.text,parentCount:event.parents.length}
  }
  const points=windowEvents.map(projection)
  const projected=new Map(points.map(p=>[p.id,p]))
  const strands:ThreadStrand[]=[]
  let totalStrands=0
  for(const event of events)totalStrands+=event.parents.length
  for(const child of windowEvents){
    const to=projected.get(child.id)!
    for(const fromId of child.parents){
      const from=projected.get(fromId)
      if(!from)continue  // never invent an edge to an omitted ancestor
      const dx=to.px-from.px,dy=to.py-from.py
      // Real edges, artistically curved by recorded source positions.
      const bend=clamp(dx*.17,-44,44)
      const c1x=from.px+dx*.38,c1y=from.py+dy*.12-bend
      const c2x=to.px-dx*.38,c2y=to.py-dy*.12+bend
      const d='M '+from.px.toFixed(2)+' '+from.py.toFixed(2)+' C '+c1x.toFixed(2)+' '+c1y.toFixed(2)+', '+c2x.toFixed(2)+' '+c2y.toFixed(2)+', '+to.px.toFixed(2)+' '+to.py.toFixed(2)
      strands.push({key:fromId+'>'+child.id,from:fromId,to:child.id,actor:child.actor,d,depth:(from.depth+to.depth)/2})
    }
  }
  return {points,strands,hiddenEvents,hiddenStrands:totalStrands-strands.length,totalStrands,yaw}
}

export function threadFocus(trace:HolonTrace,id:string|null):HolonEvent|null {
  return trace.events.find(e=>e.id===id)??trace.events.at(-1)??null
}
