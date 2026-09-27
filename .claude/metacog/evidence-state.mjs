#!/usr/bin/env node
// AEGIS Ω — Metacognitive Evidence-State Evaluator (Gate 0)
// Dependency-free. Pure evaluation: no repository/network mutation.

import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

export const SCHEMA = 'aegis.metacognitive-evidence-receipt.v1'
const SHA256_RE = /^sha256:[0-9a-f]{64}$/i
const COMMIT_RE = /^[0-9a-f]{40}$/i

export function canon(v) {
  if (v === null || typeof v !== 'object') {
    return JSON.stringify(typeof v === 'string' ? v.normalize('NFC') : v)
  }
  if (Array.isArray(v)) return '[' + v.map(canon).join(',') + ']'
  const keys = Object.keys(v).sort()
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}'
}

export const sha256 = (v) => createHash('sha256').update(typeof v === 'string' ? v : canon(v), 'utf8').digest('hex')

function assert(cond, message) {
  if (!cond) throw new Error(message)
}

function normalizeEvidence(item, currentHead) {
  assert(item && typeof item === 'object', 'evidence item must be an object')
  assert(typeof item.evidence_id === 'string' && item.evidence_id.length > 0, 'evidence_id required')

  const boundHead = item.bound_head_sha ?? null
  if (boundHead !== null) assert(COMMIT_RE.test(boundHead), `${item.evidence_id}: invalid bound_head_sha`)

  const conclusion = String(item.conclusion ?? 'UNKNOWN').toUpperCase()
  const terminalSuccess = conclusion === 'SUCCESS'
  const exactHead = boundHead !== null && currentHead !== null && boundHead === currentHead
  const artifact = item.artifact && typeof item.artifact === 'object' ? item.artifact : null
  const digest = artifact?.digest ?? null
  const digestValid = digest === null ? null : SHA256_RE.test(String(digest))
  const available = artifact?.available === true
  const expired = artifact?.expired === true || Number(artifact?.http_status) === 410
  const loadBearing = item.load_bearing !== false

  let evidenceState
  if (!terminalSuccess) evidenceState = 'EXECUTION_NOT_SUCCESSFUL'
  else if (boundHead !== null && !exactHead) evidenceState = 'STALE_HEAD_BINDING'
  else if (!artifact) evidenceState = 'SUCCESS_WITHOUT_CONTENT_ARTIFACT'
  else if (available) evidenceState = 'CURRENT_REINSPECTABLE'
  else if (expired) evidenceState = 'HISTORICAL_NOT_REINSPECTABLE'
  else evidenceState = 'CONTENT_AVAILABILITY_UNKNOWN'

  const triggers = []
  if (evidenceState === 'HISTORICAL_NOT_REINSPECTABLE') triggers.push('EVIDENCE_DECAY')
  if (evidenceState === 'STALE_HEAD_BINDING') triggers.push('EXACT_HEAD_DRIFT')
  if (evidenceState === 'CONTENT_AVAILABILITY_UNKNOWN') triggers.push('OBSERVABILITY_UNKNOWN')
  if (evidenceState === 'EXECUTION_NOT_SUCCESSFUL') triggers.push('EXECUTION_FAILURE')
  if (digest !== null && digestValid === false) triggers.push('DIGEST_FORMAT_INVALID')

  return {
    evidence_id: item.evidence_id,
    kind: item.kind ?? 'UNSPECIFIED',
    load_bearing: loadBearing,
    conclusion,
    bound_head_sha: boundHead,
    exact_head_bound: exactHead,
    artifact: artifact ? {
      id: artifact.id ?? null,
      digest,
      digest_format_valid: digestValid,
      available,
      expired,
      http_status: artifact.http_status ?? null,
      expires_at: artifact.expires_at ?? null,
    } : null,
    evidence_state: evidenceState,
    triggers,
  }
}

function aggregateState(evidence) {
  const required = evidence.filter(e => e.load_bearing)
  if (required.length === 0) return 'NOT_ESTABLISHED'

  if (required.some(e => e.evidence_state === 'EXECUTION_NOT_SUCCESSFUL')) return 'NOT_ESTABLISHED'
  if (required.some(e => e.evidence_state === 'STALE_HEAD_BINDING')) return 'NOT_ESTABLISHED'
  if (required.some(e => e.evidence_state === 'CONTENT_AVAILABILITY_UNKNOWN')) return 'NOT_ESTABLISHED'
  if (required.some(e => e.artifact?.digest_format_valid === false)) return 'NOT_ESTABLISHED'
  if (required.some(e => e.evidence_state === 'HISTORICAL_NOT_REINSPECTABLE')) return 'HISTORICAL_NOT_REINSPECTABLE'
  if (required.every(e => e.evidence_state === 'CURRENT_REINSPECTABLE')) return 'CURRENT_REINSPECTABLE'
  return 'BOUNDED_HISTORICAL_ONLY'
}

function claimAuthority(state, evidence) {
  const exactSuccess = evidence.some(e => e.load_bearing && e.conclusion === 'SUCCESS' && e.exact_head_bound)
  const reinspectable = state === 'CURRENT_REINSPECTABLE'

  return {
    recorded_execution_status: exactSuccess ? 'ALLOW_HISTORICAL_FACT' : 'NOT_ESTABLISHED',
    current_content_reinspection: reinspectable ? 'ALLOW' : 'DENY',
    independent_content_revalidation: reinspectable ? 'ALLOW' : 'DENY',
    merge_admission: 'NO_PROMOTION',
    claims_promotion: 'NO_PROMOTION',
    authority_grant: 'NO_PROMOTION',
  }
}

function revalidationPlan(state, evidence) {
  const expired = evidence.filter(e => e.load_bearing && e.evidence_state === 'HISTORICAL_NOT_REINSPECTABLE')
  const stale = evidence.filter(e => e.load_bearing && e.evidence_state === 'STALE_HEAD_BINDING')
  const unknown = evidence.filter(e => e.load_bearing && e.evidence_state === 'CONTENT_AVAILABILITY_UNKNOWN')

  if (stale.length) {
    return {
      required: true,
      scope: 'EXACT_HEAD_REPLAY',
      reason: 'One or more load-bearing evidence objects are bound to a different repository head.',
      evidence_ids: stale.map(e => e.evidence_id),
    }
  }
  if (expired.length) {
    return {
      required: true,
      scope: 'CONTENT_ARTIFACT_REFRESH_SAME_HEAD',
      reason: 'Historical execution success is preserved, but evidence bytes are no longer independently reinspectable.',
      evidence_ids: expired.map(e => e.evidence_id),
    }
  }
  if (unknown.length || state === 'NOT_ESTABLISHED') {
    return {
      required: true,
      scope: 'EVIDENCE_REESTABLISHMENT',
      reason: 'Load-bearing evidence is incomplete, unknown, stale, malformed, or unsuccessful.',
      evidence_ids: [...unknown.map(e => e.evidence_id)],
    }
  }
  return { required: false, scope: 'NONE', reason: null, evidence_ids: [] }
}

export function evaluateSnapshot(snapshot) {
  assert(snapshot && typeof snapshot === 'object', 'snapshot must be an object')
  assert(typeof snapshot.observed_at === 'string' && snapshot.observed_at.length > 0, 'observed_at required')

  const currentHead = snapshot.head_sha ?? null
  if (currentHead !== null) assert(COMMIT_RE.test(currentHead), 'invalid head_sha')
  const previousHead = snapshot.previous_head_sha ?? currentHead
  if (previousHead !== null) assert(COMMIT_RE.test(previousHead), 'invalid previous_head_sha')

  const evidence = (snapshot.evidence ?? [])
    .map(item => normalizeEvidence(item, currentHead))
    .sort((a, b) => a.evidence_id.localeCompare(b.evidence_id))

  const currentState = aggregateState(evidence)
  const previousState = snapshot.previous_epistemic_state ?? null
  const codeDrift = previousHead !== null && currentHead !== null && previousHead !== currentHead
  const stateDrift = previousState !== null && previousState !== currentState

  const triggerSet = new Set(evidence.flatMap(e => e.triggers))
  if (stateDrift) triggerSet.add('EPISTEMIC_STATE_DRIFT')
  if (stateDrift && !codeDrift) triggerSet.add('ZERO_CODE_DRIFT_EPISTEMIC_CHANGE')
  if (currentState !== 'CURRENT_REINSPECTABLE') triggerSet.add('CLAIM_AUTHORITY_CONTRACTION')

  const revalidation = revalidationPlan(currentState, evidence)
  if (revalidation.required) triggerSet.add('REVALIDATION_REQUIRED')
  triggerSet.add('AUTHORITY_NON_ESCALATION')
  triggerSet.add('LINEAGE_PRESERVATION')

  const body = {
    schema: SCHEMA,
    subject: snapshot.subject ?? null,
    observed_at: snapshot.observed_at,
    head_sha: currentHead,
    previous_head_sha: previousHead,
    code_drift: codeDrift,
    previous_epistemic_state: previousState,
    current_epistemic_state: currentState,
    epistemic_state_drift: stateDrift,
    evidence,
    triggers: [...triggerSet].sort(),
    claims: claimAuthority(currentState, evidence),
    revalidation,
    lineage: {
      prior_receipt_sha256: snapshot.prior_receipt_sha256 ?? null,
      replaces_prior_facts: false,
      preserves_historical_receipts: true,
    },
    authority_effect: 'NONE',
  }

  return { ...body, receipt_sha256: sha256(body) }
}

function main() {
  const [cmd, path] = process.argv.slice(2)
  if (cmd !== 'evaluate' || !path) {
    console.error('usage: evidence-state.mjs evaluate <snapshot.json>')
    process.exit(2)
  }
  try {
    const snapshot = JSON.parse(readFileSync(path, 'utf8'))
    const receipt = evaluateSnapshot(snapshot)
    process.stdout.write(JSON.stringify(receipt, null, 2) + '\n')
  } catch (err) {
    const fail = {
      schema: SCHEMA,
      outcome: 'DENIED',
      authority_effect: 'NONE',
      error: `${err?.name ?? 'Error'}: ${err?.message ?? String(err)}`,
    }
    fail.receipt_sha256 = sha256(fail)
    process.stdout.write(JSON.stringify(fail, null, 2) + '\n')
    process.exit(1)
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])) main()
