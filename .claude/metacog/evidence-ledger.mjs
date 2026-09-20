#!/usr/bin/env node
// AEGIS Ω — Metacognitive Evidence Transition Ledger v0.2
// Hash-chained, fail-closed, authority-neutral. No network or repo mutation.

import { appendFileSync, existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { sha256, SCHEMA as RECEIPT_SCHEMA } from './evidence-state.mjs'

export const LEDGER_SCHEMA = 'aegis.metacognitive-evidence-ledger.v1'
export const TRANSITION_SCHEMA = 'aegis.metacognitive-evidence-transition.v1'
export const GENESIS = '0'.repeat(64)
const HASH_RE = /^[0-9a-f]{64}$/

function assert(cond, msg) { if (!cond) throw new Error(msg) }

export function readLedger(path) {
  if (!existsSync(path)) return []
  const raw = readFileSync(path, 'utf8')
  if (!raw.trim()) return []
  return raw.split('\n').filter(Boolean).map((line, i) => {
    try { return JSON.parse(line) }
    catch (e) { throw new Error(`ledger line ${i} invalid JSON: ${e.message}`) }
  })
}

export function verifyReceipt(receipt) {
  assert(receipt && typeof receipt === 'object', 'receipt must be an object')
  assert(receipt.schema === RECEIPT_SCHEMA, `unexpected receipt schema: ${receipt.schema}`)
  assert(typeof receipt.receipt_sha256 === 'string' && HASH_RE.test(receipt.receipt_sha256), 'invalid receipt_sha256')
  assert(receipt.authority_effect === 'NONE', 'evidence receipt may not grant authority')
  const { receipt_sha256, ...body } = receipt
  const recomputed = sha256(body)
  assert(recomputed === receipt_sha256, `receipt hash mismatch: expected ${receipt_sha256}, recomputed ${recomputed}`)
  return true
}

function transitionBody(receipt, sequence, previousTransitionHash) {
  return {
    schema: TRANSITION_SCHEMA,
    sequence,
    previous_transition_hash: previousTransitionHash,
    receipt_sha256: receipt.receipt_sha256,
    observed_at: receipt.observed_at,
    subject: receipt.subject ?? null,
    head_sha: receipt.head_sha ?? null,
    previous_head_sha: receipt.previous_head_sha ?? null,
    current_epistemic_state: receipt.current_epistemic_state,
    previous_epistemic_state: receipt.previous_epistemic_state ?? null,
    epistemic_state_drift: Boolean(receipt.epistemic_state_drift),
    revalidation_scope: receipt.revalidation?.scope ?? 'NONE',
    authority_effect: receipt.authority_effect,
    storage_mode: 'RUNTIME_LOCAL',
  }
}

export function certifyLedger(entries) {
  let previous = GENESIS
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i]
    if (e.schema !== TRANSITION_SCHEMA) return { is_valid: false, broken_at: i, reason: 'schema' }
    if (e.sequence !== i) return { is_valid: false, broken_at: i, reason: 'sequence' }
    if (e.previous_transition_hash !== previous) return { is_valid: false, broken_at: i, reason: 'previous_transition_hash' }
    const { transition_hash, ...body } = e
    if (!HASH_RE.test(String(transition_hash ?? ''))) return { is_valid: false, broken_at: i, reason: 'transition_hash_format' }
    const recomputed = sha256(body)
    if (recomputed !== transition_hash) return { is_valid: false, broken_at: i, reason: 'transition_hash' }
    previous = transition_hash
  }
  return {
    is_valid: true,
    entry_count: entries.length,
    terminal_hash: entries.length ? entries.at(-1).transition_hash : null,
    latest_receipt_sha256: entries.length ? entries.at(-1).receipt_sha256 : null,
    latest_epistemic_state: entries.length ? entries.at(-1).current_epistemic_state : null,
    latest_head_sha: entries.length ? entries.at(-1).head_sha : null,
  }
}

export function latestLedgerState(path) {
  const entries = readLedger(path)
  const cert = certifyLedger(entries)
  assert(cert.is_valid, `evidence ledger invalid at ${cert.broken_at}: ${cert.reason}`)
  return { entries, cert, latest: entries.length ? entries.at(-1) : null }
}

export function appendReceipt(receipt, ledgerPath) {
  verifyReceipt(receipt)
  const { entries, cert, latest } = latestLedgerState(ledgerPath)

  const priorExisting = entries.find(e => e.receipt_sha256 === receipt.receipt_sha256)
  if (priorExisting) {
    return {
      appended: false,
      duplicate: true,
      sequence: priorExisting.sequence,
      transition_hash: priorExisting.transition_hash,
      ledger_entry_count: entries.length,
    }
  }

  const declaredPrior = receipt.lineage?.prior_receipt_sha256 ?? null
  if (!latest) {
    assert(declaredPrior === null, 'lineage gap: first transition must have null prior_receipt_sha256')
  } else {
    assert(typeof declaredPrior === 'string' && HASH_RE.test(declaredPrior), 'lineage gap: subsequent transition must bind prior_receipt_sha256')
    assert(declaredPrior === latest.receipt_sha256,
      `lineage gap: declared prior ${declaredPrior} != ledger latest ${latest.receipt_sha256}`)
    assert(receipt.previous_epistemic_state === latest.current_epistemic_state,
      `previous epistemic state mismatch: ${receipt.previous_epistemic_state} != ${latest.current_epistemic_state}`)
    assert(receipt.previous_head_sha === latest.head_sha,
      `previous head mismatch: ${receipt.previous_head_sha} != ${latest.head_sha}`)
  }

  const sequence = entries.length
  const previousTransitionHash = cert.terminal_hash ?? GENESIS
  const body = transitionBody(receipt, sequence, previousTransitionHash)
  const entry = { ...body, transition_hash: sha256(body) }
  appendFileSync(ledgerPath, JSON.stringify(entry) + '\n', 'utf8')

  return {
    appended: true,
    duplicate: false,
    sequence,
    transition_hash: entry.transition_hash,
    ledger_entry_count: sequence + 1,
  }
}

function main() {
  const [cmd, arg1, arg2] = process.argv.slice(2)
  try {
    if (cmd === 'append' && arg1) {
      const receipt = JSON.parse(readFileSync(arg1, 'utf8'))
      const ledger = arg2 || process.env.AEGIS_EVIDENCE_LEDGER || resolve('.claude/metacog/evidence-transitions.log')
      console.log(JSON.stringify(appendReceipt(receipt, ledger)))
      return
    }
    if (cmd === 'certify') {
      const ledger = arg1 || process.env.AEGIS_EVIDENCE_LEDGER || resolve('.claude/metacog/evidence-transitions.log')
      console.log(JSON.stringify(certifyLedger(readLedger(ledger))))
      return
    }
    console.error('usage: evidence-ledger.mjs append <receipt.json> [ledger.log] | certify [ledger.log]')
    process.exit(2)
  } catch (err) {
    console.error(`EVIDENCE_LEDGER_DENIED ${err?.message ?? String(err)}`)
    process.exit(1)
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) main()
