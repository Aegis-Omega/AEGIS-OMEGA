#!/usr/bin/env node
// ============================================================
// AEGIS — Agent-Mesh Verdict Ledger (harness-layer / Gate 0)
//
// Enacts the Guardian→Verifier→Implementer triad energy cycle
// (agent-mesh skill). Each phase verdict is hash-chained and
// permanently archived — a Guardian VETO cannot be retroactively
// removed without breaking the chain.
//
// Energy cycle phases:
//   GUARDIAN_ASSESS  — inhibitory gate (L6+L7); PASS or VETO
//   VERIFIER_CHECK   — proprioceptive gate (L1+L2); ELIGIBLE or INELIGIBLE
//   IMPLEMENTER_EXEC — motor output (L3+L5); COMPLETE or FAILED
//   GUARDIAN_FINAL   — closure review (L6+L7); PASS or VETO
//
// A cycle is COMPLETE when all four phases resolve affirmatively.
// A VETO or FAILED verdict is permanent — the autopoietic membrane
// rejects the component. Forging a reversal breaks the hash chain.
//
// Hash body (all fields that affect constitutional integrity):
//   { phase, agent, verdict, proposal, reason, sequence, previous_verdict_hash }
// verdict_hash = SHA-256(canon(body))
//
// Metadata (not hashed): verdict_hash, schema_version, cycle_id
//
// cycle_id is a short correlation tag (not a UUID) grouping the four
// phases of one proposal cycle. Not hashed — does not affect integrity.
//
// Dependency-free: node:crypto + node:fs.
// ============================================================
import { createHash } from 'node:crypto'
import { readFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { dirname, join } from 'node:path'

const REPO      = process.env.CLAUDE_PROJECT_DIR || '/home/user/AEGIS--'
const DIR       = join(REPO, '.claude/metacog')
const LEDGER    = join(DIR, 'verdicts.jsonl')
const CHAIN_MJS = join(DIR, 'chain.mjs')
const GENESIS   = '0'.repeat(64)
const SCHEMA    = '1.0.0'

// Agent cognitive roles (mirrors agent-mesh skill)
const AGENTS = {
  guardian:    'L6+L7 inhibitory-cortex',
  verifier:    'L1+L2 cerebellum',
  implementer: 'L3+L5 motor-cortex',
}

// Valid verdicts per phase
const PHASE_VERDICTS = {
  GUARDIAN_ASSESS:  ['PASS', 'VETO'],
  VERIFIER_CHECK:   ['ELIGIBLE', 'INELIGIBLE'],
  IMPLEMENTER_EXEC: ['COMPLETE', 'FAILED'],
  GUARDIAN_FINAL:   ['PASS', 'VETO'],
}

// Affirmative verdicts (allow the cycle to proceed)
const AFFIRMATIVE = new Set(['PASS', 'ELIGIBLE', 'COMPLETE'])

// Verdicts that require a reason
const NEEDS_REASON = new Set(['VETO', 'INELIGIBLE', 'FAILED'])

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
const lastHash = es => (es.length ? es[es.length - 1].verdict_hash : GENESIS)
const lastSeq  = es => (es.length ? es[es.length - 1].sequence : -1)

// ── record: append a verdict ──────────────────────────────────────────────────
// usage: record <phase> <agent> <verdict> <proposal> [reason] [--cycle <id>]
function record(phase, agent, verdict, proposal, reason, cycleId) {
  if (!PHASE_VERDICTS[phase]) {
    console.error(`agent-mesh: unknown phase "${phase}" (known: ${Object.keys(PHASE_VERDICTS).join(', ')})`)
    process.exit(1)
  }
  if (!AGENTS[agent]) {
    console.error(`agent-mesh: unknown agent "${agent}" (known: ${Object.keys(AGENTS).join(', ')})`)
    process.exit(1)
  }
  if (!PHASE_VERDICTS[phase].includes(verdict)) {
    console.error(`agent-mesh: verdict "${verdict}" invalid for phase "${phase}" (valid: ${PHASE_VERDICTS[phase].join(', ')})`)
    process.exit(1)
  }
  if (!proposal || !proposal.trim()) {
    console.error('agent-mesh: proposal description required')
    process.exit(1)
  }
  if (NEEDS_REASON.has(verdict) && (!reason || !reason.trim())) {
    console.error(`agent-mesh: reason required for "${verdict}" verdict — the triad must explain every blocking decision`)
    process.exit(1)
  }

  const es    = readLines(LEDGER)
  const seq   = lastSeq(es) + 1
  const prev  = lastHash(es)
  const cycle = cycleId || (Date.now().toString(36) + Math.random().toString(36).slice(2, 7))

  const body = {
    phase,
    agent,
    verdict,
    proposal:              proposal.normalize('NFC').slice(0, 200),
    reason:                (reason || '').normalize('NFC').slice(0, 400),
    sequence:              seq,
    previous_verdict_hash: prev,
  }
  const verdict_hash = sha256(canon(body))
  const entry = { ...body, verdict_hash, schema_version: SCHEMA, cycle_id: cycle }

  mkdirSync(dirname(LEDGER), { recursive: true })
  appendFileSync(LEDGER, JSON.stringify(entry) + '\n')

  // Observe in live metacog chain (best-effort — chain optional)
  try {
    const tag = AFFIRMATIVE.has(verdict) ? '✓' : '✗'
    execFileSync('node', [CHAIN_MJS, 'observe', 'EXECUTIVE', 'T2',
      `agent-mesh ${phase}/${agent}: ${verdict} ${tag} — ${proposal.slice(0, 60)}`],
      { stdio: 'ignore' })
  } catch { /* live chain is optional */ }

  console.log(JSON.stringify({
    verdict, phase, agent, sequence: seq,
    verdict_hash: verdict_hash.slice(0, 12),
    cycle_id:     cycle,
    affirmative:  AFFIRMATIVE.has(verdict),
  }))
  // Exit 1 for blocking verdicts so callers can short-circuit the cycle
  process.exit(AFFIRMATIVE.has(verdict) ? 0 : 1)
}

// ── certify: re-walk the ledger, detect any tamper ───────────────────────────
function certify() {
  const es = readLines(LEDGER)
  let is_valid = true, broken_at = null
  for (let i = 0; i < es.length; i++) {
    const expectedPrev = i === 0 ? GENESIS : es[i - 1].verdict_hash
    if (es[i].previous_verdict_hash !== expectedPrev) { is_valid = false; broken_at = i; break }
    const { verdict_hash, schema_version, cycle_id, ...body } = es[i]
    if (sha256(canon(body)) !== verdict_hash) { is_valid = false; broken_at = i; break }
  }
  console.log(JSON.stringify({
    is_valid,
    entry_count:       es.length,
    terminal_hash:     es.length ? es[es.length - 1].verdict_hash.slice(0, 16) : null,
    broken_at,
    veto_count:        es.filter(e => e.verdict === 'VETO').length,
    ineligible_count:  es.filter(e => e.verdict === 'INELIGIBLE').length,
    failed_count:      es.filter(e => e.verdict === 'FAILED').length,
    complete_count:    es.filter(e => e.verdict === 'COMPLETE').length,
  }))
}

// ── gate: pre-commit integrity check ─────────────────────────────────────────
// Exits 0 if the ledger is intact (tamper-free).
// Exits 2 if the chain is broken (hash mismatch or prev_hash divergence).
// Verdict enforcement (veto = no commit) is a higher-level protocol concern;
// the gate's job is to guarantee the ledger itself is tamper-evident.
function gate() {
  const es = readLines(LEDGER)
  for (let i = 0; i < es.length; i++) {
    const expectedPrev = i === 0 ? GENESIS : es[i - 1].verdict_hash
    if (es[i].previous_verdict_hash !== expectedPrev) {
      console.error(`AGENT-MESH TAMPER — verdict chain broken at entry ${i} (prev_hash mismatch).\n  This is a T0_ABORT condition — the verdict record cannot be trusted.`)
      process.exit(2)
    }
    const { verdict_hash, schema_version, cycle_id, ...body } = es[i]
    if (sha256(canon(body)) !== verdict_hash) {
      console.error(`AGENT-MESH TAMPER — verdict ${i} hash invalid (${verdict_hash.slice(0, 12)} ≠ recomputed).\n  A verdict was retroactively altered. This is a constitutional breach.`)
      process.exit(2)
    }
  }
  const veto_count  = es.filter(e => e.verdict === 'VETO').length
  const complete    = es.filter(e => e.verdict === 'COMPLETE').length
  console.log(`agent-mesh: ${es.length} verdicts verified — ${complete} complete, ${veto_count} veto${veto_count !== 1 ? 's' : ''} on record. chain intact. OK.`)
  process.exit(0)
}

// ── tail: last N verdicts (human-readable) ───────────────────────────────────
function tail(n = 8) {
  const es = readLines(LEDGER)
  const last = es.slice(-Math.abs(n))
  if (last.length === 0) { console.log('(no verdicts recorded)'); return }
  last.forEach(e => {
    const mark = AFFIRMATIVE.has(e.verdict) ? '✓' : '✗'
    const reason = e.reason ? ` — ${e.reason.slice(0, 60)}` : ''
    console.log(`${mark} [${e.sequence}] ${e.phase}/${e.agent}: ${e.verdict}${reason}`)
    console.log(`    proposal: ${e.proposal.slice(0, 80)}`)
    console.log(`    hash: ${e.verdict_hash.slice(0, 16)} | cycle: ${e.cycle_id}`)
  })
}

const [cmd, ...args] = process.argv.slice(2)
switch (cmd) {
  case 'record': {
    // Parse: record <phase> <agent> <verdict> <proposal> [reason] [--cycle <id>]
    let cycle = undefined
    const cleanArgs = []
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--cycle' && args[i + 1]) { cycle = args[++i] }
      else cleanArgs.push(args[i])
    }
    const [phase, agent, verdict, proposal, ...reasonParts] = cleanArgs
    record(phase, agent, verdict, proposal, reasonParts.join(' '), cycle)
    break
  }
  case 'certify': certify(); break
  case 'gate':    gate();    break
  case 'tail':    tail(parseInt(args[0]) || 8); break
  default:
    console.error('usage: agent-mesh.mjs record <phase> <agent> <verdict> <proposal> [reason] [--cycle <id>]')
    console.error('       agent-mesh.mjs certify | gate | tail [n]')
    console.error('')
    console.error('phases:  GUARDIAN_ASSESS | VERIFIER_CHECK | IMPLEMENTER_EXEC | GUARDIAN_FINAL')
    console.error('agents:  guardian | verifier | implementer')
    console.error('verdicts: PASS/VETO | ELIGIBLE/INELIGIBLE | COMPLETE/FAILED | PASS/VETO')
    process.exit(2)
}
