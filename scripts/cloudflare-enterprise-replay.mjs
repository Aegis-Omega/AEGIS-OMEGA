import { execFileSync, spawnSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const TARGET_BRANCH = 'feat/openai-sota-autonomous-company-v1'
const EXPECTED_SUITE_COUNT = 23
const SOURCE_BLOB_CONTRACT = Object.freeze({
  'supabase/migrations/20260922193000_scale_os_company_runtime_v2.sql': '9a4c6e4fda02e8fc01ba8b7d6b9bc2b65b20ac91',
  'supabase/migrations/20260922205500_scale_os_enterprise_opportunities_v1.sql': '7db3fcbff9b7c3c8538d524690c57b2a4763ab85',
  'supabase/migrations/20260922211500_scale_os_enterprise_resources_v1.sql': '5dbab3f199362560b8cde97f656e1cd1106d5eab',
  'supabase/migrations/20260922213000_scale_os_enterprise_event_immutability_v1.sql': '82da850049a7cdc0d9701fe9182da02600b8ebe6',
  'supabase/migrations/20260922214000_scale_os_enterprise_event_insert_guard_v1.sql': '9b140d8afda32146bbd80d9d4803155cd388826e',
  'supabase/migrations/20260922220500_supabase_advisor_performance_hardening_v1.sql': '90c4ee638a11b2cbcf858d6e6cdb4395d94cddbf',
  'sovereign-omega-v2/test/native-runtime/scale-os-company-runtime-v2.test.mjs': '112f3fd565405a5376fcf244dc945c4135cc714b',
})
const OUT = resolve('worker-src/generated-enterprise-replay.ts')

function receipt(value) {
  const body = {
    schema: 'AEGIS_CLOUDFLARE_ENTERPRISE_REPLAY_V1',
    authority_effect: 'NONE',
    ...value,
  }
  writeFileSync(
    OUT,
    `export const ENTERPRISE_REPLAY_RECEIPT = Object.freeze(${JSON.stringify(body, null, 2)} as const)\n`,
  )
  process.stdout.write(JSON.stringify(body) + '\n')
}

function run(command, args, cwd, stage) {
  const result = spawnSync(command, args, {
    cwd,
    env: process.env,
    encoding: 'utf8',
    maxBuffer: 20 * 1024 * 1024,
  })
  if (result.stdout) process.stdout.write(result.stdout)
  if (result.stderr) process.stderr.write(result.stderr)
  if (result.error) {
    const error = new Error(`${stage}: ${result.error.message}`)
    error.stage = stage
    error.exitStatus = null
    error.outputTail = ''
    throw error
  }
  if (result.status !== 0) {
    const combined = `${result.stdout ?? ''}\n${result.stderr ?? ''}`
    const error = new Error(`${stage} exited ${result.status}`)
    error.stage = stage
    error.exitStatus = result.status
    error.outputTail = combined.slice(-6000)
    throw error
  }
}

if (process.env.WORKERS_CI !== '1') {
  process.stdout.write('AEGIS Cloudflare replay skipped outside Workers CI\n')
  process.exit(0)
}

const branch = process.env.WORKERS_CI_BRANCH ?? ''
const buildUuid = process.env.WORKERS_CI_BUILD_UUID ?? null
const injectedSha = process.env.WORKERS_CI_COMMIT_SHA ?? ''
const gitSha = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim()

if (branch !== TARGET_BRANCH) {
  receipt({
    status: 'NOT_RUN_FOR_BRANCH',
    source_head: gitSha,
    workers_ci_commit_sha: injectedSha || null,
    branch,
    build_uuid: buildUuid,
    strict_typecheck: 'NOT_RUN',
    falsifiers: 'NOT_RUN',
  })
  process.exit(0)
}

if (!/^[0-9a-f]{40}$/.test(injectedSha) || injectedSha !== gitSha) {
  receipt({
    status: 'FAIL',
    source_head: gitSha,
    workers_ci_commit_sha: injectedSha || null,
    branch,
    build_uuid: buildUuid,
    strict_typecheck: 'NOT_RUN',
    falsifiers: 'NOT_RUN',
    failure: 'EXACT_HEAD_BINDING_FAILED',
  })
  process.exit(1)
}

const cwd = resolve('sovereign-omega-v2')
const sourceBlobs = {}
for (const [path, expected] of Object.entries(SOURCE_BLOB_CONTRACT)) {
  const actual = execFileSync('git', ['hash-object', path], { encoding: 'utf8' }).trim()
  sourceBlobs[path] = actual
  if (actual !== expected) {
    receipt({
      status: 'FAIL',
      source_head: gitSha,
      workers_ci_commit_sha: injectedSha,
      branch,
      build_uuid: buildUuid,
      strict_typecheck: 'NOT_RUN',
      falsifiers: 'NOT_RUN',
      source_blobs: sourceBlobs,
      failure: `SOURCE_BLOB_CONTRACT_DRIFT:${path}:${actual}!=${expected}`,
    })
    process.exit(1)
  }
}

try {
  run('npm', ['ci', '--ignore-scripts', '--include=dev', '--no-audit', '--no-fund'], cwd, 'NPM_CI')

  const tsc = resolve(cwd, 'node_modules/.bin/tsc')
  run(tsc, [
    '--noEmit',
    '--strict',
    '--target', 'ES2022',
    '--module', 'ES2022',
    '--moduleResolution', 'bundler',
    '--lib', 'ES2022,DOM',
    'src/sovereignty/provider-adapters/openai-managed-agents-api.ts',
    'src/sovereignty/provider-adapters/openai-managed-agents-client-binding.ts',
    'src/sovereignty/autonomous-company-loop.ts',
    'src/sovereignty/company-model-router.ts',
    'src/sovereignty/company-evidence-authority.ts',
    'src/sovereignty/company-approval-packet.ts',
    'src/sovereignty/company-model-promotion.ts',
    'src/sovereignty/company-work-graph.ts',
    'src/sovereignty/company-enterprise-opportunity.ts',
    'src/sovereignty/company-enterprise-mail-ingest.ts',
    'src/sovereignty/company-enterprise-resource-admission.ts',
    'src/sovereignty/company-enterprise-followup-policy.ts',
    'src/sovereignty/company-enterprise-engagement-gate.ts',
    'src/sovereignty/company-enterprise-action-packet.ts',
    'src/sovereignty/company-enterprise-ledger-reconcile.ts',
    'src/sovereignty/company-enterprise-production-readiness.ts',
    'src/sovereignty/company-enterprise-prospect-admission.ts',
    'src/sovereignty/company-hosted-replay-admission.ts',
  ], cwd, 'STRICT_TSC')

  const tests = [
    'test/native-runtime/openai-autonomous-company.test.mjs',
    'test/native-runtime/openai-company-production.test.mjs',
    'test/native-runtime/company-evidence-authority.test.mjs',
    'test/native-runtime/company-approval-packet.test.mjs',
    'test/native-runtime/company-model-promotion.test.mjs',
    'test/native-runtime/company-work-graph.test.mjs',
    'test/native-runtime/scale-os-company-runtime-v2.test.mjs',
    'test/native-runtime/scale-os-enterprise-opportunities-v1.test.mjs',
    'test/native-runtime/scale-os-enterprise-resources-v1.test.mjs',
    'test/native-runtime/scale-os-enterprise-event-immutability-v1.test.mjs',
    'test/native-runtime/scale-os-enterprise-event-insert-guard-v1.test.mjs',
    'test/native-runtime/openai-complimentary-canary.test.mjs',
    'test/native-runtime/company-enterprise-opportunity.test.mjs',
    'test/native-runtime/company-enterprise-mail-ingest.test.mjs',
    'test/native-runtime/company-enterprise-resource-admission.test.mjs',
    'test/native-runtime/company-enterprise-followup-policy.test.mjs',
    'test/native-runtime/company-enterprise-engagement-gate.test.mjs',
    'test/native-runtime/company-enterprise-action-packet.test.mjs',
    'test/native-runtime/company-enterprise-ledger-reconcile.test.mjs',
    'test/native-runtime/company-enterprise-production-readiness.test.mjs',
    'test/native-runtime/company-enterprise-prospect-admission.test.mjs',
    'test/native-runtime/company-hosted-replay-admission.test.mjs',
    'test/native-runtime/supabase-advisor-performance-hardening-v1.test.mjs',
  ]

  if (tests.length !== EXPECTED_SUITE_COUNT) {
    throw new Error(`SUITE_CONTRACT_DRIFT:${tests.length}!=${EXPECTED_SUITE_COUNT}`)
  }

  run('node', ['--test', ...tests], cwd, 'NODE_TEST')

  receipt({
    status: 'PASS',
    source_head: gitSha,
    workers_ci_commit_sha: injectedSha,
    branch,
    build_uuid: buildUuid,
    node_version: process.version,
    strict_typecheck: 'PASS',
    falsifiers: 'PASS',
    suite_count: tests.length,
    suite_contract_count: EXPECTED_SUITE_COUNT,
    source_blobs: sourceBlobs,
    write_authority: 'NOT_GRANTED',
    merge_authority: 'NOT_GRANTED',
    deploy_authority: 'NOT_GRANTED',
    financial_authority: 'NOT_GRANTED',
  })
} catch (error) {
  receipt({
    status: 'FAIL',
    source_head: gitSha,
    workers_ci_commit_sha: injectedSha,
    branch,
    build_uuid: buildUuid,
    node_version: process.version,
    strict_typecheck: 'NOT_ESTABLISHED',
    falsifiers: 'NOT_ESTABLISHED',
    failure: error instanceof Error ? error.message : String(error),
    failure_stage: error && typeof error === 'object' && 'stage' in error ? error.stage : null,
    failure_exit_status: error && typeof error === 'object' && 'exitStatus' in error ? error.exitStatus : null,
    failure_output_tail: error && typeof error === 'object' && 'outputTail' in error ? error.outputTail : null,
    source_blobs: sourceBlobs,
    diagnostic_mode: true,
    build_gate: 'RECEIPT_STATUS_ONLY',
  })
  process.stdout.write('AEGIS Cloudflare diagnostic replay recorded FAIL receipt; preview deploy continues for receipt retrieval.\n')
}
