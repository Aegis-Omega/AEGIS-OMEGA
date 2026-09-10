import assert from 'node:assert/strict'
import {
  DLSS5_REFERENCE,
  buildDlss5Receipt,
  evaluateDlss5Capability,
} from '../dist/dlss5.js'

assert.equal(DLSS5_REFERENCE.technology, 'NVIDIA DLSS 5')
assert.equal(DLSS5_REFERENCE.feature, '3D-Guided Neural Rendering')
assert.equal(DLSS5_REFERENCE.streamline.plugin, 'sl.dlss_nr')
assert.equal(DLSS5_REFERENCE.streamline.first_supported_release, '2.14.0')
assert.equal(DLSS5_REFERENCE.streamline.tracked_release, '2.14.1')
assert.equal(DLSS5_REFERENCE.authority_effect, 'NONE')

const missing = evaluateDlss5Capability(undefined)
assert.equal(missing.status, 'NOT_VERIFIED')
assert.deepEqual(missing.reason_codes, ['ENVIRONMENT_MANIFEST_MISSING'])
assert.equal(missing.execution_release, 'BLOCKED')

const amd = evaluateDlss5Capability({
  schema: 'AEGIS_ENVIRONMENT_MANIFEST_V1',
  gpu: { vendor: 'AMD', model: 'AMD Radeon RX 570 Graphics (8GB)' },
  source_digest: 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  captured_at: '2026-09-10T17:00:00Z',
})
assert.equal(amd.status, 'UNSUPPORTED')
assert.deepEqual(amd.reason_codes, ['DLSS5_HARDWARE_UNSUPPORTED'])
assert.equal(amd.execution_release, 'BLOCKED')

const rtx5090 = {
  schema: 'AEGIS_ENVIRONMENT_MANIFEST_V1',
  gpu: { vendor: 'NVIDIA', model: 'NVIDIA GeForce RTX 5090' },
  source_digest: 'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  captured_at: '2026-09-10T17:00:00Z',
}
const eligible = evaluateDlss5Capability(rtx5090)
assert.equal(eligible.status, 'ELIGIBLE_FOR_RUNTIME_PROBE')
assert.deepEqual(eligible.reason_codes, [])
assert.equal(eligible.execution_release, 'BLOCKED_PENDING_RUNTIME_PROBE')

const first = buildDlss5Receipt(rtx5090)
const second = buildDlss5Receipt(rtx5090)
assert.equal(first.receipt_digest, second.receipt_digest)
assert.match(first.receipt_digest, /^sha256:[0-9a-f]{64}$/)

const changed = buildDlss5Receipt({ ...rtx5090, source_digest: 'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc' })
assert.notEqual(first.receipt_digest, changed.receipt_digest)
assert.equal(first.authority_effect, 'NONE')

console.log('DLSS5_CORE_PASS reference=1 capability=3 receipt_determinism=2')
