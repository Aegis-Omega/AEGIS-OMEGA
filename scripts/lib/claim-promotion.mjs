import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'

const SHA256_RE = /^[0-9a-f]{64}$/
const SHA40_RE = /^[0-9a-f]{40}$/
const TRANSITION_STATUSES = new Set(['VERIFIED', 'OPEN', 'NOT_ESTABLISHED'])

function serialize(value, stack) {
  if (value === null) return 'null'
  if (value === true) return 'true'
  if (value === false) return 'false'

  const t = typeof value
  if (t === 'string') return JSON.stringify(value)
  if (t === 'number') {
    if (!Number.isFinite(value)) throw new TypeError('non-finite number is not RFC8785 JSON')
    return Object.is(value, -0) ? '0' : JSON.stringify(value)
  }
  if (t === 'undefined') throw new TypeError('undefined is not RFC8785 JSON')
  if (t === 'bigint') throw new TypeError('bigint is not RFC8785 JSON')
  if (t === 'function' || t === 'symbol') throw new TypeError(`${t} is not RFC8785 JSON`)

  if (stack.has(value)) throw new TypeError('cyclic value is not JSON')
  stack.add(value)
  try {
    if (Array.isArray(value)) {
      const items = []
      for (let i = 0; i < value.length; i += 1) {
        if (!(i in value) || value[i] === undefined) {
          throw new TypeError('undefined/sparse array item is not RFC8785 JSON')
        }
        items.push(serialize(value[i], stack))
      }
      return `[${items.join(',')}]`
    }
    if (t === 'object') {
      const keys = Object.keys(value).sort()
      const pairs = []
      for (const key of keys) {
        if (value[key] === undefined) throw new TypeError('undefined object field is not RFC8785 JSON')
        pairs.push(`${JSON.stringify(key)}:${serialize(value[key], stack)}`)
      }
      return `{${pairs.join(',')}}`
    }
  } finally {
    stack.delete(value)
  }
  throw new TypeError(`unsupported type ${t}`)
}

export function canonicalizeJCSStrict(value) {
  return serialize(value, new Set())
}

function sha256(data) {
  return crypto.createHash('sha256').update(data).digest('hex')
}

export function sha256JCS(value) {
  return sha256(Buffer.from(canonicalizeJCSStrict(value), 'utf8'))
}

function safeRepoPath(repoRoot, rel) {
  if (typeof rel !== 'string' || rel.length === 0 || path.isAbsolute(rel)) {
    throw new Error(`invalid repository path: ${String(rel)}`)
  }
  const root = path.resolve(repoRoot)
  const abs = path.resolve(root, rel)
  if (abs !== root && !abs.startsWith(`${root}${path.sep}`)) {
    throw new Error(`path escapes repository root: ${rel}`)
  }
  return abs
}

export function computeBundleDigest(repoRoot, paths) {
  if (!Array.isArray(paths) || paths.length === 0) throw new Error('bundle paths must be non-empty')
  const unique = new Set(paths)
  if (unique.size !== paths.length) throw new Error('bundle paths contain duplicates')
  const entries = [...paths].sort().map((rel) => {
    const abs = safeRepoPath(repoRoot, rel)
    const bytes = fs.readFileSync(abs)
    return { path: rel, sha256: sha256(bytes) }
  })
  return sha256JCS(entries)
}

function jsonFileDigest(repoRoot, rel) {
  const abs = safeRepoPath(repoRoot, rel)
  const value = JSON.parse(fs.readFileSync(abs, 'utf8'))
  return sha256JCS(value)
}

function defaultIsAncestor(repoRoot, source, current) {
  try {
    execFileSync('git', ['merge-base', '--is-ancestor', source, current], {
      cwd: repoRoot,
      stdio: 'ignore',
    })
    return true
  } catch {
    return false
  }
}

function requiredString(obj, key, errors) {
  if (typeof obj?.[key] !== 'string' || obj[key].length === 0) {
    errors.push(`MISSING_OR_INVALID_FIELD:${key}`)
    return false
  }
  return true
}

export function validatePromotionManifest({
  repoRoot,
  manifest,
  policy,
  currentHead,
  isAncestor = (source, current) => defaultIsAncestor(repoRoot, source, current),
}) {
  const errors = []
  const add = (e) => { if (!errors.includes(e)) errors.push(e) }

  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
    return { ok: false, decision: 'DENY', errors: ['MANIFEST_NOT_OBJECT'] }
  }

  for (const key of [
    'schema', 'claim_id', 'baseline_digest', 'source_head_sha', 'claim_statement',
    'claim_statement_digest', 'red_contract_digest', 'implementation_digest',
    'negative_control_receipt_digest', 'ci_run_identity', 'verification_receipt_digest',
    'admission_policy_digest', 'final_epistemic_status', 'admission_decision',
  ]) requiredString(manifest, key, errors)

  if (manifest.schema !== 'AEGIS_CLAIM_PROMOTION_V1') add('SCHEMA_VERSION_INVALID')
  if (!/^CLM-\d{3}$/.test(manifest.claim_id || '')) add('CLAIM_ID_INVALID')

  for (const key of [
    'baseline_digest', 'claim_statement_digest', 'red_contract_digest', 'implementation_digest',
    'negative_control_receipt_digest', 'verification_receipt_digest', 'admission_policy_digest',
  ]) {
    if (!SHA256_RE.test(manifest[key] || '')) add(`DIGEST_FORMAT_INVALID:${key}`)
  }

  if (manifest.baseline_digest !== policy?.baseline_digest) add('BASELINE_DIGEST_MISMATCH')

  try {
    const expected = sha256JCS({ claim_id: manifest.claim_id, claim_statement: manifest.claim_statement })
    if (expected !== manifest.claim_statement_digest) add('CLAIM_STATEMENT_DIGEST_MISMATCH')
  } catch {
    add('CLAIM_STATEMENT_DIGEST_MISMATCH')
  }

  const bindings = manifest.bindings
  if (!bindings || typeof bindings !== 'object' || Array.isArray(bindings)) {
    add('BINDINGS_MISSING')
  } else {
    try {
      if (computeBundleDigest(repoRoot, bindings.red_contract_paths) !== manifest.red_contract_digest) {
        add('RED_CONTRACT_DIGEST_MISMATCH')
      }
    } catch {
      add('RED_CONTRACT_DIGEST_MISMATCH')
    }
    try {
      if (computeBundleDigest(repoRoot, bindings.implementation_paths) !== manifest.implementation_digest) {
        add('IMPLEMENTATION_DIGEST_MISMATCH')
      }
    } catch {
      add('IMPLEMENTATION_DIGEST_MISMATCH')
    }
    try {
      if (jsonFileDigest(repoRoot, bindings.negative_control_receipt_path) !== manifest.negative_control_receipt_digest) {
        add('NEGATIVE_CONTROL_RECEIPT_DIGEST_MISMATCH')
      }
    } catch {
      add('NEGATIVE_CONTROL_RECEIPT_DIGEST_MISMATCH')
    }
    try {
      if (jsonFileDigest(repoRoot, bindings.verification_receipt_path) !== manifest.verification_receipt_digest) {
        add('VERIFICATION_RECEIPT_DIGEST_MISMATCH')
      }
    } catch {
      add('VERIFICATION_RECEIPT_DIGEST_MISMATCH')
    }
    try {
      const boundPolicyDigest = jsonFileDigest(repoRoot, bindings.admission_policy_path)
      if (boundPolicyDigest !== manifest.admission_policy_digest) add('POLICY_DIGEST_MISMATCH')
      if (sha256JCS(policy) !== boundPolicyDigest) add('POLICY_BINDING_MISMATCH')
    } catch {
      add('POLICY_DIGEST_MISMATCH')
    }
  }

  if (!SHA40_RE.test(manifest.source_head_sha || '')) {
    add('SOURCE_HEAD_INVALID')
  } else if (!SHA40_RE.test(currentHead || '')) {
    add('CURRENT_HEAD_INVALID')
  } else {
    let ancestor = false
    try { ancestor = Boolean(isAncestor(manifest.source_head_sha, currentHead)) } catch { ancestor = false }
    if (!ancestor) add('SOURCE_HEAD_NOT_ANCESTOR')
  }

  try {
    const ciRe = new RegExp(policy?.ci_run_identity_pattern || 'a^')
    if (!ciRe.test(manifest.ci_run_identity || '')) add('CI_RUN_IDENTITY_INVALID')
  } catch {
    add('CI_RUN_IDENTITY_INVALID')
  }

  const requiredIds = Array.isArray(policy?.required_transition_ids) ? policy.required_transition_ids : []
  const transitions = Array.isArray(manifest.required_transitions) ? manifest.required_transitions : []
  if (!Array.isArray(manifest.required_transitions)) add('REQUIRED_TRANSITIONS_MISSING')
  const seen = new Set()
  const byId = new Map()
  for (const t of transitions) {
    if (!t || typeof t.transition_id !== 'string') {
      add('TRANSITION_ID_INVALID')
      continue
    }
    if (seen.has(t.transition_id)) add(`DUPLICATE_TRANSITION:${t.transition_id}`)
    seen.add(t.transition_id)
    if (!requiredIds.includes(t.transition_id)) add(`UNKNOWN_TRANSITION:${t.transition_id}`)
    if (!TRANSITION_STATUSES.has(t.status)) add(`TRANSITION_STATUS_INVALID:${t.transition_id}`)
    byId.set(t.transition_id, t)
  }

  let hasUnverifiedRequired = false
  for (const id of requiredIds) {
    const t = byId.get(id)
    if (!t) {
      add(`MISSING_REQUIRED_TRANSITION:${id}`)
      hasUnverifiedRequired = true
      continue
    }
    if (t.status !== 'VERIFIED') {
      hasUnverifiedRequired = true
      if (t.status === 'OPEN') add(`OPEN_REQUIRED_TRANSITION:${id}`)
      else add(`UNVERIFIED_REQUIRED_TRANSITION:${id}`)
    }
  }

  const admittable = new Set(policy?.admittable_statuses || [])
  const deferred = new Set(policy?.deferred_statuses || [])
  if (!admittable.has(manifest.final_epistemic_status) && !deferred.has(manifest.final_epistemic_status)) {
    add('FINAL_EPISTEMIC_STATUS_INVALID')
  }

  if (deferred.has(manifest.final_epistemic_status) && manifest.admission_decision !== 'DEFER') {
    add('TARGET_STATUS_MUST_DEFER')
  }

  if (manifest.admission_decision === 'ADMIT') {
    if (!admittable.has(manifest.final_epistemic_status) || hasUnverifiedRequired) {
      add('AUTHORITY_LEAKAGE')
    }
  } else if (!['DEFER', 'DENY'].includes(manifest.admission_decision)) {
    add('ADMISSION_DECISION_INVALID')
  }

  return {
    ok: errors.length === 0,
    decision: errors.length === 0 ? manifest.admission_decision : 'DENY',
    errors,
  }
}

export function findVerifiedClaimMutations(baseClaims, currentClaims) {
  const base = new Map((baseClaims || []).filter(Boolean).map((c) => [c.id, c]))
  const required = []
  for (const current of currentClaims || []) {
    if (!current || current.tier !== 'Verified' || typeof current.id !== 'string') continue
    const previous = base.get(current.id)
    if (!previous || previous.tier !== 'Verified') {
      required.push(current.id)
      continue
    }
    if (canonicalizeJCSStrict(previous) !== canonicalizeJCSStrict(current)) required.push(current.id)
  }
  return required.sort()
}
