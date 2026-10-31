// GitLab CI REST metadata -> existing AEGIS Sovereign Provider Mesh.
// This is a content-hashed local observation, NOT GitLab-signed attestation,
// an Azure/GitLab subscription grant or permission to execute a job.
// Source: GET /projects/:id/pipelines/:pipeline_id and /jobs for same project.

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export interface GitLabCiJobEvidenceV1 {
  project_id: string
  pipeline_id: string
  job_id: string
  job_pipeline_id: string
  pipeline_head_sha: string
  job_head_sha: string
  expected_head_sha: string
  pipeline_status: 'created' | 'pending' | 'running' | 'success' | 'failed' | 'canceled' | 'skipped' | 'manual'
  job_status: 'created' | 'pending' | 'running' | 'success' | 'failed' | 'canceled' | 'skipped' | 'manual'
  runner_id: number | null
  started_at: string | null
  finished_at: string | null
}

const DECIMAL = /^(0|[1-9][0-9]*)$/
const GIT_SHA = /^[0-9a-f]{40}$/
const PIPELINE_STATES = new Set(['created','pending','running','success','failed','canceled','skipped','manual'])
const JOB_STATES = new Set(['created','pending','running','success','failed','canceled','skipped','manual'])

function validDecimal(s: unknown): boolean {
  return typeof s === 'string' && DECIMAL.test(s)
}
function validGitSha(s: unknown): boolean {
  return typeof s === 'string' && GIT_SHA.test(s)
}
function assertTimestamp(field: string, s: unknown): void {
  if (s === null) return
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(s) || !Number.isFinite(Date.parse(s))) {
    throw new TypeError(`${field} must be a UTC timestamp or null`)
  }
}
function validate(job: GitLabCiJobEvidenceV1, generation: string): void {
  if (!job || typeof job !== 'object') throw new TypeError('missing GitLab CI job evidence')
  for (const field of ['project_id','pipeline_id','job_id','job_pipeline_id'] as const) {
    if (!validDecimal(job[field])) throw new TypeError(`${field} must be canonical unsigned decimal`)
  }
  for (const field of ['pipeline_head_sha','job_head_sha','expected_head_sha'] as const) {
    if (!validGitSha(job[field])) throw new TypeError(`${field} must be lowercase Git SHA-1`)
  }
  if (!validDecimal(generation)) throw new TypeError('observation_generation must be canonical unsigned decimal')
  if (!PIPELINE_STATES.has(job.pipeline_status)) throw new TypeError('invalid GitLab pipeline status')
  if (!JOB_STATES.has(job.job_status)) throw new TypeError('invalid GitLab job status')
  if (job.runner_id !== null && (!Number.isSafeInteger(job.runner_id) || job.runner_id < 0)) {
    throw new TypeError('runner_id must be nonnegative safe integer or null')
  }
  assertTimestamp('started_at', job.started_at)
  assertTimestamp('finished_at', job.finished_at)
  if (job.started_at !== null && job.finished_at !== null
      && Date.parse(job.finished_at) < Date.parse(job.started_at)) {
    throw new TypeError('finished_at must not precede started_at')
  }
}

/** A trusted caller must independently fetch both GitLab REST records.
 * The SHA and project bindings here defend against cross-run or stale reuse.
 * The returned hash is NOT a signature or proof of API source authenticity.
 */
export async function observeGitLabCiJobV1(
  job: GitLabCiJobEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  validate(job, observation_generation)
  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_GITLAB_CI_JOB_EVIDENCE_V1', job,
  })) as SHA256Hex
  const boundToRequestedSource = job.pipeline_id === job.job_pipeline_id
    && job.pipeline_head_sha === job.job_head_sha
    && job.job_head_sha === job.expected_head_sha
  const terminalPipeline = job.pipeline_status === 'success' || job.pipeline_status === 'failed'
  const terminalJob = job.job_status === 'success' || job.job_status === 'failed'
  const runnerExecuted = typeof job.runner_id === 'number' && job.runner_id > 0
    && job.started_at !== null && job.finished_at !== null
  const verifiedExecutionMetadata = boundToRequestedSource && terminalPipeline
    && terminalJob && runnerExecuted
  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'gitlab-ci',
    state: verifiedExecutionMetadata ? 'OBSERVED_AVAILABLE' : 'UNKNOWN',
    observed_capabilities: verifiedExecutionMetadata
      ? ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW'] : [],
    evidence_hash, observation_generation, authority_effect: 'NONE',
  }
}
