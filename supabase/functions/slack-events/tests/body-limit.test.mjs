import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {stripTypeScriptTypes} from 'node:module'
import {webcrypto} from 'node:crypto'
const source=stripTypeScriptTypes(readFileSync(new URL('../index.ts',import.meta.url),'utf8'),{mode:'strip'})
function handler(){
  let fn, externalCalls=0
  const Deno={env:{get:n=>n==='SLACK_SIGNING_SECRET'?'test-secret':''},serve:x=>{fn=x}}
  new Function('Deno','EdgeRuntime','crypto','fetch','console',source)(Deno,{waitUntil(){throw Error('background unexpectedly scheduled')}},webcrypto,()=>{externalCalls++;throw Error('NETWORK_NOT_ALLOWED')},{error(){}})
  return {fn,network:()=>externalCalls}
}
function request(body,{stream=false,headers={}}={}){
  if(!stream) return new Request('https://example.invalid/slack',{method:'POST',headers,body})
  const bytes=new TextEncoder().encode(body)
  let i=0
  const streamBody=new ReadableStream({pull(controller){
    if(i>=bytes.length){controller.close();return}
    const end=Math.min(i+4096,bytes.length)
    controller.enqueue(bytes.slice(i,end));i=end
  }})
  return new Request('https://example.invalid/slack',{method:'POST',headers,body:streamBody,duplex:'half'})
}
test('rejects untrusted large fixed request before HMAC',async()=>{
  const h=handler()
  const res=await h.fn(request('A'.repeat(70*1024)))
  assert.equal(res.status,413)
  assert.equal(h.network(),0)
})
test('rejects oversized chunked stream without Content-Length',async()=>{
  const h=handler()
  const res=await h.fn(request('A'.repeat(90*1024),{stream:true}))
  assert.equal(res.status,413)
  assert.equal(h.network(),0)
})
test('rejects over-limit Content-Length before reading an untrusted stream',async()=>{
  const h=handler()
  let pulls=0
  const stream=new ReadableStream({pull(controller){pulls++;controller.enqueue(new TextEncoder().encode('x'));controller.close()}})
  const req=new Request('https://example.invalid/slack',{method:'POST',headers:{'content-length':String(999999)},body:stream,duplex:'half'})
  const res=await h.fn(req)
  assert.equal(res.status,413)
  assert.equal(pulls<=1,true)
})
test('small invalid signature is rejected as unauthorized, not size-limited',async()=>{
  const h=handler()
  const res=await h.fn(request('short-body'))
  assert.equal(res.status,401)
})
