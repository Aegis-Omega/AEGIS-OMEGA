import test from 'node:test'
import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  canonicalizeJCSStrict,
  computeBundleDigest,
  findVerifiedClaimMutations,
  sha256JCS,
  validatePromotionManifest,
} from '../scripts/lib/claim-promotion.mjs'

const BASELINE = '457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404'
const SOURCE_HEAD = 'a'.repeat(40)
const CURRENT_HEAD = 'b'.repeat(40)

function sha256Bytes(data) {
  return crypto.createHash('sha256').update(data).digest('hex')
}

// Independent test-side canonicalizer for ASCII-domain fixtures.
function fixtureJCS(value) {
  if (value === null) return 'null'
  if (value === true) return 'true'
  if (value === false) return 'false'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new TypeError('non-finite')
    return Object.is(value, -0) ? '0' : JSON.stringify(value)
  }
  if (typeof value === 'string') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(fixtureJCS).join(',')}]`
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort()
    return `{${keys.map((k) => `${JSON.stringify(k)}:${fixtureJCS(value[k])}`).join(',')}}`
  }
  throw new TypeError(`unsupported ${typeof value}`)
}

function fixtureSha256JCS(value) {
  return sha256Bytes(Buffer.from(fixtureJCS(value), 'utf8'))
}

function fixtureBundleDigest(root, paths) {
  const entries = [...paths].sort().map((rel) => ({
    path: rel,
    sha256: sha256Bytes(fs.readFileSync(path.join(root, rel))),
  }))
  return fixtureSha256JCS(entries)
}

function writeJson(root, rel, value) {
  const abs = path.join(root, rel)
  fs.mkdirSync(path.dirname(abs), { recursive: true })
  fs.writeFileSync(abs, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

function makeFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'aegis-claim-promotion-'))
  fs.mkdirSync(path.join(root, 'test/contracts'), { recursive: true })
  fs.mkdirSync(path.join(root, 'src/feature'), { recursive: true })
  fs.mkdirSync(path.join(root, 'receipts'), { recursive: true })
  fs.mkdirSync(path.join(root, 'docs'), { recursive: true })

  writeJson(root, 'test/contracts/CLM-999.red.json', {
    schema: 'AEGIS_RED_CONTRACT_V1',
    claim_id: 'CLM-999',
    falsifiers: ['OPEN_DEPENDENCY', 'DIGEST_MISMATCH'],
  })
  fs.writeFileSync(path.join(root, 'src/feature/claim.ts'), 'export const claim = 1\n', 'utf8')
  writeJson(root, 'receipts/CLM-999.negative.json', {
    schema: 'AEGIS_NEGATIVE_CONTROL_RECEIPT_V1', status: 'PASS', controls: 2,
  })
  writeJson(root, 'receipts/CLM-999.verification.json', {
    schema: 'AEGIS_VERIFICATION_RECEIPT_V1', status: 'PASS', tests: 12,
  })

  const policy = {
    schema: 'AEGIS_CLAIM_ADMISSION_POLICY_V1',
    baseline_digest: BASELINE,
    required_transition_ids: [
      'RED_CONTRACT', 'IMPLEMENTATION', 'NEGATIVE_CONTROLS', 'EXACT_HEAD_CI', 'ATTESTED_RECEIPT',
    ],
    admittable_statuses: ['MACHINE_BOUND', 'EMPIRICAL', 'EXTERNAL_ESTABLISHED'],
    deferred_statuses: ['TARGET_OPEN', 'NOT_ESTABLISHED'],
    ci_run_identity_pattern: '^https://github\\.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/[0-9]+$',
  }
  writeJson(root, 'docs/claim-admission-policy.v1.json', policy)

  const statement = 'Claim promotion gate denies authority when any required transition is open.'
  const manifest = {
    schema: 'AEGIS_CLAIM_PROMOTION_V1',
    claim_id: 'CLM-999',
    baseline_digest: BASELINE,
    source_head_sha: SOURCE_HEAD,
    claim_statement: statement,
    claim_statement_digest: fixtureSha256JCS({ claim_id: 'CLM-999', claim_statement: statement }),
    red_contract_digest: fixtureBundleDigest(root, ['test/contracts/CLM-999.red.json']),
    implementation_digest: fixtureBundleDigest(root, ['src/feature/claim.ts']),
    negative_control_receipt_digest: fixtureSha256JCS(JSON.parse(fs.readFileSync(path.join(root, 'receipts/CLM-999.negative.json'), 'utf8'))),
    ci_run_identity: 'https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/123456789',
    verification_receipt_digest: fixtureSha256JCS(JSON.parse(fs.readFileSync(path.join(root, 'receipts/CLM-999.verification.json'), 'utf8'))),
    admission_policy_digest: fixtureSha256JCS(policy),
    final_epistemic_status: 'MACHINE_BOUND',
    admission_decision: 'ADMIT',
    bindings: {
      red_contract_paths: ['test/contracts/CLM-999.red.json'],
      implementation_paths: ['src/feature/claim.ts'],
      negative_control_receipt_path: 'receipts/CLM-999.negative.json',
      verification_receipt_path: 'receipts/CLM-999.verification.json',
      admission_policy_path: 'docs/claim-admission-policy.v1.json',
    },
    required_transitions: [
      { transition_id: 'RED_CONTRACT', status: 'VERIFIED' },
      { transition_id: 'IMPLEMENTATION', status: 'VERIFIED' },
      { transition_id: 'NEGATIVE_CONTROLS', status: 'VERIFIED' },
      { transition_id: 'EXACT_HEAD_CI', status: 'VERIFIED' },
      { transition_id: 'ATTESTED_RECEIPT', status: 'VERIFIED' },
    ],
  }
  return { root, policy, manifest }
}

test('RFC8785 key ordering uses UTF-16 code units, not Unicode code points', () => {
  const value = { '\uE000': 2, '😀': 1 }
  assert.equal(canonicalizeJCSStrict(value), '{"😀":1,"":2}')
})

test('strict JCS rejects bigint and undefined object fields', () => {
  assert.throws(() => canonicalizeJCSStrict({ value: 1n }), /bigint|unsupported/i)
  assert.throws(() => canonicalizeJCSStrict({ kept: 1, dropped: undefined }), /undefined/i)
})

test('digest helpers match independent fixture implementation', () => {
  const { root } = makeFixture()
  assert.equal(sha256JCS({ b: 2, a: 1 }), fixtureSha256JCS({ b: 2, a: 1 }))
  assert.equal(
    computeBundleDigest(root, ['src/feature/claim.ts', 'test/contracts/CLM-999.red.json']),
    fixtureBundleDigest(root, ['src/feature/claim.ts', 'test/contracts/CLM-999.red.json']),
  )
})

test('fully bound verified tuple admits', () => {
  const { root, policy, manifest } = makeFixture()
  const result = validatePromotionManifest({
    repoRoot: root,
    manifest,
    policy,
    currentHead: CURRENT_HEAD,
    isAncestor: () => true,
  })
  assert.equal(result.ok, true)
  assert.equal(result.decision, 'ADMIT')
  assert.deepEqual(result.errors, [])
})

test('OPEN required transition blocks MACHINE_BOUND admission', () => {
  const { root, policy, manifest } = makeFixture()
  manifest.required_transitions[2].status = 'OPEN'
  const result = validatePromotionManifest({ repoRoot: root, manifest, policy, currentHead: CURRENT_HEAD, isAncestor: () => true })
  assert.equal(result.ok, false)
  assert.ok(result.errors.includes('OPEN_REQUIRED_TRANSITION:NEGATIVE_CONTROLS'))
  assert.ok(result.errors.includes('AUTHORITY_LEAKAGE'))
})

test('baseline mismatch fails closed', () => {
  const { root, policy, manifest } = makeFixture()
  manifest.baseline_digest = '0'.repeat(64)
  const result = validatePromotionManifest({ repoRoot: root, manifest, policy, currentHead: CURRENT_HEAD, isAncestor: () => true })
  assert.equal(result.ok, false)
  assert.ok(result.errors.includes('BASELINE_DIGEST_MISMATCH'))
})

test('bound implementation mutation is detected as digest mismatch', () => {
  const { root, policy, manifest } = makeFixture()
  fs.appendFileSync(path.join(root, 'src/feature/claim.ts'), 'export const substituted = true\n')
  const result = validatePromotionManifest({ repoRoot: root, manifest, policy, currentHead: CURRENT_HEAD, isAncestor: () => true })
  assert.equal(result.ok, false)
  assert.ok(result.errors.includes('IMPLEMENTATION_DIGEST_MISMATCH'))
})

test('non-ancestor source head fails closed', () => {
  const { root, policy, manifest } = makeFixture()
  const result = validatePromotionManifest({ repoRoot: root, manifest, policy, currentHead: CURRENT_HEAD, isAncestor: () => false })
  assert.equal(result.ok, false)
  assert.ok(result.errors.includes('SOURCE_HEAD_NOT_ANCESTOR'))
})

test('TARGET_OPEN cannot issue ADMIT', () => {
  const { root, policy, manifest } = makeFixture()
  manifest.final_epistemic_status = 'TARGET_OPEN'
  const result = validatePromotionManifest({ repoRoot: root, manifest, policy, currentHead: CURRENT_HEAD, isAncestor: () => true })
  assert.equal(result.ok, false)
  assert.ok(result.errors.includes('TARGET_STATUS_MUST_DEFER'))
})

test('new Verified claim requires promotion manifest', () => {
  const base = [{ id: 'CLM-001', claim: 'A', tier: 'Proposed' }]
  const current = [{ id: 'CLM-001', claim: 'A', tier: 'Proposed' }, { id: 'CLM-999', claim: 'B', tier: 'Verified' }]
  assert.deepEqual(findVerifiedClaimMutations(base, current), ['CLM-999'])
})

test('tier promotion and material mutation of Verified claim require promotion', () => {
  const base = [
    { id: 'CLM-001', claim: 'A', tier: 'Proposed', evidence: [] },
    { id: 'CLM-002', claim: 'B', tier: 'Verified', evidence: ['Code: a.ts'] },
  ]
  const current = [
    { id: 'CLM-001', claim: 'A', tier: 'Verified', evidence: ['Code: b.ts'] },
    { id: 'CLM-002', claim: 'B changed', tier: 'Verified', evidence: ['Code: a.ts'] },
  ]
  assert.deepEqual(findVerifiedClaimMutations(base, current), ['CLM-001', 'CLM-002'])
})

test('unchanged Verified claim needs no new promotion', () => {
  const claim = { id: 'CLM-002', claim: 'B', tier: 'Verified', evidence: ['Code: a.ts'] }
  assert.deepEqual(findVerifiedClaimMutations([claim], [structuredClone(claim)]), [])
})
