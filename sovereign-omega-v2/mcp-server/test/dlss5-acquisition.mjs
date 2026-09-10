import assert from 'node:assert/strict'

import { acquireDlss5Evidence, DLSS5_ACQUISITION_CONTRACT } from '../dist/dlss5-acquisition.js'
import { verifyDlss5RuntimeProbe } from '../dist/dlss5-runtime.js'

const SHA = 'a'.repeat(40)
const CAPABILITY = `sha256:${'b'.repeat(64)}`
const NOW = '2026-09-10T18:30:00.000Z'
const PLUGIN = new TextEncoder().encode('test-sl-dlss-nr-plugin-bytes')

const baseConfig = {
  candidate_sha: SHA,
  capability_receipt_digest: CAPABILITY,
  streamline_version: '2.14.1',
  streamline_plugin_path: '/opt/streamline/sl.dlss_nr.dll',
}

const io = (stdout, pluginBytes = PLUGIN) => ({
  queryGpu: () => ({ ok: true, stdout }),
  readPlugin: () => pluginBytes,
  now: () => NOW,
})

assert.equal(DLSS5_ACQUISITION_CONTRACT.schema, 'AEGIS_DLSS5_ACQUISITION_CONTRACT_V1')
assert.deepEqual(DLSS5_ACQUISITION_CONTRACT.nvidia_smi.args, [
  '--query-gpu=name,driver_version,pci.bus_id',
  '--format=csv,noheader,nounits',
])
assert.equal(DLSS5_ACQUISITION_CONTRACT.authority_effect, 'NONE')
assert(!JSON.stringify(DLSS5_ACQUISITION_CONTRACT).match(/curl|wget|install|download/i))

const unavailable = acquireDlss5Evidence(baseConfig, {
  queryGpu: () => ({ ok: false, stdout: '', error: 'ENOENT' }),
  readPlugin: () => PLUGIN,
  now: () => NOW,
})
assert.equal(unavailable.status, 'ACQUISITION_BLOCKED')
assert(unavailable.reason_codes.includes('NVIDIA_SMI_UNAVAILABLE'))
assert.equal(unavailable.authority_effect, 'NONE')

const unsupported = acquireDlss5Evidence(
  baseConfig,
  io('NVIDIA GeForce RTX 4090, 590.12, 00000000:01:00.0\n'),
)
assert.equal(unsupported.status, 'ACQUISITION_BLOCKED')
assert(unsupported.reason_codes.includes('DLSS5_HARDWARE_UNSUPPORTED'))

const ambiguous = acquireDlss5Evidence(
  baseConfig,
  io([
    'NVIDIA GeForce RTX 5090, 590.12, 00000000:01:00.0',
    'NVIDIA GeForce RTX 5090, 590.12, 00000000:02:00.0',
  ].join('\n')),
)
assert.equal(ambiguous.status, 'ACQUISITION_BLOCKED')
assert(ambiguous.reason_codes.includes('GPU_SELECTION_AMBIGUOUS'))

const missingPlugin = acquireDlss5Evidence(
  baseConfig,
  {
    ...io('NVIDIA GeForce RTX 5090, 590.12, 00000000:01:00.0\n'),
    readPlugin: () => null,
  },
)
assert.equal(missingPlugin.status, 'ACQUISITION_BLOCKED')
assert(missingPlugin.reason_codes.includes('DLSS5_PLUGIN_UNAVAILABLE'))

const captured = acquireDlss5Evidence(
  baseConfig,
  io('NVIDIA GeForce RTX 5090, 590.12, 00000000:01:00.0\n'),
)
assert.equal(captured.status, 'EVIDENCE_CAPTURED')
assert.equal(captured.rendering_claim, 'NOT_ESTABLISHED')
assert.equal(captured.runtime_claim, 'NOT_ESTABLISHED')
assert.equal(captured.execution_release, 'BLOCKED_PENDING_RUNTIME_EXECUTION')
assert.equal(captured.claim_promotion, 'BLOCKED')
assert.equal(captured.authority_effect, 'NONE')
assert.match(captured.acquisition_receipt_digest, /^sha256:[0-9a-f]{64}$/)
assert.match(captured.evidence.observation_digest, /^sha256:[0-9a-f]{64}$/)
assert.equal(captured.evidence.gpu.vendor, 'NVIDIA')
assert.equal(captured.evidence.gpu.model, 'NVIDIA GeForce RTX 5090')
assert.equal(captured.evidence.gpu.driver_version, '590.12')
assert.equal(captured.evidence.streamline.plugin, 'sl.dlss_nr')
assert.match(captured.evidence.streamline.plugin_digest, /^sha256:[0-9a-f]{64}$/)
assert.equal(captured.evidence.checks.hardware_eligible, true)
assert.equal(captured.evidence.checks.plugin_present, true)
assert.equal(captured.evidence.checks.feature_query, 'ERROR')
assert.equal(captured.evidence.checks.evaluation_executed, false)

const runtimeDisposition = verifyDlss5RuntimeProbe(captured.evidence)
assert.equal(runtimeDisposition.status, 'RUNTIME_PROBE_REJECTED')
assert(runtimeDisposition.reason_codes.includes('DLSS5_FEATURE_QUERY_NOT_SUPPORTED'))
assert(runtimeDisposition.reason_codes.includes('RUNTIME_EVALUATION_NOT_EXECUTED'))

const replay = acquireDlss5Evidence(
  baseConfig,
  io('NVIDIA GeForce RTX 5090, 590.12, 00000000:01:00.0\n'),
)
assert.equal(replay.acquisition_receipt_digest, captured.acquisition_receipt_digest)
assert.equal(replay.evidence.observation_digest, captured.evidence.observation_digest)

console.log('DLSS5_ACQUISITION_PASS contract=1 blocked=4 captured=1 deterministic=2 runtime_promotion=0 authority=NONE')
