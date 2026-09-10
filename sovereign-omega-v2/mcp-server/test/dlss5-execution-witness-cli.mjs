import assert from 'node:assert/strict'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'

const sha = 'a'.repeat(40)
const digestA = `sha256:${'1'.repeat(64)}`
const digestB = `sha256:${'2'.repeat(64)}`
const digestC = `sha256:${'3'.repeat(64)}`
const digestD = `sha256:${'4'.repeat(64)}`

const root = mkdtempSync(join(tmpdir(), 'aegis-dlss5-witness-'))
const positivePath = join(root, 'positive.json')
const invalidPath = join(root, 'invalid.json')

writeFileSync(positivePath, JSON.stringify({
  schema: 'AEGIS_DLSS5_EXECUTION_WITNESS_EVIDENCE_V1',
  candidate_sha: sha,
  acquisition_receipt_digest: digestA,
  probe_binary_digest: digestB,
  probe_observation_digest: digestC,
  captured_at: '2026-09-10T18:55:00.000Z',
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
}))
writeFileSync(invalidPath, '{broken')

function run(path) {
  return spawnSync(process.execPath, ['dist/dlss5-execution-witness-cli.js'], {
    encoding: 'utf8',
    env: {
      ...process.env,
      AEGIS_DLSS5_EXECUTION_WITNESS_PATH: path ?? '',
    },
  })
}

const positive = run(positivePath)
assert.equal(positive.status, 0, positive.stderr)
const positiveValue = JSON.parse(positive.stdout)
assert.equal(positiveValue.status, 'EXECUTION_WITNESS_OBSERVED')
assert.equal(positiveValue.runtime_execution, 'OBSERVED_FOR_DECLARED_PROBE_ONLY')
assert.equal(positiveValue.rendering_claim, 'NOT_ESTABLISHED')
assert.equal(positiveValue.quality_claim, 'NOT_ESTABLISHED')
assert.equal(positiveValue.authority_effect, 'NONE')

const missing = run('')
assert.equal(missing.status, 2)
const missingValue = JSON.parse(missing.stdout)
assert.equal(missingValue.status, 'EXECUTION_WITNESS_NOT_VERIFIED')
assert.deepEqual(missingValue.reason_codes, ['EXECUTION_WITNESS_FILE_MISSING'])
assert.equal(missingValue.execution_release, 'BLOCKED')

const invalid = run(invalidPath)
assert.equal(invalid.status, 2)
const invalidValue = JSON.parse(invalid.stdout)
assert.equal(invalidValue.status, 'EXECUTION_WITNESS_NOT_VERIFIED')
assert.deepEqual(invalidValue.reason_codes, ['EXECUTION_WITNESS_JSON_INVALID'])
assert.equal(invalidValue.authority_effect, 'NONE')

console.log('DLSS5_EXECUTION_WITNESS_CLI_PASS positive=1 missing=1 invalid_json=1 gpu_execution=0 authority=NONE')
