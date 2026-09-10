export type Dlss5RuntimeProbeEvidence = {
  schema: 'AEGIS_DLSS5_RUNTIME_PROBE_EVIDENCE_V1'
  candidate_sha: string
  capability_receipt_digest: string
  observation_digest: string
  captured_at: string
  gpu: {
    vendor: string
    model: string
    driver_version: string
  }
  streamline: {
    version: string
    plugin: string
    plugin_digest: string
  }
  checks: {
    hardware_eligible: boolean
    plugin_present: boolean
    feature_query: 'SUPPORTED' | 'UNSUPPORTED' | 'ERROR'
    evaluation_executed: boolean
  }
}

export type Dlss5RuntimeProbeStatus =
  | 'RUNTIME_PROBE_NOT_VERIFIED'
  | 'RUNTIME_PROBE_REJECTED'
  | 'RUNTIME_PROBE_OBSERVED'

export type Dlss5RuntimeProbeVerification = {
  status: Dlss5RuntimeProbeStatus
  execution_release: 'BLOCKED' | 'BLOCKED_PENDING_INDEPENDENT_REPLAY'
  rendering_claim: 'NOT_ESTABLISHED'
  claim_promotion: 'BLOCKED'
  authority_effect: 'NONE'
  reason_codes: string[]
  candidate_sha?: string
  capability_receipt_digest?: string
  observation_digest?: string
}

export const DLSS5_RUNTIME_CONTRACT = Object.freeze({
  schema: 'AEGIS_DLSS5_RUNTIME_CONTRACT_V1',
  purpose: 'Verify a content-addressed DLSS 5 runtime observation without granting execution or rendering-truth authority.',
  required_bindings: Object.freeze([
    'candidate_sha',
    'capability_receipt_digest',
    'observation_digest',
    'gpu.vendor',
    'gpu.model',
    'gpu.driver_version',
    'streamline.version',
    'streamline.plugin',
    'streamline.plugin_digest',
    'checks.hardware_eligible',
    'checks.plugin_present',
    'checks.feature_query',
    'checks.evaluation_executed',
  ]),
  minimum_streamline_version: '2.14.0',
  required_plugin: 'sl.dlss_nr',
  supported_hardware_scope: 'GeForce RTX 50 Series GPUs',
  observed_status: 'RUNTIME_PROBE_OBSERVED',
  rendering_claim_on_observation: 'NOT_ESTABLISHED',
  authority_effect: 'NONE',
} as const)

const SHA256 = /^sha256:[0-9a-f]{64}$/
const COMMIT_SHA = /^[0-9a-f]{40}$/

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function validTimestamp(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && Number.isFinite(Date.parse(value))
}

function versionAtLeast2140(value: unknown): boolean {
  if (typeof value !== 'string') return false
  const match = value.match(/^(\d+)\.(\d+)\.(\d+)$/)
  if (!match) return false
  const major = Number(match[1])
  const minor = Number(match[2])
  const patch = Number(match[3])
  return major > 2 || (major === 2 && (minor > 14 || (minor === 14 && patch >= 0)))
}

function failure(
  status: 'RUNTIME_PROBE_NOT_VERIFIED' | 'RUNTIME_PROBE_REJECTED',
  reasonCodes: string[],
  binding: Partial<Pick<Dlss5RuntimeProbeVerification, 'candidate_sha' | 'capability_receipt_digest' | 'observation_digest'>> = {},
): Dlss5RuntimeProbeVerification {
  return {
    status,
    execution_release: 'BLOCKED',
    rendering_claim: 'NOT_ESTABLISHED',
    claim_promotion: 'BLOCKED',
    authority_effect: 'NONE',
    reason_codes: reasonCodes,
    ...binding,
  }
}

export function verifyDlss5RuntimeProbe(input: unknown): Dlss5RuntimeProbeVerification {
  if (!isRecord(input)) return failure('RUNTIME_PROBE_NOT_VERIFIED', ['RUNTIME_EVIDENCE_MISSING'])
  if (input['schema'] !== 'AEGIS_DLSS5_RUNTIME_PROBE_EVIDENCE_V1') {
    return failure('RUNTIME_PROBE_NOT_VERIFIED', ['RUNTIME_EVIDENCE_INVALID'])
  }

  const candidateSha = input['candidate_sha']
  const capabilityReceiptDigest = input['capability_receipt_digest']
  const observationDigest = input['observation_digest']
  const capturedAt = input['captured_at']
  const gpu = input['gpu']
  const streamline = input['streamline']
  const checks = input['checks']

  if (
    typeof candidateSha !== 'string' || !COMMIT_SHA.test(candidateSha) ||
    typeof capabilityReceiptDigest !== 'string' || !SHA256.test(capabilityReceiptDigest) ||
    typeof observationDigest !== 'string' || !SHA256.test(observationDigest) ||
    !validTimestamp(capturedAt) ||
    !isRecord(gpu) || !isRecord(streamline) || !isRecord(checks)
  ) {
    return failure('RUNTIME_PROBE_NOT_VERIFIED', ['RUNTIME_EVIDENCE_INVALID'])
  }

  const binding = {
    candidate_sha: candidateSha,
    capability_receipt_digest: capabilityReceiptDigest,
    observation_digest: observationDigest,
  }
  const reasons: string[] = []

  const vendor = gpu['vendor']
  const model = gpu['model']
  const driverVersion = gpu['driver_version']
  if (!(typeof vendor === 'string' && /nvidia/i.test(vendor) && typeof model === 'string' && /\bgeforce\s+rtx\s+50/i.test(model))) {
    reasons.push('DLSS5_HARDWARE_UNSUPPORTED')
  }
  if (typeof driverVersion !== 'string' || driverVersion.trim().length === 0) reasons.push('DRIVER_VERSION_MISSING')

  if (!versionAtLeast2140(streamline['version'])) reasons.push('STREAMLINE_VERSION_UNSUPPORTED')
  if (streamline['plugin'] !== 'sl.dlss_nr') reasons.push('DLSS5_PLUGIN_MISMATCH')
  if (typeof streamline['plugin_digest'] !== 'string' || !SHA256.test(streamline['plugin_digest'])) {
    reasons.push('DLSS5_PLUGIN_DIGEST_INVALID')
  }

  if (checks['hardware_eligible'] !== true) reasons.push('HARDWARE_ELIGIBILITY_NOT_OBSERVED')
  if (checks['plugin_present'] !== true) reasons.push('DLSS5_PLUGIN_NOT_OBSERVED')
  if (checks['feature_query'] !== 'SUPPORTED') reasons.push('DLSS5_FEATURE_QUERY_NOT_SUPPORTED')
  if (checks['evaluation_executed'] !== true) reasons.push('RUNTIME_EVALUATION_NOT_EXECUTED')

  if (reasons.length > 0) return failure('RUNTIME_PROBE_REJECTED', reasons, binding)

  return {
    status: 'RUNTIME_PROBE_OBSERVED',
    execution_release: 'BLOCKED_PENDING_INDEPENDENT_REPLAY',
    rendering_claim: 'NOT_ESTABLISHED',
    claim_promotion: 'BLOCKED',
    authority_effect: 'NONE',
    reason_codes: [],
    ...binding,
  }
}
