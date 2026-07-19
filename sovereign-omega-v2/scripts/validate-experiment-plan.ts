#!/usr/bin/env node
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

import { canonicalizeJCS } from '../src/core/canonicalize.js'
import { sha256Hex } from '../src/core/hashing.js'
import type { SHA256Hex } from '../src/core/types.js'
import {
  assertExperimentPlanV01,
  buildAdmissionReceiptV01,
  computeExpectedParentStateRootV01,
  type AdmissionContextV01,
  type AdmissionEvidenceV01,
  type ExperimentPlanV01,
} from '../src/sovereignty/experiment-admission.js'

function argument(name: string): string | null {
  const index = process.argv.indexOf(name)
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1]! : null
}

function requiredArgument(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`missing required argument ${name}`)
  return value
}

function git(...args: string[]): string {
  return execFileSync('git', args, { encoding: 'utf8' }).trim()
}

function candidateBlob(candidateSha: string, path: string): string {
  return git('rev-parse', `${candidateSha}:${path}`)
}

async function canonicalJsonSha256(path: string): Promise<SHA256Hex> {
  const parsed = JSON.parse(readFileSync(path, 'utf8')) as unknown
  return sha256Hex(canonicalizeJCS(parsed))
}

async function fileSha256(path: string): Promise<SHA256Hex> {
  return sha256Hex(new Uint8Array(readFileSync(path)))
}

function assertCandidateBlob(candidateSha: string, label: string, path: string, expected: string): void {
  const actual = candidateBlob(candidateSha, path)
  if (actual !== expected) throw new Error(`${label} blob mismatch: expected ${expected}, got ${actual}`)
}

function assertBootstrapBoundary(plan: ExperimentPlanV01, parentSha: string): void {
  if (plan.execution_class !== 'BOOTSTRAP_GOVERNANCE') return
  try {
    git('cat-file', '-e', `${parentSha}:${plan.admission_workflow.path}`)
  } catch {
    return
  }
  throw new Error('bootstrap governance is forbidden after the admission workflow exists in the parent')
}

async function main(): Promise<void> {
  const planPath = requiredArgument('--plan')
  const candidateSha = requiredArgument('--candidate-sha')
  const parentSha = requiredArgument('--parent-sha')
  const repository = requiredArgument('--repository')
  const outputDir = requiredArgument('--output-dir')

  const plan = JSON.parse(readFileSync(planPath, 'utf8')) as ExperimentPlanV01
  const sourceTimestamp = git('show', '-s', '--format=%cI', candidateSha)
  const context: AdmissionContextV01 = {
    repository,
    candidate_sha: candidateSha,
    parent_sha: parentSha,
    source_timestamp: sourceTimestamp,
    workflow_ref: process.env.GITHUB_WORKFLOW_REF ?? 'local',
    workflow_run_id: process.env.GITHUB_RUN_ID ?? 'local',
    workflow_run_attempt: process.env.GITHUB_RUN_ATTEMPT ?? '1',
  }

  await assertExperimentPlanV01(plan, context)
  assertBootstrapBoundary(plan, parentSha)

  assertCandidateBlob(candidateSha, 'constitution', plan.constitution.path, plan.constitution.blob_id)
  assertCandidateBlob(candidateSha, 'policy', plan.policy.path, plan.policy.blob_id)
  assertCandidateBlob(candidateSha, 'sovereignty contracts', plan.sovereignty_contracts.path, plan.sovereignty_contracts.blob_id)
  assertCandidateBlob(candidateSha, 'admission workflow', plan.admission_workflow.path, plan.admission_workflow.blob_id)
  assertCandidateBlob(candidateSha, 'admission executable', plan.admission_executable.path, plan.admission_executable.blob_id)
  assertCandidateBlob(candidateSha, 'integration ledger generator', plan.integration_ledger_generator.path, plan.integration_ledger_generator.blob_id)

  const claimsRoot = await canonicalJsonSha256(plan.claims_ledger.path)
  if (claimsRoot !== plan.claims_ledger.root) throw new Error('claims ledger root mismatch')

  const parentStateRoot = await computeExpectedParentStateRootV01(plan)
  if (parentStateRoot !== plan.expected_parent_state_root) throw new Error('parent state root mismatch')

  const ledgerJsonPath = resolve(outputDir, 'INTEGRATION_LEDGER.json')
  const evidence: AdmissionEvidenceV01 = {
    plan_path: planPath,
    plan_sha256: await sha256Hex(canonicalizeJCS({ domain: 'AEGIS_EXPERIMENT_PLAN_V0_1', plan })),
    constitution_sha256: await fileSha256(plan.constitution.path),
    policy_sha256: await fileSha256(plan.policy.path),
    sovereignty_contracts_sha256: await fileSha256(plan.sovereignty_contracts.path),
    claims_ledger_sha256: await fileSha256(plan.claims_ledger.path),
    admission_workflow_sha256: await fileSha256(plan.admission_workflow.path),
    admission_executable_sha256: await fileSha256(plan.admission_executable.path),
    integration_ledger_generator_sha256: await fileSha256(plan.integration_ledger_generator.path),
    integration_ledger_json_sha256: await fileSha256(ledgerJsonPath),
  }

  const receipt = await buildAdmissionReceiptV01(plan, context, evidence)
  const receiptPath = resolve(outputDir, 'ADMISSION_RECEIPT.json')
  mkdirSync(dirname(receiptPath), { recursive: true })
  writeFileSync(receiptPath, canonicalizeJCS(receipt))
  writeFileSync(resolve(outputDir, 'EVIDENCE_MANIFEST.json'), canonicalizeJCS({
    schema_version: '0.1.0',
    plan_path: planPath,
    candidate_sha: candidateSha,
    parent_sha: parentSha,
    expected_parent_state_root: plan.expected_parent_state_root,
    evidence,
    receipt_hash: receipt.receipt_hash,
  }))
  console.log(`ADMITTED ${plan.experiment_id} ${receipt.receipt_hash}`)
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error)
  const outputDir = argument('--output-dir')
  if (outputDir) {
    const denialPath = resolve(outputDir, 'DENIAL_RECEIPT.json')
    mkdirSync(dirname(denialPath), { recursive: true })
    writeFileSync(denialPath, canonicalizeJCS({
      schema_version: '0.1.0',
      receipt_kind: 'AEGIS_EXPERIMENT_ADMISSION_DENIAL_V0_1',
      outcome: 'DENIED',
      candidate_sha: argument('--candidate-sha'),
      parent_sha: argument('--parent-sha'),
      plan_path: argument('--plan'),
      repository: argument('--repository'),
      workflow_ref: process.env.GITHUB_WORKFLOW_REF ?? 'local',
      workflow_run_id: process.env.GITHUB_RUN_ID ?? 'local',
      workflow_run_attempt: process.env.GITHUB_RUN_ATTEMPT ?? '1',
      reason: message,
    }))
  }
  console.error(`DENIED: ${message}`)
  process.exitCode = 1
})
