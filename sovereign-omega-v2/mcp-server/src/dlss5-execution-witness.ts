import { createHash } from 'node:crypto'

export type Dlss5ExecutionWitnessEvidence = {
  schema: 'AEGIS_DLSS5_EXECUTION_WITNESS_EVIDENCE_V1'
  candidate_sha: string
  acquisition_receipt_digest: string
  probe_binary_digest: string
  probe_observation_digest: string
  captured_at: string
  gpu: {
    vendor: string
    model: string
    driver_version: string
    pci_bus_id: string
  }
  streamline: {
    version: string
    plugin: string
    plugin_digest: string
  }
  execution: {
    feature_query: 'SUPPORTED' | 'UNSUPPORTED' | 'ERROR'
    evaluation_executed: boolean
    evaluation_status: 'SUCCESS' | 'FAILED' | 'ERROR'
    native_probe_exit_code: number
  }
}

export type Dlss5ExecutionWitnessStatus =
  | 'EXECUTION_WITNESS_NOT_VERIFIED'
  | 'EXECUTION_WITNESS_REJECTED'
  | 'EXECUTION_WITNESS_OBSERVED'

export type Dlss5ExecutionWitnessVerification = {
  status: Dlss5ExecutionWitnessStatus
  execution_release: 'BLOCKED' | 'BLOCKED_PENDING_INDEPENDENT_REPLAY'
  runtime_execution: 'NOT_ESTABLISHED' | 'OBSERVED_FOR_DECLARED_PROBE_ONLY'
  rendering_claim: 'NOT_ESTABLISHED'
  quality_claim: 'NOT_ESTABLISHED'
  claim_promotion: 'BLOCKED'
  authority_effect: 'NONE'
  reason_codes: string[]
  candidate_sha?: string
  acquisition_receipt_digest?: string
  probe_observation_digest?: string
  witness_receipt_digest?: string
}

export const DLSS5_EXECUTION_WITNESS_CONTRACT = Object.freeze({
  schema: 'AEGIS_DLSS5_EXECUTION_WITNESS_CONTRACT_V1',
  purpose: 'Verify host-produced Streamline execution evidence without converting execution observation into rendering-truth authority.',
  required_plugin: 'sl.dlss_nr',
  minimum_streamline_version: '2.14.0',
  supported_hardware_scope: 'GeForce RTX 50 Series GPUs',
  required_execution_observations: Object.freeze([
    'feature_query',
    'evaluation_executed',
    'evaluation_status',
    'native_probe_exit_code',
  ]),
  positive_runtime_scope: 'OBSERVED_FOR_DECLARED_PROBE_ONLY',
  rendering_claim_on_observation: 'NOT_ESTABLISHED',
  quality_claim_on_observation: 'NOT_ESTABLISHED',
  execution_release_on_observation: 'BLOCKED_PENDING_INDEPENDENT_REPLAY',
  claim_promotion: 'BLOCKED',
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

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== undefined)
    .sort(([a], [b]) => a.localeCompare(b))
  return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${canonicalize(item)}`).join(',')}}`
}

function digest(value: unknown): string {
  return `sha256:${createHash('sha256').update(canonicalize(value), 'utf8').digest('hex')}`
}

function failure(
  status: 'EXECUTION_WITNESS_NOT_VERIFIED' | 'EXECUTION_WITNESS_REJECTED',
  reasonCodes: string[],
  binding: Partial<Pick<Dlss5ExecutionWitnessVerification, 'candidate_sha' | 'acquisition_receipt_digest' | 'probe_observation_digest'>> = {},
): Dlss5ExecutionWitnessVerification {
  return {
    status,
    execution_release: 'BLOCKED',
    runtime_execution: 'NOT_ESTABLISHED',
    rendering_claim: 'NOT_ESTABLISHED',
    quality_claim: 'NOT_ESTABLISHED',
    claim_promotion: 'BLOCKED',
    authority_effect: 'NONE',
    reason_codes: reasonCodes,
    ...binding,
  }
}

export function verifyDlss5ExecutionWitness(input: unknown): Dlss5ExecutionWitnessVerification {
  if (input === undefined || input === null) {
    return failure('EXECUTION_WITNESS_NOT_VERIFIED', ['EXECUTION_WITNESS_EVIDENCE_MISSING'])
  }
  if (!isRecord(input) || input['schema'] !== 'AEGIS_DLSS5_EXECUTION_WITNESS_EVIDENCE_V1') {
    return failure('EXECUTION_WITNESS_NOT_VERIFIED', ['EXECUTION_WITNESS_EVIDENCE_INVALID'])
  }

  const candidateSha = input['candidate_sha']
  const acquisitionReceiptDigest = input['acquisition_receipt_digest']
  const probeBinaryDigest = input['probe_binary_digest']
  const probeObservationDigest = input['probe_observation_digest']
  const capturedAt = input['captured_at']
  const gpu = input['gpu']
  const streamline = input['streamline']
  const execution = input['execution']

  if (
    typeof candidateSha !== 'string' || !COMMIT_SHA.test(candidateSha) ||
    typeof acquisitionReceiptDigest !== 'string' || !SHA256.test(acquisitionReceiptDigest) ||
    typeof probeBinaryDigest !== 'string' || !SHA256.test(probeBinaryDigest) ||
    typeof probeObservationDigest !== 'string' || !SHA256.test(probeObservationDigest) ||
    !validTimestamp(capturedAt) ||
    !isRecord(gpu) || !isRecord(streamline) || !isRecord(execution)
  ) {
    return failure('EXECUTION_WITNESS_NOT_VERIFIED', ['EXECUTION_WITNESS_EVIDENCE_INVALID'])
  }

  const binding = {
    candidate_sha: candidateSha,
    acquisition_receipt_digest: acquisitionReceiptDigest,
    probe_observation_digest: probeObservationDigest,
  }
  const reasons: string[] = []

  const vendor = gpu['vendor']
  const model = gpu['model']
  const driverVersion = gpu['driver_version']
  const pciBusId = gpu['pci_bus_id']
  if (!(typeof vendor === 'string' && /nvidia/i.test(vendor) && typeof model === 'string' && /\bgeforce\s+rtx\s+50/i.test(model))) {
    reasons.push('DLSS5_HARDWARE_UNSUPPORTED')
  }
  if (typeof driverVersion !== 'string' || driverVersion.trim().length === 0) reasons.push('DRIVER_VERSION_MISSING')
  if (typeof pciBusId !== 'string' || pciBusId.trim().length === 0) reasons.push('GPU_PCI_BUS_ID_MISSING')

  if (!versionAtLeast2140(streamline['version'])) reasons.push('STREAMLINE_VERSION_UNSUPPORTED')
  if (streamline['plugin'] !== 'sl.dlss_nr') reasons.push('DLSS5_PLUGIN_MISMATCH')
  if (typeof streamline['plugin_digest'] !== 'string' || !SHA256.test(streamline['plugin_digest'])) {
    reasons.push('DLSS5_PLUGIN_DIGEST_INVALID')
  }

  if (execution['feature_query'] !== 'SUPPORTED') reasons.push('DLSS5_FEATURE_QUERY_NOT_SUPPORTED')
  if (execution['evaluation_executed'] !== true) reasons.push('RUNTIME_EVALUATION_NOT_EXECUTED')
  if (execution['evaluation_status'] !== 'SUCCESS') reasons.push('RUNTIME_EVALUATION_NOT_SUCCESSFUL')
  if (!Number.isInteger(execution['native_probe_exit_code']) || execution['native_probe_exit_code'] !== 0) {
    reasons.push('NATIVE_PROBE_EXIT_NONZERO')
  }

  if (reasons.length > 0) return failure('EXECUTION_WITNESS_REJECTED', reasons, binding)

  const receiptPayload = {
    schema: 'AEGIS_DLSS5_EXECUTION_WITNESS_RECEIPT_V1',
    candidate_sha: candidateSha,
    acquisition_receipt_digest: acquisitionReceiptDigest,
    probe_binary_digest: probeBinaryDigest,
    probe_observation_digest: probeObservationDigest,
    captured_at: capturedAt,
    gpu: {
      vendor,
      model,
      driver_version: driverVersion,
      pci_bus_id: pciBusId,
    },
    streamline: {
      version: streamline['version'],
      plugin: streamline['plugin'],
      plugin_digest: streamline['plugin_digest'],
    },
    execution: {
      feature_query: execution['feature_query'],
      evaluation_executed: execution['evaluation_executed'],
      evaluation_status: execution['evaluation_status'],
      native_probe_exit_code: execution['native_probe_exit_code'],
    },
    runtime_execution: 'OBSERVED_FOR_DECLARED_PROBE_ONLY',
    rendering_claim: 'NOT_ESTABLISHED',
    quality_claim: 'NOT_ESTABLISHED',
    authority_effect: 'NONE',
  }

  return {
    status: 'EXECUTION_WITNESS_OBSERVED',
    execution_release: 'BLOCKED_PENDING_INDEPENDENT_REPLAY',
    runtime_execution: 'OBSERVED_FOR_DECLARED_PROBE_ONLY',
    rendering_claim: 'NOT_ESTABLISHED',
    quality_claim: 'NOT_ESTABLISHED',
    claim_promotion: 'BLOCKED',
    authority_effect: 'NONE',
    reason_codes: [],
    ...binding,
    witness_receipt_digest: digest(receiptPayload),
  }
}
