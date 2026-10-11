import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {stripTypeScriptTypes} from 'node:module'
import {webcrypto} from 'node:crypto'

const source=stripTypeScriptTypes(readFileSync(new URL('../index.ts',import.meta.url),'utf8').replace(/^import .*$/gm,''),{mode:'strip'})
function harness(blocks, dbRows=[{customer_email:'user@example.test',plan:'starter',ls_order_id:'ord_1',updated_at:'2026-10-11T05:00:00Z'}]) {
 const stats={provider:0,db:0,body:[]}
 const chain={select(){return chain},eq(){return chain},order(){return chain},limit(){stats.db++;return Promise.resolve({data:dbRows,error:null})}}
 const Deno={env:{get:n=>({ANTHROPIC_API_KEY:'fake',AEGIS_PURCHASE_READERS:'T12345:UOPERATOR'})[n]??''},serve(){}}
 const fetch=async(_url,opts)=>{stats.provider++;stats.body.push(JSON.parse(opts.body));return Response.json(stats.provider===1?{
    stop_reason:'tool_use',content:blocks
 }:{stop_reason:'end_turn',content:[{type:'text',text:'Verified: 42 purchases'}]})}
 const createClient=()=>({from(t){assert.equal(t,'purchases');return chain}})
 const runAgent=new Function('Deno','fetch','crypto','createClient','CORS','console','atob','btoa',source+'\nreturn runAgent')(Deno,fetch,webcrypto,createClient,{},console,atob,btoa)
 return {run:()=>runAgent('How many purchases are there?','', 'UOPERATOR','T12345'),stats}
}
const one=[{type:'tool_use',name:'query_purchases',id:'tool1',input:{limit:10}}]
test('purchase response only contains actual observed rows, not a hallucinated aggregate',async()=>{
 const h=harness(one)
 const result=await h.run()
 const value=JSON.parse(result.result)
 assert.equal(value.schema,'aegis.purchase_rows.v1')
 assert.equal(value.status,'OBSERVED_DB_ROWS')
 assert.equal(value.rows.length,1)
 assert.equal(value.returned_row_count,1)
 assert.equal(value.is_global_total,false)
 assert.equal(value.rows[0].customer_email,'user@example.test')
 assert.doesNotMatch(result.result,/42 purchases/)
 assert.equal(h.stats.provider,1)
 assert.equal(h.stats.db,1)
})
test('multiple purchase tools in one provider response are rejected before DB query',async()=>{
 const h=harness([...one,{type:'tool_use',name:'query_purchases',id:'tool2',input:{limit:25}}])
 await assert.rejects(h.run(),/MODEL_INCOMPLETE|TOOL_VERIFICATION_FAILED/)
 assert.equal(h.stats.db,0)
 assert.equal(h.stats.provider,1)
})
test('invalid DB result representation cannot masquerade as a sample',async()=>{
 const h=harness(one,{total:42})
 await assert.rejects(h.run(),/TOOL_VERIFICATION_FAILED/)
 assert.equal(h.stats.provider,1)
})

test('adapter must not launder an unexpected secret field into observed purchase evidence',async()=>{
 const h=harness(one,[{customer_email:'user@example.test',plan:'starter',ls_order_id:'ord_1',updated_at:'2026-10-11T05:00:00Z',internal_api_token:'NOT_FOR_OUTPUT'}])
 await assert.rejects(h.run(),/TOOL_VERIFICATION_FAILED/)
 assert.equal(h.stats.provider,1)
 assert.equal(h.stats.db,1)
})
test('adapter must not certify incomplete projected rows',async()=>{
 const h=harness(one,[{customer_email:'user@example.test',plan:'starter'}])
 await assert.rejects(h.run(),/TOOL_VERIFICATION_FAILED/)
})
test('adapter must reject malformed non-nullable timestamp',async()=>{
 const h=harness(one,[{customer_email:null,plan:'starter',ls_order_id:'ord_1',updated_at:'not-a-time'}])
 await assert.rejects(h.run(),/TOOL_VERIFICATION_FAILED/)
})

test('actual nullable customer_email with the full four-column projection remains valid',async()=>{
 const h=harness(one,[{customer_email:null,plan:'full',ls_order_id:'ord_nullable',updated_at:'2026-10-11T05:00:00+00:00'}])
 const value=JSON.parse((await h.run()).result)
 assert.equal(value.status,'OBSERVED_DB_ROWS')
 assert.equal(value.rows[0].customer_email,null)
})

test('impossible Gregorian date cannot be called an observed database timestamp',async()=>{
 const h=harness(one,[{customer_email:'user@example.test',plan:'starter',ls_order_id:'ord_1',updated_at:'2026-02-31T05:00:00Z'}])
 await assert.rejects(h.run(),/TOOL_VERIFICATION_FAILED/)
})

test('valid leap day remains eligible as database evidence',async()=>{
 const h=harness(one,[{customer_email:null,plan:'full',ls_order_id:'ord_leap',updated_at:'2024-02-29T23:30:00+00:00'}])
 assert.equal(JSON.parse((await h.run()).result).rows[0].ls_order_id,'ord_leap')
})
