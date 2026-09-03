import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluateMemoryAuthority, MemoryVerdict } from '../src/memory-authority-gate.mjs';

const base = {
  requestId: 'req-001', actionDigest: 'sha256:action-a',
  observedStateDigest: 'sha256:state-5', admittedStateDigest: 'sha256:state-5',
  observedPolicyDigest: 'sha256:policy-3', admittedPolicyDigest: 'sha256:policy-3',
  observedAuthorityEpoch: 7, admittedAuthorityEpoch: 7,
  priorReceiptActionDigest: null,
};

test('allows only an exact fresh authority/state tuple', () => {
  const verdict = evaluateMemoryAuthority(base);
  assert.equal(verdict.verdict, MemoryVerdict.ALLOW);
  assert.deepEqual(verdict.reasons, []);
});

test('denies stale state even when policy and epoch match', () => {
  const verdict = evaluateMemoryAuthority({...base, observedStateDigest:'sha256:state-4'});
  assert.equal(verdict.verdict, MemoryVerdict.DENY);
  assert.ok(verdict.reasons.includes('STALE_STATE'));
});

test('denies stale policy even when state and epoch match', () => {
  const verdict = evaluateMemoryAuthority({...base, observedPolicyDigest:'sha256:policy-2'});
  assert.equal(verdict.verdict, MemoryVerdict.DENY);
  assert.ok(verdict.reasons.includes('STALE_POLICY'));
});

test('denies authority epoch mismatch', () => {
  const verdict = evaluateMemoryAuthority({...base, observedAuthorityEpoch:6});
  assert.equal(verdict.verdict, MemoryVerdict.DENY);
  assert.ok(verdict.reasons.includes('STALE_AUTHORITY_EPOCH'));
});

test('denies replay of a previously receipted action digest', () => {
  const verdict = evaluateMemoryAuthority({...base, priorReceiptActionDigest:base.actionDigest});
  assert.equal(verdict.verdict, MemoryVerdict.DENY);
  assert.ok(verdict.reasons.includes('ACTION_REPLAY'));
});

test('fails closed on missing memory bindings', () => {
  const verdict = evaluateMemoryAuthority({...base, admittedPolicyDigest:''});
  assert.equal(verdict.verdict, MemoryVerdict.DENY);
  assert.ok(verdict.reasons.includes('INCOMPLETE_MEMORY_BINDING'));
});
