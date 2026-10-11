// AEGIS encrypted outbox: exact-source mock integration, Node 22.16+.
// No network, provider credentials or production database are used.
import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {stripTypeScriptTypes} from 'node:module'
import {webcrypto} from 'node:crypto'
const a=stripTypeScriptTypes(readFileSync(new URL('../index.ts',import.meta.url),'utf8').replace(/^import .*$/gm,''),{mode:'strip'})
const s=stripTypeScriptTypes(readFileSync(new URL('../../slack-events/index.ts',import.meta.url),'utf8'),{mode:'strip'})
const CAP='K'.repeat(48), SIGN='Q'.repeat(40), KEY=Buffer.alloc(32,7).toString('base64')
const CID='C123456', ID='slack:event:Ev1234567890', ACTOR='UOPERATOR', TEAM='T12345'
const env={AEGIS_AGENT_INVOKE_SECRET:CAP,ANTHROPIC_API_KEY:'fake',SUPABASE_URL:'https://mock.invalid',SUPABASE_SERVICE_ROLE_KEY:'fake',AEGIS_RESULT_ENCRYPTION_KEY_B64:KEY}
function db(){
  const claimed=new Set(),rows=new Map(), stats={paid:0,claim:0,lease:0}
  return {rows,stats,createClient:()=>({
    from(table){
      if(table==='aegis_agent_dispatch_claims_v1')return {insert:async({event_digest})=>{
        stats.claim++
        if(claimed.has(event_digest))return {error:{code:'23505'}}
        claimed.add(event_digest);return {error:null}
      }}
      assert.equal(table,'aegis_agent_result_outbox_v1')
      return {insert:async row=>{
        rows.set(row.event_digest,{...row,state:'READY',attempt:null,count:0});return {error:null}
      }}
    },
    async rpc(name,p){
      const row=rows.get(p.p_event_digest)
      if(name==='aegis_outbox_claim_delivery_v1'){
        if(!row||row.destination_digest!==p.p_destination_digest||row.state!=='READY'||row.count>=3)return {data:[],error:null}
        row.state='SENDING';row.attempt=p.p_attempt_id;row.count++;stats.lease++
        return {data:[{ciphertext_b64:row.ciphertext_b64,iv_b64:row.iv_b64}],error:null}
      }
      assert.equal(name,'aegis_outbox_complete_delivery_v1')
      if(!row||row.state!=='SENDING'||row.attempt!==p.p_attempt_id||row.destination_digest!==p.p_destination_digest)return {data:false,error:null}
      row.state=p.p_delivered?'DELIVERED':'READY';row.attempt=null
      return {data:true,error:null}
    }
  })}
}
function agent(data,config=env,overrideFetch=null){
  let handler
  const Deno={env:{get:n=>config[n]??''},serve:f=>handler=f}
  const fetch=overrideFetch??(async()=>{data.stats.paid++;return Response.json({stop_reason:'end_turn',content:[{type:'text',text:'private result'}]})})
  new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',a)(Deno,fetch,webcrypto,data.createClient,{}, {error(){}},atob,btoa)
  return handler
}
async function send(h,op='dispatch',fields={},token=CAP){
  const res=await h(new Request('https://mock.invalid/agent',{method:'POST',headers:{'x-aegis-agent-secret':token},body:JSON.stringify({
    operation:op,task:'check',dispatch_id:ID,channel_id:CID,actor_id:ACTOR,team_id:TEAM,...fields,
  })}))
  return [res.status,await res.json()]
}
function slack(h, mode='accepted'){
  let handler;const pending=[],network=[]
  const Deno={env:{get:n=>({...env,SLACK_SIGNING_SECRET:SIGN,SLACK_BOT_TOKEN:'fake',AEGIS_SLACK_ALLOWED_USER_IDS:ACTOR,AEGIS_SLACK_ALLOWED_CHANNEL_IDS:CID,AEGIS_SLACK_ALLOWED_TEAM_IDS:TEAM})[n]??''},serve:f=>handler=f}
  const fetch=async(url,opts)=>{
    network.push(String(url))
    if(String(url).endsWith('/functions/v1/agent'))return h(new Request(String(url),{method:'POST',headers:opts.headers,body:opts.body}))
    assert.equal(String(url),'https://slack.com/api/chat.postMessage')
    if(mode==='rejected')return Response.json({ok:false,error:'channel_not_found'})
    if(mode==='ambiguous')return new Response('unparseable')
    return Response.json({ok:true})
  }
  new Function('Deno','EdgeRuntime','crypto','fetch','console',s)(Deno,{waitUntil:p=>pending.push(p)},webcrypto,fetch,{error(){}})
  return {handler,pending,network}
}
async function signed(body,ctype='application/x-www-form-urlencoded'){
  const time=String(Math.floor(Date.now()/1000))
  const key=await webcrypto.subtle.importKey('raw',new TextEncoder().encode(SIGN),{name:'HMAC',hash:'SHA-256'},false,['sign'])
  const mac=await webcrypto.subtle.sign('HMAC',key,new TextEncoder().encode('v0:'+time+':'+body))
  return new Request('https://mock.invalid/slack',{method:'POST',headers:{'content-type':ctype,'x-slack-request-timestamp':time,'x-slack-signature':'v0='+Buffer.from(mac).toString('hex')},body})
}
const form=(user=ACTOR,channel=CID)=>new URLSearchParams({user_id:user,team_id:TEAM,channel_id:channel,user_name:'operator',text:'check',trigger_id:'13345224609.738474920.8088930838d88f008e0'}).toString()
test('bearer token rejection precedes paid work',async()=>{const d=db();assert.equal((await send(agent(d),'dispatch',{},'invalid'))[0],401);assert.equal(d.stats.paid,0)})
test('encryption key required before paid work',async()=>{const d=db();assert.equal((await send(agent(d,{...env,AEGIS_RESULT_ENCRYPTION_KEY_B64:''}))[0],503);assert.equal(d.stats.paid,0)})
test('result stored encrypted, no plaintext response',async()=>{
 const d=db(),h=agent(d);const [status,body]=await send(h);assert.equal(status,200);assert.equal(body.status,'RESULT_STORED')
 assert.ok(!JSON.stringify([...d.rows.values()]).includes('private result'));assert.equal(d.stats.paid,1)
})
test('two agents with same event: only one paid model call',async()=>{
 const d=db(),a1=agent(d),a2=agent(d);const r=await Promise.all([send(a1),send(a2)])
 assert.deepEqual(r.map(x=>x[0]).sort((a,b)=>a-b),[200,409]);assert.equal(d.stats.paid,1)
})
test('decryption recovery without provider key',async()=>{
 const d=db();assert.equal((await send(agent(d)))[0],200)
 const h=agent(d,{...env,ANTHROPIC_API_KEY:''})
 const [status,result]=await send(h,'claim_delivery',{attempt_id:crypto.randomUUID()})
 assert.equal(status,200);assert.equal(result.result,'private result');assert.equal(d.stats.paid,1)
})
test('same event cannot be recovered into another Slack channel',async()=>{
 const d=db(),h=agent(d);await send(h);assert.equal((await send(h,'claim_delivery',{attempt_id:crypto.randomUUID(),channel_id:'C999999'}))[0],409)
})
test('confirmed delivery cannot be claimed twice',async()=>{
 const d=db(),h=agent(d);await send(h);const attempt=crypto.randomUUID()
 assert.equal((await send(h,'claim_delivery',{attempt_id:attempt}))[0],200)
 assert.equal((await send(h,'complete_delivery',{attempt_id:attempt,delivery_accepted:true}))[0],200)
 assert.equal((await send(h,'claim_delivery',{attempt_id:crypto.randomUUID()}))[0],409)
})
test('known rejection permits bounded retry, not new inference',async()=>{
 const d=db(),h=agent(d);await send(h)
 for(let i=0;i<3;i++){const attempt=crypto.randomUUID();assert.equal((await send(h,'claim_delivery',{attempt_id:attempt}))[0],200)
 assert.equal((await send(h,'complete_delivery',{attempt_id:attempt,delivery_accepted:false}))[0],200)}
 assert.equal((await send(h,'claim_delivery',{attempt_id:crypto.randomUUID()}))[0],409);assert.equal(d.stats.paid,1)
})
test('ambiguous delivery remains SENDING and requires operator',async()=>{
 const d=db(),h=agent(d);await send(h);const attempt=crypto.randomUUID()
 assert.equal((await send(h,'claim_delivery',{attempt_id:attempt}))[0],200)
 assert.equal((await send(h,'claim_delivery',{attempt_id:crypto.randomUUID()}))[0],409)
 assert.equal((await send(h,'complete_delivery',{attempt_id:crypto.randomUUID(),delivery_accepted:false}))[0],409)
})
test('tampered ciphertext never decrypts to a delivered result',async()=>{
 const d=db(),h=agent(d);await send(h);const row=[...d.rows.values()][0];row.ciphertext_b64='AAAA'
 assert.equal((await send(h,'claim_delivery',{attempt_id:crypto.randomUUID()}))[0],503);assert.equal(row.state,'SENDING')
})
test('signing and allowlisted actor gate Slack before inference',async()=>{
 const d=db(),h=slack(agent(d));const r=await h.handler(await signed(form('U_UNTRUSTED')))
 assert.equal(r.status,403);assert.equal(d.stats.paid,0)
})
test('allowed Slack channel required before inference',async()=>{
 const d=db(),h=slack(agent(d));const r=await h.handler(await signed(form(ACTOR,'C999999')))
 assert.equal(r.status,403);assert.equal(d.stats.paid,0)
})
test('Slack denial enables output-only retry on same event',async()=>{
 const d=db(),h=agent(d);const rejected=slack(h,'rejected')
 assert.equal((await rejected.handler(await signed(form()))).status,200)
 await Promise.all(rejected.pending);assert.equal(d.stats.paid,1);assert.equal([...d.rows.values()][0].state,'READY')
 const ok=slack(h)
 assert.equal((await ok.handler(await signed(form()))).status,200)
 await Promise.all(ok.pending);assert.equal(d.stats.paid,1);assert.equal([...d.rows.values()][0].state,'DELIVERED')
})
test('Slack uncertain delivery never retries inference or result',async()=>{
 const d=db(),h=agent(d);const uncertain=slack(h,'ambiguous')
 assert.equal((await uncertain.handler(await signed(form()))).status,200)
 await Promise.all(uncertain.pending);assert.equal(d.stats.paid,1);assert.equal([...d.rows.values()][0].state,'SENDING')
 const retry=slack(h);assert.equal((await retry.handler(await signed(form()))).status,200)
 await Promise.all(retry.pending);assert.equal(d.stats.paid,1);assert.equal([...d.rows.values()][0].state,'SENDING')
})

test('AES-GCM AAD rejects ciphertext substitution between different events',async()=>{
 const d=db(),h=agent(d)
 assert.equal((await send(h))[0],200)
 assert.equal((await send(h,'dispatch',{dispatch_id:'slack:event:Ev9999999999'}))[0],200)
 const rows=[...d.rows.values()]
 assert.equal(rows.length,2)
 rows[0].ciphertext_b64=rows[1].ciphertext_b64
 rows[0].iv_b64=rows[1].iv_b64
 assert.equal((await send(h,'claim_delivery',{attempt_id:crypto.randomUUID()}))[0],503)
 assert.equal(rows[0].state,'SENDING')
 assert.equal(d.stats.paid,2)
})

test('signed Slack app mention stores and delivers without repeat inference',async()=>{
 const d=db(),h=agent(d),worker=slack(h)
 const body=JSON.stringify({type:'event_callback',team_id:TEAM,event_id:'Ev1234567890',
   event:{type:'app_mention',user:ACTOR,channel:CID,text:'<@BOT> inspect',ts:'123.1'}})
 assert.equal((await worker.handler(await signed(body,'application/json'))).status,200)
 await Promise.all(worker.pending)
 assert.equal(d.stats.paid,1)
 assert.equal([...d.rows.values()][0].state,'DELIVERED')
 assert.equal((await worker.handler(await signed(body,'application/json'))).status,200)
 await Promise.all(worker.pending)
 assert.equal(d.stats.paid,1)
})
test('Slack mention with missing stable event ID cannot dispatch',async()=>{
 const d=db(),worker=slack(agent(d))
 const body=JSON.stringify({type:'event_callback',team_id:TEAM,
   event:{type:'app_mention',user:ACTOR,channel:CID,text:'<@BOT> do work',ts:'123.1'}})
 assert.equal((await worker.handler(await signed(body,'application/json'))).status,400)
 assert.equal(d.stats.paid,0)
})
test('wrong result encryption key leaves delivery uncertain, no new inference',async()=>{
 const d=db(),original=agent(d);assert.equal((await send(original))[0],200)
 const wrong=agent(d,{...env,AEGIS_RESULT_ENCRYPTION_KEY_B64:Buffer.alloc(32,8).toString('base64')})
 assert.equal((await send(wrong,'claim_delivery',{attempt_id:crypto.randomUUID()}))[0],503)
 assert.equal([...d.rows.values()][0].state,'SENDING')
 assert.equal(d.stats.paid,1)
})

test('operator can request output-only recovery from Slack without new model spend',async()=>{
 const d=db(),h=agent(d),rejected=slack(h,'rejected')
 const first=await rejected.handler(await signed(form()))
 assert.equal(first.status,200)
 const ack=await first.json()
 assert.equal(ack.response_type,'ephemeral')
 assert.match(ack.text,/slack:slash:/)
 await Promise.all(rejected.pending)
 assert.equal(d.stats.paid,1)
 assert.equal([...d.rows.values()][0].state,'READY')
 const recovered=slack(h)
 const recoveryForm=new URLSearchParams({
   user_id:ACTOR,team_id:TEAM,channel_id:CID,text:'recover slack:slash:13345224609.738474920.8088930838d88f008e0',
   trigger_id:'13345224609.738474920.NEWRECOVERID',
 }).toString()
 const reply=await recovered.handler(await signed(recoveryForm))
 assert.equal(reply.status,200)
 assert.equal((await reply.json()).response_type,'ephemeral')
 await Promise.all(recovered.pending)
 assert.equal(d.stats.paid,1)
 assert.equal([...d.rows.values()][0].state,'DELIVERED')
})
test('operator recovery rejects arbitrary references before provider call',async()=>{
 const d=db(),worker=slack(agent(d))
 const recoveryForm=new URLSearchParams({user_id:ACTOR,team_id:TEAM,channel_id:CID,
   text:'recover INVALID_REFERENCE',trigger_id:'13345224609.738474920.NEWRECOVERID',
 }).toString()
 assert.equal((await worker.handler(await signed(recoveryForm))).status,400)
 assert.equal(d.stats.paid,0)
})

test('encrypted result cannot be recovered by another allowed user in same channel',async()=>{
 const d=db(),h=agent(d)
 assert.equal((await send(h))[0],200)
 const [status,body]=await send(h,'claim_delivery',{actor_id:'UCOLLEAGUE',team_id:TEAM,attempt_id:crypto.randomUUID()})
 assert.equal(status,409)
 assert.equal(body.error,'OUTBOX_NOT_AVAILABLE')
 assert.equal(d.stats.paid,1)
})
test('result cannot be recovered from another Slack workspace',async()=>{
 const d=db(),h=agent(d)
 assert.equal((await send(h))[0],200)
 assert.equal((await send(h,'claim_delivery',{team_id:'T99999',attempt_id:crypto.randomUUID()}))[0],409)
 assert.equal(d.stats.paid,1)
})
test('signed Slack event with unapproved workspace never calls model',async()=>{
 const d=db(),worker=slack(agent(d))
 const bad=new URLSearchParams({user_id:ACTOR,team_id:'T99999',channel_id:CID,text:'check',
   trigger_id:'13345224609.738474920.8088930838d88f008e0'}).toString()
 assert.equal((await worker.handler(await signed(bad))).status,403)
 assert.equal(d.stats.paid,0)
})
test('agent rejects missing actor and workspace before a paid call',async()=>{
 const d=db(),h=agent(d)
 assert.equal((await send(h,'dispatch',{actor_id:undefined}))[0],400)
 assert.equal((await send(h,'dispatch',{team_id:undefined}))[0],400)
 assert.equal(d.stats.paid,0)
})

test('model-invented notification tool cannot send outside encrypted outbox',async()=>{
 const d=db(),urls=[]
 let turns=0
 const h=agent(d,env,async(url)=>{
   urls.push(String(url))
   if(!String(url).includes('api.anthropic.com')) throw Error('UNGOVERNED_SIDE_EFFECT')
   d.stats.paid++
   return Response.json(turns++===0
     ? {stop_reason:'tool_use',content:[{type:'tool_use',id:'t1',
         name:'send_notification',input:{channel:'both',text:'private customer data'}}]}
     : {stop_reason:'end_turn',content:[{type:'text',text:'refused the notification'}]})
 })
 const [status,body]=await send(h)
 assert.equal(status,503)
 assert.equal(body.error,'MODEL_INCOMPLETE')
 assert.equal(d.rows.size,0)
 assert.equal(urls.length,1)
 assert.ok(urls.every(url=>url.includes('api.anthropic.com')))
})

test('unadvertised repeated model tool calls abort on first paid turn',async()=>{
 const d=db()
 const h=agent(d,env,async()=>{
   d.stats.paid++
   return Response.json({stop_reason:'tool_use',content:[{
     type:'tool_use',id:'t'+d.stats.paid,name:'unavailable_tool',input:{}
   }]})
 })
 const [status,body]=await send(h)
 assert.equal(status,503)
 assert.equal(body.error,'MODEL_INCOMPLETE')
 assert.equal(d.stats.paid,1)
 assert.equal(d.rows.size,0)
})
test('empty final model reply cannot become a paid success receipt',async()=>{
 const d=db()
 const h=agent(d,env,async()=>{
   d.stats.paid++
   return Response.json({stop_reason:'end_turn',content:[{type:'text',text:'   '}]})
 })
 const [status,body]=await send(h)
 assert.equal(status,503)
 assert.equal(body.error,'MODEL_INCOMPLETE')
 assert.equal(d.stats.paid,1)
 assert.equal(d.rows.size,0)
})

test('max_tokens is rejected after one provider call without storing a result',async()=>{
 const d=db()
 const h=agent(d,env,async()=>{
   d.stats.paid++
   return Response.json({stop_reason:'max_tokens',content:[{type:'text',text:'partial answer'}]})
 })
 const [status,body]=await send(h)
 assert.equal(status,503)
 assert.equal(body.error,'MODEL_INCOMPLETE')
 assert.equal(d.stats.paid,1)
 assert.equal(d.rows.size,0)
})
