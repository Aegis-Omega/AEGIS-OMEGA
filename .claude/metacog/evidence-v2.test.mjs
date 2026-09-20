import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { evaluateSnapshot } from './evidence-state.mjs'
import { verifyReceipt, certifyLedger, readLedger } from './evidence-ledger.mjs'
import { runEvidenceCycle } from './evidence-cycle.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const CHAIN = resolve(HERE, 'chain.mjs')
const HEAD = 'c01de9f663c43ca2e23cf953b163cd399906ff49'
const DIGEST = 'sha256:5b3dac100c0ac3ed70ae33b7af4820f28e079c0f119bac8e5aa3551b7b638ae9'

function expiredSnapshot() {
  return {
    schema: 'aegis.metacognitive-evidence-snapshot.v1',
    subject: { repository: 'Aegis-Omega/AEGIS-OMEGA', kind: 'pull_request', id: 356 },
    observed_at: '2026-09-20T05:46:00Z',
    head_sha: HEAD,
    previous_head_sha: HEAD,
    previous_epistemic_state: 'CURRENT_REINSPECTABLE',
    prior_receipt_sha256: null,
    evidence: [{
      evidence_id: 'github-actions:osv:run-34462602971:artifact-10146189388',
      kind: 'OSV_SARIF',
      load_bearing: true,
      conclusion: 'SUCCESS',
      bound_head_sha: HEAD,
      artifact: {
        id: '10146189388',
        digest: DIGEST,
        available: false,
        expired: true,
        http_status: 410,
        expires_at: '2026-09-15T09:48:44Z',
      },
    }],
  }
}

function refreshedSnapshot() {
  return {
    schema: 'aegis.metacognitive-evidence-snapshot.v1',
    subject: { repository: 'Aegis-Omega/AEGIS-OMEGA', kind: 'pull_request', id: 356 },
    observed_at: '2026-09-20T06:30:00Z',
    head_sha: HEAD,
    evidence: [{
      evidence_id: 'github-actions:osv:synthetic-refresh',
      kind: 'OSV_SARIF',
      load_bearing: true,
      conclusion: 'SUCCESS',
      bound_head_sha: HEAD,
      artifact: {
        id: 'synthetic-refresh',
        digest: 'sha256:' + 'a'.repeat(64),
        available: true,
        expired: false,
        http_status: 200,
      },
    }],
  }
}

function runtime() {
  const dir = mkdtempSync(join(tmpdir(), 'aegis-metacog-evidence-'))
  mkdirSync(join(dir, '.claude/metacog'), { recursive: true })
  return {
    dir,
    snapshot: join(dir, 'snapshot.json'),
    receipt: join(dir, '.claude/metacog/evidence-receipt.tmp'),
    ledger: join(dir, '.claude/metacog/evidence-transitions.log'),
    chain: join(dir, '.claude/metacog/chain.jsonl'),
    env: { ...process.env, CLAUDE_PROJECT_DIR: dir, AEGIS_METACOG_CHAIN: join(dir, '.claude/metacog/chain.jsonl') },
  }
}

function cycle(snapshot, rt) {
  writeFileSync(rt.snapshot, JSON.stringify(snapshot))
  return runEvidenceCycle({
    snapshotPath: rt.snapshot,
    receiptPath: rt.receipt,
    ledgerPath: rt.ledger,
    chainPath: CHAIN,
    env: rt.env,
  })
}

test('PR #356 decay is a zero-code-drift epistemic transition with no authority effect', () => {
  const r = evaluateSnapshot(expiredSnapshot())
  assert.equal(r.receipt_sha256, '097f3e81f6e5a59dd6d736cb3874b80da95e827257702edb0a85049ff0e5d397')
  assert.equal(r.current_epistemic_state, 'HISTORICAL_NOT_REINSPECTABLE')
  assert.equal(r.code_drift, false)
  assert.ok(r.triggers.includes('EVIDENCE_DECAY'))
  assert.ok(r.triggers.includes('ZERO_CODE_DRIFT_EPISTIC_CHANGE') === false)
  assert.ok(r.triggers.includes('ZERO_CODE_DRIFT_EPISTEMIC_CHANGE'))
  assert.equal(r.revalidation.scope, 'CONTENT_ARTIFACT_REFRESH_SAME_HEAD')
  assert.equal(r.authority_effect, 'NONE')
})

test('digest metadata never substitutes for missing artifact bytes', () => {
  const r = evaluateSnapshot(expiredSnapshot())
  assert.equal(r.evidence[0].artifact.digest_format_valid, true)
  assert.equal(r.claims.current_content_reinspection, 'DENY')
  assert.equal(r.claims.independent_content_revalidation, 'DENY')
})

test('cycle binds full receipt and transition hashes into real live chain.mjs', () => {
  const rt = runtime()
  const r = cycle(expiredSnapshot(), rt)
  assert.equal(r.chain.certified.is_valid, true)
  const entry = JSON.parse(readFileSync(rt.chain, 'utf8').trim())
  assert.equal(entry.observation.layer, 'METACOGNITIVE')
  assert.ok(entry.observation.signal.includes(`receipt=${r.receipt_sha256}`))
  assert.ok(entry.observation.signal.includes(`transition=${r.ledger.transition_hash}`))
  assert.ok(entry.observation.signal.includes('authority=NONE'))
})

test('exact replay is idempotent', () => {
  const rt = runtime()
  const a = cycle(expiredSnapshot(), rt)
  const b = cycle(expiredSnapshot(), rt)
  assert.equal(a.receipt_sha256, b.receipt_sha256)
  assert.equal(b.ledger.duplicate, true)
  assert.equal(readLedger(rt.ledger).length, 1)
  assert.equal(readFileSync(rt.chain, 'utf8').trim().split('\n').length, 1)
})

test('same-head refreshed bytes recover reinspectability with prior lineage auto-bound', () => {
  const rt = runtime()
  const a = cycle(expiredSnapshot(), rt)
  const b = cycle(refreshedSnapshot(), rt)
  assert.equal(b.current_epistemic_state, 'CURRENT_REINSPECTABLE')
  assert.equal(b.revalidation_scope, 'NONE')
  const receipt = JSON.parse(readFileSync(rt.receipt, 'utf8'))
  assert.equal(receipt.lineage.prior_receipt_sha256, a.receipt_sha256)
  assert.equal(receipt.previous_epistemic_state, 'HISTORICAL_NOT_REINSPECTABLE')
  assert.equal(receipt.previous_head_sha, HEAD)
  assert.equal(certifyLedger(readLedger(rt.ledger)).is_valid, true)
})

test('explicit lineage mismatch fails closed before append', () => {
  const rt = runtime()
  cycle(expiredSnapshot(), rt)
  const next = refreshedSnapshot()
  next.prior_receipt_sha256 = 'b'.repeat(64)
  assert.throws(() => cycle(next, rt), /snapshot prior receipt mismatch/)
  assert.equal(readLedger(rt.ledger).length, 1)
})

test('tampering a receipt is detected before ledger admission', () => {
  const r = evaluateSnapshot(expiredSnapshot())
  r.current_epistemic_state = 'CURRENT_REINSPECTABLE'
  assert.throws(() => verifyReceipt(r), /receipt hash mismatch/)
})
