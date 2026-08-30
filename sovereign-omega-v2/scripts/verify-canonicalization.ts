#!/usr/bin/env node
// ============================================================
// SOVEREIGN OMEGA — Cross-Engine Canonicalization Verification
// Run before deployment to confirm RFC 8785 parity.
// This script is the Gate 1 deployment prerequisite.
// ============================================================

import { verifyRFC8785Conformance, canonicalizeJCSString } from '../src/core/canonicalize.js'
import { sha256Hex } from '../src/core/hashing.js'

async function main() {
  console.log('=== SOVEREIGN OMEGA: Canonicalization Verification ===\n')

  // Gate 1: RFC 8785 test vector conformance
  const { passed, failed } = verifyRFC8785Conformance()
  console.log(`RFC 8785 Test Vectors: ${passed} passed, ${failed.length} failed`)

  if (failed.length > 0) {
    console.error('\nFAILED VECTORS:')
    for (const f of failed) {
      console.error(`  Index ${f.index}: expected ${f.expected}, got ${f.got}`)
    }
    console.error('\n[GATE 1 FAILED] — Do not proceed to deployment.')
    process.exit(1)
  }

  // Hash stability check: same input must always produce same SHA-256
  const testPayload = {
    event_type: 'SYSTEM_OUTPUT',
    payload: { score: 75, strengths: ['a', 'b', 'c'] },
    timestamp_ms: 1_600_000_000_000,
  }

  const canonical1 = new TextEncoder().encode(canonicalizeJCSString(testPayload))
  const canonical2 = new TextEncoder().encode(canonicalizeJCSString(testPayload))

  const hash1 = await sha256Hex(canonical1)
  const hash2 = await sha256Hex(canonical2)

  if (hash1 !== hash2) {
    console.error('[GATE 1 FAILED] Hash instability detected.')
    process.exit(1)
  }

  console.log(`Hash Stability: OK (${hash1.slice(0, 16)}...)`)
  console.log('\n[GATE 1 PASSED] RFC 8785 conformance verified.\n')
}

main().catch(err => {
  console.error('Verification error:', err)
  process.exit(1)
})
