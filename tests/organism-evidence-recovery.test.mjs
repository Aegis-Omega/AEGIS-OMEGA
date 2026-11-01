// AEGIS: exact-source cross-store crash recovery. No cloud, main, or secrets.
import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,existsSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join,resolve} from 'node:path'
import {spawnSync} from 'node:child_process'
import {runEvidenceCycle} from '../.claude/metacog/evidence-cycle.mjs'
import {certifyLedger,readLedger} from '../.claude/metacog/evidence-ledger.mjs'

const engine=resolve('.claude/metacog/chain.mjs')
const HEAD='a'.repeat(40)
function setup(){
  const root=mkdtempSync(join(tmpdir(),'aegis-ledger-chain-recovery-'))
  const meta=join(root,'.claude/metacog');mkdirSync(meta,{recursive:true})
  const chainFile=join(meta,'chain.jsonl')
  const env={...process.env,CLAUDE_PROJECT_DIR:root,AEGIS_METACOG_CHAIN:chainFile}
  const boot=spawnSync(process.execPath,[engine,'observe','SENSATION','T1','trusted-bootstrap'],{env,encoding:'utf8'})
  assert.equal(boot.status,0,boot.stderr)
  const snapshotPath=join(root,'snapshot.json')
  writeFileSync(snapshotPath,JSON.stringify({
    schema:'aegis.metacognitive-evidence-snapshot.v1',observed_at:'2026-11-01T15:00:00Z',
    head_sha:HEAD,subject:{repository:'Aegis-Omega/AEGIS-OMEGA',kind:'test',id:560},
    evidence:[{evidence_id:'source-a',kind:'SOURCE_BYTES',load_bearing:true,conclusion:'SUCCESS',bound_head_sha:HEAD,
      artifact:{id:'fixture',digest:'sha256:'+'a'.repeat(64),available:true,expired:false,http_status:200}}]
  }))
  return {root,meta,chainFile,env,options:{snapshotPath,receiptPath:join(meta,'receipt.json'),ledgerPath:join(meta,'ledger.jsonl'),chainPath:engine,env}}
}
function entryCount(f){return readFileSync(f.chainFile,'utf8').trim().split('\n').length}
function certify(f){
  const p=spawnSync(process.execPath,[engine,'certify'],{env:f.env,encoding:'utf8'})
  assert.equal(p.status,0)
  const c=JSON.parse(p.stdout);assert.equal(c.is_valid,true);return c
}
function ledger(f){const x=readLedger(f.options.ledgerPath);assert.equal(certifyLedger(x).is_valid,true);return x}

test('repair lost chain mirror after ledger append, preserving one receipt',()=>{
  const f=setup();const baseline=entryCount(f)
  assert.throws(()=>runEvidenceCycle({...f.options,chainPath:join(f.root,'missing.mjs')}),/metacognitive chain engine missing/)
  assert.equal(ledger(f).length,1);assert.equal(entryCount(f),baseline)
  const r=runEvidenceCycle(f.options)
  assert.equal(r.ledger.duplicate,true)
  assert.equal(r.chain.mirrored,true)
  assert.equal(entryCount(f),baseline+1)
  assert.equal(ledger(f).length,1)
  certify(f)
})

test('duplicate completed event is idempotent and certified, not appended twice',()=>{
  const f=setup()
  const first=runEvidenceCycle(f.options)
  const count=entryCount(f)
  const second=runEvidenceCycle(f.options)
  assert.equal(second.ledger.duplicate,true)
  assert.equal(second.chain.skipped_duplicate,true)
  assert.equal(entryCount(f),count)
  assert.equal(second.chain.certified?.is_valid,true)
  assert.equal(first.receipt_sha256,second.receipt_sha256)
})

test('tampered ledger cannot be used as a repair authority',()=>{
  const f=setup()
  assert.throws(()=>runEvidenceCycle({...f.options,chainPath:join(f.root,'missing.mjs')}))
  const record=ledger(f)[0]
  record.current_epistemic_state='FORGED'
  writeFileSync(f.options.ledgerPath,JSON.stringify(record)+'\n')
  assert.throws(()=>runEvidenceCycle(f.options),/evidence ledger invalid/)
  assert.equal(entryCount(f),1)
})

test('missing chain after failed transaction must HOLD, not manufacture continuity',()=>{
  const f=setup()
  assert.throws(()=>runEvidenceCycle({...f.options,chainPath:join(f.root,'missing.mjs')}))
  writeFileSync(f.chainFile,'')
  assert.throws(()=>runEvidenceCycle(f.options),/UNANCHORED|CHAIN_EMPTY|missing|empty/i)
  assert.equal(ledger(f).length,1)
})

test('repair latest lost mirror while preserving the earlier valid mirror',()=>{
  const f=setup()
  const a=runEvidenceCycle(f.options)
  const countBefore=entryCount(f)
  const old=JSON.parse(readFileSync(f.options.snapshotPath,'utf8'))
  old.observed_at='2026-11-01T15:01:00Z'
  writeFileSync(f.options.snapshotPath,JSON.stringify(old))
  const injected=join(f.root,'fail-observe.mjs')
  writeFileSync(injected,`import {spawnSync} from 'node:child_process'
if(process.argv[2]==='observe')process.exit(23)
const x=spawnSync(process.execPath,[process.env.AEGIS_CHAIN_ENGINE,...process.argv.slice(2)],{stdio:'inherit',env:process.env})
process.exit(x.status??1)
`)
  assert.throws(()=>runEvidenceCycle({...f.options,chainPath:injected,
    env:{...f.env,AEGIS_CHAIN_ENGINE:engine}}),/chain observe failed/)
  assert.equal(ledger(f).length,2)
  assert.equal(entryCount(f),countBefore)
  const repaired=runEvidenceCycle(f.options)
  assert.equal(repaired.chain.mirrored,true)
  assert.equal(repaired.chain.recovered_from_ledger,true)
  assert.equal(ledger(f).length,2)
  assert.equal(entryCount(f),countBefore+1)
  certify(f)
})

test('newer evidence cannot overtake an unresolved ledger-to-chain transaction',()=>{
  const f=setup()
  assert.throws(()=>runEvidenceCycle({...f.options,chainPath:join(f.root,'missing.mjs')}))
  const snapshot=JSON.parse(readFileSync(f.options.snapshotPath,'utf8'))
  snapshot.observed_at='2026-11-01T15:06:00Z'
  writeFileSync(f.options.snapshotPath,JSON.stringify(snapshot))
  assert.throws(()=>runEvidenceCycle(f.options),/EVIDENCE_PENDING_UNMIRRORED/)
  assert.equal(ledger(f).length,1)
  assert.equal(entryCount(f),1)
})
