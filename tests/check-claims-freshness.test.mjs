import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const thisDir = path.dirname(fileURLToPath(import.meta.url));
const guard = path.resolve(thisDir, '../scripts/check-claims-freshness.mjs');
function git(repo, ...args) { return execFileSync('git', args, {cwd:repo, encoding:'utf8'}).trim(); }
function setup() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'aegis-claims-'));
  git(root,'init','-q'); git(root,'config','user.email','aegis-test@example.invalid'); git(root,'config','user.name','AEGIS Test');
  fs.mkdirSync(path.join(root,'proofs'));
  fs.mkdirSync(path.join(root,'docs'));
  fs.writeFileSync(path.join(root,'proofs/evidence.ts'),'export const verified = true;\n');
  git(root,'add','.'); git(root,'commit','-qm','baseline evidence');
  const pin=git(root,'rev-parse','HEAD');
  const claim={id:'CLM-001',claim:'proof',tier:'Verified',eq:'EQ-A',verified_against:pin,evidence:['Code: proofs/evidence.ts:1-1'],fails_if:'test'};
  const save = () => {fs.writeFileSync(path.join(root,'docs/claims.json'),JSON.stringify({claims:[claim]},null,2));git(root,'add','.');git(root,'commit','-qm','save claims');};
  save();
  return {root,claim,save,pin,cleanup:()=>fs.rmSync(root,{recursive:true,force:true})};
}
function run(root, args=[]) {
  const r=spawnSync(process.execPath,[guard,'--repo',root,...args],{encoding:'utf8'});
  assert.equal(r.error,undefined); return {status:r.status,output:JSON.parse(r.stdout)};
}
test('valid Git pinned evidence passes provenance freshness but not proof verification',()=>{
  const s=setup();try{const r=run(s.root);assert.equal(r.status,0);assert.equal(r.output.disposition,'FRESHNESS_ONLY_PASS');assert.equal(r.output.proof_correctness_checked,false);assert.equal(r.output.fresh_reference_claims,1);}finally{s.cleanup();}
});
test('evidence modified after verification pin fails closed',()=>{
  const s=setup();try{fs.appendFileSync(path.join(s.root,'proofs/evidence.ts'),'export const changed = true;\n');git(s.root,'add','.');git(s.root,'commit','-qm','change evidence');const r=run(s.root);assert.equal(r.status,1);assert.equal(r.output.disposition,'NOT_ADMITTED');assert(r.output.results[0].issues.includes('STALE_EVIDENCE:proofs/evidence.ts'));}finally{s.cleanup();}
});
test('invalid pin cannot yield fresh verdict',()=>{
  const s=setup();try{s.claim.verified_against='0000000';s.save();const r=run(s.root);assert.equal(r.status,1);assert(r.output.results[0].issues.includes('PIN_UNRESOLVED'));}finally{s.cleanup();}
});
test('incorrect expected exact HEAD is rejected',()=>{
  const s=setup();try{const r=run(s.root,['--expected-head','0'.repeat(40)]);assert.equal(r.status,1);assert.equal(r.output.reason,'HEAD_MISMATCH');}finally{s.cleanup();}
});
test('untracked evidence path cannot yield fresh verdict',()=>{
  const s=setup();try{s.claim.evidence=['Test: proofs/absent.ts'];s.save();const r=run(s.root);assert.equal(r.status,1);assert(r.output.results[0].issues.includes('EVIDENCE_NOT_TRACKED_AT_HEAD:proofs/absent.ts'));}finally{s.cleanup();}
});
test('missing code/test evidence is non-admitted',()=>{
  const s=setup();try{s.claim.evidence=['Spec: see document'];s.save();const r=run(s.root);assert.equal(r.status,1);assert(r.output.results[0].issues.includes('NO_CODE_OR_TEST_EVIDENCE'));}finally{s.cleanup();}
});
test('non-repository fails without pass',()=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'aegis-no-git-'));try{const r=run(dir);assert.equal(r.status,1);assert.equal(r.output.reason,'HEAD_UNAVAILABLE');}finally{fs.rmSync(dir,{recursive:true,force:true});}
});

test('modified local claims cannot be confused with committed exact-head claims',()=>{
  const s=setup();try{fs.appendFileSync(path.join(s.root,'docs/claims.json'),'\n ');const r=run(s.root);assert.equal(r.status,1);assert.equal(r.output.reason,'CLAIMS_NOT_HEAD_BOUND');}finally{s.cleanup();}
});
test('empty verified set cannot produce a misleading PASS',()=>{
  const s=setup();try{s.claim.tier='Proposed';s.claim.eq='EQ-D';s.save();const r=run(s.root);assert.equal(r.status,1);assert.equal(r.output.reason,'NO_VERIFIED_CLAIMS');}finally{s.cleanup();}
});
test('path traversal evidence is rejected',()=>{
  const s=setup();try{s.claim.evidence=['Code: ../outside.ts'];s.save();const r=run(s.root);assert.equal(r.status,1);assert(r.output.results[0].issues.includes('INVALID_EVIDENCE_PATH:../outside.ts'));}finally{s.cleanup();}
});

test('tracked directory cannot impersonate a regular evidence file',()=>{
  const s=setup();try{s.claim.evidence=['Code: proofs'];s.save();const r=run(s.root);assert.equal(r.status,1);assert(r.output.results[0].issues.includes('EVIDENCE_NOT_REGULAR_FILE:proofs'));}finally{s.cleanup();}
});
test('symlink cannot impersonate a regular evidence file',()=>{
  const s=setup();try{fs.symlinkSync('evidence.ts',path.join(s.root,'proofs','symlink.ts'));git(s.root,'add','.');git(s.root,'commit','-qm','symlink');s.claim.evidence=['Test: proofs/symlink.ts'];s.save();const r=run(s.root);assert.equal(r.status,1);assert(r.output.results[0].issues.includes('EVIDENCE_NOT_REGULAR_FILE:proofs/symlink.ts'));}finally{s.cleanup();}
});
test('shallow Git checkout fails closed before assessing evidence',()=>{
  const s=setup();const clone=fs.mkdtempSync(path.join(os.tmpdir(),'aegis-shallow-'));try{
    git(clone,'clone','--depth','1','--quiet',`file://${s.root}`,'shallow');
    const r=run(path.join(clone,'shallow'));
    assert.equal(r.status,1);assert.equal(r.output.reason,'GIT_HISTORY_INCOMPLETE');
  }finally{fs.rmSync(clone,{recursive:true,force:true});s.cleanup();}
});
test('pin from a different branch cannot falsely count as ancestor of HEAD',()=>{
  const s=setup();try{
    git(s.root,'checkout','-qb','divergent',s.pin);
    fs.writeFileSync(path.join(s.root,'proofs/evidence.ts'),'export const divergent = true;\n');
    git(s.root,'add','.');git(s.root,'commit','-qm','diverge proof');const other=git(s.root,'rev-parse','HEAD');
    git(s.root,'checkout','-q','master');s.claim.verified_against=other;s.save();
    const r=run(s.root);assert.equal(r.status,1);assert(r.output.results[0].issues.includes('PIN_NOT_IN_HEAD_HISTORY'));
  }finally{s.cleanup();}
});
