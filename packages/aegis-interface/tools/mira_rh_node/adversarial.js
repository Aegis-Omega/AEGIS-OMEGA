'use strict';
const fs = require('fs');
const crypto = require('crypto');
const {check} = require('./verify');
const src=path=>JSON.parse(fs.readFileSync(path,'utf8'));
const canon=v=>Array.isArray(v)?'['+v.map(canon).join(',')+']':v&&typeof v==='object'?
 '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canon(v[k])).join(',')+'}':JSON.stringify(v);
const rehash=r=>{delete r.receipt_sha256;r.receipt_sha256=crypto.createHash('sha256').update(canon(r)).digest('hex');return r;};
function shouldReject(name,r){
  let denied=false;try{check(rehash(r));}catch(e){denied=true;console.log(`${name} -> ${e.message}`);}
  if(!denied)throw Error('FAIL_OPEN: '+name);
}
const prefix=(process.argv[2]||'tests/fixtures/receipts/').replace(/\/?$/, '/');
let p=src(prefix+'v7_reflection_receipt.json');p.checked.R_u_ascending[0]='0';shouldReject('forged-normal-form',p);
p=src(prefix+'v7_reflection_receipt.json');p.checked.P_s_ascending[1]='0';shouldReject('forged-polynomial',p);
p=src(prefix+'finite_gram_receipt.json');p.statement.matrix[1][1]='-1';shouldReject('forged-negative-form',p);
p=src(prefix+'finite_gram_receipt.json');p.checked.weights[0]='-1';shouldReject('forged-weights',p);
p=src(prefix+'prime_cutoff_receipt.json');p.checked.exp_2delta_strict_upper_bound='1';shouldReject('forged-cutoff',p);
p=src(prefix+'prime_cutoff_receipt.json');p.riemann_hypothesis_proven=true;shouldReject('forged-RH',p);
p=src(prefix+'v7_reflection_receipt.json');p.checked.claim='Universal RH is proved';shouldReject('forged-claim-text',p);
p=src(prefix+'v7_reflection_receipt.json');p.checked.analytic_claims=[];shouldReject('forged-open-qualification',p);
p=src(prefix+'v7_reflection_receipt.json');p.rh_obligations=[];shouldReject('erased-RH-obligations',p);
p=src(prefix+'finite_gram_receipt.json');p.checked.checked_scope='ALL_WEIL_FORMS';shouldReject('forged-gram-scope',p);
p=src(prefix+'prime_cutoff_receipt.json');p.statement.delta='2/2000';shouldReject('noncanonical-rational',p);
console.log('11/11 NODE TAMPER ATTACKS REJECTED EVEN WITH RECALCULATED SHA256');
