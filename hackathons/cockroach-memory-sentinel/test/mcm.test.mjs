import test from 'node:test';
import assert from 'node:assert/strict';
import { buildMcmObservation, routeVerificationDemand } from '../src/mcm.mjs';

const node = {
  nodeId: 'agent-7',
  confidenceBps: 6200,
  evidenceFreshnessBps: 4100,
  loadBps: 8800,
  reliabilityBps: 7300,
  observedAuthorityEnvelope: 'D2',
  contradictionCount: 2,
};

test('MCM observation is hard-bound to observation-only T2 with zero authority weight', () => {
  const observation = buildMcmObservation(node);
  assert.equal(observation.authorityEffect, 'OBSERVATION_ONLY');
  assert.equal(observation.observationTier, 'T2');
  assert.equal(observation.authorityWeight, 0);
  assert.equal(observation.mayGroundStateTransition, false);
});

test('MCM preserves observed authority envelope but cannot expand it', () => {
  const observation = buildMcmObservation(node);
  assert.equal(observation.observedAuthorityEnvelope, 'D2');
  assert.equal(observation.proposedAuthorityEnvelope, null);
});

test('routing asks for independent verification under contradiction or stale evidence', () => {
  const decision = routeVerificationDemand(buildMcmObservation(node));
  assert.equal(decision.requiresIndependentWitness, true);
  assert.ok(decision.reasons.includes('CONTRADICTION_CLUSTER'));
  assert.ok(decision.reasons.includes('EVIDENCE_FRESHNESS_LOW'));
});

test('resource pressure may change routing priority but not authority', () => {
  const decision = routeVerificationDemand(buildMcmObservation(node));
  assert.equal(decision.routingPriority, 'HIGH');
  assert.equal(decision.authorityMutationPermitted, false);
});
