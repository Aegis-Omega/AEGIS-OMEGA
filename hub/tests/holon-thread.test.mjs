import test from 'node:test'
import assert from 'node:assert/strict'
import {buildHolonicThread,HOLON_THREAD_WINDOW,threadFocus} from '../src/lib/holonThread.ts'

const id=n=>'thread-event-'+String(n).padStart(5,'0')
function evt(n,kind='branch',parents=[],actor='human'){
  return {id:id(n),seq:n,kind,actor,origin:actor==='human'?'direct_human':'pasted_external',
    lens:'none',text:'Idea '+n,parents,recorded_at:'2026-10-16T00:00:00Z',previous_hash:'HASH',hash:'HASH'+n}
}
const trace=events=>({schema:'AEGIS_HOLON_MAXIMUS_TRACE_V1',events})

test('empty thread renders zero invented nodes, arcs and totals',()=>{
  const a=buildHolonicThread(trace([]))
  assert.deepEqual(a.points,[]);assert.deepEqual(a.strands,[])
  assert.equal(a.totalStrands,0);assert.equal(a.hiddenEvents,0)
  assert.equal(threadFocus(trace([]),null),null)
})

test('seed is the only point and never sprouts ornamental graph arcs',()=>{
  const j=trace([evt(1,'seed')]);const a=buildHolonicThread(j)
  assert.equal(a.points.length,1);assert.equal(a.strands.length,0)
  assert.equal(a.points[0].seq,1)
  assert.equal(a.points[0].kind,'seed')
})

test('every visible connection corresponds to one explicit parent id',()=>{
  const j=trace([evt(1,'seed'),evt(2,'branch',[id(1)]),evt(3,'branch',[id(1)],'model'),
    evt(4,'select',[id(2)]),evt(5,'select',[id(3)]),evt(6,'weave',[id(4),id(5)])])
  const a=buildHolonicThread(j,.35)
  assert.equal(a.points.length,6);assert.equal(a.strands.length,6)
  for(const edge of a.strands){
    const child=j.events.find(e=>e.id===edge.to)
    assert(child.parents.includes(edge.from))
    assert.equal(edge.actor,child.actor)
    assert.match(edge.d,/^M [\d.]+ [\d.]+ C /)
  }
  assert.equal(a.points.find(x=>x.id===id(3)).actor,'model')
})

test('original source roles survive projection unchanged',()=>{
  const j=trace([evt(1,'seed'),evt(2,'branch',[id(1)],'agent'),evt(3,'select',[id(2)])])
  const a=buildHolonicThread(j)
  assert.deepEqual(a.points.map(p=>p.actor),['human','agent','human'])
})

test('camera changes perspective but never node/edge identity',()=>{
  const j=trace([evt(1,'seed'),evt(2,'branch',[id(1)]),evt(3,'branch',[id(2)])])
  const a=buildHolonicThread(j,-.5),b=buildHolonicThread(j,.5)
  assert.deepEqual(a.points.map(p=>p.id),b.points.map(p=>p.id))
  assert.deepEqual(a.strands.map(e=>e.key),b.strands.map(e=>e.key))
  assert.notDeepEqual(a.points.map(p=>p.px),b.points.map(p=>p.px))
})

test('geometry stays finite and inside viewport at yaw extremes',()=>{
  const ev=[evt(1,'seed')]
  for(let n=2;n<=40;n++)ev.push(evt(n,'branch',[id(Math.max(1,n-1))],n%2?'human':'model'))
  for(const yaw of [-1e5,-.72,0,.72,1e5]){
    const a=buildHolonicThread(trace(ev),yaw)
    for(const p of a.points){
      assert(Number.isFinite(p.px));assert(Number.isFinite(p.py));assert(Number.isFinite(p.depth))
      assert(p.px>=18&&p.px<=782);assert(p.py>=26&&p.py<=444)
    }
    assert(a.yaw>=-.72&&a.yaw<=.72)
  }
  assert.throws(()=>buildHolonicThread(trace(ev),NaN),/non-finite camera yaw/)
})

test('large history is bounded, and edges to hidden ancestors stay hidden',()=>{
  const ev=[evt(1,'seed')];for(let n=2;n<=128;n++)ev.push(evt(n,'branch',[id(1)]))
  const a=buildHolonicThread(trace(ev))
  assert.equal(a.points.length,HOLON_THREAD_WINDOW)
  assert.equal(a.hiddenEvents,128-HOLON_THREAD_WINDOW)
  assert.equal(a.strands.length,0)
  assert.equal(a.hiddenStrands,127)
  assert.equal(a.totalStrands,127)
})

test('full ancestry is preserved through focus on an omitted ancestor',()=>{
  const ev=[evt(1,'seed')];for(let n=2;n<=35;n++)ev.push(evt(n,'branch',[id(n-1)]))
  const j=trace(ev),a=buildHolonicThread(j)
  assert.equal(a.strands.length,HOLON_THREAD_WINDOW-1)
  assert.equal(a.hiddenStrands,34-(HOLON_THREAD_WINDOW-1))
  assert.equal(threadFocus(j,id(1)).seq,1)
  assert.equal(threadFocus(j,'missing').seq,35)
})

test('pure deterministic projection returns identical output',()=>{
  const j=trace([evt(1,'seed'),evt(2,'branch',[id(1)]),evt(3,'select',[id(2)])])
  assert.deepEqual(buildHolonicThread(j,.4),buildHolonicThread(j,.4))
})

test('historical windows reveal earlier records without inventing later links',()=>{
  const ev=[evt(1,'seed')];for(let n=2;n<=80;n++)ev.push(evt(n,'branch',[id(n-1)]))
  const full=buildHolonicThread(trace(ev),0)
  const earlier=buildHolonicThread(trace(ev),0,30)
  assert.equal(full.windowStart,80-HOLON_THREAD_WINDOW)
  assert.equal(earlier.windowStart,30-HOLON_THREAD_WINDOW)
  assert.equal(earlier.windowEnd,30)
  assert.equal(earlier.hiddenAfter,50)
  assert.equal(earlier.hiddenBefore,6)
  assert.equal(earlier.strands.length,HOLON_THREAD_WINDOW-1)
  assert(earlier.strands.every(edge=>Number(edge.to.slice(-5))<=30))
  assert.equal(earlier.hiddenStrands,79-(HOLON_THREAD_WINDOW-1))
})

test('invalid history windows fail closed and overflows clamp',()=>{
  const j=trace([evt(1,'seed'),evt(2,'branch',[id(1)])])
  assert.throws(()=>buildHolonicThread(j,0,NaN),/non-finite window/)
  assert.equal(buildHolonicThread(j,0,-100).points.length,0)
  assert.equal(buildHolonicThread(j,0,999).points.length,2)
})
