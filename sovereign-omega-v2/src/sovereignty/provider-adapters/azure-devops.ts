/** Azure DevOps Pipeline Run + Build Timeline Job -> existing Sovereign Provider Mesh.
 * This normalized evidence is UNTRUSTED until source API reads are verified by
 * a caller with Azure DevOps vso.build permission. The local SHA-256 checksum
 * is NOT an Azure signature, execution authority, or quota/credit receipt.
 * Run: GET /{project}/_apis/pipelines/{pipelineId}/runs/{runId}
 * Timeline: GET /{project}/_apis/build/builds/{runId}/timeline
 */
import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import { PROVIDER_MESH_SCHEMA_VERSION, type ProviderObservationV1 } from '../provider-mesh.js'

export interface AzureDevOpsJobEvidenceV1 {
  requested_organization: string
  run_organization: string
  requested_project: string
  run_project: string
  requested_pipeline_id: string
  run_pipeline_id: string
  run_id: string
  timeline_build_id: string
  expected_head_sha: string
  run_repository_version: string
  run_state: 'unknown' | 'inProgress' | 'canceling' | 'completed'
  run_result: 'unknown' | 'succeeded' | 'failed' | 'canceled' | null
  timeline_record_type: string
  timeline_job_state: 'pending' | 'inProgress' | 'completed'
  timeline_job_result: 'succeeded' | 'succeededWithIssues' | 'failed' | 'canceled' | 'skipped' | null
  worker_name: string | null
  job_started_at: string | null
  job_finished_at: string | null
}
const NAME = /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$/
const DECIMAL = /^(0|[1-9][0-9]*)$/
const SHA = /^[0-9a-f]{40}$/
const RUN_STATES = new Set(['unknown', 'inProgress', 'canceling', 'completed'])
const RUN_RESULTS = new Set(['unknown', 'succeeded', 'failed', 'canceled', null])
const JOB_STATES = new Set(['pending', 'inProgress', 'completed'])
const JOB_RESULTS = new Set(['succeeded', 'succeededWithIssues', 'failed', 'canceled', 'skipped', null])

function validateTimestamp(field: string, value: unknown): void {
  if (value === null) return
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(value)
      || !Number.isFinite(Date.parse(value))) throw new TypeError(field + ' must be a UTC timestamp or null')
}
function validate(input: AzureDevOpsJobEvidenceV1, generation: string): void {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new TypeError('missing Azure job evidence')
  for (const field of ['requested_organization', 'run_organization', 'requested_project', 'run_project'] as const) {
    if (typeof input[field] !== 'string' || !NAME.test(input[field])) throw new TypeError(field + ' must be an Azure path segment')
  }
  for (const field of ['requested_pipeline_id', 'run_pipeline_id', 'run_id', 'timeline_build_id'] as const) {
    if (typeof input[field] !== 'string' || !DECIMAL.test(input[field])) throw new TypeError(field + ' must be canonical decimal')
  }
  for (const field of ['expected_head_sha', 'run_repository_version'] as const) {
    if (typeof input[field] !== 'string' || !SHA.test(input[field])) throw new TypeError(field + ' must be lowercase Git SHA-1')
  }
  if (typeof generation !== 'string' || !DECIMAL.test(generation)) throw new TypeError('observation_generation must be canonical decimal')
  if (!RUN_STATES.has(input.run_state)) throw new TypeError('invalid Azure run state')
  if (!RUN_RESULTS.has(input.run_result)) throw new TypeError('invalid Azure run result')
  if (typeof input.timeline_record_type !== 'string') throw new TypeError('invalid Azure timeline record type')
  if (!JOB_STATES.has(input.timeline_job_state)) throw new TypeError('invalid Azure timeline job state')
  if (!JOB_RESULTS.has(input.timeline_job_result)) throw new TypeError('invalid Azure timeline job result')
  if (input.worker_name !== null && (typeof input.worker_name !== 'string' || input.worker_name.length > 128)) {
    throw new TypeError('worker_name must be bounded string or null')
  }
  validateTimestamp('job_started_at', input.job_started_at)
  validateTimestamp('job_finished_at', input.job_finished_at)
  if (input.job_started_at !== null && input.job_finished_at !== null &&
      Date.parse(input.job_finished_at) < Date.parse(input.job_started_at)) {
    throw new TypeError('job_finished_at must not precede job_started_at')
  }
}
/** Returns only metadata-level substrate availability, never admission.
 * Caller must bind authenticated GET Run and GET Timeline under SAME project,
 * verify independent Azure account identity and check actual spending/entitlement.
 * A successful historical job is NOT proof for any other requested SHA.
 */
export async function observeAzureDevOpsJobV1(
  evidence: AzureDevOpsJobEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  validate(evidence, observation_generation)
  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_AZURE_DEVOPS_JOB_EVIDENCE_V1', evidence,
  })) as SHA256Hex
  const bound = evidence.requested_organization === evidence.run_organization
    && evidence.requested_project === evidence.run_project
    && evidence.requested_pipeline_id === evidence.run_pipeline_id
    && evidence.run_id === evidence.timeline_build_id
    && evidence.run_repository_version === evidence.expected_head_sha
  const terminal = evidence.run_state === 'completed'
    && (evidence.run_result === 'succeeded' || evidence.run_result === 'failed')
    && evidence.timeline_record_type === 'Job'
    && evidence.timeline_job_state === 'completed'
    && (evidence.timeline_job_result === 'succeeded' || evidence.timeline_job_result === 'failed')
  const ranOnAgent = typeof evidence.worker_name === 'string'
    && evidence.worker_name.trim().length > 0
    && evidence.job_started_at !== null && evidence.job_finished_at !== null
  const available = bound && terminal && ranOnAgent
  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'azure-devops-pipelines',
    state: available ? 'OBSERVED_AVAILABLE' : 'UNKNOWN',
    observed_capabilities: available ? ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW'] : [],
    evidence_hash, observation_generation, authority_effect: 'NONE',
  }
}
