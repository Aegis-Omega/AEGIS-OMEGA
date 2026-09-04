#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

import {
  findVerifiedClaimMutations,
  validatePromotionManifest,
} from './lib/claim-promotion.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..')
const CLAIMS_PATH = path.join(REPO_ROOT, 'docs', 'claims.json')
const BASELINE_PATH = path.join(REPO_ROOT, 'docs', 'research-control-baseline.v0.4.json')
const POLICY_PATH = path.join(REPO_ROOT, 'docs', 'claim-admission-policy.v1.json')
const PROMOTION_DIR = path.join(REPO_ROOT, 'docs', 'claim-promotions')

function fail(message) {
  console.error(`FAIL_CLOSED: ${message}`)
  process.exit(1)
}

function readJson(abs) {
  try {
    return JSON.parse(fs.readFileSync(abs, 'utf8'))
  } catch (error) {
    fail(`cannot read/parse ${path.relative(REPO_ROOT, abs)}: ${error.message}`)
  }
}

function claimsFrom(doc, label) {
  const claims = Array.isArray(doc) ? doc : doc?.claims
  if (!Array.isArray(claims)) fail(`${label}: missing claims array`)
  return claims
}

function git(args) {
  return execFileSync('git', args, { cwd: REPO_ROOT, encoding: 'utf8' }).trim()
}

function parseArgs(argv) {
  const out = { baseSha: null }
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--base-sha') {
      out.baseSha = argv[i + 1] || null
      i += 1
    } else {
      fail(`unknown argument: ${argv[i]}`)
    }
  }
  return out
}

function loadBaseClaims(baseSha) {
  if (!/^[0-9a-f]{40}$/.test(baseSha || '')) fail('base SHA must be full 40-hex')
  try {
    const raw = git(['show', `${baseSha}:docs/claims.json`])
    return claimsFrom(JSON.parse(raw), `base ${baseSha}`)
  } catch (error) {
    fail(`cannot resolve base claims at ${baseSha}: ${error.message}`)
  }
}

function loadPromotionManifests() {
  if (!fs.existsSync(PROMOTION_DIR)) return []
  const files = fs.readdirSync(PROMOTION_DIR)
    .filter((name) => name.endsWith('.json'))
    .sort()
  return files.map((name) => {
    const abs = path.join(PROMOTION_DIR, name)
    return { name, manifest: readJson(abs) }
  })
}

function main() {
  const { baseSha } = parseArgs(process.argv.slice(2))
  const baseline = readJson(BASELINE_PATH)
  const policy = readJson(POLICY_PATH)
  const currentClaims = claimsFrom(readJson(CLAIMS_PATH), 'HEAD docs/claims.json')
  const currentHead = git(['rev-parse', 'HEAD'])

  const errors = []
  const add = (message) => { if (!errors.includes(message)) errors.push(message) }

  if (baseline?.baseline_digest_sha256 !== policy?.baseline_digest) {
    add('BASELINE_POLICY_DIGEST_MISMATCH')
  }
  if (baseline?.status !== 'VERIFIED_RESEARCH_CONTROL_BASELINE') {
    add('BASELINE_STATUS_INVALID')
  }

  const currentById = new Map(currentClaims.filter(Boolean).map((claim) => [claim.id, claim]))
  const manifestEntries = loadPromotionManifests()
  const manifestsByClaim = new Map()
  const validationByClaim = new Map()

  for (const { name, manifest } of manifestEntries) {
    if (!manifest || typeof manifest.claim_id !== 'string') {
      add(`MANIFEST_CLAIM_ID_INVALID:${name}`)
      continue
    }
    if (manifestsByClaim.has(manifest.claim_id)) {
      add(`DUPLICATE_PROMOTION_MANIFEST:${manifest.claim_id}`)
      continue
    }
    manifestsByClaim.set(manifest.claim_id, manifest)

    const claim = currentById.get(manifest.claim_id)
    if (!claim) {
      add(`PROMOTION_CLAIM_NOT_IN_LEDGER:${manifest.claim_id}`)
      continue
    }
    if (manifest.claim_statement !== claim.claim) {
      add(`CLAIM_STATEMENT_BINDING_MISMATCH:${manifest.claim_id}`)
    }

    const result = validatePromotionManifest({
      repoRoot: REPO_ROOT,
      manifest,
      policy,
      currentHead,
    })
    validationByClaim.set(manifest.claim_id, result)
    for (const error of result.errors) add(`${manifest.claim_id}:${error}`)
  }

  let requiredPromotions = []
  if (baseSha) {
    const baseClaims = loadBaseClaims(baseSha)
    requiredPromotions = findVerifiedClaimMutations(baseClaims, currentClaims)
    for (const claimId of requiredPromotions) {
      const manifest = manifestsByClaim.get(claimId)
      if (!manifest) {
        add(`MISSING_PROMOTION_MANIFEST:${claimId}`)
        continue
      }
      const result = validationByClaim.get(claimId)
      if (!result?.ok || result.decision !== 'ADMIT') {
        add(`VERIFIED_LEDGER_REQUIRES_ADMIT:${claimId}`)
      }
      if (!policy.admittable_statuses.includes(manifest.final_epistemic_status)) {
        add(`VERIFIED_LEDGER_STATUS_NOT_ADMITTABLE:${claimId}`)
      }
    }
  }

  const admitted = [...validationByClaim.entries()]
    .filter(([, result]) => result.ok && result.decision === 'ADMIT')
    .map(([claimId]) => claimId)
    .sort()
  const deferred = [...validationByClaim.entries()]
    .filter(([, result]) => result.ok && result.decision === 'DEFER')
    .map(([claimId]) => claimId)
    .sort()

  console.log('================ CLAIM PROMOTION ADMISSION ================')
  console.log(`Baseline:            ${policy.baseline_digest}`)
  console.log(`Current HEAD:        ${currentHead}`)
  console.log(`PR base:             ${baseSha || 'NONE'}`)
  console.log(`Required promotions: ${requiredPromotions.length ? requiredPromotions.join(', ') : 'NONE'}`)
  console.log(`Admitted manifests:  ${admitted.length ? admitted.join(', ') : 'NONE'}`)
  console.log(`Deferred manifests:  ${deferred.length ? deferred.join(', ') : 'NONE'}`)

  if (errors.length) {
    console.error('\nCLAIM PROMOTION VALIDATION FAILED:')
    for (const error of errors) console.error(`  x ${error}`)
    console.error(`\n${errors.length} hard error(s).`)
    process.exit(1)
  }

  console.log('\nOK — claim promotion boundary is fail-closed and satisfied for this diff.')
}

main()
