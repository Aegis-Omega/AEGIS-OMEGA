import test from 'node:test'
import assert from 'node:assert/strict'
import {appendHolonEvent,verifyHolonTrace,emptyHolonTrace,selectedHolonBranches} from '../src/lib/holonTrace.ts'
const draft=(kind,parents=[])=>({id:crypto.randomUUID(),kind,parents,actor:'human',origin:'direct_human',lens:'none',text:kind,recorded_at:'2026-11-02T10:00:00.000Z'})
async function selected(count=2){
  let j=await appendHolonEvent(emptyHolonTrace(),draft('seed'))
  for(let i=0;i<count;i++){
    j=await appendHolonEvent(j,draft('branch',[j.events[0].id]))
    j=await appendHolonEvent(j,draft('select',[j.events.at(-1).id]))
  }
  return j
}
const choices=j=>j.events.filter(e=>e.kind==='select').map(e=>e.id)
test('weaving four choices releases capacity for another full cycle and preserves history',async()=>{
  let j=await selected(4), original=JSON.stringify(j.events)
  const first=choices(j)
  j=await appendHolonEvent(j,draft('weave',first))
  assert.deepEqual(selectedHolonBranches(j),[])
  assert.equal(JSON.stringify(j.events.slice(0,-1)),original)
  for(let i=0;i<4;i++){
    j=await appendHolonEvent(j,draft('branch',[j.events.find(e=>e.kind==='weave').id]))
    j=await appendHolonEvent(j,draft('select',[j.events.at(-1).id]))
  }
  assert.equal(selectedHolonBranches(j).length,4)
  j=await appendHolonEvent(j,draft('weave',choices(j).slice(-4)))
  assert.deepEqual(selectedHolonBranches(j),[])
  assert.deepEqual(await verifyHolonTrace(JSON.parse(JSON.stringify(j))),j)
})
test('closed choices cannot be reused in a second weave',async()=>{
  let j=await selected(), ids=choices(j)
  j=await appendHolonEvent(j,draft('weave',ids))
  await assert.rejects(()=>appendHolonEvent(j,draft('weave',ids)),/active human choices/)
})
test('weave must include every active choice',async()=>{
  const j=await selected(3)
  await assert.rejects(()=>appendHolonEvent(j,draft('weave',choices(j).slice(0,2))),/every active/)
})
test('duplicate choice for the same direction is rejected',async()=>{
  const j=await selected()
  await assert.rejects(()=>appendHolonEvent(j,draft('select',[j.events[1].id])),/already selected/)
})
test('fifth active choice is rejected by the data contract',async()=>{
  let j=await selected(4)
  j=await appendHolonEvent(j,draft('branch',[j.events[0].id]))
  await assert.rejects(()=>appendHolonEvent(j,draft('select',[j.events.at(-1).id])),/four active/)
})
test('a historical direction can be deliberately selected again in a new cycle',async()=>{
  let j=await selected(), branch=j.events[1].id
  j=await appendHolonEvent(j,draft('weave',choices(j)))
  j=await appendHolonEvent(j,draft('select',[branch]))
  assert.deepEqual(selectedHolonBranches(j).map(e=>e.id),[branch])
})
test('rehashing an imported stream cannot legitimize replayed choices',async()=>{
  let j=await selected(), ids=choices(j)
  j=await appendHolonEvent(j,draft('weave',ids))
  const {hash,...last}=j.events.at(-1)
  const raw={...last,id:crypto.randomUUID(),seq:last.seq+1,previous_hash:hash}
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(raw)))
  const forged={...raw,hash:Buffer.from(digest).toString('hex')}
  await assert.rejects(()=>verifyHolonTrace({...j,events:[...j.events,forged]}),/active human choices/)
})
