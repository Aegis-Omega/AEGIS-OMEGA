import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  assertExperimentPlanV01,
  buildAdmissionReceiptV01,
  computeApprovalRecordHashV01,
  computeExpectedParentStateRootV01,
  hashExperimentPlanV01,
  type AdmissionContextV01,
  type AdmissionEvidenceV01,
  type ExperimentPlanV01,
} from '../../src/sovereignty/experiment-admission.js'

const h = (digit: string) => digit.repeat(64) as SHA256Hex
const g = (digit: string) => digit.repeat(40)

async function fixture(): Promise<{ plan: ExperimentPlanV01; context: AdmissionContextV01; evidence: AdmissionEvidenceV01 }> {
  const approval = {
    required: true as const,
    state: 'APPROVED' as const,
    operator_actor_id: 'tarikskalic',
    operator_session_id: 'session-1',
    authorization_basis: 'explicit-go',
    decided_at: '2026-07-19T00:03:12Z',
    signature_mode: 'GITHUB_OIDC_ATTESTATION' as const,
    approval_record_hash: h('0'),
  }
  approval.approval_record_hash = await computeApprovalRecordHashV01(approval)
  const plan: ExperimentPlanV01 = {
    schema_version: '0.1.0',
    experiment_id: 'admission-fixture',
    title: 'Admission fixture',
    execution_class: 'EXPERIMENT',
    repository: 'Aegis-Omega/AEGIS-OMEGA',
    expected_parent_sha: g('1'),
    expected_parent_state_root: h('0'),
    constitution: { path: 'CONSTITUTIONAL_DECLARATION.md', blob_id: g('2') },
    policy: { path: 'docs/rfcs/0001.md', blob_id: g('3') },
    sovereignty_contracts: { path: 'src/contracts.ts', blob_id: g('4') },
    claims_ledger: { path: '.aegis/claims-ledger.json', root: h('5') },
    admission_workflow: { path: '.github/workflows/experiment-admission.yml', blob_id: g('6') },
    admission_executable: { path: 'scripts/validate.ts', blob_id: g('7') },
    integration_ledger_generator: { path: 'scripts/integration_ledger.py', blob_id: g('8') },
    requested_authority_domains: ['github:artifact-write', 'github:attestation-write'],
    expected_outputs: ['ADMISSION_RECEIPT.json', 'EVIDENCE_MANIFEST.json'],
    evidence_tier: 'T1',
    budget: { max_duration_seconds: 900, max_mutations: 0, max_cost_microunits: 0 },
    termination_conditions: ['budget_exhausted', 'observability_expired', 'operator_emergency_stop'],
    operator_approval: approval,
    observability: {
      provider: 'github-actions',
      durable_execution_required: true,
      cancellation_mechanism: 'github-actions-cancel-run',
      heartbeat_max_seconds: 300,
      emergency_stop_reference: 'cancel-run',
    },
    replay_package: {
      required: true,
      include_plan: true,
      include_admission_receipt: true,
      include_evidence_manifest: true,
      include_integration_ledger: true,
    },
  }
  plan.expected_parent_state_root = await computeExpectedParentStateRootV01(plan)
  const context: AdmissionContextV01 = {
    repository: plan.repository,
    candidate_sha: g('9'),
    parent_sha: plan.expected_parent_sha,
    source_timestamp: '2026-07-19T00:03:12Z',
    workflow_ref: 'Aegis-Omega/AEGIS-OMEGA/.github/workflows/experiment-admission.yml@refs/pull/1/merge',
    workflow_run_id: '1',
    workflow_run_attempt: '1',
  }
  const evidence: AdmissionEvidenceV01 = {
    plan_path: '.aegis/experiments/admission-fixture.json',
    plan_sha256: await hashExperimentPlanV01(plan),
    constitution_sha256: h('a'),
    policy_sha256: h('b'),
    sovereignty_contracts_sha256: h('c'),
    claims_ledger_sha256: h('d'),
    admission_workflow_sha256: h('e'),
    admission_executable_sha256: h('f'),
    integration_ledger_generator_sha256: h('1'),
    integration_ledger_json_sha256: h('2'),
  }
  return { plan, context, evidence }
}

describe('experiment admission v0.1', () => {
  it('is deterministic and binds the candidate commit into the receipt', async () => {
    const { plan, context, evidence } = await fixture()
    const first = await buildAdmissionReceiptV01(plan, context, evidence)
    const second = await buildAdmissionReceiptV01(plan, context, evidence)
    expect(first).toEqual(second)
    expect(first.candidate_sha).toBe(context.candidate_sha)
    expect(first.receipt_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('rejects an unexpected parent', async () => {
    const { plan, context } = await fixture()
    await expect(assertExperimentPlanV01(plan, { ...context, parent_sha: g('a') })).rejects.toThrow('expected_parent_sha')
  })

  it('rejects missing explicit approval', async () => {
    const { plan, context } = await fixture()
    const denied = { ...plan, operator_approval: { ...plan.operator_approval, state: 'REJECTED' as never } }
    await expect(assertExperimentPlanV01(denied, context)).rejects.toThrow('explicitly APPROVED')
  })

  it('rejects unsorted authority domains', async () => {
    const { plan, context } = await fixture()
    const denied = { ...plan, requested_authority_domains: [...plan.requested_authority_domains].reverse() }
    await expect(assertExperimentPlanV01(denied, context)).rejects.toThrow('sorted and unique')
  })

  it('rejects an incomplete replay package', async () => {
    const { plan, context } = await fixture()
    const denied = { ...plan, replay_package: { ...plan.replay_package, include_integration_ledger: false as true } }
    await expect(assertExperimentPlanV01(denied, context)).rejects.toThrow('replay package is incomplete')
  })

  it('changes the receipt when the candidate changes', async () => {
    const { plan, context, evidence } = await fixture()
    const first = await buildAdmissionReceiptV01(plan, context, evidence)
    const second = await buildAdmissionReceiptV01(plan, { ...context, candidate_sha: g('a') }, evidence)
    expect(first.receipt_hash).not.toBe(second.receipt_hash)
  })
})
