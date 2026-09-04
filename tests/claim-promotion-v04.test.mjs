import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { spawnSync } from 'node:child_process';

const BASELINE = '457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404';
const HEAD = 'a'.repeat(40);
const RUN = 'https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/123456789';

function writeJson(root, rel, value) {
  const p = join(root, rel);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(value, null, 2) + '\n');
  return p;
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

function request(id, finalStatus = 'TARGET_OPEN', overrides = {}) {
  return {
    claim_id: id,
    baseline_digest: BASELINE,
    final_epistemic_status: finalStatus,
    red_contract: {
      contract_id: `RED-${id}`,
      falsifiers: ['reject on missing evidence'],
      mandatory_transitions: [],
    },
    implementation_files: [],
    negative_control_receipts: [],
    verification_receipts: [],
    required_transitions: [],
    ...overrides,
  };
}

function fixture({
  baseClaims = [],
  headClaims = [],
  requests = [],
  baselineDigest = BASELINE,
  policyBaselineDigest = BASELINE,
} = {}) {
  const root = mkdtempSync(join(tmpdir(), 'aegis-v04-'));
  writeFileSync(join(root, 'impl.ts'), 'export const x = 1\n');
  const baseline = writeJson(root, 'governance/aegis-master-notebook-v0.4.lock.json', {
    version: '0.4',
    baseline_digest: baselineDigest,
    global_rh_status: 'NOT_PROVEN_AT_CURRENT_CLOSURE',
  });
  const policy = writeJson(root, 'governance/claim-promotion-policy.v1.json', {
    policy_id: 'AEGIS_CLAIM_PROMOTION_ENFORCEMENT_V1',
    policy_version: 1,
    baseline_digest: policyBaselineDigest,
    open_transition_statuses: ['TARGET_OPEN', 'NOT_ESTABLISHED'],
    machine_bound_forbidden_if_any: ['EXTERNAL_ESTABLISHED', 'TARGET_OPEN', 'NOT_ESTABLISHED'],
  });
  const base = writeJson(root, 'base-claims.json', { claims: baseClaims });
  const head = writeJson(root, 'head-claims.json', { claims: headClaims });
  const requestFile = writeJson(root, 'governance/claim-promotion-requests-v0.4.json', {
    version: '0.4',
    baseline_digest: baselineDigest,
    requests,
  });
  return { root, baseline, policy, base, head, requestFile, receipt: join(root, 'receipt.json') };
}

function run(fx) {
  return spawnSync(process.execPath, [
    'scripts/validate-claim-promotions-v04.mjs',
    '--repo-root', fx.root,
    '--baseline', fx.baseline,
    '--policy', fx.policy,
    '--base-claims', fx.base,
    '--head-claims', fx.head,
    '--requests', fx.requestFile,
    '--candidate-sha', HEAD,
    '--ci-run-identity', RUN,
    '--receipt-output', fx.receipt,
  ], { encoding: 'utf8', cwd: process.cwd() });
}

test('finalizes a TARGET_OPEN request into an exact-head immutable tuple receipt', () => {
  const c = claim('CLM-900', 'Proposed');
  const fx = fixture({ headClaims: [c], requests: [request(c.id)] });
  const r = run(fx);
  assert.equal(r.status, 0, r.stderr || r.stdout);
  assert.match(r.stdout, /PROMOTION_GATE_OK/);

  const receipt = JSON.parse(readFileSync(fx.receipt, 'utf8'));
  assert.equal(receipt.tuples.length, 1);
  const out = receipt.tuples[0];
  assert.equal(out.tuple.claim_id, c.id);
  assert.equal(out.tuple.baseline_digest, BASELINE);
  assert.equal(out.tuple.source_head_sha, HEAD);
  assert.equal(out.tuple.ci_run_identity, RUN);
  assert.equal(out.tuple.final_epistemic_status, 'TARGET_OPEN');
  for (const k of [
    'claim_statement_digest',
    'red_contract_digest',
    'implementation_digest',
    'negative_control_receipt_digest',
    'verification_receipt_digest',
    'admission_policy_digest',
  ]) assert.match(out.tuple[k], /^[0-9a-f]{64}$/);
  assert.match(out.tuple_digest, /^[0-9a-f]{64}$/);
});

test('fails closed when a new claim has no promotion request', () => {
  const c = claim('CLM-901', 'Proposed');
  const fx = fixture({ headClaims: [c] });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /PROMOTION_REQUEST_MISSING/);
});

test('fails closed when a request is not bound to the canonical v0.4 baseline digest', () => {
  const c = claim('CLM-902', 'Proposed');
  const req = request(c.id);
  req.baseline_digest = 'f'.repeat(64);
  const fx = fixture({ headClaims: [c], requests: [req] });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /BASELINE_DIGEST_MISMATCH/);
});

test('fails closed if the canonical admission policy is not baseline-bound', () => {
  const c = claim('CLM-903', 'Proposed');
  const fx = fixture({ headClaims: [c], requests: [request(c.id)], policyBaselineDigest: 'f'.repeat(64) });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /ADMISSION_POLICY_BASELINE_MISMATCH/);
});

test('fails closed on authority leakage across an OPEN mandatory transition', () => {
  const c = claim('CLM-904', 'Verified');
  const transitionId = 'GLOBAL_ANALYTIC_BRIDGES';
  const fx = fixture({
    headClaims: [c],
    requests: [request(c.id, 'MACHINE_BOUND', {
      red_contract: {
        contract_id: `RED-${c.id}`,
        falsifiers: ['global analytic bridge must close'],
        mandatory_transitions: [transitionId],
      },
      implementation_files: ['impl.ts'],
      negative_control_receipts: [{ status: 'PASS', control: 'negative' }],
      verification_receipts: [{ status: 'PASS', check: 'green' }],
      required_transitions: [{ transition_id: transitionId, status: 'TARGET_OPEN' }],
    })],
  });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /AUTHORITY_LEAKAGE/);
});

test('fails closed if EXTERNAL_ESTABLISHED evidence is promoted as MACHINE_BOUND', () => {
  const c = claim('CLM-905', 'Verified');
  const transitionId = 'LIFE_SCIENCES_DATABASE_EVIDENCE';
  const fx = fixture({
    headClaims: [c],
    requests: [request(c.id, 'MACHINE_BOUND', {
      red_contract: {
        contract_id: `RED-${c.id}`,
        falsifiers: ['external evidence cannot self-upgrade'],
        mandatory_transitions: [transitionId],
      },
      implementation_files: ['impl.ts'],
      negative_control_receipts: [{ status: 'PASS', control: 'negative' }],
      verification_receipts: [{ status: 'PASS', check: 'green' }],
      required_transitions: [{ transition_id: transitionId, status: 'EXTERNAL_ESTABLISHED' }],
    })],
  });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /AUTHORITY_LEAKAGE/);
});

test('fails closed when a mandatory transition has no status binding', () => {
  const c = claim('CLM-906', 'Verified');
  const fx = fixture({
    headClaims: [c],
    requests: [request(c.id, 'EMPIRICAL', {
      red_contract: {
        contract_id: `RED-${c.id}`,
        falsifiers: ['measurement must be bound'],
        mandatory_transitions: ['MEASUREMENT'],
      },
      implementation_files: ['impl.ts'],
      negative_control_receipts: [{ status: 'PASS', control: 'negative' }],
      verification_receipts: [{ status: 'PASS', check: 'green' }],
      required_transitions: [],
    })],
  });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /MANDATORY_TRANSITION_STATUS_MISSING/);
});

test('requires evidence-bearing artifacts before EMPIRICAL or MACHINE_BOUND admission', () => {
  const c = claim('CLM-907', 'Verified');
  const fx = fixture({
    headClaims: [c],
    requests: [request(c.id, 'EMPIRICAL', {
      red_contract: {
        contract_id: `RED-${c.id}`,
        falsifiers: ['measurement must be present'],
        mandatory_transitions: ['MEASUREMENT'],
      },
      required_transitions: [{ transition_id: 'MEASUREMENT', status: 'MACHINE_BOUND' }],
    })],
  });
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /EVIDENCE_BINDING_INCOMPLETE/);
});

test('fails closed if canonical policy semantics are weakened', () => {
  const c = claim('CLM-908', 'Proposed');
  const fx = fixture({ headClaims: [c], requests: [request(c.id)] });
  const policy = JSON.parse(readFileSync(fx.policy, 'utf8'));
  policy.machine_bound_forbidden_if_any = ['TARGET_OPEN', 'NOT_ESTABLISHED'];
  writeFileSync(fx.policy, JSON.stringify(policy, null, 2) + '\n');
  const r = run(fx);
  assert.notEqual(r.status, 0);
  assert.match(`${r.stdout}\n${r.stderr}`, /ADMISSION_POLICY_SEMANTICS_MISMATCH/);
});
