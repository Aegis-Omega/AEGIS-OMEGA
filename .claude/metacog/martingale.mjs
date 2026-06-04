#!/usr/bin/env node
// ============================================================
// AEGIS — Martingale Suspension Harness (harness-layer / Gate 0)
//
// Enacts the constitutional martingale of src/constitutional/martingale.ts:
//   E[S_{n+1} | F_n] = S_n  — adaptation may not outrun replay-verifiability.
//
// Faithful mapping into the running automaton:
//   replay_verifiability = total verified self-observations (metacog chain length)
//   adaptive_power       = significant capability mutations =
//                            (ratified φ-quorum changes) + (TIER_PROMOTION obs)
//                          — the analog of APPROVED CAPABILITY_EVOLUTION entries
//   adaptive_ratio       = adaptive_power / replay_verifiability
//   is_anchored          = metacog chain integrity AND ratification ledger integrity
//
// SUSPENDED  iff  !is_anchored  OR  adaptive_power·1e6 > replay_verifiability·618034
//   (integer ppm threshold = 1/φ; NO f64 in the decision)
//
// Constitutional consequence (enforced, not asserted): when SUSPENDED, mutation
// authority is withdrawn — the pre-commit gate blocks the commit. Two ways to
// trip it: (a) tamper either hash chain → !is_anchored; (b) ratify/ promote
// capabilities faster than 1/φ of total self-observation → entropy unbounded.
// You cannot mutate faster than you can account for your own mutations.
//
// Dependency-free: node:crypto + node:fs.
// ============================================================
import { createHash } from 'node:crypto'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const REPO   = process.env.CLAUDE_PROJECT_DIR || '/home/user/AEGIS--'
const DIR    = join(REPO, '.claude/metacog')
const CHAIN  = process.env.AEGIS_METACOG_CHAIN || join(DIR, 'chain.jsonl')
const LEDGER = process.env.AEGIS_QUORUM_LEDGER || join(DIR, 'ratifications.jsonl')
const GENESIS = '0'.repeat(64)
const THRESHOLD_PPM = 618034
const PPM = 1_000_000

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

// Re-walk the metacog chain (entry_hash algorithm from chain.mjs / loop.ts).
function certifyChain(es) {
  for (let i = 0; i < es.length; i++) {
    const expectedPrev = i === 0 ? GENESIS : es[i - 1].entry_hash
    if (es[i].previous_entry_hash !== expectedPrev) return false
    const rec = sha256(canon({
      observation: es[i].observation,
      previous_entry_hash: es[i].previous_entry_hash,
      sequence: String(es[i].sequence),
    }))
    if (rec !== es[i].entry_hash) return false
  }
  return true
}
// Re-walk the ratification ledger (convergence_hash algorithm from quorum.mjs).
function certifyLedger(es) {
  for (let i = 0; i < es.length; i++) {
    const expectedPrev = i === 0 ? GENESIS : es[i - 1].convergence_hash
    if (es[i].previous_convergence_hash !== expectedPrev) return false
    const { convergence_hash, schema_version, is_replay_reconstructable, ...body } = es[i]
    if (sha256(canon(body)) !== convergence_hash) return false
  }
  return true
}

function certificate() {
  const chain  = readLines(CHAIN)
  const ledger = readLines(LEDGER)

  const chain_valid  = certifyChain(chain)
  const ledger_valid = certifyLedger(ledger)
  const is_anchored  = chain_valid && ledger_valid

  const replay_verifiability = chain.length
  const ratified_count   = ledger.filter(r => r.ratified === true).length
  const tier_promotions  = chain.filter(e => e.observation?.layer === 'TIER_PROMOTION').length
  const adaptive_power   = ratified_count + tier_promotions

  // Integer ppm decision — no f64.
  const ratio_ppm = replay_verifiability > 0
    ? Math.floor(adaptive_power * PPM / replay_verifiability)
    : 0
  const entropy_bounded = adaptive_power * PPM <= replay_verifiability * THRESHOLD_PPM
  const suspended = !is_anchored || !entropy_bounded

  return {
    suspended,
    is_anchored,
    chain_valid,
    ledger_valid,
    entropy_bounded,
    adaptive_power,
    replay_verifiability,
    adaptive_ratio_ppm: ratio_ppm,
    mutation_rate_limit_ppm: THRESHOLD_PPM,
    breakdown: { ratified_count, tier_promotions },
  }
}

const [cmd] = process.argv.slice(2)
const cert = certificate()
switch (cmd) {
  case 'status':
  case 'certify':
    console.log(JSON.stringify(cert))
    break
  case 'gate':
    // Enforcement: exit 2 (block) if suspended; exit 0 if anchored & bounded.
    if (cert.suspended) {
      const reason = !cert.is_anchored
        ? `chain integrity broken (chain_valid=${cert.chain_valid}, ledger_valid=${cert.ledger_valid}) — E[S_{n+1}|F_n] ≠ S_n`
        : `mutation authority exceeded: adaptive_ratio ${cert.adaptive_ratio_ppm}ppm > 1/φ ${THRESHOLD_PPM}ppm`
      console.error(`MARTINGALE SUSPENDED — mutation authority withdrawn.\n  ${reason}`)
      process.exit(2)
    }
    console.log(`martingale anchored — adaptive ${cert.adaptive_power}/${cert.replay_verifiability} (${cert.adaptive_ratio_ppm}ppm ≤ ${THRESHOLD_PPM}ppm). OK.`)
    process.exit(0)
  default:
    console.error('usage: martingale.mjs status | certify | gate')
    process.exit(2)
}
