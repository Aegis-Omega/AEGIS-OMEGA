// AEGIS Hosted Replay Admission V1
// Provider build status is transport evidence only. A hosted replay is admitted
// only when the replay receipt is exact-head bound and all declared gates pass.

export interface HostedEnterpriseReplayReceiptV1 {
  readonly schema: 'AEGIS_CLOUDFLARE_ENTERPRISE_REPLAY_V1'
  readonly status: 'PASS' | 'FAIL' | 'UNVERIFIED_SOURCE_ONLY' | 'NOT_RUN_FOR_BRANCH'
  readonly source_head: string | null
  readonly workers_ci_commit_sha: string | null
  readonly branch: string | null
  readonly build_uuid: string | null
  readonly node_version?: string | null
  readonly strict_typecheck: 'PASS' | 'NOT_ESTABLISHED' | 'NOT_RUN'
  readonly falsifiers: 'PASS' | 'NOT_ESTABLISHED' | 'NOT_RUN'
  readonly suite_count?: number
  readonly write_authority?: 'NOT_GRANTED'
  readonly merge_authority?: 'NOT_GRANTED'
  readonly deploy_authority?: 'NOT_GRANTED'
  readonly financial_authority?: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
}

export interface HostedReplayAdmissionInputV1 {
  readonly expected_head: string
  readonly expected_branch: string
  readonly provider_check_conclusion: 'success' | 'failure' | 'cancelled' | 'skipped' | null
  readonly receipt: HostedEnterpriseReplayReceiptV1 | null
  readonly minimum_suite_count: number
}

export interface HostedReplayAdmissionDecisionV1 {
  readonly status: 'ADMITTED' | 'DENIED'
  readonly exact_head_execution: 'VERIFIED_PASS' | 'NOT_VERIFIED'
  readonly reasons: readonly string[]
  readonly provider: 'CLOUDFLARE_WORKERS_BUILDS'
  readonly authority_effect: 'NONE'
}

function sha(value: unknown,label:string):string{
  if(typeof value!=='string'||!/^[0-9a-f]{40}$/.test(value)) throw new TypeError(`${label} must be Git SHA-1 hex`)
  return value
}
function text(value:unknown,label:string):string{
  if(typeof value!=='string'||!value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

export function admitHostedEnterpriseReplayV1(
  input: HostedReplayAdmissionInputV1,
): HostedReplayAdmissionDecisionV1 {
  const expectedHead=sha(input?.expected_head,'expected_head')
  const expectedBranch=text(input?.expected_branch,'expected_branch')
  if(!Number.isSafeInteger(input.minimum_suite_count)||input.minimum_suite_count<1){
    throw new TypeError('minimum_suite_count must be positive safe integer')
  }

  const reasons:string[]=[]
  const receipt=input.receipt

  if(input.provider_check_conclusion!=='success'){
    reasons.push('PROVIDER_CHECK_NOT_SUCCESS')
  }
  if(!receipt){
    reasons.push('REPLAY_RECEIPT_MISSING')
  }else{
    if(receipt.schema!=='AEGIS_CLOUDFLARE_ENTERPRISE_REPLAY_V1') reasons.push('REPLAY_SCHEMA_MISMATCH')
    if(receipt.status!=='PASS') reasons.push('REPLAY_STATUS_NOT_PASS')
    if(receipt.source_head!==expectedHead) reasons.push('SOURCE_HEAD_MISMATCH')
    if(receipt.workers_ci_commit_sha!==expectedHead) reasons.push('WORKERS_CI_HEAD_MISMATCH')
    if(receipt.source_head!==receipt.workers_ci_commit_sha) reasons.push('INTERNAL_HEAD_MISMATCH')
    if(receipt.branch!==expectedBranch) reasons.push('BRANCH_MISMATCH')
    if(typeof receipt.build_uuid!=='string'||!receipt.build_uuid.trim()) reasons.push('BUILD_UUID_MISSING')
    if(receipt.strict_typecheck!=='PASS') reasons.push('STRICT_TYPECHECK_NOT_PASS')
    if(receipt.falsifiers!=='PASS') reasons.push('FALSIFIERS_NOT_PASS')
    if(!Number.isSafeInteger(receipt.suite_count)||Number(receipt.suite_count)<input.minimum_suite_count){
      reasons.push('SUITE_COUNT_BELOW_CONTRACT')
    }
    for(const [label,value] of [
      ['WRITE_AUTHORITY',receipt.write_authority],
      ['MERGE_AUTHORITY',receipt.merge_authority],
      ['DEPLOY_AUTHORITY',receipt.deploy_authority],
      ['FINANCIAL_AUTHORITY',receipt.financial_authority],
    ] as const){
      if(value!=='NOT_GRANTED') reasons.push(`${label}_WIDENED_OR_MISSING`)
    }
    if(receipt.authority_effect!=='NONE') reasons.push('AUTHORITY_EFFECT_NOT_NONE')
  }

  const admitted=reasons.length===0
  return Object.freeze({
    status:admitted?'ADMITTED':'DENIED',
    exact_head_execution:admitted?'VERIFIED_PASS':'NOT_VERIFIED',
    reasons:Object.freeze(reasons),
    provider:'CLOUDFLARE_WORKERS_BUILDS',
    authority_effect:'NONE',
  })
}


export interface ExternalHostedReplayReceiptV1 {
  readonly schema: 'AEGIS_EXTERNAL_HOSTED_REPLAY_V1'
  readonly provider: 'gitlab'
  readonly target_pr: number
  readonly github_source_sha: string
  readonly gitlab_pipeline_id: string
  readonly gitlab_job_id: string
  readonly gitlab_runner_id: string
  readonly gitlab_runner_description: string
  readonly test_scope: readonly string[]
  readonly result: 'PASS' | 'FAIL'
  readonly authority_effect: 'NONE'
  readonly receipt_sha256: string
}

export interface ExternalHostedReplayAdmissionInputV1 {
  readonly expected_head: string
  readonly expected_pr: number
  readonly provider_check_conclusion: 'success' | 'failure' | 'cancelled' | 'skipped' | null
  readonly provider_observed_receipt_sha256: string | null
  readonly receipt: ExternalHostedReplayReceiptV1 | null
  readonly minimum_test_scope_count: number
}

export interface ExternalHostedReplayAdmissionDecisionV1 {
  readonly status: 'ADMITTED' | 'DENIED'
  readonly exact_head_execution: 'VERIFIED_PASS' | 'NOT_VERIFIED'
  readonly evidence_authority: 'PROVIDER_ATTESTATION'
  readonly reasons: readonly string[]
  readonly provider: 'GITLAB_EXTERNAL_REPLAY'
  readonly native_github_required_context_effect: 'NONE'
  readonly production_admission_effect: 'NONE'
  readonly authority_effect: 'NONE'
}

function positiveDecimal(value: unknown, label: string): string {
  if (typeof value !== 'string' || !/^[1-9][0-9]*$/.test(value)) {
    throw new TypeError(`${label} must be a positive decimal identifier`)
  }
  return value
}

function digest(value: unknown, label: string): string {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) {
    throw new TypeError(`${label} must be lowercase SHA-256 hex`)
  }
  return value
}

export function admitExternalHostedReplayV1(
  input: ExternalHostedReplayAdmissionInputV1,
): ExternalHostedReplayAdmissionDecisionV1 {
  const expectedHead = sha(input?.expected_head, 'expected_head')
  if (!Number.isSafeInteger(input.expected_pr) || input.expected_pr < 1) {
    throw new TypeError('expected_pr must be positive safe integer')
  }
  if (!Number.isSafeInteger(input.minimum_test_scope_count) || input.minimum_test_scope_count < 1) {
    throw new TypeError('minimum_test_scope_count must be positive safe integer')
  }

  const reasons: string[] = []
  const receipt = input.receipt

  if (input.provider_check_conclusion !== 'success') {
    reasons.push('PROVIDER_CHECK_NOT_SUCCESS')
  }

  let observedReceiptSha = ''
  if (input.provider_observed_receipt_sha256 === null) {
    reasons.push('PROVIDER_RECEIPT_DIGEST_MISSING')
  } else {
    try {
      observedReceiptSha = digest(
        input.provider_observed_receipt_sha256,
        'provider_observed_receipt_sha256',
      )
    } catch {
      reasons.push('PROVIDER_RECEIPT_DIGEST_INVALID')
    }
  }

  if (!receipt) {
    reasons.push('REPLAY_RECEIPT_MISSING')
  } else {
    if (receipt.schema !== 'AEGIS_EXTERNAL_HOSTED_REPLAY_V1') reasons.push('REPLAY_SCHEMA_MISMATCH')
    if (receipt.provider !== 'gitlab') reasons.push('PROVIDER_ID_MISMATCH')
    if (receipt.result !== 'PASS') reasons.push('REPLAY_STATUS_NOT_PASS')
    if (receipt.target_pr !== input.expected_pr) reasons.push('TARGET_PR_MISMATCH')
    if (receipt.github_source_sha !== expectedHead) reasons.push('SOURCE_HEAD_MISMATCH')

    for (const [label, value] of [
      ['GITLAB_PIPELINE_ID', receipt.gitlab_pipeline_id],
      ['GITLAB_JOB_ID', receipt.gitlab_job_id],
      ['GITLAB_RUNNER_ID', receipt.gitlab_runner_id],
    ] as const) {
      try {
        positiveDecimal(value, label)
      } catch {
        reasons.push(`${label}_INVALID`)
      }
    }

    if (typeof receipt.gitlab_runner_description !== 'string' || !receipt.gitlab_runner_description.trim()) {
      reasons.push('GITLAB_RUNNER_DESCRIPTION_MISSING')
    }

    if (
      !Array.isArray(receipt.test_scope) ||
      receipt.test_scope.length < input.minimum_test_scope_count ||
      receipt.test_scope.some(item => typeof item !== 'string' || !item.trim())
    ) {
      reasons.push('TEST_SCOPE_BELOW_CONTRACT')
    } else if (new Set(receipt.test_scope).size !== receipt.test_scope.length) {
      reasons.push('TEST_SCOPE_DUPLICATE')
    }

    let receiptSha = ''
    try {
      receiptSha = digest(receipt.receipt_sha256, 'receipt_sha256')
    } catch {
      reasons.push('RECEIPT_SHA256_INVALID')
    }
    if (receiptSha && observedReceiptSha && receiptSha !== observedReceiptSha) {
      reasons.push('PROVIDER_RECEIPT_DIGEST_MISMATCH')
    }
    if (receipt.authority_effect !== 'NONE') reasons.push('AUTHORITY_EFFECT_NOT_NONE')
  }

  const admitted = reasons.length === 0
  return Object.freeze({
    status: admitted ? 'ADMITTED' : 'DENIED',
    exact_head_execution: admitted ? 'VERIFIED_PASS' : 'NOT_VERIFIED',
    evidence_authority: 'PROVIDER_ATTESTATION',
    reasons: Object.freeze(reasons),
    provider: 'GITLAB_EXTERNAL_REPLAY',
    native_github_required_context_effect: 'NONE',
    production_admission_effect: 'NONE',
    authority_effect: 'NONE',
  })
}
