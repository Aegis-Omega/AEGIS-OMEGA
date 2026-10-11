// Source-bound Slack rendering contract: no paid provider, DB, or Slack calls.
import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {stripTypeScriptTypes} from 'node:module'
import {webcrypto} from 'node:crypto'

const source=stripTypeScriptTypes(readFileSync(new URL('../index.ts',import.meta.url),'utf8'),{mode:'strip'})
const SECRET='slack-test-signing-secret'
const CAP='D'.repeat(48)
const TEAM='T112233', ACTOR='U112233', CHANNEL='C112233'
async function signed(){
  const body=new URLSearchParams({
    user_id:ACTOR,team_id:TEAM,channel_id:CHANNEL,user_name:'operator',
    text:'provide result',trigger_id:'134243.934343.abc42',
  }).toString()
  const now=String(Math.floor(Date.now()/1000))
  const k=await webcrypto.subtle.importKey('raw',new TextEncoder().encode(SECRET),
    {name:'HMAC',hash:'SHA-256'},false,['sign'])
  const sig='v0='+Buffer.from(new Uint8Array(await webcrypto.subtle.sign('HMAC',k,
    new TextEncoder().encode(`v0:${now}:${body}`)))).toString('hex')
  return new Request('https://mock.invalid/slack-events',{method:'POST',
    headers:{'content-type':'application/x-www-form-urlencoded',
      'x-slack-request-timestamp':now,'x-slack-signature':sig},body})
}
test('untrusted result cannot trigger Slack mrkdwn, mentions or link expansion',async()=>{
  const untrusted='ALERT <!channel> <@U112233> <https://example.invalid|verify> *fake bold*'
  let handler;const pending=[],messages=[]
  const Deno={env:{get:k=>({
    SLACK_SIGNING_SECRET:SECRET,SLACK_BOT_TOKEN:'xoxb-mock',
    SUPABASE_URL:'https://mock.invalid',AEGIS_AGENT_INVOKE_SECRET:CAP,
    AEGIS_SLACK_ALLOWED_TEAM_IDS:TEAM,AEGIS_SLACK_ALLOWED_USER_IDS:ACTOR,
    AEGIS_SLACK_ALLOWED_CHANNEL_IDS:CHANNEL,
  })[k]||''},serve:f=>handler=f}
  async function mockFetch(url,opts){
    if(String(url)==='https://slack.com/api/chat.postMessage'){
      messages.push(JSON.parse(opts.body))
      return Response.json({ok:true})
    }
    if(String(url).endsWith('/functions/v1/agent')){
      const request=JSON.parse(opts.body)
      if(!request.operation || request.operation==='dispatch')
        return Response.json({status:'RESULT_STORED'})
      if(request.operation==='claim_delivery')
        return Response.json({status:'DELIVERY_LEASED',result:untrusted})
      if(request.operation==='complete_delivery')
        return Response.json({ok:true})
    }
    throw Error('Unexpected outbound request')
  }
  new Function('Deno','EdgeRuntime','crypto','fetch','console',source)(
    Deno,{waitUntil:p=>pending.push(p)},webcrypto,mockFetch,{error(){}}
  )
  assert.equal((await handler(await signed())).status,200)
  await Promise.all(pending)
  assert.equal(messages.length,1)
  const msg=messages[0]
  assert.equal(msg.channel,CHANNEL)
  assert.equal(msg.mrkdwn,false)
  assert.equal(msg.parse,'none')
  assert.equal(msg.link_names,false)
  assert.ok(msg.text.includes(untrusted))
  assert.match(msg.text,/^AEGIS Ω — /)
})
