#!/usr/bin/env node
// ============================================================
// AEGIS — BFT φ-Quorum Ratification Harness (harness-layer / Gate 0)
//
// Enacts the documented alliance ratification: a φ-weighted Byzantine
// quorum over the three-member alliance, faithful to:
//   - swarm.ts (SwarmConvergenceRecord shape, convergence_hash inputs)
//   - automaton-workflow: vote weights Claude 618 / GPT-4o 191 / Qwen 191
//   - the edge-verifier threshold 618034/1_000_000 (integer; NO f64 in the
//     decision — mirrors the "Atomic scale, no f64" constitutional note)
//
// A change is RATIFIED iff the approving weight clears 1/φ:
//   approve_weight * 1_000_000 >= total_weight * 618_034     (integer compare)
//
// Load-bearing property (provable): Claude alone is 618/1000 = 0.618000, which
// is below 1/φ = 0.618034 — the coordinator CANNOT self-ratify. At least one
// ally must concur. This is the φ self-similarity enforced, not asserted.
//
// Each ratification is hash-chained into ratifications.jsonl (genesis '0'×64,
// monotonic sequence, prev-linked) and recorded as an EXECUTIVE observation in
// the live metacognitive chain. Dependency-free: node:crypto + node:fs.
// ============================================================
import { createHash } from 'node:crypto'
import { readFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { dirname, join } from 'node:path'

const REPO   = process.env.CLAUDE_PROJECT_DIR || '/home/user/AEGIS--'
const DIR    = join(REPO, '.claude/metacog')
const LEDGER = process.env.AEGIS_QUORUM_LEDGER || join(DIR, 'ratifications.jsonl')
const CHAIN_MJS = join(DIR, 'chain.mjs')
const GENESIS = '0'.repeat(64)
const SCHEMA  = '1.0.0'

// 1/φ as integer parts-per-million — the constitutional edge-verifier threshold.
// 1/φ = (√5−1)/2 = 0.6180339887…  → truncated to 618034 ppm.
const THRESHOLD_PPM = 618034
const PPM = 1_000_000

// Declared alliance vote weights (sum = 1000). Source: automaton-workflow / CLAUDE.md.
const WEIGHTS = { 'claude': 618, 'gpt-4o': 191, 'qwen': 191 }
// Quorum is over the FULL validator set: an absent or rejecting member is
// non-approving weight. This is what makes Claude-alone (618/1000) fall short.
const TOTAL_ALLIANCE = Object.values(WEIGHTS).reduce((a, b) => a + b, 0)

function canon(v) {
  if (v === null || typeof v !== 'object') {
    return JSON.stringify(typeof v === 'string' ? v.normalize('NFC') : v)
  }
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']'
  return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}'
}
const sha256 = s => createHash('sha256').update(s, 'utf8').digest('hex')

function readLines(path) {
  if (!existsSync(path)) return []
  return readFileSync(path, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l))
}
const lastHash = es => (es.length ? es[es.length - 1].convergence_hash : GENESIS)
const lastSeq  = es => (es.length ? es[es.length - 1].sequence : -1)

// ── ratify: weighted Byzantine quorum over a proposal ──
// usage: ratify "<subject>" claude:approve qwen:approve gpt-4o:reject
function ratify(subject, voteArgs) {
  if (!subject) { console.error('quorum: subject required'); process.exit(1) }
  if (voteArgs.length === 0) { console.error('quorum: at least one vote required'); process.exit(1) }

  const votes = []
  let approve_weight = 0
  const total_weight = TOTAL_ALLIANCE  // quorum is over the full validator set
  const seen = new Set()
  for (const arg of voteArgs) {
    const [node, verdict] = arg.split(':')
    const weight = WEIGHTS[node]
    if (weight === undefined) { console.error(`quorum: unknown node "${node}" (known: ${Object.keys(WEIGHTS).join(', ')})`); process.exit(1) }
    if (verdict !== 'approve' && verdict !== 'reject') { console.error(`quorum: verdict must be approve|reject, got "${verdict}"`); process.exit(1) }
    if (seen.has(node)) { console.error(`quorum: duplicate vote from "${node}"`); process.exit(1) }
    seen.add(node)
    votes.push({ node_id: node, weight, verdict })
    if (verdict === 'approve') approve_weight += weight
  }

  // Integer φ-threshold decision — no f64.
  const ratified = approve_weight * PPM >= total_weight * THRESHOLD_PPM

  const es  = readLines(LEDGER)
  const seq = lastSeq(es) + 1
  const prev = lastHash(es)
  const subject_hash = sha256(subject.normalize('NFC'))
  const body = {
    subject_hash,
    votes,
    approve_weight,
    total_weight,
    threshold_ppm: THRESHOLD_PPM,
    ratified,
    sequence: seq,
    previous_convergence_hash: prev,
  }
  const convergence_hash = sha256(canon(body))
  const record = { ...body, convergence_hash, schema_version: SCHEMA, is_replay_reconstructable: true }

  mkdirSync(dirname(LEDGER), { recursive: true })
  appendFileSync(LEDGER, JSON.stringify(record) + '\n')

  // Record the ratification in the live metacognitive chain (best-effort).
  try {
    const ratio = (approve_weight / total_weight).toFixed(6)
    execFileSync('node', [CHAIN_MJS, 'observe', 'EXECUTIVE', 'T2',
      `ratification: ${subject.slice(0, 80)} | weight ${approve_weight}/${total_weight} (${ratio}) | ratified=${ratified}`],
      { stdio: 'ignore' })
  } catch { /* chain optional */ }

  console.log(JSON.stringify({
    ratified, approve_weight, total_weight,
    approve_ratio_ppm: Math.floor(approve_weight * PPM / total_weight),
    threshold_ppm: THRESHOLD_PPM,
    sequence: seq,
    convergence_hash: convergence_hash.slice(0, 12),
  }))
  process.exit(ratified ? 0 : 1)
}

// ── certify: re-walk the ratification ledger, detect any tamper ──
function certify() {
  const es = readLines(LEDGER)
  let is_valid = true, broken_at = null
  for (let i = 0; i < es.length; i++) {
    const expectedPrev = i === 0 ? GENESIS : es[i - 1].convergence_hash
    if (es[i].previous_convergence_hash !== expectedPrev) { is_valid = false; broken_at = i; break }
    const { convergence_hash, schema_version, is_replay_reconstructable, ...body } = es[i]
    if (sha256(canon(body)) !== convergence_hash) { is_valid = false; broken_at = i; break }
  }
  console.log(JSON.stringify({
    is_valid, entry_count: es.length,
    terminal_hash: es.length ? es[es.length - 1].convergence_hash : null,
    broken_at,
  }))
}

function weights() { console.log(JSON.stringify({ weights: WEIGHTS, threshold_ppm: THRESHOLD_PPM, note: '1/φ ≈ 0.618034; Claude alone (0.618000) is below threshold by design' })) }

const [cmd, ...args] = process.argv.slice(2)
switch (cmd) {
  case 'ratify':  ratify(args[0], args.slice(1)); break
  case 'certify': certify(); break
  case 'weights': weights(); break
  default:
    console.error('usage: quorum.mjs ratify "<subject>" <node:approve|reject>... | certify | weights')
    process.exit(2)
}
