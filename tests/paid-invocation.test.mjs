import test from 'node:test'
import assert from 'node:assert/strict'
import { handlePaidInvocation } from '../worker-src/paidInvocation.ts'

const env={ANTHROPIC_API_KEY:'fake-server-only-secret'}
const body={objective:'   Investigate the cause of a red build   ',mode:'analysis',live:true}
const request=(payload=body,headers={})=>new Request('https://aegis-vertex.aegisomega.com/platform/collaborate',{
  method:'POST',headers:{'content-type':'application/json',...headers},body:typeof payload==='string'?payload:JSON.stringify(payload)
})
const make=()=>{
 const calls={auth:0,provider:0}
 const deps={
  originAllowed:()=>true,cors:()=>({}),
  reserve:async()=>{calls.auth++;return {admitted:true}},
  provider:async(objective,mode,key)=>{calls.provider++;assert.equal(objective,'Investigate the cause of a red build');assert.equal(mode,'analysis');assert.equal(key,env.ANTHROPIC_API_KEY);return {result:'test-only'}},
  envelope:(id,data)=>({id,data,is_replay_reconstructable:null}),id:()=> 'collab-test-id'
 }
 return {calls,deps}
}

test('valid admission calls provider exactly once after auth and returns bounded envelope',async()=>{
 const {calls,deps}=make()
 const r=await handlePaidInvocation(request(),env,deps)
 assert.equal(r.status,200)
 assert.deepEqual(calls,{auth:1,provider:1})
 assert.equal((await r.json()).data.result,'test-only')
})
test('browser origin rejection executes neither authorization nor provider',async()=>{
 const {calls,deps}=make();deps.originAllowed=()=>false
 const r=await handlePaidInvocation(request(body,{origin:'https://evil.example'}),env,deps)
 assert.equal(r.status,403);assert.equal((await r.json()).code,'ORIGIN_FORBIDDEN')
 assert.deepEqual(calls,{auth:0,provider:0})
})
test('without configured provider key nothing executes',async()=>{
 const {calls,deps}=make();const r=await handlePaidInvocation(request(),{},deps)
 assert.equal(r.status,503);assert.deepEqual(calls,{auth:0,provider:0})
})
test('malformed json and oversize inputs never reach admission',async()=>{
 const {calls,deps}=make()
 assert.equal((await handlePaidInvocation(request('{bad'),env,deps)).status,400)
 assert.equal((await handlePaidInvocation(request({objective:'x'.repeat(701),mode:'analysis',live:true}),env,deps)).status,400)
 assert.equal((await handlePaidInvocation(request(' '.repeat(4097)),env,deps)).status,413)
 assert.deepEqual(calls,{auth:0,provider:0})
})
test('unsupported modes reject before reservation',async()=>{
 const {calls,deps}=make();let r=await handlePaidInvocation(request({...body,mode:'admin'}),env,deps)
 assert.equal(r.status,400);assert.deepEqual(calls,{auth:0,provider:0})
})
test('explicit demo never silently bills provider',async()=>{
 const {calls,deps}=make();let r=await handlePaidInvocation(request({...body,live:false}),env,deps)
 assert.equal(r.status,501);assert.equal((await r.json()).code,'DEMO_NOT_IMPLEMENTED')
 assert.deepEqual(calls,{auth:0,provider:0})
})
test('denied quota never reaches provider',async()=>{
 const {calls,deps}=make();deps.reserve=async()=>{calls.auth++;return{admitted:false,code:'KEY_INVALID_REVOKED_OR_LIMIT_REACHED',status:403}}
 const r=await handlePaidInvocation(request(),env,deps)
 assert.equal(r.status,403);assert.deepEqual(calls,{auth:1,provider:0})
})
test('provider error returns 502 without leaking keys or upstream text',async()=>{
 const {calls,deps}=make();deps.provider=async()=>{calls.provider++;throw Error('secret backend message')}
 const r=await handlePaidInvocation(request(),env,deps);const raw=await r.text()
 assert.equal(r.status,502);assert.deepEqual(calls,{auth:1,provider:1})
 assert.ok(!raw.includes('secret backend message')&&!raw.includes('fake-server-only-secret'))
})
test('missing content-type rejected',async()=>{
 const {calls,deps}=make();let r=await handlePaidInvocation(request(body,{'content-type':'text/plain'}),env,deps)
 assert.equal(r.status,415);assert.deepEqual(calls,{auth:0,provider:0})
})