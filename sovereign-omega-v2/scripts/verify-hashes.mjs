#!/usr/bin/env node
// ============================================================
// SOVEREIGN OMEGA — Frozen File Hash Verification
// CWD-independent: resolves constitutional files relative to this script.
//
// Exit codes:
//   0 — all files present and hash-correct
//   1 — at least one file present but hash WRONG
//   2 — at least one required file absent
// ============================================================

import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const RUNTIME_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const FROZEN_FILES = {
  'python/gate.py':   'bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc',
  'python/dna.py':    'cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8',
  'python/router.py': '8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941',
}

let hashFailed = false
let filesMissing = false

for (const [relativePath, expectedHash] of Object.entries(FROZEN_FILES)) {
  const absolutePath = resolve(RUNTIME_ROOT, relativePath)

  if (!existsSync(absolutePath)) {
    console.error(`  MISSING: ${relativePath}`)
    filesMissing = true
    continue
  }

  const actualHash = createHash('sha256')
    .update(readFileSync(absolutePath))
    .digest('hex')

  if (actualHash === expectedHash) {
    console.log(`  OK:      ${relativePath}`)
  } else {
    console.error(`  FAIL:    ${relativePath}`)
    console.error(`           Expected: ${expectedHash}`)
    console.error(`           Got:      ${actualHash}`)
    hashFailed = true
  }
}

if (hashFailed) {
  console.error('\n[FROZEN FILE VIOLATION] Constitutional bytes differ from the approved hashes.')
  console.error('A new hash may be admitted only through an explicit, evidence-bound constitutional change.')
  process.exit(1)
}

if (filesMissing) {
  console.error('\n[CONSTITUTIONAL FILES MISSING] Integrity verification is incomplete and fails closed.')
  process.exit(2)
}

console.log(`\nAll frozen files present and hash-verified under ${RUNTIME_ROOT}.`)
