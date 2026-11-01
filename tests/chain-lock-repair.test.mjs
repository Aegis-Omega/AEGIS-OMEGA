import {test} from 'node:test'
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {mkdtempSync,writeFileSync,readFileSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join,resolve} from 'node:path'
const REPAIR=resolve('scripts/repair_chain_lock.py')
function fixture(){
 const dir=mkdtempSync(join(tmpdir(),'aegis-lock-repair-'))
 const path=join(dir,'chain.mjs')
 writeFileSync(path,`function acquireLock() {\n  return false // stale lock — proceed anyway rather than deadlock\n}\nfunction observe() {\n  acquireLock()\n  try { return true } finally { releaseLock() }\n}\n`)
 return path
}
test('lock patch dry run matches exact source and mutates nothing',()=>{
 const path=fixture(),original=readFileSync(path,'utf8')
 const r=spawnSync('python',[REPAIR,path],{encoding:'utf8',cwd:resolve('.')})
 assert.equal(r.status,0);assert.equal(readFileSync(path,'utf8'),original)
})
test('lock patch fails closed instead of continuing while another writer owns lock',()=>{
 const path=fixture(),r=spawnSync('python',[REPAIR,path,'--apply'],{encoding:'utf8',cwd:resolve('.')})
 assert.equal(r.status,0)
 const source=readFileSync(path,'utf8')
 assert.ok(source.includes("throw new Error('metacog: lock acquisition failed"))
 assert.equal(source.includes('return false // stale lock'),false)
})
test('lock patch refuses unknown or already patched implementation',()=>{
 const path=fixture();spawnSync('python',[REPAIR,path,'--apply'],{encoding:'utf8',cwd:resolve('.')})
 const r=spawnSync('python',[REPAIR,path,'--apply'],{encoding:'utf8',cwd:resolve('.')})
 assert.notEqual(r.status,0)
})
