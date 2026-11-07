import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import { projectLabObservation } from '../dist/lab-receipt.js'

const target = {
  work_id: 'AEGIS-734',
  execution_id: '123e4567-e89b-42d3-a456-426614174000',
  expected_source_sha: 'a'.repeat(40),
}
const envelope = (status, data = {}) => ({
  contract_version: '1.0.0',
  execution_id: target.execution_id,
  data: { execution_id: target.execution_id, status, ...data },
})
const project = (payload) => projectLabObservation(payload, target)

test('pending and running have no claimed artifacts, verifiers, or admission', () => {
  for (const status of ['pending', 'running']) {
    const r = project(envelope(status))
    assert.equal(r.observation, 'RUNNING')
    assert.equal(r.worker_identity, 'UNKNOWN')
    assert.equal(r.artifact_evidence, 'UNKNOWN')
    assert.equal(r.independent_verification, 'NOT_RUN')
    assert.equal(r.admission, 'NOT_ADMITTED')
  }
})
test('provider complete is never verified or admitted on its own', () => {
  const r = project(envelope('complete', { result: { output: 'done' } }))
  assert.equal(r.observation, 'COMPLETE_UNVERIFIED')
  assert.equal(r.source_binding, 'UNKNOWN')
  assert.equal(r.artifact_evidence, 'UNKNOWN')
  assert.equal(r.admission, 'NOT_ADMITTED')
})
test('a reported 64-hex artifact digest remains unattested', () => {
  const r = project(envelope('complete', { result: { artifact_sha256: 'b'.repeat(64) } }))
  assert.equal(r.artifact_evidence, 'UNATTESTED_CLAIM')
  assert.equal(r.independent_verification, 'NOT_RUN')
  assert.equal(r.observation, 'COMPLETE_UNVERIFIED')
})
test('provider reported error cannot be promoted into successful work', () => {
  const r = project(envelope('error', { error: 'runtime unavailable' }))
  assert.equal(r.observation, 'FAILED')
  assert.equal(r.worker_identity, 'UNKNOWN')
})
test('missing backend, wrong contract and malformed payload reject', () => {
  for (const payload of [null, {}, [], { contract_version: '2.0.0', data: {} },
    { ...envelope('complete'), data: null }]) {
    assert.equal(project(payload).reason, 'INVALID_PROVIDER_ENVELOPE')
  }
})
test('wrong execution identity rejects before considering status', () => {
  const raw = envelope('complete')
  raw.execution_id = 'wrong'
  assert.equal(project(raw).reason, 'EXECUTION_ID_MISMATCH')
  const raw2 = envelope('complete', { execution_id: 'wrong' })
  assert.equal(project(raw2).reason, 'EXECUTION_ID_MISMATCH')
})
test('wrong task identity rejects', () => {
  assert.equal(project(envelope('complete', { work_id: 'AEGIS-735' })).reason, 'WORK_ID_MISMATCH')
})
test('stale/wrong source rejects', () => {
  const r = project(envelope('complete', { source_sha: 'b'.repeat(40) }))
  assert.equal(r.reason, 'SOURCE_SHA_MISMATCH')
  assert.equal(r.source_binding, 'MISMATCH')
  assert.equal(r.admission, 'NOT_ADMITTED')
})
test('self-reported matching SHA does not authenticate the source', () => {
  const r = project(envelope('complete', { source_sha: target.expected_source_sha, work_id: target.work_id }))
  assert.equal(r.source_binding, 'UNATTESTED_MATCH')
  assert.equal(r.independent_verification, 'NOT_RUN')
  assert.equal(r.observation, 'COMPLETE_UNVERIFIED')
})
test('unknown or fabricated status rejects', () => {
  for (const status of ['success', 'verified', 'approved', null, undefined]) {
    assert.equal(project(envelope(status)).reason, 'INVALID_BRIDGE_STATUS')
  }
})

test('lab capability is exactly D0 and bound to the actual MCP tool', () => {
  const filename = fileURLToPath(new URL('../../../harness/policies/capability-map.v1.json', import.meta.url))
  const source = JSON.parse(readFileSync(filename, 'utf8'))
  const permission = source.capabilities['mcp.lab.receipt']
  assert.deepEqual(permission, {
    skill_id: 'orchestration_routing',
    allowed_action_classes: ['D0'],
    allowed_tools: ['aegis_lab_receipt'],
  })
  assert.deepEqual(source.capabilities['mcp.execution.read'].allowed_tools, ['aegis_get_execution'])
  for (const rule of [permission, source.capabilities['mcp.execution.read']]) {
    assert.deepEqual(rule.allowed_action_classes, ['D0'])
  }
})
