import assert from 'node:assert/strict'

import {
  DLSS5_EXECUTION_WITNESS_CONTRACT,
  verifyDlss5ExecutionWitness,
} from '../dist/dlss5-execution-witness.js'

const sha = 'a'.repeat(40)
const digestA = `sha256:${'1'.repeat(64)}`
const digestB = `sha256:${'2'.repeat(64)}`
const digestC = `sha256:${'3'.repeat(64)}`
const digestD = `sha256:${'4'.repeat(64)}`

const positive = {
  schema: 'AEGIS_DLSS5_EXECUTION_WITNESS_EVIDENCE_V1',
  candidate_sha: sha,
  acquisition_receipt_digest: digestA,
  probe_binary_digest: digestB,
  probe_observation_digest: digestC,
  captured_at: '2026-09-10T18:50:00.000Z',
  gpu: {
    vendor: 'NVIDIA',
    model: 'NVIDIA GeForce RTX 5090',
    driver_version: '580.00',
    pci_bus_id: '00000000:01:00.0',
  },
  streamline: {
    version: '2.14.1',
    plugin: 'sl.dlss_nr',
    plugin_digest: digestD,
  },
  execution: {
    feature_query: 'SUPPORTED',
    evaluation_executed: true,
    evaluation_status: 'SUCCESS',
    native_probe_exit_code: 0,
  },
}

assert.equal(DLSS5_EXECUTION_WITNESS_CONTRACT.schema, 'AEGIS_DLSS5_EXECUTION_WITNESS_CONTRACT_V1')
assert.equal(DLSS5_EXECUTION_WITNESS_CONTRACT.required_plugin, 'sl.dlss_nr')
assert.equal(DLSS5_EXECUTION_WITNESS_CONTRACT.minimum_streamline_version, '2.14.0')
assert.equal(DLSS5_EXECUTION_WITNESS_CONTRACT.rendering_claim_on_observation, 'NOT_ESTABLISHED')
assert.equal(DLSS5_EXECUTION_WITNESS_CONTRACT.quality_claim_on_observation, 'NOT_ESTABLISHED')
assert.equal(DLSS5_EXECUTION_WITNESS_CONTRACT.authority_effect, 'NONE')

const missing = verifyDlss5ExecutionWitness(undefined)
assert.equal(missing.status, 'EXECUTION_WITNESS_NOT_VERIFIED')
assert.deepEqual(missing.reason_codes, ['EXECUTION_WITNESS_EVIDENCE_MISSING'])
assert.equal(missing.runtime_execution, 'NOT_ESTABLISHED')
assert.equal(missing.execution_release, 'BLOCKED')
assert.equal(missing.authority_effect, 'NONE')

const unsupported = verifyDlss5ExecutionWitness({
  ...positive,
  gpu: { ...positive.gpu, model: 'NVIDIA GeForce RTX 4090' },
})
assert.equal(unsupported.status, 'EXECUTION_WITNESS_REJECTED')
assert(unsupported.reason_codes.includes('DLSS5_HARDWARE_UNSUPPORTED'))

const wrongPlugin = verifyDlss5ExecutionWitness({
  ...positive,
  streamline: { ...positive.streamline, plugin: 'sl.dlss_g' },
})
assert.equal(wrongPlugin.status, 'EXECUTION_WITNESS_REJECTED')
assert(wrongPlugin.reason_codes.includes('DLSS5_PLUGIN_MISMATCH'))

const noFeature = verifyDlss5ExecutionWitness({
  ...positive,
  execution: { ...positive.execution, feature_query: 'UNSUPPORTED' },
})
assert.equal(noFeature.status, 'EXECUTION_WITNESS_REJECTED')
assert(noFeature.reason_codes.includes('DLSS5_FEATURE_QUERY_NOT_SUPPORTED'))

const noEvaluation = verifyDlss5ExecutionWitness({
  ...positive,
  execution: { ...positive.execution, evaluation_executed: false },
})
assert.equal(noEvaluation.status, 'EXECUTION_WITNESS_REJECTED')
assert(noEvaluation.reason_codes.includes('RUNTIME_EVALUATION_NOT_EXECUTED'))

const failedEvaluation = verifyDlss5ExecutionWitness({
  ...positive,
  execution: { ...positive.execution, evaluation_status: 'FAILED' },
})
assert.equal(failedEvaluation.status, 'EXECUTION_WITNESS_REJECTED')
assert(failedEvaluation.reason_codes.includes('RUNTIME_EVALUATION_NOT_SUCCESSFUL'))

const nonZero = verifyDlss5ExecutionWitness({
  ...positive,
  execution: { ...positive.execution, native_probe_exit_code: 7 },
})
assert.equal(nonZero.status, 'EXECUTION_WITNESS_REJECTED')
assert(nonZero.reason_codes.includes('NATIVE_PROBE_EXIT_NONZERO'))

const observed = verifyDlss5ExecutionWitness(positive)
assert.equal(observed.status, 'EXECUTION_WITNESS_OBSERVED')
assert.equal(observed.runtime_execution, 'OBSERVED_FOR_DECLARED_PROBE_ONLY')
assert.equal(observed.execution_release, 'BLOCKED_PENDING_INDEPENDENT_REPLAY')
assert.equal(observed.rendering_claim, 'NOT_ESTABLISHED')
assert.equal(observed.quality_claim, 'NOT_ESTABLISHED')
assert.equal(observed.claim_promotion, 'BLOCKED')
assert.equal(observed.authority_effect, 'NONE')
assert.match(observed.witness_receipt_digest, /^sha256:[0-9a-f]{64}$/)
assert.equal(observed.acquisition_receipt_digest, digestA)
assert.equal(observed.probe_observation_digest, digestC)

const replay = verifyDlss5ExecutionWitness(structuredClone(positive))
assert.equal(replay.witness_receipt_digest, observed.witness_receipt_digest)

console.log('DLSS5_EXECUTION_WITNESS_PASS contract=1 missing=1 rejection=6 observed=1 deterministic=2 rendering_claim=NOT_ESTABLISHED authority=NONE')
