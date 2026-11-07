/**
 * Read-only projection of an existing AEGIS Bridge execution.
 *
 * work_id and expected_source_sha are caller selectors, NEVER proof of a
 * worker, source provenance, artifact, or admission. The bridge currently
 * exposes an execution status but does not attest these identities.
 * Keep these dimensions UNKNOWN unless actual independently bound evidence
 * becomes available. This adapter has no network, storage or authority side
 * effects and does not construct another task ledger.
 */

type Dict = Record<string, unknown>
export type LabObservation = {
  work_id: string
  execution_id: string
  expected_source_sha: string
  observation: 'RUNNING' | 'FAILED' | 'COMPLETE_UNVERIFIED' | 'UNKNOWN' | 'REJECTED'
  bridge_status: 'pending' | 'running' | 'complete' | 'error' | 'UNKNOWN'
  source_binding: 'UNKNOWN' | 'UNATTESTED_MATCH' | 'MISMATCH'
  worker_identity: 'UNKNOWN'
  artifact_evidence: 'UNKNOWN' | 'UNATTESTED_CLAIM'
  independent_verification: 'NOT_RUN'
  admission: 'NOT_ADMITTED'
  reason: string
}

function object(value: unknown): Dict | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Dict : null
}

export function projectLabObservation(
  payload: unknown,
  requested: { work_id: string; execution_id: string; expected_source_sha: string },
): LabObservation {
  const baseline: LabObservation = {
    work_id: requested.work_id,
    execution_id: requested.execution_id,
    expected_source_sha: requested.expected_source_sha,
    observation: 'UNKNOWN',
    bridge_status: 'UNKNOWN',
    source_binding: 'UNKNOWN',
    worker_identity: 'UNKNOWN',
    artifact_evidence: 'UNKNOWN',
    independent_verification: 'NOT_RUN',
    admission: 'NOT_ADMITTED',
    reason: 'BACKEND_EVIDENCE_INSUFFICIENT',
  }
  const envelope = object(payload)
  const data = envelope ? object(envelope['data']) : null
  if (!envelope || !data || envelope['contract_version'] !== '1.0.0') {
    return { ...baseline, observation: 'REJECTED', reason: 'INVALID_PROVIDER_ENVELOPE' }
  }
  if (envelope['execution_id'] !== requested.execution_id ||
      data['execution_id'] !== requested.execution_id) {
    return { ...baseline, observation: 'REJECTED', reason: 'EXECUTION_ID_MISMATCH' }
  }
  // Optional metadata is an observed claim, not an attestation. Explicit
  // contradictions reject the entire envelope rather than being ignored.
  if (data['work_id'] !== undefined && data['work_id'] !== requested.work_id) {
    return { ...baseline, observation: 'REJECTED', reason: 'WORK_ID_MISMATCH' }
  }
  if (data['source_sha'] !== undefined && data['source_sha'] !== requested.expected_source_sha) {
    return { ...baseline, observation: 'REJECTED', source_binding: 'MISMATCH', reason: 'SOURCE_SHA_MISMATCH' }
  }
  const source_binding = data['source_sha'] === requested.expected_source_sha
    ? 'UNATTESTED_MATCH' : 'UNKNOWN'
  const status = data['status']
  if (status !== 'pending' && status !== 'running' && status !== 'complete' && status !== 'error') {
    return { ...baseline, source_binding, observation: 'REJECTED', reason: 'INVALID_BRIDGE_STATUS' }
  }
  const artifact = object(data['result'])
  const artifact_evidence = artifact && typeof artifact['artifact_sha256'] === 'string' &&
    /^[0-9a-f]{64}$/.test(artifact['artifact_sha256'])
    ? 'UNATTESTED_CLAIM' : 'UNKNOWN'
  if (status === 'pending' || status === 'running') {
    return { ...baseline, bridge_status: status, source_binding, observation: 'RUNNING',
      reason: 'EXECUTION_NOT_TERMINAL' }
  }
  if (status === 'error') {
    return { ...baseline, bridge_status: status, source_binding, observation: 'FAILED',
      reason: 'PROVIDER_REPORTED_ERROR' }
  }
  return { ...baseline, bridge_status: status, source_binding, artifact_evidence,
    observation: 'COMPLETE_UNVERIFIED', reason: 'NO_INDEPENDENT_SOURCE_OR_ARTIFACT_ATTESTATION' }
}
