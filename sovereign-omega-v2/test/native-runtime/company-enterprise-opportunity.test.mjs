import test from 'node:test';
import assert from 'node:assert/strict';
import {loadRepositoryTypescript} from './load-repository-ts.mjs';

const loaded = await loadRepositoryTypescript(['sovereignty/company-enterprise-opportunity.ts']);
test.after(() => loaded.cleanup());
const {
  createEnterpriseOpportunityV1: create,
  advanceEnterpriseOpportunityV1: advance,
  classifyEnterpriseCommercialActionV1: classify,
} = loaded.modules['sovereignty/company-enterprise-opportunity.ts'];

const direct = (id, kind, gen='1') => ({
  evidence_id:id, kind, authority:'DIRECT_OBSERVATION', source_ref:`gmail:${id}`, observed_generation:gen,
});
const provider = (id, kind, gen='1') => ({
  evidence_id:id, kind, authority:'PROVIDER_ATTESTATION', source_ref:`provider:${id}`, observed_generation:gen,
});

function discovered() {
  return create({opportunity_id:'opp-1', account_name:'Example Enterprise', discovery_evidence:direct('d1','DISCOVERY')});
}

test('discovery requires admitted evidence and grants no authority', () => {
  const opp=discovered();
  assert.equal(opp.stage,'DISCOVERED');
  assert.equal(opp.external_authority,'NOT_GRANTED');
  assert.equal(opp.authority_effect,'NONE');
  assert.throws(()=>create({opportunity_id:'x',account_name:'X',discovery_evidence:provider('d2','DISCOVERY')}),/DISCOVERY_EVIDENCE/);
});

test('stage skipping is fail-closed', () => {
  assert.throws(()=>advance(discovered(),'QUALIFIED_REPLY',[direct('q','QUALIFYING_REPLY')]),/STAGE_SKIP/);
});

test('a draft is not evidence that outbound was sent', () => {
  assert.throws(()=>advance(discovered(),'CONTACTED',[direct('draft','DISCOVERY')]),/OUTBOUND_SENT/);
  assert.equal(advance(discovered(),'CONTACTED',[direct('sent','OUTBOUND_SENT')]).stage,'CONTACTED');
});

test('provider attestation cannot establish sent, payment, or audit-start events', () => {
  assert.throws(()=>advance(discovered(),'CONTACTED',[provider('sent','OUTBOUND_SENT')]),/OUTBOUND_SENT/);
  let opp=advance(discovered(),'CONTACTED',[direct('sent','OUTBOUND_SENT')]);
  opp=advance(opp,'QUALIFIED_REPLY',[direct('reply','QUALIFYING_REPLY')]);
  opp=advance(opp,'SCOPING_CALL_HELD',[direct('call','SCOPING_CALL')]);
  opp=advance(opp,'WRITTEN_SCOPE_AGREED',[direct('scope','SCOPE_AGREEMENT')]);
  assert.throws(()=>advance(opp,'PAYMENT_RECEIVED',[provider('pay','PAYMENT_RECORD')]),/PAYMENT_RECORD/);
  opp=advance(opp,'PAYMENT_RECEIVED',[direct('pay','PAYMENT_RECORD')]);
  assert.throws(()=>advance(opp,'AUDIT_STARTED',[provider('start','AUDIT_START')]),/AUDIT_START/);
});

test('payment received and audit started require separate evidence', () => {
  let opp=advance(discovered(),'CONTACTED',[direct('sent','OUTBOUND_SENT')]);
  opp=advance(opp,'QUALIFIED_REPLY',[direct('reply','QUALIFYING_REPLY')]);
  opp=advance(opp,'SCOPING_CALL_HELD',[direct('call','SCOPING_CALL')]);
  opp=advance(opp,'WRITTEN_SCOPE_AGREED',[direct('scope','SCOPE_AGREEMENT')]);
  opp=advance(opp,'PAYMENT_RECEIVED',[direct('pay','PAYMENT_RECORD')]);
  assert.throws(()=>advance(opp,'AUDIT_STARTED',[direct('pay','AUDIT_START')]),/EVIDENCE_REUSE/);
  const started=advance(opp,'AUDIT_STARTED',[direct('start','AUDIT_START')]);
  assert.equal(started.stage,'AUDIT_STARTED');
  assert.deepEqual(started.evidence_refs,['d1','sent','reply','call','scope','pay','start']);
});

test('closed-lost requires an evidenced loss reason and can occur from any open stage', () => {
  assert.throws(()=>advance(discovered(),'CLOSED_LOST',[]),/LOSS_REASON/);
  assert.equal(advance(discovered(),'CLOSED_LOST',[direct('lost','LOSS_REASON')]).stage,'CLOSED_LOST');
});

test('commercial action classifier keeps consequential actions behind operator grant', () => {
  assert.deepEqual(classify('DRAFT_OUTREACH'),{action:'DRAFT_OUTREACH',action_class:'DRAFT',operator_grant_required:false,authority_effect:'NONE'});
  assert.equal(classify('SEND_OUTREACH').action_class,'EXTERNAL_MESSAGE');
  assert.equal(classify('SEND_OUTREACH').operator_grant_required,true);
  assert.equal(classify('SEND_SCOPE_WITH_TERMS').action_class,'LEGAL_COMMITMENT');
  assert.equal(classify('REQUEST_PAYMENT').action_class,'FINANCIAL');
  assert.equal(classify('START_AUDIT').operator_grant_required,false);
});
