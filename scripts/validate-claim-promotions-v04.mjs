#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';

const CANONICAL_BASELINE_DIGEST = '457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404';
const HEX64 = /^[0-9a-f]{64}$/;
const SHA40 = /^[0-9a-f]{40}$/;
const FINAL_STATUSES = new Set(['MACHINE_BOUND', 'EMPIRICAL', 'TARGET_OPEN']);
const TRANSITION_STATUSES = new Set([
  'MACHINE_BOUND',
  'EXTERNAL_ESTABLISHED',
  'TARGET_OPEN',
  'NOT_ESTABLISHED',
  'ADMITTED',
]);

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (!a.startsWith('--')) throw new Error(`unexpected argument ${a}`);
    const key = a.slice(2);
    const value = argv[i + 1];
    if (value === undefined || value.startsWith('--')) throw new Error(`missing value for --${key}`);
    out[key] = value;
    i += 1;
  }
  return out;
}

function canonicalizeJCS(value) {
  if (value === null) return 'null';
  switch (typeof value) {
    case 'boolean': return value ? 'true' : 'false';
    case 'string': return JSON.stringify(value);
    case 'number':
      if (!Number.isFinite(value)) throw new Error('JCS_NON_FINITE_NUMBER');
      return JSON.stringify(value);
    case 'object': {
      if (Array.isArray(value)) return `[${value.map(canonicalizeJCS).join(',')}]`;
      const keys = Object.keys(value).sort();
      return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalizeJCS(value[k])}`).join(',')}}`;
    }
    default:
      throw new Error(`JCS_UNSUPPORTED_TYPE:${typeof value}`);
  }
}

function sha256Hex(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function digestJCS(value) {
  return sha256Hex(Buffer.from(canonicalizeJCS(value), 'utf8'));
}

function readJSON(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (e) {
    throw new Error(`JSON_READ_FAILED:${file}:${e.message}`);
  }
}

function resolveFrom(root, p) {
  return path.isAbsolute(p) ? p : path.join(root, p);
}

function readBaseClaimsFromGit(root, baseSha) {
  if (!SHA40.test(baseSha)) throw new Error('BASE_SHA_INVALID');
  try {
    execFileSync('git', ['cat-file', '-e', `${baseSha}^{commit}`], { cwd: root, stdio: 'ignore' });
  } catch {
    throw new Error(`BASE_SHA_NOT_FOUND:${baseSha}`);
  }
  try {
    const raw = execFileSync('git', ['show', `${baseSha}:docs/claims.json`], { cwd: root, encoding: 'utf8' });
    return JSON.parse(raw);
  } catch (e) {
    try {
      execFileSync('git', ['cat-file', '-e', `${baseSha}:docs/claims.json`], { cwd: root, stdio: 'ignore' });
    } catch {
      return { claims: [] };
    }
    throw new Error(`BASE_CLAIMS_READ_FAILED:${e.message}`);
  }
}

function asClaimMap(doc, label) {
  if (!doc || !Array.isArray(doc.claims)) throw new Error(`${label}_CLAIMS_ARRAY_MISSING`);
  const m = new Map();
  for (const c of doc.claims) {
    if (!c || typeof c.id !== 'string') throw new Error(`${label}_CLAIM_ID_INVALID`);
    if (m.has(c.id)) throw new Error(`${label}_CLAIM_DUPLICATE:${c.id}`);
    m.set(c.id, c);
  }
  return m;
}

function claimRequiresPromotion(baseClaim, headClaim) {
  if (!headClaim || headClaim.tier === 'Removed') return false;
  if (!baseClaim) return true;
  return canonicalizeJCS(baseClaim) !== canonicalizeJCS(headClaim);
}

function canonicalClaimStatement(claim) {
  return {
    claim_id: claim.id,
    statement: claim.claim,
    tier: claim.tier,
    eq: claim.eq,
    dependencies: Array.isArray(claim.dependencies) ? [...claim.dependencies] : [],
  };
}

function nonEmptyObject(v) {
  return v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length > 0;
}

function validateAuthority(req, claim, errors) {
  const status = req.final_epistemic_status;
  if (!FINAL_STATUSES.has(status)) {
    errors.push(`FINAL_STATUS_INVALID:${req.claim_id}:${status}`);
    return;
  }

  if (claim.tier === 'Proposed' && status !== 'TARGET_OPEN') {
    errors.push(`STATUS_TIER_MISMATCH:${req.claim_id}:Proposed=>${status}`);
  }
  if (claim.tier === 'Verified' && status === 'TARGET_OPEN') {
    errors.push(`STATUS_TIER_MISMATCH:${req.claim_id}:Verified=>TARGET_OPEN`);
  }

  const transitions = Array.isArray(req.required_transitions) ? req.required_transitions : [];
  for (const t of transitions) {
    if (!t || typeof t.transition_id !== 'string' || !t.transition_id) {
      errors.push(`TRANSITION_ID_INVALID:${req.claim_id}`);
      continue;
    }
    if (!TRANSITION_STATUSES.has(t.status)) {
      errors.push(`TRANSITION_STATUS_INVALID:${req.claim_id}:${t.transition_id}:${t.status}`);
    }
  }

  const hasOpen = transitions.some((t) => t?.status === 'TARGET_OPEN' || t?.status === 'NOT_ESTABLISHED');
  const hasExternal = transitions.some((t) => t?.status === 'EXTERNAL_ESTABLISHED');
  if (hasOpen && status !== 'TARGET_OPEN') {
    errors.push(`AUTHORITY_LEAKAGE:${req.claim_id}:OPEN_TRANSITION=>${status}`);
  }
  if (hasExternal && status === 'MACHINE_BOUND') {
    errors.push(`AUTHORITY_LEAKAGE:${req.claim_id}:EXTERNAL_ESTABLISHED=>MACHINE_BOUND`);
  }

  if (status !== 'TARGET_OPEN') {
    if (!transitions.length || !Array.isArray(req.implementation_files) || req.implementation_files.length === 0 ||
        !Array.isArray(req.negative_control_receipts) || req.negative_control_receipts.length === 0 ||
        !Array.isArray(req.verification_receipts) || req.verification_receipts.length === 0) {
      errors.push(`EVIDENCE_BINDING_INCOMPLETE:${req.claim_id}`);
    }
  }
}

function implementationManifest(root, files, claimId, errors) {
  const list = Array.isArray(files) ? files : [];
  const seen = new Set();
  const out = [];
  for (const rel of list) {
    if (typeof rel !== 'string' || !rel || path.isAbsolute(rel) || rel.split(/[\\/]/).includes('..')) {
      errors.push(`IMPLEMENTATION_PATH_INVALID:${claimId}:${String(rel)}`);
      continue;
    }
    if (seen.has(rel)) {
      errors.push(`IMPLEMENTATION_PATH_DUPLICATE:${claimId}:${rel}`);
      continue;
    }
    seen.add(rel);
    const abs = path.join(root, rel);
    if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
      errors.push(`IMPLEMENTATION_PATH_MISSING:${claimId}:${rel}`);
      continue;
    }
    out.push({ path: rel, sha256: sha256Hex(fs.readFileSync(abs)) });
  }
  out.sort((a, b) => Buffer.from(a.path, 'utf8').compare(Buffer.from(b.path, 'utf8')));
  return out;
}

function buildTuple({ claim, req, baselineDigest, candidateSha, ciRunIdentity, root, errors }) {
  if (req.baseline_digest !== baselineDigest) {
    errors.push(`BASELINE_DIGEST_MISMATCH:${req.claim_id}`);
  }
  if (!nonEmptyObject(req.red_contract)) errors.push(`RED_CONTRACT_MISSING:${req.claim_id}`);
  if (!nonEmptyObject(req.admission_policy)) errors.push(`ADMISSION_POLICY_MISSING:${req.claim_id}`);
  if (!Array.isArray(req.negative_control_receipts)) errors.push(`NEGATIVE_CONTROL_RECEIPTS_INVALID:${req.claim_id}`);
  if (!Array.isArray(req.verification_receipts)) errors.push(`VERIFICATION_RECEIPTS_INVALID:${req.claim_id}`);

  validateAuthority(req, claim, errors);
  const implManifest = implementationManifest(root, req.implementation_files, req.claim_id, errors);

  const tuple = {
    claim_id: req.claim_id,
    baseline_digest: baselineDigest,
    source_head_sha: candidateSha,
    claim_statement_digest: digestJCS(canonicalClaimStatement(claim)),
    red_contract_digest: digestJCS(req.red_contract ?? null),
    implementation_digest: digestJCS(implManifest),
    negative_control_receipt_digest: digestJCS(req.negative_control_receipts ?? null),
    ci_run_identity: ciRunIdentity,
    verification_receipt_digest: digestJCS(req.verification_receipts ?? null),
    admission_policy_digest: digestJCS(req.admission_policy ?? null),
    final_epistemic_status: req.final_epistemic_status,
  };
  for (const [k, v] of Object.entries(tuple)) {
    if (k.endsWith('_digest') && !HEX64.test(v)) errors.push(`DIGEST_INVALID:${req.claim_id}:${k}`);
  }
  return {
    tuple,
    tuple_digest: digestJCS(tuple),
    required_transitions: Array.isArray(req.required_transitions) ? req.required_transitions : [],
    implementation_manifest: implManifest,
  };
}

function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (e) {
    console.error(`PROMOTION_GATE_FAILED ARGUMENT_ERROR:${e.message}`);
    process.exit(2);
  }

  const root = path.resolve(args['repo-root'] ?? process.cwd());
  const baselinePath = resolveFrom(root, args.baseline ?? 'governance/aegis-master-notebook-v0.4.lock.json');
  const headPath = resolveFrom(root, args['head-claims'] ?? 'docs/claims.json');
  const requestsPath = resolveFrom(root, args.requests ?? 'governance/claim-promotion-requests-v0.4.json');
  const receiptOutput = args['receipt-output'] ? resolveFrom(root, args['receipt-output']) : null;
  const candidateSha = args['candidate-sha'] ?? (() => {
    try { return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(); }
    catch { return ''; }
  })();
  const ciRunIdentity = args['ci-run-identity'] ?? '';

  const errors = [];
  if (!SHA40.test(candidateSha)) errors.push(`CANDIDATE_SHA_INVALID:${candidateSha}`);
  if (!ciRunIdentity) errors.push('CI_RUN_IDENTITY_MISSING');

  let baselineDoc, headDoc, baseDoc, requestDoc;
  try { baselineDoc = readJSON(baselinePath); } catch (e) { errors.push(e.message); }
  try { headDoc = readJSON(headPath); } catch (e) { errors.push(e.message); }
  try { requestDoc = readJSON(requestsPath); } catch (e) { errors.push(e.message); }
  try {
    if (args['base-claims']) baseDoc = readJSON(resolveFrom(root, args['base-claims']));
    else if (args['base-sha']) baseDoc = readBaseClaimsFromGit(root, args['base-sha']);
    else errors.push('BASE_BINDING_MISSING');
  } catch (e) { errors.push(e.message); }

  if (baselineDoc?.baseline_digest !== CANONICAL_BASELINE_DIGEST) {
    errors.push(`BASELINE_LOCK_MISMATCH:${baselineDoc?.baseline_digest ?? 'missing'}`);
  }
  if (requestDoc?.baseline_digest !== CANONICAL_BASELINE_DIGEST) {
    errors.push(`REQUEST_LEDGER_BASELINE_MISMATCH:${requestDoc?.baseline_digest ?? 'missing'}`);
  }
  if (requestDoc && !Array.isArray(requestDoc.requests)) errors.push('REQUESTS_ARRAY_MISSING');

  if (errors.length) return fail(errors);

  let baseMap, headMap;
  try {
    baseMap = asClaimMap(baseDoc, 'BASE');
    headMap = asClaimMap(headDoc, 'HEAD');
  } catch (e) {
    return fail([e.message]);
  }

  const requestMap = new Map();
  for (const req of requestDoc.requests) {
    if (!req || typeof req.claim_id !== 'string') {
      errors.push('PROMOTION_REQUEST_ID_INVALID');
      continue;
    }
    if (requestMap.has(req.claim_id)) errors.push(`PROMOTION_REQUEST_DUPLICATE:${req.claim_id}`);
    requestMap.set(req.claim_id, req);
  }

  const changed = [];
  for (const [id, headClaim] of headMap) {
    if (claimRequiresPromotion(baseMap.get(id), headClaim)) changed.push(id);
  }
  changed.sort();

  for (const id of changed) {
    if (!requestMap.has(id)) errors.push(`PROMOTION_REQUEST_MISSING:${id}`);
  }
  for (const id of requestMap.keys()) {
    if (!changed.includes(id)) errors.push(`ORPHAN_PROMOTION_REQUEST:${id}`);
  }
  if (errors.length) return fail(errors);

  const tuples = [];
  for (const id of changed) {
    const req = requestMap.get(id);
    tuples.push(buildTuple({
      claim: headMap.get(id),
      req,
      baselineDigest: CANONICAL_BASELINE_DIGEST,
      candidateSha,
      ciRunIdentity,
      root,
      errors,
    }));
  }

  if (errors.length) return fail(errors);

  const receipt = {
    schema_version: 'claim-promotion-receipt.v1',
    baseline_version: '0.4',
    baseline_digest: CANONICAL_BASELINE_DIGEST,
    candidate_sha: candidateSha,
    ci_run_identity: ciRunIdentity,
    tuples,
  };
  if (receiptOutput) {
    fs.mkdirSync(path.dirname(receiptOutput), { recursive: true });
    fs.writeFileSync(receiptOutput, JSON.stringify(receipt, null, 2) + '\n');
  }
  console.log(`PROMOTION_GATE_OK claims_changed=${changed.length} tuples=${tuples.length} candidate=${candidateSha}`);
}

function fail(errors) {
  const unique = [...new Set(errors)];
  console.error('PROMOTION_GATE_FAILED');
  for (const e of unique) console.error(`  ${e}`);
  process.exit(1);
}

main();
