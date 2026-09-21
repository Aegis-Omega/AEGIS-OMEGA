// ============================================================
// GitHub Actions -> Sovereign Provider Mesh adapter V1
// EPISTEMIC TIER: T1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export interface GitHubActionsJobEvidenceV1 {
  run_id: string
  job_id: string
  head_sha: string
  status: 'queued' | 'in_progress' | 'completed'
  conclusion:
    | 'success'
    | 'failure'
    | 'cancelled'
    | 'skipped'
    | 'timed_out'
    | 'action_required'
    | 'neutral'
    | null
  runner_id: number
  runner_name: string
  steps_count: number
}

const DECIMAL_PATTERN = /^(0|[1-9][0-9]*)$/
const GIT_OBJECT_PATTERN = /^[0-9a-f]{40,64}$/

function assertDecimal(field: string, value: string): void {
  if (!DECIMAL_PATTERN.test(value)) throw new TypeError(`${field} must be canonical unsigned decimal`)
}

function assertJob(job: GitHubActionsJobEvidenceV1): void {
  assertDecimal('run_id', job.run_id)
  assertDecimal('job_id', job.job_id)
  if (!GIT_OBJECT_PATTERN.test(job.head_sha)) throw new TypeError('head_sha must be a lowercase Git object id')
  if (!Number.isSafeInteger(job.runner_id) || job.runner_id < 0) throw new TypeError('runner_id must be a non-negative safe integer')
  if (!Number.isSafeInteger(job.steps_count) || job.steps_count < 0) throw new TypeError('steps_count must be a non-negative safe integer')
  if (job.runner_id === 0 && job.runner_name !== '') {
    throw new TypeError('runner_name must be empty when runner_id is zero')
  }
}

async function evidenceHash(job: GitHubActionsJobEvidenceV1): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_GITHUB_ACTIONS_JOB_EVIDENCE_V1',
    job,
  }))
}

export async function observeGitHubActionsJobV1(
  job: GitHubActionsJobEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  assertJob(job)
  assertDecimal('observation_generation', observation_generation)

  const evidence_hash = await evidenceHash(job)

  if (job.status !== 'completed') {
    return {
      schema_version: PROVIDER_MESH_SCHEMA_VERSION,
      provider_id: 'github-actions',
      state: 'UNKNOWN',
      observed_capabilities: [],
      evidence_hash,
      observation_generation,
      authority_effect: 'NONE',
    }
  }

  // Any completed job that was assigned to a real runner and executed at
  // least one step proves the runner/workflow substrate was available.
  // The workload may still have failed; that is not provider unavailability.
  if (job.runner_id > 0 && job.steps_count > 0) {
    return {
      schema_version: PROVIDER_MESH_SCHEMA_VERSION,
      provider_id: 'github-actions',
      state: 'OBSERVED_AVAILABLE',
      observed_capabilities: ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW'],
      evidence_hash,
      observation_generation,
      authority_effect: 'NONE',
    }
  }

  // A terminal job that never obtained a runner and executed no steps is a
  // pre-start infrastructure failure. This is the exact runner_id=0 / steps=[]
  // condition currently visible on the affected AEGIS workflows.
  if (job.runner_id === 0 && job.steps_count === 0) {
    return {
      schema_version: PROVIDER_MESH_SCHEMA_VERSION,
      provider_id: 'github-actions',
      state: 'OBSERVED_UNAVAILABLE',
      observed_capabilities: ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW'],
      evidence_hash,
      observation_generation,
      authority_effect: 'NONE',
    }
  }

  // Ambiguous terminal metadata fails closed rather than inventing a provider
  // availability conclusion.
  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'github-actions',
    state: 'UNKNOWN',
    observed_capabilities: [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
