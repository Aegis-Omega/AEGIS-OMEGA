/** Independent BigInt/rational replay of Python MIRA-RH receipts. Node >= 18. */
'use strict';
const fs = require('fs');
const crypto = require('crypto');
const SCHEMA = 'aegis-mira-rh-proof-ir/v1';
const fail = (msg) => { throw new Error('HOLD_' + msg); };
const gcd = (a,b) => {a=a<0n?-a:a; b=b<0n?-b:b; while(b){const c=a%b;a=b;b=c;}return a;};
class Q {
  constructor(a,b=1n) {
    a=BigInt(a);b=BigInt(b);if (b===0n) fail('DIV_ZERO');if(b<0n){a=-a;b=-b;}
    let g=gcd(a,b);this.a=a/g;this.b=b/g;
  }
  add(o){return new Q(this.a*o.b+o.a*this.b,this.b*o.b);}
  neg(){return new Q(-this.a,this.b);}
  sub(o){return this.add(o.neg());}
  mul(o){return new Q(this.a*o.a,this.b*o.b);}
  div(o){return new Q(this.a*o.b,this.b*o.a);}
  eq(o){return this.a===o.a&&this.b===o.b;}
  lt(o){return this.a*o.b < o.a*this.b;}
  str(){return this.b===1n?`${this.a}`:`${this.a}/${this.b}`;}
}
const q = x => {
  if(typeof x !=='string' || !/^(?:0|-?[1-9][0-9]*)(?:\/[1-9][0-9]*)?$/.test(x) || x==='-0')fail('RATIONAL');
  let t=x.split('/');if(t.some(z=>z.length>121))fail('RATIONAL_SIZE');
  const parsed=new Q(BigInt(t[0]),BigInt(t[1]||'1'));
  if(parsed.str()!==x)fail('NONCANONICAL_RATIONAL');
  return parsed;
};
const Z = new Q(0n), O=new Q(1n), HALF=new Q(1n,2n), QUARTER=new Q(1n,4n);
const tr=a=>{a=a.slice();while(a.length>1&&a[a.length-1].eq(Z))a.pop();return a;};
const ad=(a,b)=>tr(Array.from({length:Math.max(a.length,b.length)},(_,i)=>(a[i]||Z).add(b[i]||Z)));
const mu=(a,b)=>{let r=Array(a.length+b.length-1).fill(Z);for(let i=0;i<a.length;i++)for(let j=0;j<b.length;j++)r[i+j]=r[i+j].add(a[i].mul(b[j]));return tr(r);};
const co=(a,b)=>{let r=[Z];for(let i=a.length-1;i>=0;i--)r=ad(mu(r,b),[a[i]]);return r;};
const pe=(a,b)=>a.length===b.length&&a.every((x,i)=>x.eq(b[i]));
const evalQ=(a,x)=>{let r=Z;for(let i=a.length-1;i>=0;i--)r=r.mul(x).add(a[i]);return r;};
const canon = value => {
  if(Array.isArray(value))return '['+value.map(canon).join(',')+']';
  if(value && typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canon(value[k])).join(',')+'}';
  return JSON.stringify(value);
};
const equal=(a,b)=>canon(a)===canon(b);
const keys=(a,ks)=>a && typeof a==='object' && !Array.isArray(a) &&
  Object.keys(a).sort().join('|')===ks.slice().sort().join('|');
const must=(condition, msg)=>{if(!condition)fail(msg);};
const RH_OBLIGATIONS=[
 'exact-source full Weil explicit-formula identity',
 'universal Weil positivity for all admissible g',
 'proof term for the unmodified Mathlib RiemannHypothesis'
];
function check(receipt){
  must(keys(receipt,['schema','kind','statement','checked','authority_class',
    'local_exact_arithmetic_checked','lean_kernel_checked','riemann_hypothesis_proven',
    'rh_obligations','receipt_sha256']),'RECEIPT_SHAPE');
  must(receipt.schema===SCHEMA && receipt.authority_class==='NONE' &&
    receipt.lean_kernel_checked === false && receipt.riemann_hypothesis_proven === false &&
    receipt.local_exact_arithmetic_checked === true && equal(receipt.rh_obligations,RH_OBLIGATIONS),
    'AUTHORITY_OR_OPEN_OBLIGATIONS');
  let payload={...receipt};delete payload.receipt_sha256;
  must(crypto.createHash('sha256').update(canon(payload),'utf8').digest('hex')===receipt.receipt_sha256,'DIGEST_MISMATCH');
  const c=receipt.checked, st=receipt.statement;
  let expected;
  if(receipt.kind==='reflection_polynomial'){
    must(keys(st,['coefficients_s_ascending']) && Array.isArray(st.coefficients_s_ascending) &&
      st.coefficients_s_ascending.length>=1 && st.coefficients_s_ascending.length<=65,'INPUT_SHAPE');
    const P=tr(st.coefficients_s_ascending.map(q));
    must(!pe(P,[Z]),'ZERO_POLYNOMIAL');
    must(evalQ(P,Z).eq(Z)&&evalQ(P,O).eq(Z)&&pe(ad(P,co(P,[O,new Q(-1n)])),[Z]),'SYMMETRY');
    must(Array.isArray(c?.R_u_ascending) && c.R_u_ascending.length>=1 && c.R_u_ascending.length<=65,'R_SHAPE');
    const R=tr(c.R_u_ascending.map(q));
    const t=[HALF.neg(),O],u=mu(t,t),base=mu(t,ad(u,[QUARTER.neg()]));
    must(pe(mu(base,co(R,u)),P),'NORMAL_FORM_REPLAY');
    expected={
      claim:'P(0)=P(1)=0 and P(1-s)=-P(s) as Q[s] identities',
      checked_scope:'ALL_COMPLEX_S_BY_POLYNOMIAL_IDENTITY',
      degree:P.length-1,
      P_s_ascending:P.map(x=>x.str()),
      R_u_ascending:R.map(x=>x.str()),
      proof_rule:'P(s)=(s-1/2)((s-1/2)^2-1/4)R((s-1/2)^2)',
      source_theorem:'exact symbolic normal form, replayed from input coefficients',
      analytic_claims:[
        'G(s)=P(s)Phi(s) requires Mellin integration-by-parts hypotheses',
        'Phi(1-s)=Phi(s) requires real-even bump hypotheses',
        'full explicit formula, universal Weil positivity, and RH are OPEN'
      ]
    };
  } else if(receipt.kind==='finite_gram_sos'){
    must(keys(st,['matrix','vectors','weights']) && Array.isArray(st.matrix) &&
      Array.isArray(st.vectors) && Array.isArray(st.weights) && st.matrix.length>=1 &&
      st.matrix.length<=64 && st.vectors.length>=1 && st.vectors.length<=64 &&
      st.vectors.length===st.weights.length,'GRAM_INPUT');
    let A=st.matrix.map(row=>{must(Array.isArray(row),'A_ROW');return row.map(q);});
    let V=st.vectors.map(row=>{must(Array.isArray(row),'V_ROW');return row.map(q);});
    let W=st.weights.map(q);
    let n=A.length;
    must(V.every(row=>row.length===n)&&A.every(row=>row.length===n)&&W.every(w=>!w.lt(Z)),'SOS_DIMENSIONS_WEIGHTS');
    for(let i=0;i<n;i++)for(let j=0;j<n;j++){
      must(A[i][j].eq(A[j][i]),'ASYMMETRIC');
      let rhs=Z;for(let k=0;k<W.length;k++)rhs=rhs.add(W[k].mul(V[k][i]).mul(V[k][j]));
      must(A[i][j].eq(rhs),'GRAM_IDENTITY');
    }
    expected={
      claim:'forall x in R^n, x^T A x = sum_i w_i (v_i^T x)^2 >= 0',
      checked_scope:'ALL_REAL_VECTORS_IN_DECLARED_FINITE_DIMENSION',
      matrix:A.map(row=>row.map(v=>v.str())),
      vectors:V.map(row=>row.map(v=>v.str())),
      weights:W.map(v=>v.str()),
      dimension:n,
      proof_rule:'exact rational matrix coefficient comparison + nonnegative weights',
      analytic_claims:['No identification with the full Weil form Q(g) has been established']
    };
  } else if(receipt.kind==='support_prime_cutoff'){
    must(keys(st,['delta']),'CUTOFF_INPUT');
    const d=q(st.delta),x=d.mul(new Q(2n));
    must(Z.lt(x)&&x.lt(O),'DELTA');
    const bound=O.div(O.sub(x));must(bound.lt(new Q(2n)),'NOT_PRIME_FREE');
    expected={
      claim:'IF supp(g)⊆[exp(-d),exp(d)], THEN A_g(n)=A_g(1/n)=0 for every integer n>=2',
      checked_scope:'CONDITIONAL_SUPPORT_TO_ALL_PRIME_POWERS',
      delta:d.str(),
      exp_2delta_strict_upper_bound:bound.str(),
      proof_rule:'0<x<1 -> exp(x)<=1/(1-x); monotonicity; ratio support of autocorrelation',
      analytic_claims:[
        'Support premise, regularity and normalization dy must be discharged against actual Lean definitions',
        'Prime cutoff eliminates no zero-side spectral terms and does not imply RH'
      ]
    };
  }else fail('UNKNOWN_GOAL');
  must(equal(c,expected),'CHECKED_METADATA_MISMATCH');
  return true;
}

if(require.main===module){
  try{
    if(process.argv.length<3)fail('MISSING_FILE');
    for(let f of process.argv.slice(2)){
      check(JSON.parse(fs.readFileSync(f,'utf8')));
      console.log(`VERIFIED_NODE_EXACT ${f} (RH_OPEN)`);
    }
  }catch(e){console.error(String(e));process.exitCode=2;}
}
module.exports={check, Q, q};
