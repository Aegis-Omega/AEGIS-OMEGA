import test from 'node:test'
import assert from 'node:assert/strict'
import {loadRepositoryTypescript} from './load-repository-ts.mjs'

const loaded=await loadRepositoryTypescript(['sovereignty/company-hosted-replay-admission.ts'])
test.after(()=>loaded.cleanup())
const {admitHostedEnterpriseReplayV1:admit,admitExternalHostedReplayV1:admitExternal}=loaded.modules['sovereignty/company-hosted-replay-admission.ts']

const HEAD='2bcc8027bbe760541ac9c1c3da336f6455ce6509'
const BRANCH='feat/openai-sota-autonomous-company-v1'
const receipt=(overrides={})=>({
  schema:'AEGIS_CLOUDFLARE_ENTERPRISE_REPLAY_V1',
  status:'PASS',
  source_head:HEAD,
  workers_ci_commit_sha:HEAD,
  branch:BRANCH,
  build_uuid:'26a1226f-5de5-4efe-bed2-d9e9255dbf50',
  node_version:'v24.18.0',
  strict_typecheck:'PASS',
  falsifiers:'PASS',
  suite_count:21,
  write_authority:'NOT_GRANTED',
  merge_authority:'NOT_GRANTED',
  deploy_authority:'NOT_GRANTED',
  financial_authority:'NOT_GRANTED',
  authority_effect:'NONE',
  ...overrides,
})
const input=(overrides={})=>({
  expected_head:HEAD,
  expected_branch:BRANCH,
  provider_check_conclusion:'success',
  receipt:receipt(),
  minimum_suite_count:21,
  ...overrides,
})

test('exact-head Cloudflare receipt is admitted only when all evidence passes',()=>{
  const r=admit(input())
  assert.equal(r.status,'ADMITTED')
  assert.equal(r.exact_head_execution,'VERIFIED_PASS')
  assert.deepEqual(r.reasons,[])
  assert.equal(r.provider,'CLOUDFLARE_WORKERS_BUILDS')
})

test('provider build success alone is never hosted replay evidence',()=>{
  const r=admit(input({receipt:null}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.reasons.includes('REPLAY_RECEIPT_MISSING'))
})

test('green provider check with FAIL receipt is denied',()=>{
  const r=admit(input({receipt:receipt({status:'FAIL',strict_typecheck:'NOT_ESTABLISHED',falsifiers:'NOT_ESTABLISHED'})}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.reasons.includes('REPLAY_STATUS_NOT_PASS'))
  assert.ok(r.reasons.includes('STRICT_TYPECHECK_NOT_PASS'))
})

test('head drift is rejected independently on both receipt bindings',()=>{
  const stale='d90aa2f5df1a1637335c3dbadb74ba7fd8b6e2e4'
  let r=admit(input({receipt:receipt({source_head:stale})}))
  assert.ok(r.reasons.includes('SOURCE_HEAD_MISMATCH'))
  assert.ok(r.reasons.includes('INTERNAL_HEAD_MISMATCH'))
  r=admit(input({receipt:receipt({workers_ci_commit_sha:stale})}))
  assert.ok(r.reasons.includes('WORKERS_CI_HEAD_MISMATCH'))
})

test('suite truncation and authority widening are denied',()=>{
  const r=admit(input({receipt:receipt({
    suite_count:20,
    financial_authority:undefined,
  })}))
  assert.ok(r.reasons.includes('SUITE_COUNT_BELOW_CONTRACT'))
  assert.ok(r.reasons.includes('FINANCIAL_AUTHORITY_WIDENED_OR_MISSING'))
})

test('provider failure denies even a syntactically green receipt',()=>{
  const r=admit(input({provider_check_conclusion:'failure'}))
  assert.ok(r.reasons.includes('PROVIDER_CHECK_NOT_SUCCESS'))
})

test('branch mismatch is denied',()=>{
  const r=admit(input({receipt:receipt({branch:'main'})}))
  assert.ok(r.reasons.includes('BRANCH_MISMATCH'))
})


const EXTERNAL_HEAD='4d6e6b34677affe489ea20aea2ed9353aa53839b'
const EXTERNAL_RECEIPT_SHA='a'.repeat(64)
const externalReceipt=(overrides={})=>({
  schema:'AEGIS_EXTERNAL_HOSTED_REPLAY_V1',
  provider:'gitlab',
  target_pr:691,
  github_source_sha:EXTERNAL_HEAD,
  gitlab_pipeline_id:'2885659545',
  gitlab_job_id:'16756087069',
  gitlab_runner_id:'54907241',
  gitlab_runner_description:'k8s.saas-linux-small-amd64.runners-manager.gitlab.com/default',
  test_scope:['evidence-gradient-compiler','quantumdna-fail-closed','qpy-runtime-lock-guard'],
  result:'PASS',
  authority_effect:'NONE',
  receipt_sha256:EXTERNAL_RECEIPT_SHA,
  ...overrides,
})
const externalInput=(overrides={})=>({
  expected_head:EXTERNAL_HEAD,
  expected_pr:691,
  provider_check_conclusion:'success',
  provider_observed_receipt_sha256:EXTERNAL_RECEIPT_SHA,
  receipt:externalReceipt(),
  minimum_test_scope_count:3,
  ...overrides,
})

test('exact-head GitLab receipt is admitted as external replay evidence only',()=>{
  const r=admitExternal(externalInput())
  assert.equal(r.status,'ADMITTED')
  assert.equal(r.exact_head_execution,'VERIFIED_PASS')
  assert.equal(r.evidence_authority,'PROVIDER_ATTESTATION')
  assert.deepEqual(r.reasons,[])
  assert.equal(r.provider,'GITLAB_EXTERNAL_REPLAY')
  assert.equal(r.native_github_required_context_effect,'NONE')
  assert.equal(r.production_admission_effect,'NONE')
  assert.equal(r.authority_effect,'NONE')
})

test('GitLab provider success without provider-observed receipt digest is denied',()=>{
  const r=admitExternal(externalInput({provider_observed_receipt_sha256:null}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.reasons.includes('PROVIDER_RECEIPT_DIGEST_MISSING'))
})

test('GitLab receipt digest mismatch is denied',()=>{
  const r=admitExternal(externalInput({provider_observed_receipt_sha256:'b'.repeat(64)}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.reasons.includes('PROVIDER_RECEIPT_DIGEST_MISMATCH'))
})

test('GitLab external replay rejects stale GitHub source head',()=>{
  const r=admitExternal(externalInput({receipt:externalReceipt({github_source_sha:'1'.repeat(40)})}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.reasons.includes('SOURCE_HEAD_MISMATCH'))
})

test('GitLab external replay rejects zero or missing runner identity',()=>{
  const r=admitExternal(externalInput({receipt:externalReceipt({gitlab_runner_id:'0'})}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.reasons.includes('GITLAB_RUNNER_ID_INVALID'))
})

test('GitLab external replay rejects truncated test scope',()=>{
  const r=admitExternal(externalInput({receipt:externalReceipt({test_scope:['one']})}))
  assert.equal(r.status,'DENIED')
  assert.ok(r.reasons.includes('TEST_SCOPE_BELOW_CONTRACT'))
})

test('GitLab external replay never substitutes for native GitHub admission',()=>{
  const r=admitExternal(externalInput())
  assert.equal(r.status,'ADMITTED')
  assert.equal(r.native_github_required_context_effect,'NONE')
  assert.equal(r.production_admission_effect,'NONE')
})
