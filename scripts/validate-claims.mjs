#!/usr/bin/env node
// Self-enforcing Claims Ledger validator.
// Manuscript-governance gate — orthogonal to the constitutional CEREMONY quorum.
// Zero external deps: node:fs / node:path / node:child_process + a hand-rolled schema check.
//
// Enforces the full rule set from docs/CLAIMS_LEDGER.md:
//   - structural shape (id pattern, required fields per tier)
//   - unique ids, resolvable dependencies, acyclic dependency graph
//   - anti-laundering: Verified deps only Verified; Derived deps only Verified/Derived;
//     no claim may depend on a Removed claim
//   - Proposed => EQ-C or EQ-D (Proposed+EQ-A / Proposed+EQ-B prohibited)
//   - Verified => >=1 Code:/Test: artifact + non-empty fails_if + verified_against
//   - Derived => >=1 dependency ; Removed => non-empty removal_reason
//   - every Code:/Test: evidence path resolves at HEAD
//   - freshness (warning-level): Verified evidence changed after verified_against
//   - markdown<->json parity of the CLM id set
// Exits 1 on any hard violation; 0 otherwise. Freshness is warning-only.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const CLAIMS_JSON = path.join(REPO_ROOT, 'docs', 'claims.json');
const SCHEMA_JSON = path.join(REPO_ROOT, 'docs', 'claims.schema.json');
const LEDGER_MD = path.join(REPO_ROOT, 'docs', 'CLAIMS_LEDGER.md');

const errors = [];
const warnings = [];
const err = (m) => errors.push(m);
const warn = (m) => warnings.push(m);

const ID_RE = /^CLM-\d{3}$/;
const TIERS = ['Verified', 'Derived', 'Proposed', 'Removed'];
const EQS = ['EQ-A', 'EQ-B', 'EQ-C', 'EQ-D'];

function readJSON(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (e) {
    console.error(`FATAL: cannot read/parse ${path.relative(REPO_ROOT, p)}: ${e.message}`);
    process.exit(1);
  }
}

// Best-effort ancestor check; treats git failures as "cannot prove stale" (no warning).
function git(args) {
  return execFileSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8' }).trim();
}
function isAncestor(a, b) {
  try {
    execFileSync('git', ['merge-base', '--is-ancestor', a, b], { cwd: REPO_ROOT, stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

// Parse an evidence string of form "Type: path:lines @commit" and return
// { type, filePath } for Code:/Test: entries, else null.
function parseEvidencePath(ev) {
  const m = /^(Code|Test):\s*(.+)$/.exec(ev);
  if (!m) return null;
  let rest = m[2].trim();
  rest = rest.replace(/\s+@[0-9a-fA-F]{4,40}\b.*$/, ''); // strip " @commit ..."
  const firstTok = rest.split(/\s+/)[0]; // path token, before any parenthetical prose
  const filePath = firstTok.replace(/:[\d,\-]+$/, ''); // strip trailing :lines / :a-b,c-d
  return { type: m[1], filePath };
}

// ---- minimal draft-2020-12 subset schema check (shape only) --------------------
function schemaShapeCheck(claim, i) {
  const where = `claims[${i}] (${claim && claim.id ? claim.id : '?'})`;
  if (typeof claim !== 'object' || claim === null || Array.isArray(claim)) {
    err(`${where}: not an object`);
    return;
  }
  const allowed = new Set([
    'id', 'claim', 'tier', 'eq', 'dependencies', 'evidence',
    'fails_if', 'verified_against', 'removal_reason',
  ]);
  for (const k of Object.keys(claim)) {
    if (!allowed.has(k)) err(`${where}: unexpected property "${k}"`);
  }
  if (typeof claim.id !== 'string' || !ID_RE.test(claim.id)) {
    err(`${where}: "id" must match ^CLM-\\d{3}$`);
  }
  if (typeof claim.claim !== 'string' || claim.claim.length < 1) {
    err(`${where}: "claim" must be a non-empty string`);
  }
  if (!TIERS.includes(claim.tier)) {
    err(`${where}: "tier" must be one of ${TIERS.join('/')}`);
  }
  if (!EQS.includes(claim.eq)) {
    err(`${where}: "eq" must be one of ${EQS.join('/')}`);
  }
  if (claim.dependencies !== undefined) {
    if (!Array.isArray(claim.dependencies)) err(`${where}: "dependencies" must be an array`);
    else for (const d of claim.dependencies) {
      if (typeof d !== 'string' || !ID_RE.test(d)) err(`${where}: dependency "${d}" is not a CLM id`);
    }
  }
  if (claim.evidence !== undefined) {
    if (!Array.isArray(claim.evidence)) err(`${where}: "evidence" must be an array`);
    else for (const e of claim.evidence) {
      if (typeof e !== 'string') err(`${where}: evidence entries must be strings`);
    }
  }
  for (const s of ['fails_if', 'verified_against', 'removal_reason']) {
    if (claim[s] !== undefined && typeof claim[s] !== 'string') {
      err(`${where}: "${s}" must be a string`);
    }
  }
  // conditional required fields (mirrors schema if/then)
  if (claim.tier === 'Verified' && !claim.verified_against) {
    err(`${where}: Verified claim requires "verified_against"`);
  }
  if (claim.tier === 'Removed' && !claim.removal_reason) {
    err(`${where}: Removed claim requires "removal_reason"`);
  }
}

function main() {
  // schema file must at least parse (structural gate presence)
  readJSON(SCHEMA_JSON);
  const doc = readJSON(CLAIMS_JSON);
  const claims = Array.isArray(doc) ? doc : doc.claims;
  if (!Array.isArray(claims)) {
    err('claims.json: missing top-level "claims" array');
    return finish();
  }

  // Rule 1 — structural shape
  claims.forEach((c, i) => schemaShapeCheck(c, i));

  // index by id + Rule 2 (unique ids)
  const byId = new Map();
  for (const c of claims) {
    if (!c || typeof c.id !== 'string') continue;
    if (byId.has(c.id)) err(`duplicate id ${c.id}`);
    byId.set(c.id, c);
  }

  // Rule 2 — dependencies resolve
  for (const c of claims) {
    for (const d of c.dependencies || []) {
      if (!byId.has(d)) err(`${c.id}: dependency ${d} does not resolve to any claim`);
    }
  }

  // Rule 3 — acyclic (DFS)
  {
    const WHITE = 0, GRAY = 1, BLACK = 2;
    const color = new Map([...byId.keys()].map((k) => [k, WHITE]));
    const stack = [];
    let cycleFound = false;
    const visit = (id) => {
      if (cycleFound) return;
      color.set(id, GRAY);
      stack.push(id);
      for (const d of (byId.get(id)?.dependencies || [])) {
        if (!byId.has(d)) continue;
        if (color.get(d) === GRAY) {
          const from = stack.indexOf(d);
          err(`dependency cycle: ${[...stack.slice(from), d].join(' -> ')}`);
          cycleFound = true;
          return;
        }
        if (color.get(d) === WHITE) visit(d);
      }
      stack.pop();
      color.set(id, BLACK);
    };
    for (const id of byId.keys()) if (color.get(id) === WHITE) visit(id);
  }

  // Rule 4 — anti-laundering on dependency status
  for (const c of claims) {
    for (const d of c.dependencies || []) {
      const dep = byId.get(d);
      if (!dep) continue;
      if (dep.tier === 'Removed') {
        err(`${c.id}: depends on Removed claim ${d} (laundering a struck claim)`);
      }
      if (c.tier === 'Verified' && dep.tier !== 'Verified') {
        err(`${c.id} (Verified) may depend only on Verified; ${d} is ${dep.tier}`);
      }
      if (c.tier === 'Derived' && !['Verified', 'Derived'].includes(dep.tier)) {
        err(`${c.id} (Derived) may depend only on Verified/Derived; ${d} is ${dep.tier}`);
      }
    }
  }

  // Rule 5 — Proposed => EQ-C or EQ-D
  for (const c of claims) {
    if (c.tier === 'Proposed' && (c.eq === 'EQ-A' || c.eq === 'EQ-B')) {
      err(`${c.id}: Proposed+${c.eq} is prohibited (Proposed must be EQ-C or EQ-D)`);
    }
  }

  // Rules 6/7/8 + evidence non-emptiness for Verified/Derived
  for (const c of claims) {
    const ev = c.evidence || [];
    if (c.tier === 'Verified') {
      const hasCodeOrTest = ev.some((e) => /^(Code|Test):/.test(e));
      if (!hasCodeOrTest) err(`${c.id}: Verified requires >=1 Code:/Test: evidence artifact`);
      if (!c.fails_if || !c.fails_if.trim()) err(`${c.id}: Verified requires non-empty fails_if`);
      if (!c.verified_against) err(`${c.id}: Verified requires verified_against`);
    }
    if (c.tier === 'Derived') {
      if ((c.dependencies || []).length < 1) err(`${c.id}: Derived requires >=1 dependency`);
      if (ev.length < 1) err(`${c.id}: Derived requires non-empty evidence`);
    }
    if (c.tier === 'Removed') {
      if (!c.removal_reason || !c.removal_reason.trim()) err(`${c.id}: Removed requires non-empty removal_reason`);
    }
  }

  // Rule 9 — Code:/Test: evidence paths resolve at HEAD
  for (const c of claims) {
    for (const ev of c.evidence || []) {
      const parsed = parseEvidencePath(ev);
      if (!parsed) continue;
      const abs = path.join(REPO_ROOT, parsed.filePath);
      if (!fs.existsSync(abs)) {
        err(`${c.id}: evidence path does not exist: ${parsed.filePath}  (from "${ev}")`);
      }
    }
  }

  // Rule 10 — freshness (warning-level) for Verified claims
  let staleCount = 0;
  const staleClaims = new Set();
  for (const c of claims) {
    if (c.tier !== 'Verified' || !c.verified_against) continue;
    for (const ev of c.evidence || []) {
      const parsed = parseEvidencePath(ev);
      if (!parsed) continue;
      const abs = path.join(REPO_ROOT, parsed.filePath);
      if (!fs.existsSync(abs)) continue;
      let lastChange;
      try {
        lastChange = git(['log', '-1', '--format=%H', '--', parsed.filePath]);
      } catch { continue; }
      if (!lastChange) continue;
      // STALE when the file's last change is NOT an ancestor of verified_against,
      // i.e. the pinned commit predates the latest change to the evidence file.
      if (!isAncestor(lastChange, c.verified_against)) {
        warn(`STALE: ${c.id} verified_against=${c.verified_against} but ${parsed.filePath} last changed at ${lastChange.slice(0, 7)}`);
        staleClaims.add(c.id);
      }
    }
  }
  staleCount = staleClaims.size;

  // Rule 11 — markdown<->json id-set parity
  let mdIds = new Set();
  try {
    const md = fs.readFileSync(LEDGER_MD, 'utf8');
    for (const m of md.matchAll(/\bCLM-\d{3}\b/g)) mdIds.add(m[0]);
  } catch (e) {
    err(`cannot read ${path.relative(REPO_ROOT, LEDGER_MD)}: ${e.message}`);
  }
  const jsonIds = new Set(byId.keys());
  const missingInJson = [...mdIds].filter((id) => !jsonIds.has(id)).sort();
  const missingInMd = [...jsonIds].filter((id) => !mdIds.has(id)).sort();
  if (missingInJson.length) err(`ids in CLAIMS_LEDGER.md but not claims.json: ${missingInJson.join(', ')}`);
  if (missingInMd.length) err(`ids in claims.json but not CLAIMS_LEDGER.md: ${missingInMd.join(', ')}`);

  return finish({ claims, byId, staleCount, staleClaims, jsonIds });
}

function finish(ctx) {
  if (warnings.length) {
    console.log('\nWARNINGS (non-blocking):');
    for (const w of warnings) console.log(`  ! ${w}`);
  }
  if (errors.length) {
    console.error('\nVALIDATION FAILED:');
    for (const e of errors) console.error(`  x ${e}`);
    console.error(`\n${errors.length} error(s).`);
    process.exit(1);
  }
  if (ctx) printCoverage(ctx);
  console.log('\nOK — claims ledger is self-consistent.');
  process.exit(0);
}

function printCoverage({ claims, byId, staleCount, staleClaims }) {
  const total = claims.length;
  const byTier = { Verified: 0, Derived: 0, Proposed: 0, Removed: 0 };
  const byEq = { 'EQ-A': 0, 'EQ-B': 0, 'EQ-C': 0, 'EQ-D': 0 };
  for (const c of claims) {
    byTier[c.tier] = (byTier[c.tier] || 0) + 1;
    byEq[c.eq] = (byEq[c.eq] || 0) + 1;
  }
  const verified = byTier.Verified;
  const pct = (n) => total ? ((100 * n) / total).toFixed(1) : '0.0';
  const freshVerified = verified - staleCount;

  // orphans: no dependents AND no dependencies (informational)
  const hasDependents = new Set();
  for (const c of claims) for (const d of c.dependencies || []) hasDependents.add(d);
  const orphans = claims.filter(
    (c) => (c.dependencies || []).length === 0 && !hasDependents.has(c.id),
  ).map((c) => c.id);

  console.log('\n================ CLAIMS LEDGER COVERAGE REPORT ================');
  console.log(`Total claims:            ${total}`);
  console.log('By tier:');
  for (const t of TIERS) console.log(`  ${t.padEnd(9)} ${byTier[t] || 0}`);
  console.log('EQ distribution:');
  for (const q of EQS) console.log(`  ${q}        ${byEq[q] || 0}`);
  console.log(`%Verified:               ${pct(verified)}%  (${verified}/${total})`);
  console.log(`%Verified fresh @HEAD:   ${verified ? ((100 * freshVerified) / verified).toFixed(1) : '0.0'}%  (${freshVerified}/${verified})`);
  console.log(`Stale (warning) claims:  ${staleCount}${staleCount ? '  [' + [...staleClaims].join(', ') + ']' : ''}`);
  console.log(`Orphan claims (info):    ${orphans.length}${orphans.length ? '  [' + orphans.join(', ') + ']' : ''}`);
  console.log('==============================================================');
}

main();
