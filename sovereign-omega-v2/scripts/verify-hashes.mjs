#!/usr/bin/env node
// ============================================================
// SOVEREIGN OMEGA — Frozen File Hash Verification
// Run before any session that touches constitutional files.
//
// Exit codes:
//   0 — all files present and hash-correct
//   1 — at least one file present but hash WRONG (constitutional violation)
//   2 — at least one file absent (not yet authored; /guardian decision pending)
//       A missing constitutional file is NOT the same as a passing check.
// ============================================================

import { createHash } from 'crypto'
import { readFileSync, existsSync } from 'fs'

const FROZEN_FILES = {
  'python/gate.py':   'bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc',
  'python/dna.py':    'cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8',
  'python/router.py': '8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941',
}

let hashFailed = false
let filesMissing = false

for (const [file, expectedHash] of Object.entries(FROZEN_FILES)) {
  if (!existsSync(file)) {
    console.warn(`  WARN: ${file} — file not present; constitutional check INCOMPLETE`)
    filesMissing = true
    continue
  }
  const content = readFileSync(file)
  const actualHash = createHash('sha256').update(content).digest('hex')
  if (actualHash === expectedHash) {
    console.log(`  OK:   ${file}`)
  } else {
    console.error(`  FAIL: ${file}`)
    console.error(`        Expected: ${expectedHash}`)
    console.error(`        Got:      ${actualHash}`)
    hashFailed = true
  }
}

if (hashFailed) {
  console.error('\n[FROZEN FILE VIOLATION] One or more constitutional files have been modified.')
  console.error('Requires /guardian APPROVED verdict before proceeding.')
  process.exit(1)
}

if (filesMissing) {
  console.warn('\n[CONSTITUTIONAL FILES ABSENT] gate.py / dna.py / router.py do not exist.')
  console.warn('Integrity check is INCOMPLETE — not a pass.')
  console.warn('Operator must decide: migrate from sovereign-omega/ or author new implementations.')
  console.warn('Creation requires /guardian APPROVED verdict.')
  process.exit(2)
}

console.log('\nAll frozen files present and hash-verified.')

