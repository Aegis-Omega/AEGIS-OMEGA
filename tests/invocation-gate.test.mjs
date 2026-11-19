import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { reservePaidInvocation, paidOriginAllowed, paidCors } from '../worker-src/invocationGate.ts'

const valid = 'aegis_'+ 'A'.repeat(32)
const env = { SUPABASE_URL: 'https://demo.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'private-service-role-fixture' }
const request = (k=valid)=>new Request('https://aegis-vertex.aegisomega.com/platform/collaborate',{method:'POST',headers:{'x-api-key':k}})

const allowed = async (url, init) => {
  assert.equal(url,'https://demo.supabase.co/rest/v1/rpc/reserve_aegis_edge_collaboration')
  assert.equal(init.method,'POST')
  assert.equal(init.headers.apikey,env.SUPABASE_SERVICE_ROLE_KEY)
  assert.equal(init.headers.Authorization,'Bearer '+env.SUPABASE_SERVICE_ROLE_KEY)
  const digest=createHash('sha256').update(valid).digest('hex')
  assert.deepEqual(JSON.parse(init.body),{p_key_hash:digest})
  assert.equal(init.body.includes(valid),false)
  return new Response('true',{status:200,headers:{'content-type':'application/json'}})
}

test('missing key fails before network',async()=>{
  let called=false
  const r=await reservePaidInvocation(request(''),env,async()=>{called=true;throw Error('network')})
  assert.deepEqual(r,{admitted:false,status:401,code:'API_KEY_REQUIRED'})
  assert.equal(called,false)
})
test('bare prefix is not accepted',async()=>{
  const r=await reservePaidInvocation(request('aegis_any'),env,async()=>{throw Error('should not call')})
  assert.equal(r.status,401)
})
test('missing backend fails closed with zero calls',async()=>{
  const r=await reservePaidInvocation(request(),{},async()=>{throw Error('called')})
  assert.equal(r.status,503)
})
test('valid key is SHA-256 hashed, atomically reserved and never transmitted raw',async()=>{
  assert.deepEqual(await reservePaidInvocation(request(),env,allowed),{admitted:true})
})
test('revoked or depleted key is denied, not disclosed',async()=>{
  const r=await reservePaidInvocation(request(),env,async()=>new Response('false',{status:200}))
  assert.deepEqual(r,{admitted:false,status:403,code:'KEY_INVALID_REVOKED_OR_LIMIT_REACHED'})
})
test('malformed RPC response fails closed',async()=>{
  const r=await reservePaidInvocation(request(),env,async()=>new Response('"true"',{status:200}))
  assert.equal(r.status,503)
})
test('auth RPC error and network failure are fail-closed',async()=>{
  const r=await reservePaidInvocation(request(),env,async()=>new Response('no',{status:500}))
  assert.equal(r.status,503)
  const s=await reservePaidInvocation(request(),env,async()=>{throw Error('network down')})
  assert.equal(s.status,503)
})
test('untrusted browser origins cannot use paid CORS',()=>{
  assert.equal(paidOriginAllowed('https://evil.example'),false)
  assert.equal(paidOriginAllowed('https://aegisomega.com'),true)
  assert.equal(paidOriginAllowed(null),true) // CLI callers authenticated separately
  assert.equal(paidCors('https://evil.example')['Access-Control-Allow-Origin'],undefined)
  assert.equal(paidCors('https://aegisomega.com')['Access-Control-Allow-Origin'],'https://aegisomega.com')
})
test('malicious Supabase origin config refused before network',async()=>{
  const r=await reservePaidInvocation(request(),{...env,SUPABASE_URL:'http://127.0.0.1:54321'},async()=>{throw Error('should not call')})
  assert.equal(r.status,503)
})