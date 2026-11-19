import test from 'node:test'
import assert from 'node:assert/strict'
import {handlePaidInvocation} from '../worker-src/paidInvocation.ts'
const env = {ANTHROPIC_API_KEY:'fixture-only'}
const request = mode => new Request('https://example.test/platform/collaborate', {
 method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({objective:'Check a run',mode,live:true})
})
const calls = {reserve:0,provider:0}
const deps={originAllowed:()=>true,cors:()=>({}),reserve:async()=>{calls.reserve++;return {admitted:true}},provider:async()=>{calls.provider++;return {}} ,envelope:(id,v)=>({id,v}),id:()=> 'x'}
test('malformed object mode responds 400, not a thrown TypeError, and no billing', async()=>{
 calls.reserve=0;calls.provider=0
 const res=await handlePaidInvocation(request({toString:null}),env,deps)
 assert.equal(res.status,400)
 assert.equal((await res.json()).code,'INVALID_REQUEST')
 assert.deepEqual(calls,{reserve:0,provider:0})
})
test('array, numeric and null modes are denied without reservation',async()=>{
 for(const mode of [[],{},null,1,true]){
  calls.reserve=0;calls.provider=0
  const res=await handlePaidInvocation(request(mode),env,deps)
  assert.equal(res.status,400)
  assert.deepEqual(calls,{reserve:0,provider:0})
 }
})
