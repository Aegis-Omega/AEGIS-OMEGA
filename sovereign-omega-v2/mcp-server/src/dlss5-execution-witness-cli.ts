#!/usr/bin/env node
import { readFileSync } from 'node:fs'

import { verifyDlss5ExecutionWitness } from './dlss5-execution-witness.js'

function notVerified(reason: string) {
  return {
    status: 'EXECUTION_WITNESS_NOT_VERIFIED',
    execution_release: 'BLOCKED',
    runtime_execution: 'NOT_ESTABLISHED',
    rendering_claim: 'NOT_ESTABLISHED',
    quality_claim: 'NOT_ESTABLISHED',
    claim_promotion: 'BLOCKED',
    authority_effect: 'NONE',
    reason_codes: [reason],
  }
}

const path = process.env['AEGIS_DLSS5_EXECUTION_WITNESS_PATH'] ?? ''
if (!path) {
  console.log(JSON.stringify(notVerified('EXECUTION_WITNESS_FILE_MISSING'), null, 2))
  process.exitCode = 2
} else {
  let raw: string
  try {
    raw = readFileSync(path, 'utf8')
  } catch {
    console.log(JSON.stringify(notVerified('EXECUTION_WITNESS_FILE_UNAVAILABLE'), null, 2))
    process.exitCode = 2
    raw = ''
  }

  if (raw) {
    let evidence: unknown
    try {
      evidence = JSON.parse(raw)
    } catch {
      console.log(JSON.stringify(notVerified('EXECUTION_WITNESS_JSON_INVALID'), null, 2))
      process.exitCode = 2
      evidence = undefined
    }

    if (evidence !== undefined) {
      const result = verifyDlss5ExecutionWitness(evidence)
      console.log(JSON.stringify(result, null, 2))
      process.exitCode = result.status === 'EXECUTION_WITNESS_OBSERVED' ? 0 : 2
    }
  }
}
