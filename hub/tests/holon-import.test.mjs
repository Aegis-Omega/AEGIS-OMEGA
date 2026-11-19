import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {emptyHolonTrace,appendHolonEvent,verifyHolonTrace} from '../src/lib/holonTrace.ts'

// Execute the actual component handler, with only its two TS annotations removed.
// This checks import side effects independently of React rendering.
const source=readFileSync(new URL('../src/components/HolonMaximusStudio.tsx',import.meta.url),'utf8')
const handler=source.slice(source.indexOf('async function importTrace('),source.indexOf('  return <article'))
  .trim().replace('event:ChangeEvent<HTMLInputElement>','event').replace('parsed:unknown','parsed')
async function journal(){return appendHolonEvent(emptyHolonTrace(),{
  id:crypto.randomUUID(),kind:'seed',actor:'human',origin:'direct_human',lens:'none',
  text:'Preserve my work',parents:[],recorded_at:'2026-11-02T10:00:00.000Z'
})}
function harness(trace,confirm=true){
  const effects=[],busyRef={current:false}
  const b={trace,seed:'',branch:'',weave:'',artifact:'',busyRef,verifyHolonTrace,
    window:{confirm:()=>{effects.push(['confirm']);return confirm}}}
  for(const name of ['Trace','Notice','Error','Busy','Seed','Branch','Weave','Artifact','BranchParent']){
    b['set'+name]=value=>effects.push([name,value])
  }
  const run=new Function('b',`with(b){return (${handler})}`)(b)
  const event=raw=>({target:{value:'chosen.json',files:[{size:raw.length,text:async()=>raw}]}})
  return {b,effects,run,event,busyRef}
}
test('cancelled replacement retains journal and every draft and releases import lock',async()=>{
  const h=harness(await journal(),false)
  h.b.branch='Unrecorded work'
  await h.run(h.event(JSON.stringify(emptyHolonTrace())))
  assert.equal(h.effects.filter(e=>e[0]==='confirm').length,1)
  assert.ok(!h.effects.some(e=>['Trace','Seed','Branch','Weave','Artifact','BranchParent'].includes(e[0])))
  assert.equal(h.busyRef.current,false)
})
test('confirmed import resets stale parent and drafts and installs verified journal',async()=>{
  const h=harness(await journal())
  await h.run(h.event(JSON.stringify(emptyHolonTrace())))
  assert.deepEqual(h.effects.filter(e=>e[0]==='BranchParent'),[['BranchParent','']])
  assert.deepEqual(h.effects.filter(e=>e[0]==='Trace'),[['Trace',emptyHolonTrace()]])
  for(const name of ['Seed','Branch','Weave','Artifact'])assert.deepEqual(h.effects.filter(e=>e[0]===name),[[name,'']])
})
test('unrecorded drafts alone require replacement confirmation',async()=>{
  const h=harness(emptyHolonTrace(),false)
  h.b.seed='My new idea'
  await h.run(h.event(JSON.stringify(emptyHolonTrace())))
  assert.ok(h.effects.some(e=>e[0]==='confirm'))
  assert.ok(!h.effects.some(e=>e[0]==='Trace'))
})
test('invalid import cannot ask for replacement or mutate the journal',async()=>{
  const h=harness(await journal())
  await h.run(h.event('{"schema":"wrong","events":[]}'))
  assert.ok(h.effects.some(e=>e[0]==='Error'&&e[1]))
  assert.ok(!h.effects.some(e=>['confirm','Trace'].includes(e[0])))
  assert.equal(h.busyRef.current,false)
})
