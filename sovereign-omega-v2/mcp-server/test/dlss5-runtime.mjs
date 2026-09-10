import assert from 'node:assert/strict'

import { DLSS5_RUNTIME_CONTRACT, verifyDlss5RuntimeProbe } from '../dist/dlss5-runtime.js'

const sha = (char) => `sha256:${char.repeat(64)}`
const candidate = '7b585aad402488835896d9c2b11b158774e600f1'

assert.equal(DLSS5_RUNTIME_CONTRACT.required_plugin, 'sl.dlss_nr')
assert.equal(DLSS5_RUNTIME_CONTRACT.minimum_streamline_version, '2.14.0')
assert.equal(DLSS5_RUNTIME_CONTRACT.rendering_claim_on_observation, 'NOT_ESTABLISHED')
assert.equal(DLSS5_RUNTIME_CONTRACT.authority_effect, 'NONE')

const missing = verifyDlss5RuntimeProbe(undefined)
assert.equal(missing.status, 'RUNTIME_PROBE_NOT_VERIFIED')
assert.deepEqual(missing.reason_codes, ['RUNTIME_EVIDENCE_MISSING'])
assert.equal(missing.execution_release, 'BLOCKED')

const base = {
  schema: 'AEGIS_DLSS5_RUNTIME_PROBE_EVIDENCE_V1',
  candidate_sha: candidate,
  capability_receipt_digest: sha('1'),
  observation_digest: sha('2'),
  captured_at: '2026-09-10T18:15:00Z',
  gpu: {
    vendor: 'NVIDIA',
    model: 'GeForce RTX 5090',
    driver_version: '600.00',
  },
  streamline: {
    version: '2.14.1',
    plugin: 'sl.dlss_nr',
    plugin_digest: sha('3'),
  },
  checks: {
    hardware_eligible: true,
    plugin_present: true,
    feature_query: 'SUPPORTED',
    evaluation_executed: true,
  },
}

const observed = verifyDlss5RuntimeProbe(base)
assert.equal(observed.status, 'RUNTIME_PROBE_OBSERVED')
assert.equal(observed.execution_release, 'BLOCKED_PENDING_INDEPENDENT_REPLAY')
assert.equal(observed.rendering_claim, 'NOT_ESTABLISHED')
assert.equal(observed.claim_promotion, 'BLOCKED')
assert.equal(observed.authority_effect, 'NONE')
assert.equal(observed.capability_receipt_digest, sha('1'))
assert.equal(observed.observation_digest, sha('2'))

const amd = verifyDlss5RuntimeProbe({
  ...base,
  gpu: { vendor: 'AMD', model: 'Radeon RX 570 Graphics', driver_version: 'test' },
})
assert.equal(amd.status, 'RUNTIME_PROBE_REJECTED')
assert.ok(amd.reason_codes.includes('DLSS5_HARDWARE_UNSUPPORTED'))

const rtx40 = verifyDlss5RuntimeProbe({ ...base, gpu: { ...base.gpu, model: 'GeForce RTX 4090' } })
assert.equal(rtx40.status, 'RUNTIME_PROBE_REJECTED')
assert.deepEqual(rtx40.reason_codes, ['DLSS5_HARDWARE_UNSUPPORTED'])

const wrongPlugin = verifyDlss5RuntimeProbe({
  ...base,
  streamline: { ...base.streamline, plugin: 'sl.dlss' },
})
assert.equal(wrongPlugin.status, 'RUNTIME_PROBE_REJECTED')
assert.ok(wrongPlugin.reason_codes.includes('DLSS5_PLUGIN_MISMATCH'))

const oldStreamline = verifyDlss5RuntimeProbe({
  ...base,
  streamline: { ...base.streamline, version: '2.12.0' },
})
assert.ok(oldStreamline.reason_codes.includes('STREAMLINE_VERSION_UNSUPPORTED'))

const notExecuted = verifyDlss5RuntimeProbe({
  ...base,
  checks: { ...base.checks, evaluation_executed: false },
})
assert.equal(notExecuted.status, 'RUNTIME_PROBE_REJECTED')
assert.ok(notExecuted.reason_codes.includes('RUNTIME_EVALUATION_NOT_EXECUTED'))

console.log('DLSS5_RUNTIME_PASS contract=1 missing=1 positive=1 rejection=5 authority=NONE')
