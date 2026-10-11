import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {stripTypeScriptTypes} from 'node:module'
import {webcrypto} from 'node:crypto'

const source=stripTypeScriptTypes(readFileSync(new URL('../index.ts',import.meta.url),'utf8'),{mode:'strip'})
const SECRET='slack-signature-fixture', CAP='X'.repeat(48), TEAM='T12345', USER='U12345', CHANNEL='C12345'
async function signed(){
 const body=new URLSearchParams({user_id:USER,team_id:TEAM,channel_id:CHANNEL,
   user_name:'reviewer',text:'test output',trigger_id:'13345.2345.signedEvent'}).toString()
 const stamp=String(Math.floor(Date.now()/1000))
 const key=await webcrypto.subtle.importKey('raw',new TextEncoder().encode(SECRET),{name:'HMAC',hash:'SHA-256'},false,['sign'])
 const mac=await webcrypto.subtle.sign('HMAC',key,new TextEncoder().encode(`v0:${stamp}:${body}`))
 return new Request('https://mock.invalid/slack-events',{method:'POST',headers:{'content-type':'application/x-www-form-urlencoded',
 'x-slack-request-timestamp':stamp,'x-slack-signature':'v0='+Buffer.from(mac).toString('hex')},body})
}
async function attempt(ack){
 const calls={outbound:0,complete:0,deliveryMessages:0};let handler;const pending=[]
 const Deno={env:{get:key=>({SLACK_SIGNING_SECRET:SECRET,SLACK_BOT_TOKEN:'xoxb-fixture',SUPABASE_URL:'https://mock.invalid',
   AEGIS_AGENT_INVOKE_SECRET:CAP,AEGIS_SLACK_ALLOWED_TEAM_IDS:TEAM,
   AEGIS_SLACK_ALLOWED_USER_IDS:USER,AEGIS_SLACK_ALLOWED_CHANNEL_IDS:CHANNEL})[key]??''},serve:fn=>handler=fn}
 const fakeFetch=async(url,opts)=>{
  calls.outbound++
  if(String(url)==='https://slack.com/api/chat.postMessage'){
   calls.deliveryMessages++;return Response.json(ack)
  }
  if(String(url).endsWith('/functions/v1/agent')){
   const b=JSON.parse(opts.body)
   if(!b.operation || b.operation==='dispatch')return Response.json({status:'RESULT_STORED'})
   if(b.operation==='claim_delivery')return Response.json({status:'DELIVERY_LEASED',result:'sample'})
   if(b.operation==='complete_delivery'){calls.complete++;return Response.json({ok:true})}
  }
  throw Error('UNEXPECTED_CALL')
 }
 new Function('Deno','EdgeRuntime','crypto','fetch','console',source)(Deno,{waitUntil:p=>pending.push(p)},webcrypto,fakeFetch,{error(){}})
 assert.equal((await handler(await signed())).status,200)
 await Promise.all(pending)
 return calls
}
test('Slack bare ok:true without message coordinates is NOT a delivery receipt',async()=>{
 const r=await attempt({ok:true})
 assert.equal(r.complete,0,'must not commit DELIVERED based on unverifiable Slack acknowledgement')
})
test('Slack ok:true for unexpected channel is NOT a delivery receipt',async()=>{
 const r=await attempt({ok:true,channel:'CWRONG',ts:'1760000000.000001'})
 assert.equal(r.complete,0,'must not commit DELIVERED to wrong Slack channel')
})
test('Slack ok:true + exact channel + message timestamp IS accepted',async()=>{
 const r=await attempt({ok:true,channel:CHANNEL,ts:'1760000000.000001'})
 assert.equal(r.complete,1,'exact channel and timestamp must be confirmed once')
})
