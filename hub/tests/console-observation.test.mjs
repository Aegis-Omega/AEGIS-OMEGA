import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
const require = createRequire(import.meta.url)
const ts = require('typescript')
const source = readFileSync(new URL('../src/lib/platformConsole.ts',import.meta.url),'utf8').replace('import.meta.env.VITE_PLATFORM_URL','({VITE_PLATFORM_URL:undefined}).VITE_PLATFORM_URL')
const js = ts.transpileModule(source, { compilerOptions: { module:ts.ModuleKind.CommonJS, target:ts.ScriptTarget.ES2022 } }).outputText
function load(fetch){
  const exports={}
  vm.runInNewContext(js, { exports, require:()=>({useEffect(){},useState(){},useCallback(){}}), fetch, AbortController, setTimeout,clearTimeout,Date })
  return exports
}
const status={version:'1.0.0',contract_version:'1.0.0',total_agents:39,chain_valid:true,audit_chain_hash:'a'.repeat(64),available:true}
const cal={homeostasis_zone:'optimal',recommendation:'MAINTAIN',window_size:10,fitness_mean:.6,fitness_variance:.01,hd_equivalent:.1,stagnation_rate:0,trend:'rising',constitutional_factor_mean:.9}
function stub(responses){return async url=>{const key=new URL(url).pathname;const d=responses[key];return d===undefined?{ok:false,status:404}:{ok:true,json:async()=>({data:d})}}}
test('offline mode never manufactures verified hash, agency or tools',async()=>{
  const m=load(stub({}));const s=await m.fetchConsoleSnapshot();assert.equal(s.source,'unavailable');assert.equal(s.status.chain_valid,null);assert.equal(s.status.audit_chain_hash,null);assert.equal(s.status.available,false);assert.equal(s.status.total_agents,0);assert.equal(s.tools.length,0);assert.ok(s.checks.every(c=>!c.ok));assert.match(s.reason,/missing|invalid|unavailable/i)
})
test('backend claimed chain_valid=true is still NOT independently verified',async()=>{
 const m=load(stub({'/platform/status':status,'/platform/calibration':cal,'/platform/tools':{tools:[]}}));const s=await m.fetchConsoleSnapshot();assert.equal(s.source,'live');const c=s.checks.find(x=>x.label==='Audit-chain evidence');assert.equal(c.ok,false);assert.match(c.reason,/REPORTED VALID/)
})
test('backend reports invalid chain without converting it to success',async()=>{
 const m=load(stub({'/platform/status':{...status,chain_valid:false},'/platform/calibration':cal}));const s=await m.fetchConsoleSnapshot();assert.equal(s.source,'live');assert.equal(s.checks.find(x=>x.label==='Audit-chain evidence').ok,false);assert.match(s.checks.find(x=>x.label==='Audit-chain evidence').reason,/INVALID/)
})
test('missing calibration cannot manufacture observational health',async()=>{
 const m=load(stub({'/platform/status':status}));const s=await m.fetchConsoleSnapshot();assert.equal(s.source,'unavailable');assert.equal(s.calibration.window_size,0);assert.ok(s.checks.every(c=>!c.ok))
})
test('schema mismatch cannot pass despite API response',async()=>{
 const m=load(stub({'/platform/status':{...status,contract_version:'9.0.0'},'/platform/calibration':cal}));const s=await m.fetchConsoleSnapshot();assert.equal(s.source,'live');const c=s.checks.find(x=>x.label==='Schema version');assert.equal(c.ok,false);assert.match(c.reason,/mismatch/)
})
test('untrusted tools are not synthesized on provider failure',async()=>{
 const m=load(stub({'/platform/status':status,'/platform/calibration':cal}));const s=await m.fetchConsoleSnapshot();assert.equal(s.source,'live');assert.equal(s.tools.length,0)
})