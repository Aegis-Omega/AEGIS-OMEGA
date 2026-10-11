#!/usr/bin/env node
// AEGIS claims freshness guard: Git-exact provenance, not proof correctness.
// Fail-closed; compatible with Node.js >= 20; zero dependencies.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

function runGit(root, args) {
  const r = spawnSync('git', args, { cwd: root, encoding: 'utf8', windowsHide: true });
  if (r.error) return { ok: false, code: -1, stdout: '', stderr: r.error.message };
  return { ok: r.status === 0, code: r.status, stdout: (r.stdout || '').trim(), stderr: (r.stderr || '').trim() };
}
function fail(reason, details = {}) {
  console.log(JSON.stringify({ schema: 'aegis.claims-freshness.v1', disposition: 'NOT_ADMITTED', reason, ...details }, null, 2));
  process.exitCode = 1;
}
function parseArgs(argv) {
  const out = { repo: process.cwd(), claims: 'docs/claims.json', expectedHead: null };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (!['--repo', '--claims', '--expected-head'].includes(k) || !argv[i + 1]) throw Error(`Invalid argument: ${k}`);
    const v = argv[++i];
    if (k === '--repo') out.repo = path.resolve(v);
    if (k === '--claims') out.claims = v;
    if (k === '--expected-head') out.expectedHead = v;
  }
  return out;
}
function parseEvidence(e) {
  if (typeof e !== 'string') return null;
  const m = /^(Code|Test):\s*(\S+)/.exec(e);
  if (!m) return null;
  return m[2].replace(/:[\d,\-]+$/, '');
}
function safePath(p) {
  if (!p || path.isAbsolute(p) || p.includes('\\') || p.startsWith('-') || p.includes(':')) return false;
  const parts = p.split('/');
  return !parts.some(part => part === '..' || part === '' || part === '.');
}
function check(root, claimsFile, expectedHead) {
  const headResult = runGit(root, ['rev-parse', '--verify', 'HEAD^{commit}']);
  if (!headResult.ok || !/^[a-f0-9]{40}$/.test(headResult.stdout)) return fail('HEAD_UNAVAILABLE');
  const head = headResult.stdout;
  if (expectedHead && expectedHead !== head) return fail('HEAD_MISMATCH', { head, expected_head: expectedHead });
  const shallow = runGit(root, ['rev-parse', '--is-shallow-repository']);
  if (!shallow.ok || shallow.stdout !== 'false') return fail('GIT_HISTORY_INCOMPLETE', { head });
  if (!safePath(claimsFile)) return fail('INVALID_CLAIMS_PATH', { head });
  let claims;
  try {
    const workingClaims = fs.readFileSync(path.join(root, claimsFile), 'utf8');
    const workingBlob = runGit(root, ['hash-object', '--', claimsFile]);
    const committedBlob = runGit(root, ['rev-parse', `${head}:${claimsFile}`]);
    if (!workingBlob.ok || !committedBlob.ok || workingBlob.stdout !== committedBlob.stdout) return fail('CLAIMS_NOT_HEAD_BOUND', { head, claims_file: claimsFile });
    const parsed = JSON.parse(workingClaims);
    claims = Array.isArray(parsed) ? parsed : parsed.claims;
    if (!Array.isArray(claims)) throw Error('Missing claims array');
  } catch { return fail('CLAIMS_UNREADABLE', { head }); }
  const verified = claims.filter(c => c && c.tier === 'Verified').sort((a, b) => String(a.id).localeCompare(String(b.id)));
  if (!verified.length) return fail('NO_VERIFIED_CLAIMS', { head, claims_file: claimsFile });
  const seen = new Set();
  const results = [];
  for (const c of verified) {
    const issues = [];
    if (typeof c.id !== 'string' || !/^CLM-\d{3}$/.test(c.id) || seen.has(c.id)) issues.push('INVALID_OR_DUPLICATE_ID');
    seen.add(c.id);
    const rawPin = c.verified_against;
    let pin = null;
    if (typeof rawPin !== 'string' || !/^[a-f0-9]{7,40}$/.test(rawPin)) issues.push('INVALID_PIN');
    else {
      const resolved = runGit(root, ['rev-parse', '--verify', `${rawPin}^{commit}`]);
      if (!resolved.ok || !/^[a-f0-9]{40}$/.test(resolved.stdout)) issues.push('PIN_UNRESOLVED');
      else {
        pin = resolved.stdout;
        const ancestor = runGit(root, ['merge-base', '--is-ancestor', pin, head]);
        if (!ancestor.ok) issues.push(ancestor.code === 1 ? 'PIN_NOT_IN_HEAD_HISTORY' : 'PIN_ANCESTRY_UNVERIFIABLE');
      }
    }
    const evidence = [...new Set((Array.isArray(c.evidence) ? c.evidence : []).map(parseEvidence).filter(Boolean))].sort();
    if (!evidence.length) issues.push('NO_CODE_OR_TEST_EVIDENCE');
    const paths = [];
    for (const p of evidence) {
      if (!safePath(p)) { issues.push(`INVALID_EVIDENCE_PATH:${p}`); continue; }
      const file = runGit(root, ['cat-file', '-e', `${head}:${p}`]);
      if (!file.ok) { issues.push(`EVIDENCE_NOT_TRACKED_AT_HEAD:${p}`); continue; }
      // A tracked directory (tree) or symlink is not independently reviewable
      // Code:/Test: file evidence. Reject both instead of trusting a path string.
      const treeEntry = runGit(root, ['ls-tree', head, '--', p]);
      const match = treeEntry.stdout.match(/^(100644|100755) blob [a-f0-9]{40}\t(.+)$/);
      if (!treeEntry.ok || !match || match[2] !== p) {
        issues.push(`EVIDENCE_NOT_REGULAR_FILE:${p}`);
        continue;
      }
      const last = runGit(root, ['log', '-1', '--format=%H', head, '--', p]);
      if (!last.ok || !/^[a-f0-9]{40}$/.test(last.stdout)) { issues.push(`LAST_CHANGE_UNVERIFIABLE:${p}`); continue; }
      let fresh = null;
      if (pin) {
        const anc = runGit(root, ['merge-base', '--is-ancestor', last.stdout, pin]);
        if (!anc.ok) issues.push(`${anc.code === 1 ? 'STALE_EVIDENCE' : 'EVIDENCE_ANCESTRY_UNVERIFIABLE'}:${p}`);
        else fresh = true;
      }
      paths.push({ path: p, last_change: last.stdout, fresh_against_pin: fresh });
    }
    results.push({ id: c.id, pinned_commit: pin, outcome: issues.length ? 'UNVERIFIED_FRESHNESS' : 'FRESH_REFERENCE', issues, evidence: paths });
  }
  const failed = results.filter(r => r.outcome !== 'FRESH_REFERENCE').length;
  const receipt = {
    schema: 'aegis.claims-freshness.v1',
    head, claims_file: claimsFile, verified_claims: verified.length,
    fresh_reference_claims: verified.length - failed,
    unverified_freshness_claims: failed,
    disposition: failed ? 'NOT_ADMITTED' : 'FRESHNESS_ONLY_PASS',
    proof_correctness_checked: false,
    runtime_tests_executed: false,
    results,
  };
  console.log(JSON.stringify(receipt, null, 2));
  if (failed) process.exitCode = 1;
}
try {
  const a = parseArgs(process.argv.slice(2));
  check(a.repo, a.claims, a.expectedHead);
} catch (err) { fail('UNEXPECTED_GUARD_ERROR', { detail: String(err.message || err) }); }
