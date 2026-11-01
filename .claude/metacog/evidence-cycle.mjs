#!/usr/bin/env node
// AEGIS Ω — Metacognitive Evidence Cycle v0.2
// Evaluate snapshot -> verify lineage -> append transition ledger -> mirror the
// transition into the existing live Metacognitive Observation Chain.

import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { evaluateSnapshot } from './evidence-state.mjs'
import { appendReceipt, latestLedgerState } from './evidence-ledger.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const DEFAULT_REPO = resolve(HERE, '../..')

function assert(cond, msg) { if (!cond) throw new Error(msg) }
function readJson(path) { return JSON.parse(readFileSync(path, 'utf8')) }

function bindPrior(snapshot, ledgerPath) {
  const { latest, entries } = latestLedgerState(ledgerPath)
  const out = structuredClone(snapshot)

  if (latest) {
    try {
      const replay = evaluateSnapshot(out)
      if (replay.receipt_sha256 === latest.receipt_sha256) return out
    } catch {}
    // Recovery after a ledger-first crash: the persisted receipt contains its
    // *previous* lineage, not a fresh link to itself. Recreate that exact
    // candidate before deciding whether the input is a new observation.
    const prior = entries.at(-2) ?? null
    const retry = structuredClone(out)
    if (retry.prior_receipt_sha256 === undefined) retry.prior_receipt_sha256 = prior?.receipt_sha256 ?? null
    if (retry.previous_epistemic_state === undefined) retry.previous_epistemic_state = prior?.current_epistemic_state ?? null
    if (retry.previous_head_sha === undefined) retry.previous_head_sha = prior?.head_sha ?? (retry.head_sha ?? null)
    try {
      if (evaluateSnapshot(retry).receipt_sha256 === latest.receipt_sha256) return retry
    } catch {}
  }

  if (!latest) {
    if (out.prior_receipt_sha256 === undefined) out.prior_receipt_sha256 = null
    if (out.previous_epistemic_state === undefined) out.previous_epistemic_state = null
    if (out.previous_head_sha === undefined) out.previous_head_sha = out.head_sha ?? null
    return out
  }

  if (out.prior_receipt_sha256 === undefined) out.prior_receipt_sha256 = latest.receipt_sha256
  else assert(out.prior_receipt_sha256 === latest.receipt_sha256,
    `snapshot prior receipt mismatch: ${out.prior_receipt_sha256} != ${latest.receipt_sha256}`)

  if (out.previous_epistemic_state === undefined) out.previous_epistemic_state = latest.current_epistemic_state
  else assert(out.previous_epistemic_state === latest.current_epistemic_state,
    `snapshot previous state mismatch: ${out.previous_epistemic_state} != ${latest.current_epistemic_state}`)

  if (out.previous_head_sha === undefined) out.previous_head_sha = latest.head_sha
  else assert(out.previous_head_sha === latest.head_sha,
    `snapshot previous head mismatch: ${out.previous_head_sha} != ${latest.head_sha}`)
  return out
}

function atomicWriteJson(path, value) {
  mkdirSync(dirname(path), { recursive: true })
  const tmp = `${path}.tmp.${process.pid}`
  writeFileSync(tmp, JSON.stringify(value, null, 2) + '\n', 'utf8')
  renameSync(tmp, path)
}

function subjectToken(subject) {
  if (!subject || typeof subject !== 'object') return 'none'
  return `${String(subject.kind ?? 'subject')}:${String(subject.id ?? 'unknown')}`
}

// Reconcile a ledger-first crash without replaying a provider call or inventing
// execution authority. Ledger bytes are certified by appendReceipt; the chain
// is independently certified by the native engine before AND after mirroring.
function inspectChain(chainPath, env, { requireAnchor = false } = {}) {
  assert(existsSync(chainPath), `metacognitive chain engine missing: ${chainPath}`)
  const chainDataPath = env.AEGIS_METACOG_CHAIN || join(env.CLAUDE_PROJECT_DIR || DEFAULT_REPO, '.claude/metacog/chain.jsonl')
  assert(!requireAnchor || existsSync(chainDataPath), 'EVIDENCE_CHAIN_UNANCHORED')
  const raw = existsSync(chainDataPath) ? readFileSync(chainDataPath, 'utf8') : ''
  const entries = raw.split('\n').filter(Boolean).map(s => JSON.parse(s))
  assert(!requireAnchor || entries.length > 0, 'EVIDENCE_CHAIN_UNANCHORED')
  const cert = spawnSync(process.execPath, [chainPath, 'certify'],
    { encoding: 'utf8', env: { ...env }, timeout: 15000 })
  assert(cert.status === 0, `chain certify failed: ${cert.stderr || cert.stdout}`)
  const result = JSON.parse(cert.stdout)
  assert(result.is_valid === true && result.entry_count === entries.length, 'EVIDENCE_CHAIN_NOT_CERTIFIED')
  return { cert: result, entries, chainDataPath }
}

function mirrorMatches(entries, receipt, transition) {
  return entries.filter(e => {
    if (e.observation?.layer !== 'METACOGNITIVE' || typeof e.observation.signal !== 'string') return false
    const tokens = new Set(e.observation.signal.split(/\s+/))
    return tokens.has(`receipt=${receipt.receipt_sha256}`) &&
      tokens.has(`transition=${transition}`) && tokens.has('authority=NONE')
  })
}

function assertMirrorPrefix(ledgerEntries, chainEntries, requiredLength) {
  const observed = chainEntries.filter(e => e.observation?.layer === 'METACOGNITIVE' &&
    typeof e.observation.signal === 'string' &&
    e.observation.signal.startsWith('evidence-transition '))
  assert(observed.length === requiredLength, 'EVIDENCE_CHAIN_LEDGER_COUNT_MISMATCH')
  for (let i = 0; i < requiredLength; i++) {
    const expected = ledgerEntries[i]
    const tokens = new Set(observed[i].observation.signal.split(/\s+/))
    assert(tokens.has(`receipt=${expected.receipt_sha256}`) &&
      tokens.has(`transition=${expected.transition_hash}`) &&
      tokens.has('authority=NONE'), `EVIDENCE_CHAIN_LEDGER_ORDER_MISMATCH:${i}`)
  }
}

export function runEvidenceCycle({ snapshotPath, receiptPath, ledgerPath, chainPath, env = process.env }) {
  const rawSnapshot = readJson(snapshotPath)
  const snapshot = bindPrior(rawSnapshot, ledgerPath)
  const receipt = evaluateSnapshot(snapshot)
  const existingLedger = latestLedgerState(ledgerPath)
  if (existingLedger.latest) {
    // A new observation must not overtake an unfinished prior mirror. This
    // check happens BEFORE either the receipt or ledger is written.
    const existingChain = inspectChain(chainPath, env, { requireAnchor: true })
    const priorMatches = mirrorMatches(existingChain.entries,
      { receipt_sha256: existingLedger.latest.receipt_sha256 },
      existingLedger.latest.transition_hash)
    if (priorMatches.length === 0) {
      assert(receipt.receipt_sha256 === existingLedger.latest.receipt_sha256,
        'EVIDENCE_PENDING_UNMIRRORED')
    } else {
      assertMirrorPrefix(existingLedger.entries, existingChain.entries, existingLedger.entries.length)
    }
  }
  atomicWriteJson(receiptPath, receipt)

  const ledgerResult = appendReceipt(receipt, ledgerPath)
  let chain = { mirrored: false, skipped_duplicate: false, certified: null }
  const before = inspectChain(chainPath, env, { requireAnchor: ledgerResult.duplicate })
  const found = mirrorMatches(before.entries, receipt, ledgerResult.transition_hash)
  const { entries: ledgerEntries } = latestLedgerState(ledgerPath)
  const expectedBefore = ledgerEntries.length - (found.length ? 0 : 1)
  assertMirrorPrefix(ledgerEntries, before.entries, expectedBefore)
  assert(found.length <= 1, 'EVIDENCE_CHAIN_DUPLICATE_MIRROR')
  const conflictingReceipt = before.entries.some(e =>
    e.observation?.layer === 'METACOGNITIVE' &&
    typeof e.observation.signal === 'string' &&
    e.observation.signal.split(/\s+/).includes(`receipt=${receipt.receipt_sha256}`) &&
    !mirrorMatches([e], receipt, ledgerResult.transition_hash).length)
  assert(!conflictingReceipt, 'EVIDENCE_CHAIN_RECEIPT_CONFLICT')

  if (found.length === 1) {
    assert(ledgerResult.duplicate, 'EVIDENCE_CHAIN_MIRROR_WITHOUT_LEDGER')
    chain.skipped_duplicate = true
    chain.certified = before.cert
  } else {
    if (ledgerResult.duplicate) {
      // Only repair the latest ledger transition; later history must never be
      // reordered or silently rewritten to make a stale receipt appear current.
      const { latest } = latestLedgerState(ledgerPath)
      assert(latest?.receipt_sha256 === receipt.receipt_sha256 &&
        latest.transition_hash === ledgerResult.transition_hash, 'EVIDENCE_REPAIR_NOT_LATEST')
    }
    assert(!existsSync(before.chainDataPath + '.lock'), 'EVIDENCE_CHAIN_BUSY')
    const signal = [
      'evidence-transition',
      `receipt=${receipt.receipt_sha256}`,
      `transition=${ledgerResult.transition_hash}`,
      `subject=${subjectToken(receipt.subject)}`,
      `state=${receipt.current_epistemic_state}`,
      `drift=${Boolean(receipt.epistemic_state_drift)}`,
      `revalidation=${receipt.revalidation?.scope ?? 'NONE'}`,
      `authority=${receipt.authority_effect}`,
    ].join(' ')
    assert(signal.length <= 500, 'metacognitive evidence signal exceeds chain signal bound')
    const obs = spawnSync(process.execPath,
      [chainPath, 'observe', 'METACOGNITIVE', 'T1', signal],
      { encoding: 'utf8', env: { ...env }, timeout: 15000 })
    assert(obs.status === 0, `chain observe failed: ${obs.stderr || obs.stdout}`)
    const after = inspectChain(chainPath, env)
    assert(mirrorMatches(after.entries, receipt, ledgerResult.transition_hash).length === 1,
      'EVIDENCE_TRANSITION_NOT_MIRRORED')
    assert(after.cert.entry_count === before.cert.entry_count + 1, 'EVIDENCE_CHAIN_UNEXPECTED_APPEND')
    assertMirrorPrefix(ledgerEntries, after.entries, ledgerEntries.length)
    chain.mirrored = true
    chain.recovered_from_ledger = ledgerResult.duplicate
    chain.entry_hash_prefix = String(obs.stdout ?? '').trim()
    chain.certified = after.cert
  }

  return {
    schema: 'aegis.metacognitive-evidence-cycle-result.v1',
    receipt_sha256: receipt.receipt_sha256,
    current_epistemic_state: receipt.current_epistemic_state,
    epistemic_state_drift: receipt.epistemic_state_drift,
    revalidation_scope: receipt.revalidation?.scope ?? 'NONE',
    authority_effect: receipt.authority_effect,
    ledger: ledgerResult,
    chain,
  }
}

function main() {
  const [cmd, snapshotArg, receiptArg, ledgerArg, chainArg] = process.argv.slice(2)
  if (cmd !== 'run' || !snapshotArg) {
    console.error('usage: evidence-cycle.mjs run <snapshot.json> [receipt.json] [ledger.log] [chain.mjs]')
    process.exit(2)
  }
  const repo = process.env.CLAUDE_PROJECT_DIR || DEFAULT_REPO
  const receiptPath = receiptArg || process.env.AEGIS_EVIDENCE_RECEIPT || resolve(repo, '.claude/metacog/evidence-receipt.tmp')
  const ledgerPath = ledgerArg || process.env.AEGIS_EVIDENCE_LEDGER || resolve(repo, '.claude/metacog/evidence-transitions.log')
  const chainPath = chainArg || resolve(repo, '.claude/metacog/chain.mjs')
  try {
    const result = runEvidenceCycle({
      snapshotPath: resolve(snapshotArg), receiptPath: resolve(receiptPath),
      ledgerPath: resolve(ledgerPath), chainPath: resolve(chainPath), env: process.env,
    })
    console.log(JSON.stringify(result, null, 2))
  } catch (err) {
    console.error(`EVIDENCE_CYCLE_DENIED ${err?.message ?? String(err)}`)
    process.exit(1)
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) main()
