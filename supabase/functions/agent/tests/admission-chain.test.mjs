// Node 22+: node --test supabase/functions/agent/tests/admission-chain.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { webcrypto } from 'node:crypto'
import { fileURLToPath } from 'node:url'
// Node >=22.16 provides built-in TypeScript syntax stripping. No npm install needed.
const root = fileURLToPath(new URL('../../../../', import.meta.url))
function edge(path,env={},transport=()=>{throw Error('UNEXPECTED_NETWORK')},backgroundAvailable=true) {
  const src=readFileSync(root+path,'utf8').replace(/^import .*$/gm,'')
  const js=stripTypeScriptTypes(src, { mode: 'strip' })
  let handler
  const pending=[]
  const EdgeRuntime=backgroundAvailable ? {waitUntil:p=>pending.push(p)} : undefined
  const Deno={env:{get:n=>env[n]??''},serve:f=>{handler=f}}
  const body = path === 'supabase/functions/agent/index.ts' ? 'const CORS = {};\n' + js : js
  new Function('Deno','fetch','createClient','crypto','EdgeRuntime',body)(Deno,transport,()=>{throw Error('UNEXPECTED_DB')},webcrypto,EdgeRuntime)
  assert.equal(typeof handler,'function')
  handler.pending=pending
  return handler
}
async function signed(text,secret,time=String(Math.floor(Date.now()/1000)),channel='C123'){
  const body=new URLSearchParams({text,channel_id:channel,user_id:'U_OPERATOR'}).toString()
  const key=await webcrypto.subtle.importKey('raw',new TextEncoder().encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign'])
  const mac=await webcrypto.subtle.sign('HMAC',key,new TextEncoder().encode('v0:'+time+':'+body))
  return new Request('https://host/functions/v1/slack-events',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded','x-slack-request-timestamp':time,'x-slack-signature':'v0='+Buffer.from(mac).toString('hex')},body})
}
test('agent denies unauthorized before paid/API/DB effects',async()=>{
  let count=0
  const h=edge('supabase/functions/agent/index.ts',{ANTHROPIC_API_KEY:'dummy',AEGIS_AGENT_INVOKE_SECRET:'A'.repeat(48)},()=>{count++;throw Error('PAID_NETWORK')})
  for(const headers of [{},{'x-aegis-agent-secret':'wrong'}]){
    const r=await h(new Request('https://host/agent',{method:'POST',headers,body:'{"task":"read purchases"}'}))
    assert.equal(r.status,401)
  }
  assert.equal(count,0)
})
test('unconfigured agent fails closed',async()=>{
  const h=edge('supabase/functions/agent/index.ts',{ANTHROPIC_API_KEY:'dummy'})
  const r=await h(new Request('https://host/agent',{method:'POST',body:'{"task":"test"}'}))
  assert.equal(r.status,503)
  assert.equal((await r.json()).error,'AGENT_AUTH_NOT_CONFIGURED')
})
test('Slack missing signing secret or unauthorized user cannot dispatch',async()=>{
  let count=0
  const no=edge('supabase/functions/slack-events/index.ts',{},()=>{count++;throw Error('NETWORK')})
  assert.equal((await no(await signed('task','S'))).status,401)
  const yes=edge('supabase/functions/slack-events/index.ts',{SLACK_SIGNING_SECRET:'S',AEGIS_AGENT_INVOKE_SECRET:'A'.repeat(48)},()=>{count++;throw Error('NETWORK')})
  assert.equal((await yes(await signed('task','S'))).status,403)
  assert.equal((await yes(await signed('task','S',String(Math.floor(Date.now()/1000)-3600)))).status,401)
  assert.equal(count,0)
})
test('signed allowlisted Slack event passes dedicated capability, not NOTIFY_SECRET',async()=>{
  const secret='S',capability='A'.repeat(48),requests=[]
  const h=edge('supabase/functions/slack-events/index.ts',{SLACK_SIGNING_SECRET:secret,AEGIS_AGENT_INVOKE_SECRET:capability,AEGIS_SLACK_ALLOWED_USER_IDS:'U_OPERATOR',AEGIS_SLACK_ALLOWED_CHANNEL_IDS:'C123'},async(url,options)=>{
    requests.push({url,options})
    return new Response(JSON.stringify({result:'mock only'}),{status:200})
  })
  const ack=await h(await signed('a sensitive task with private customer data',secret))
  assert.equal(ack.status,200)
  const ackBody=await ack.json()
  assert.equal(ackBody.response_type,'ephemeral')
  assert.equal(JSON.stringify(ackBody).includes('private customer data'),false)
  assert.equal(h.pending.length,1)
  await Promise.all(h.pending)
  assert.equal(requests.length,1)
  assert.equal(requests[0].options.headers['x-aegis-agent-secret'],capability)
  assert.equal(requests[0].options.headers['x-notify-secret'],undefined)
})
test('allowed Slack user cannot dispatch to an unapproved channel',async()=>{
  let calls=0
  const h=edge('supabase/functions/slack-events/index.ts',{
    SLACK_SIGNING_SECRET:'S',
    AEGIS_AGENT_INVOKE_SECRET:'A'.repeat(48),
    AEGIS_SLACK_ALLOWED_USER_IDS:'U_OPERATOR',
    AEGIS_SLACK_ALLOWED_CHANNEL_IDS:'C_PRIVATE',
  },()=>{calls++;throw Error('UNAUTHORIZED_NETWORK')})
  const r=await h(await signed('show customer emails','S',undefined,'C123'))
  assert.equal(r.status,403)
  assert.equal(calls,0)
})
test('Slack channel must be configured (fail closed)',async()=>{
  let calls=0
  const h=edge('supabase/functions/slack-events/index.ts',{
    SLACK_SIGNING_SECRET:'S',
    AEGIS_AGENT_INVOKE_SECRET:'A'.repeat(48),
    AEGIS_SLACK_ALLOWED_USER_IDS:'U_OPERATOR',
  },()=>{calls++;throw Error('UNEXPECTED_NETWORK')})
  const r=await h(await signed('show customer emails','S'))
  assert.equal(r.status,403)
  assert.equal(calls,0)
})
test('Slack refuses to acknowledge execution without background lifetime support',async()=>{
  let calls=0
  const h=edge('supabase/functions/slack-events/index.ts',{
    SLACK_SIGNING_SECRET:'S',AEGIS_AGENT_INVOKE_SECRET:'A'.repeat(48),
    AEGIS_SLACK_ALLOWED_USER_IDS:'U_OPERATOR',AEGIS_SLACK_ALLOWED_CHANNEL_IDS:'C123',
  },()=>{calls++;throw Error('UNEXPECTED_NETWORK')},false)
  const r=await h(await signed('task','S'))
  assert.equal(r.status,503)
  assert.equal(h.pending.length,0)
  assert.equal(calls,0)
})
test('authorized app mention registers background work',async()=>{
  const secret='S',requests=[]
  const body=JSON.stringify({type:'event_callback',event:{
    type:'app_mention',user:'U_OPERATOR',channel:'C123',text:'<@U_BOT> inspect evidence',ts:'1.0'
  }})
  const timestamp=String(Math.floor(Date.now()/1000))
  const key=await webcrypto.subtle.importKey('raw',new TextEncoder().encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign'])
  const mac=await webcrypto.subtle.sign('HMAC',key,new TextEncoder().encode('v0:'+timestamp+':'+body))
  const req=new Request('https://host/functions/v1/slack-events',{
    method:'POST',headers:{'content-type':'application/json','x-slack-request-timestamp':timestamp,
      'x-slack-signature':'v0='+Buffer.from(mac).toString('hex')},body
  })
  const h=edge('supabase/functions/slack-events/index.ts',{
    SLACK_SIGNING_SECRET:secret,AEGIS_AGENT_INVOKE_SECRET:'A'.repeat(48),
    AEGIS_SLACK_ALLOWED_USER_IDS:'U_OPERATOR',AEGIS_SLACK_ALLOWED_CHANNEL_IDS:'C123',
  },async(url,options)=>{requests.push({url,options});return Response.json({result:'mock'})})
  assert.equal((await h(req)).status,200)
  assert.equal(h.pending.length,1)
  await Promise.all(h.pending)
  assert.equal(requests.length,1)
  assert.equal(requests[0].options.headers['x-aegis-agent-secret'],'A'.repeat(48))
})
test('bridge refuses synthetic attestation',async()=>{
  const h=edge('supabase/functions/bridge/index.ts')
  for(const ep of ['node','telemetry','resonance']){
    const r=await h(new Request('https://host/functions/v1/bridge/'+ep))
    assert.equal(r.status,503)
    const data=await r.json()
    assert.equal(data.verified,false)
    assert.equal(data.authority_effect,'NONE')
    assert.notEqual(data.t0_verdict,true)
    assert.notEqual(data.is_certified,true)
  }
})
