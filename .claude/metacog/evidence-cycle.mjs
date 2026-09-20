#!/usr/bin/env node
// AEGIS Ω — Metacognitive Evidence Cycle v0.2
// Evaluate snapshot -> verify lineage -> append transition ledger -> mirror the
// transition into the existing live Metacognitive Observation Chain.

import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { evaluateSnapshot } from './evidence-state.mjs'
import { appendReceipt, latestLedgerState } from './evidence-ledger.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const DEFAULT_REPO = resolve(HERE, '../..')

function assert(cond, msg) { if (!cond) throw new Error(msg) }
function readJson(path) { return JSON.parse(readFileSync(path, 'utf8')) }

function bindPrior(snapshot, ledgerPath) {
  const { latest } = latestLedgerState(ledgerPath)
  const out = structuredClone(snapshot)

  if (latest) {
    try {
      const replay = evaluateSnapshot(out)
      if (replay.receipt_sha256 === latest.receipt_sha256) return out
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

export function runEvidenceCycle({ snapshotPath, receiptPath, ledgerPath, chainPath, env = process.env }) {
  const rawSnapshot = readJson(snapshotPath)
  const snapshot = bindPrior(rawSnapshot, ledgerPath)
  const receipt = evaluateSnapshot(snapshot)
  atomicWriteJson(receiptPath, receipt)

  const ledgerResult = appendReceipt(receipt, ledgerPath)
  let chain = { mirrored: false, skipped_duplicate: false, certified: null }

  if (ledgerResult.duplicate) {
    chain.skipped_duplicate = true
  } else {
    assert(existsSync(chainPath), `metacognitive chain engine missing: ${chainPath}`)
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
      { encoding: 'utf8', env: { ...env } })
    assert(obs.status === 0, `chain observe failed: ${obs.stderr || obs.stdout}`)
    chain.mirrored = true
    chain.entry_hash_prefix = String(obs.stdout ?? '').trim()

    const cert = spawnSync(process.execPath, [chainPath, 'certify'],
      { encoding: 'utf8', env: { ...env } })
    assert(cert.status === 0, `chain certify failed: ${cert.stderr || cert.stdout}`)
    chain.certified = JSON.parse(cert.stdout)
    assert(chain.certified.is_valid === true, 'metacognitive chain failed certification after evidence transition')
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
