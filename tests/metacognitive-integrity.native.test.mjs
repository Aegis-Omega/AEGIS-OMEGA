import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, readFileSync, existsSync, unlinkSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve } from 'node:path'
import { createHash } from 'node:crypto'

const ROOT = resolve('.')
const CHAIN_SOURCE = resolve('.claude/metacog/chain.mjs')
const HOOK_SOURCE = resolve('.claude/hooks/user-prompt-intake.sh')
const sha = v => createHash('sha256').update(v).digest('hex')
const canon = v => v === null || typeof v !== 'object' ? JSON.stringify(typeof v === 'string' ? v.normalize('NFC') : v) : Array.isArray(v) ? '['+v.map(canon).join(',')+']' : '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canon(v[k])).join(',')+'}'

function fixture({ git = false } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'aegis-integrity-'))
  const chain = join(dir,'.claude/metacog/chain.mjs')
  const hook = join(dir,'.claude/hooks/user-prompt-intake.sh')
  mkdirSync(dirname(chain),{recursive:true});mkdirSync(dirname(hook),{recursive:true})
  copyFileSync(CHAIN_SOURCE,chain);copyFileSync(HOOK_SOURCE,hook)
  const chainFile=join(dir,'.claude/metacog/chain.jsonl')
  const env={...process.env, CLAUDE_PROJECT_DIR:dir, AEGIS_METACOG_CHAIN:chainFile}
  if(git){let r=spawnSync('git',['init','-q',dir],{encoding:'utf8'});assert.equal(r.status,0,r.stderr)}
  const run = (...args)=>spawnSync(process.execPath,[chain,...args],{env,encoding:'utf8'})
  const intake=()=>spawnSync('bash',[hook],{env,encoding:'utf8'})
  return {dir,chain,hook,chainFile,env,run,intake}
}

test('bootstrap: new chain directory and genesis observation are created',()=>{
  const f=fixture()
  f.env.AEGIS_METACOG_CHAIN=join(f.dir,'previously-missing/subdir/chain.jsonl')
  const a=f.run('observe','SENSATION','T1','first')
  assert.equal(a.status,0,a.stderr)
  assert.equal(existsSync(f.env.AEGIS_METACOG_CHAIN),true)
  const c=f.run('certify');assert.equal(c.status,0);assert.equal(JSON.parse(c.stdout).entry_count,1)
})

test('locked chain: append fails without deleting competing writer lock',()=>{
  const f=fixture();const lock=f.chainFile+'.lock';writeFileSync(lock,'OTHER_WRITER')
  const a=f.run('observe','SENSATION','T1','conflict')
  assert.notEqual(a.status,0)
  assert.match(a.stderr,/lock acquisition failed/)
  assert.equal(readFileSync(lock,'utf8'),'OTHER_WRITER')
  assert.equal(existsSync(f.chainFile),false)
})

test('corrupted historical observation denies append, preserves original bytes',()=>{
  const f=fixture();assert.equal(f.run('observe','SENSATION','T1','good').status,0)
  const corrupted=readFileSync(f.chainFile,'utf8').replace('good','forged')
  writeFileSync(f.chainFile,corrupted)
  const a=f.run('observe','SENSATION','T1','later')
  assert.notEqual(a.status,0)
  assert.match(a.stderr,/existing chain invalid/)
  assert.equal(readFileSync(f.chainFile,'utf8'),corrupted)
})

test('rehashed but nonmonotonic sequence fails certification and subsequent append',()=>{
  const f=fixture();assert.equal(f.run('observe','SENSATION','T1','0').status,0);assert.equal(f.run('observe','SENSATION','T1','1').status,0)
  const es=readFileSync(f.chainFile,'utf8').trim().split('\n').map(JSON.parse)
  es[1].sequence=0
  es[1].entry_hash=sha(canon({observation:es[1].observation,previous_entry_hash:es[1].previous_entry_hash,sequence:'0'}))
  writeFileSync(f.chainFile,es.map(e=>JSON.stringify(e)).join('\n')+'\n')
  const cert=JSON.parse(f.run('certify').stdout)
  assert.equal(cert.is_valid,false)
  assert.equal(cert.broken_at,1)
  assert.notEqual(f.run('observe','SENSATION','T1','new').status,0)
})

test('incompatible schema is not admitted even with a locally recomputed hash',()=>{
  const f=fixture();assert.equal(f.run('observe','SENSATION','T1','good').status,0)
  const row=JSON.parse(readFileSync(f.chainFile,'utf8'));row.schema_version='unknown-version'
  writeFileSync(f.chainFile,JSON.stringify(row)+'\n')
  const c=JSON.parse(f.run('certify').stdout);assert.equal(c.is_valid,false)
})

test('sealing a corrupt chain fails without writing seals',()=>{
  const f=fixture();assert.equal(f.run('observe','SENSATION','T1','good').status,0)
  writeFileSync(f.chainFile,readFileSync(f.chainFile,'utf8').replace('good','bad!'))
  const a=f.run('seal','invalid-chain')
  assert.notEqual(a.status,0);assert.match(a.stderr,/cannot seal invalid chain/)
  assert.equal(existsSync(join(f.dir,'.claude/metacog/seals.jsonl')),false)
})

test('healthy hook emits verified observation and valid JSON',()=>{
  const f=fixture({git:true}); const r=f.intake()
  assert.equal(r.status,0,r.stderr)
  const payload=JSON.parse(r.stdout)
  assert.equal(payload.hookSpecificOutput.hookEventName,'UserPromptSubmit')
  assert.match(payload.hookSpecificOutput.additionalContext,/OBSERVATION VERIFIED/)
  assert.match(payload.hookSpecificOutput.additionalContext,/is_valid=true/)
  assert.equal(JSON.parse(f.run('certify').stdout).entry_count,1)
})

test('missing chain engine produces hard HOLD without success context',()=>{
  const f=fixture({git:true});unlinkSync(f.chain)
  const r=f.intake();assert.equal(r.status,2)
  assert.match(r.stderr,/AEGIS_HOLD_NO_ADMISSION/)
  assert.equal(r.stdout.trim(),'')
})

test('held lock blocks prompt instead of reporting is_valid=true',()=>{
  const f=fixture({git:true});const lock=f.chainFile+'.lock';writeFileSync(lock,'owned')
  const r=f.intake();assert.equal(r.status,2)
  assert.match(r.stderr,/AEGIS_HOLD_NO_ADMISSION/)
  assert.equal(r.stdout.trim(),'')
  assert.equal(readFileSync(lock,'utf8'),'owned')
})

test('corrupted chain blocks prompt with no success context',()=>{
  const f=fixture({git:true});assert.equal(f.run('observe','SENSATION','T1','correct').status,0)
  writeFileSync(f.chainFile,readFileSync(f.chainFile,'utf8').replace('correct','tampered'))
  const r=f.intake();assert.equal(r.status,2)
  assert.match(r.stderr,/HOLD_NO_ADMISSION/)
  assert.equal(r.stdout.trim(),'')
})
