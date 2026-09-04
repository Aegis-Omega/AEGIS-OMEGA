import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';

const BASELINE = '457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404';
const HEAD = 'a'.repeat(40);

function writeJson(root, rel, value) {
  const p = join(root, rel);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(value, null, 2) + '\n');
  return p;
}

function fixture({
  baseClaims = [],
  headClaims = [],
  promotions = [],
  baselineDigest = BASELINE,
} = {}) {
  const root = mkdtempSync(join(tmpdir(), 'aegis-v04-'));
  const baseline = writeJson(root, 'governance/aegis-master-notebook-v0.4.lock.json', {
    version: '0.4',
    baseline_digest: baselineDigest,
    global_rh_status: 'NOT_PROVEN_AT_CURRENT_CLOSURE',
  });
  const base = writeJson(root, 'base-claims.json', { claims: baseClaims });
  const head = writeJson(root, 'head-claims.json', { claims: headClaims });
  const promotionFile = writeJson(root, 'governance/claim-promotions-v0.4.json', {
    version: '0.4',
    baseline_digest: baselineDigest,
    promotions,
  });
  return { root, baseline, base, head, promotionFile };
}

function run(fx) {
  return spawnSync(process.execPath, [
    'scripts/validate-claim-promotions-v04.mjs',
    '--repo-root', fx.root,
    '--baseline', fx.baseline,
    '--base-claims', fx.base,
    '--head-claims', fx.head,
    '--promotions', fx.promotionFile,
    '--candidate-sha', HEAD,
  ], { encoding: 'utf8' });
}

function claim(id, tier = 'Proposed') {
  return {
    id,
    claim: `statement ${id}`,
    tier,
    eq: tier === 'Proposed' ? 'EQ-C' : 'EQ-B',
    dependencies: [],
    evidence: [],
  };
}

function tuple(id, finalStatus = 'TARGET_OPEN') {
  return {
    claim_id: id,
    baseline_digest: BASELINE,
    source_head_sha: HEAD,
    claim_statement_digest: '1'.repeat(64),
    red_contract_digest: '2'.repeat(64),
    implementation_digest: '3'.repeat(64),
    negative_control_receipt_digest: '4'.repeat(64),
    ci_run_identity: 'test-run-1',
    verification_receipt_digest: '5'.repeat(64),
    admission_policy_digest: '6'.repeat(64),
    final_epistemic_status: finalStatus,
  };
}

test('accepts a new TARGET_OPEN claim only when its exact-head tuple is present', () => {
  const c = claim('CLM-900', 'Proposed');
  const fx = fixture({ headClaims: [c], promotions: [{ tuple: tuple(c.id) }] });
  const r = run(fx);
  assert.equal(r.status, 0, r.stderr || r.stdout);
  assert.match(r.stdout, /PROMOTION_GATE_OK/);
});

test('fails closed when a new claim has no promotion tuple', () => {
  const c = claim('CLM-901', 'Proposed');
  const fx = fixture({ headClaims: [c] });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /PROMOTION_TUPLE_MISSING/);
});

test('fails closed when a tuple is not bound to the canonical v0.4 baseline digest', () => {
  const c = claim('CLM-902', 'Proposed');
  const t = tuple(c.id);
  t.baseline_digest = 'f'.repeat(64);
  const fx = fixture({ headClaims: [c], promotions: [{ tuple: t }] });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /BASELINE_DIGEST_MISMATCH/);
});

test('fails closed when a tuple is bound to a different candidate head', () => {
  const c = claim('CLM-903', 'Proposed');
  const t = tuple(c.id);
  t.source_head_sha = 'b'.repeat(40);
  const fx = fixture({ headClaims: [c], promotions: [{ tuple: t }] });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /SOURCE_HEAD_MISMATCH/);
});

test('fails closed on authority leakage across an OPEN required transition', () => {
  const c = claim('CLM-904', 'Verified');
  const t = tuple(c.id, 'MACHINE_BOUND');
  const fx = fixture({
    headClaims: [c],
    promotions: [{
      tuple: t,
      required_transitions: [{
        transition_id: 'GLOBAL_ANALYTIC_BRIDGES',
        status: 'TARGET_OPEN',
      }],
    }],
  });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /AUTHORITY_LEAKAGE/);
});
