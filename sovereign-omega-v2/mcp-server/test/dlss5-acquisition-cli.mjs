import assert from 'node:assert/strict'
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { delimiter, join } from 'node:path'
import { tmpdir } from 'node:os'
import { spawnSync } from 'node:child_process'
import process from 'node:process'

const root = mkdtempSync(join(tmpdir(), 'aegis-dlss5-cli-'))
const binDir = join(root, 'bin')
const pluginPath = join(root, 'sl.dlss_nr.dll')
const argLog = join(root, 'args.txt')

try {
  await import('node:fs/promises').then(({ mkdir }) => mkdir(binDir))
  writeFileSync(pluginPath, 'test-plugin-bytes')
  const nvidiaSmi = join(binDir, 'nvidia-smi')
  writeFileSync(nvidiaSmi, '#!/bin/sh\nprintf "%s\\n" "$@" > "$ARG_LOG"\nprintf "NVIDIA GeForce RTX 5090, 590.12, 00000000:01:00.0\\n"\n')
  chmodSync(nvidiaSmi, 0o755)

  const env = {
    ...process.env,
    PATH: `${binDir}${delimiter}${process.env.PATH ?? ''}`,
    ARG_LOG: argLog,
    AEGIS_CANDIDATE_SHA: 'a'.repeat(40),
    AEGIS_DLSS5_CAPABILITY_RECEIPT_DIGEST: `sha256:${'b'.repeat(64)}`,
    AEGIS_DLSS5_STREAMLINE_VERSION: '2.14.1',
    AEGIS_DLSS5_STREAMLINE_PLUGIN_PATH: pluginPath,
  }

  const positive = spawnSync(process.execPath, ['dist/dlss5-acquisition-cli.js'], {
    cwd: process.cwd(), env, encoding: 'utf8', timeout: 10_000,
  })
  assert.equal(positive.status, 0, positive.stderr)
  const value = JSON.parse(positive.stdout)
  assert.equal(value.status, 'EVIDENCE_CAPTURED')
  assert.equal(value.execution_release, 'BLOCKED_PENDING_RUNTIME_EXECUTION')
  assert.equal(value.runtime_claim, 'NOT_ESTABLISHED')
  assert.equal(value.rendering_claim, 'NOT_ESTABLISHED')
  assert.equal(value.claim_promotion, 'BLOCKED')
  assert.equal(value.authority_effect, 'NONE')

  const args = readFileSync(argLog, 'utf8').trim().split(/\r?\n/)
  assert.deepEqual(args, [
    '--query-gpu=name,driver_version,pci.bus_id',
    '--format=csv,noheader,nounits',
  ])

  const blocked = spawnSync(process.execPath, ['dist/dlss5-acquisition-cli.js'], {
    cwd: process.cwd(),
    env: { ...env, PATH: root },
    encoding: 'utf8',
    timeout: 10_000,
  })
  assert.equal(blocked.status, 2)
  const denied = JSON.parse(blocked.stdout)
  assert.equal(denied.status, 'ACQUISITION_BLOCKED')
  assert(denied.reason_codes.includes('NVIDIA_SMI_UNAVAILABLE'))
  assert.equal(denied.authority_effect, 'NONE')

  console.log('DLSS5_ACQUISITION_CLI_PASS positive=1 unavailable=1 exact_args=2 authority=NONE')
} finally {
  rmSync(root, { recursive: true, force: true })
}
