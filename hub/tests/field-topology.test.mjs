import test from 'node:test'
import assert from 'node:assert/strict'
import { fieldProjection, sourceSnapshot } from '../src/fieldTopology.ts'

const sources = Object.freeze([
  Object.freeze({id:'a',index:'01',title:'Formal',area:'formal',kind:'CODE',status:'OPEN',description:'Proofs',question:'Is it closed?',boundaries:Object.freeze(['Hypothesis remains']) ,href:'https://example.org/a',action:'Read'}),
  Object.freeze({id:'b',index:'02',title:'Biology',area:'biology',kind:'PRIVATE',status:'UNKNOWN',description:'Archive',question:'Reproduced?',boundaries:Object.freeze(['Dataset private','No holdout']),action:'Not public'}),
  Object.freeze({id:'c',index:'03',title:'Physics',area:'physics',kind:'SOURCE',status:'OPEN',description:'Research',question:'Physical model?',boundaries:Object.freeze([]),href:'https://example.org/c',action:'Inspect'}),
])
test('empty view is genuinely empty',()=>{
 const f=fieldProjection([], 'absent');assert.deepEqual(f.points,[]);assert.deepEqual(f.links,[]);assert.equal(f.selection,null)
})
test('one source retains finite positions',()=>{
 const f=fieldProjection(sources.slice(0,1),'a');assert(f.points.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.scale)))
})
test('every edge is a real membership link, not fabricated proof relation',()=>{
 const f=fieldProjection(sources,'b');assert.equal(f.links.length, sources.length)
 assert(f.links.every(e=>e.from==='atlas' && e.meaning==='indexed_source' && sources.some(s=>s.id===e.to)))
})
test('selection and fallback follow actual filtered records',()=>{
 assert.equal(fieldProjection(sources,'b').selection.id,'b')
 assert.equal(fieldProjection(sources.slice(1),'a').selection.id,'b')
})
test('3D projection stays inside visible bounds for extreme or invalid input',()=>{
 for(const yaw of [-1e18,-3.14,0,3.14,1e18,Number.NaN]){
  const f=fieldProjection(sources,'a',yaw)
  assert(f.points.every(p=>p.x>=13&&p.x<=87&&p.y>=17&&p.y<=83&&p.scale>=.73&&p.scale<=1.44))
 }
})
test('spatial view actually changes when camera rotates',()=>{
 const before=fieldProjection(sources,'a',0).points.map(p=>p.x)
 const after=fieldProjection(sources,'a',.7).points.map(p=>p.x)
 assert.notDeepEqual(before,after)
})
test('snapshot is unsigned and contains source limits, no synthetic verification',()=>{
 const s=sourceSnapshot(sources[1]);assert(s.includes('UNSIGNED'));assert(s.includes('Dataset private'));assert(s.includes('NOT PUBLIC'));assert(s.includes('NOT A VERIFIED RUN'))
})
test('input arrays stay unchanged',()=>{fieldProjection(sources,'a',.3);assert.equal(sources[0].id,'a')})