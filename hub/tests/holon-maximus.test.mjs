import test from 'node:test'
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import {readFileSync} from 'node:fs'
import {appendHolonEvent,verifyHolonTrace,emptyHolonTrace,selectedHolonBranches,MAX_HOLON_EVENTS} from '../src/lib/holonTrace.ts'

const stamp='2026-10-16T09:00:00.000Z'
const draft=(kind,text,parents=[],actor='human',lens='none')=>({
  id:randomUUID(),kind,text,parents,actor,lens,origin:actor==='human'?'direct_human':'pasted_external',recorded_at:stamp
})
const seed=()=>appendHolonEvent(emptyHolonTrace(),draft('seed','Could imagination leave a visible trace?'))
const branch=(journal,text='An unexpected direction',actor='human')=>
  appendHolonEvent(journal,draft('branch',text,[journal.events[0].id],actor,'imagination'))

async function withTwoSelections(){
  let j=await seed()
  j=await branch(j,'A map of evolving ideas')
  j=await branch(j,'An independently inspectable lineage')
  const first=j.events[1],second=j.events[2]
  j=await appendHolonEvent(j,draft('select','Human selected map',[first.id]))
  j=await appendHolonEvent(j,draft('select','Human selected lineage',[second.id]))
  return j
}

test('genesis is empty and only a human may seed it', async()=>{
  assert.deepEqual(emptyHolonTrace().events,[])
  await assert.rejects(()=>appendHolonEvent(emptyHolonTrace(),draft('seed','Fake seed',[],'model')),/only a human/)
  const j=await seed()
  assert.equal(j.events[0].kind,'seed')
  assert.equal(j.events[0].previous_hash,'GENESIS')
  assert.match(j.events[0].hash,/^[0-9a-f]{64}$/)
})

test('human branches preserve original seed, immutable previous state',async()=>{
  const original=await seed(),next=await branch(original)
  assert.equal(original.events.length,1)
  assert.equal(next.events.length,2)
  assert.equal(next.events[1].parents[0],original.events[0].id)
  assert.equal(next.events[1].previous_hash,original.events[0].hash)
  assert.equal((await verifyHolonTrace(next)).events.length,2)
})

test('pasted LLM proposal remains externally unverified and cannot select itself',async()=>{
  const j=await seed()
  const copied=await branch(j,'Pasted suggestion from another model','model')
  assert.equal(copied.events[1].origin,'pasted_external')
  await assert.rejects(()=>appendHolonEvent(copied,draft('select','I choose myself',[copied.events[1].id],'model')),/only a human/)
  await assert.rejects(()=>appendHolonEvent(copied,draft('weave','I finalize myself',[copied.events[1].id],'model')),/only a human/)
})

test('human deliberate selection is an append-only event',async()=>{
  const j=await withTwoSelections()
  const choices=j.events.filter(e=>e.kind==='select')
  assert.equal(choices.length,2)
  assert.deepEqual(selectedHolonBranches(j).map(e=>e.text),[
    'A map of evolving ideas','An independently inspectable lineage'
  ])
})

test('weave requires two distinct human selections',async()=>{
  let j=await withTwoSelections()
  const ids=j.events.filter(e=>e.kind==='select').map(e=>e.id)
  await assert.rejects(()=>appendHolonEvent(j,draft('weave','One choice only',[ids[0]])),/two human choices/)
  await assert.rejects(()=>appendHolonEvent(j,draft('weave','Duplicated choice',[ids[0],ids[0]])),/invalid parents/)
  j=await appendHolonEvent(j,draft('weave','An authored, traceable spatial medium',ids))
  assert.equal(j.events.at(-1).kind,'weave')
  assert.equal(j.events.at(-1).actor,'human')
})

test('final artifact requires an existing human weave',async()=>{
  const first=await seed()
  await assert.rejects(()=>appendHolonEvent(first,draft('artifact','Premature claim',[first.events[0].id])),/artifact requires/)
  let j=await withTwoSelections()
  const ids=j.events.filter(e=>e.kind==='select').map(e=>e.id)
  j=await appendHolonEvent(j,draft('weave','Coherent platform',ids))
  const final=await appendHolonEvent(j,draft('artifact','Documented prototype intent',[j.events.at(-1).id]))
  assert.equal(final.events.at(-1).kind,'artifact')
})

test('changing text without recalculating hash fails closed',async()=>{
  const j=await withTwoSelections()
  const corrupted=JSON.parse(JSON.stringify(j))
  corrupted.events[1].text='Substituted AI-written content'
  await assert.rejects(()=>verifyHolonTrace(corrupted),/hash mismatch/)
})

test('changing actor label without recomputing hash fails closed',async()=>{
  const j=await withTwoSelections()
  const corrupted=JSON.parse(JSON.stringify(j))
  corrupted.events[1].actor='model'
  await assert.rejects(()=>verifyHolonTrace(corrupted),/actor\/source disagreement/)
})

test('untrusted imported stream cannot add undeclared fields',async()=>{
  const j=await seed()
  const corrupted=JSON.parse(JSON.stringify(j))
  corrupted.events[0].verified_authority=true
  await assert.rejects(()=>verifyHolonTrace(corrupted),/unexpected fields/)
})

test('event cannot point to future or missing parent',async()=>{
  const j=await seed()
  await assert.rejects(()=>appendHolonEvent(j,draft('branch','Unknown', ['missing-source-id'],'human','imagination')),/parent not in prior history/)
})

test('duplicate identifiers and invalid event budget cannot be admitted',async()=>{
  const j=await seed()
  const d=draft('branch','Copied identifier',[j.events[0].id],'human','imagination')
  await assert.rejects(()=>appendHolonEvent(j,{...d,id:j.events[0].id}),/duplicate id/)
  const oversize={schema:j.schema,events:Array(MAX_HOLON_EVENTS+1).fill(j.events[0])}
  await assert.rejects(()=>verifyHolonTrace(oversize),/event budget exceeded/)
})

test('portable JSON verifies after a round-trip, with no cloud or model invocation',async()=>{
  const j=await withTwoSelections()
  const restored=await verifyHolonTrace(JSON.parse(JSON.stringify(j)))
  assert.deepEqual(restored,j)
  const source=readFileSync(new URL('../src/components/HolonMaximusStudio.tsx',import.meta.url),'utf8')
  assert.match(source,/file\.size>256_000/)
  assert.match(source,/verifyHolonTrace\(parsed\)/)
  assert.doesNotMatch(source,/fetch\(|setInterval\(|new WebSocket|OpenAI|anthropic\.com/)
})

test('existing AEGIS route and original Holon material are reused',()=>{
  const app=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8')
  const shell=readFileSync(new URL('../src/HolonGlass.tsx',import.meta.url),'utf8')
  const ui=readFileSync(new URL('../src/components/HolonMaximusStudio.tsx',import.meta.url),'utf8')
  assert.match(app,/case '\/holon': return <HolonRoute route="holon"><HolonMaximusStudio/)
  assert.match(shell,/href:'\/holon'/)
  assert.match(ui,/import \{ SovereignMatter \} from '\.\/SovereignMatter\.js'/)
  assert.match(ui,/motionOverride=\{false\}/)
  assert.match(ui,/Human intent ≠ LLM proposal ≠ agent execution ≠ verifier receipt/)
})
