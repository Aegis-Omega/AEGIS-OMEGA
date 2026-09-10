import { createHash } from 'node:crypto'

import type { Dlss5RuntimeProbeEvidence } from './dlss5-runtime.js'

export type Dlss5AcquisitionConfig = {
  candidate_sha: string
  capability_receipt_digest: string
  streamline_version: string
  streamline_plugin_path: string
  gpu_pci_bus_id?: string
}

export type Dlss5AcquisitionIo = {
  queryGpu: () => { ok: boolean; stdout: string; error?: string }
  readPlugin: (path: string) => Uint8Array | null
  now: () => string
}

type AcquisitionBlocked = {
  status: 'ACQUISITION_BLOCKED'
  execution_release: 'BLOCKED'
  runtime_claim: 'NOT_ESTABLISHED'
  rendering_claim: 'NOT_ESTABLISHED'
  claim_promotion: 'BLOCKED'
  authority_effect: 'NONE'
  reason_codes: string[]
}

type AcquisitionCaptured = {
  status: 'EVIDENCE_CAPTURED'
  execution_release: 'BLOCKED_PENDING_RUNTIME_EXECUTION'
  runtime_claim: 'NOT_ESTABLISHED'
  rendering_claim: 'NOT_ESTABLISHED'
  claim_promotion: 'BLOCKED'
  authority_effect: 'NONE'
  reason_codes: []
  gpu_pci_bus_id: string
  gpu_query_digest: string
  acquisition_receipt_digest: string
  evidence: Dlss5RuntimeProbeEvidence
}

export type Dlss5AcquisitionResult = AcquisitionBlocked | AcquisitionCaptured

export const DLSS5_ACQUISITION_CONTRACT = Object.freeze({
  schema: 'AEGIS_DLSS5_ACQUISITION_CONTRACT_V1',
  purpose: 'Capture local, read-only pre-runtime evidence for a later independently governed DLSS 5 runtime probe.',
  nvidia_smi: Object.freeze({
    command: 'nvidia-smi',
    args: Object.freeze([
      '--query-gpu=name,driver_version,pci.bus_id',
      '--format=csv,noheader,nounits',
    ]),
  }),
  required_plugin: 'sl.dlss_nr',
  minimum_streamline_version: '2.14.0',
  supported_hardware_scope: 'GeForce RTX 50 Series GPUs',
  network_access: false,
  dependency_mutation: false,
  rendering: false,
  runtime_execution: false,
  runtime_claim_on_capture: 'NOT_ESTABLISHED',
  rendering_claim_on_capture: 'NOT_ESTABLISHED',
  authority_effect: 'NONE',
} as const)

const SHA256 = /^sha256:[0-9a-f]{64}$/
const COMMIT_SHA = /^[0-9a-f]{40}$/

function blocked(reasonCodes: string[]): AcquisitionBlocked {
  return {
    status: 'ACQUISITION_BLOCKED',
    execution_release: 'BLOCKED',
    runtime_claim: 'NOT_ESTABLISHED',
    rendering_claim: 'NOT_ESTABLISHED',
    claim_promotion: 'BLOCKED',
    authority_effect: 'NONE',
    reason_codes: reasonCodes,
  }
}

function versionAtLeast2140(value: string): boolean {
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

function digest(value: string | Uint8Array): string {
  return `sha256:${createHash('sha256').update(value).digest('hex')}`
}

type GpuRow = {
  model: string
  driver_version: string
  pci_bus_id: string
}

function parseGpuRows(stdout: string): GpuRow[] | null {
  const lines = stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  const rows: GpuRow[] = []
  for (const line of lines) {
    const columns = line.split(',').map((part) => part.trim())
    if (columns.length !== 3 || columns.some((part) => part.length === 0)) return null
    rows.push({ model: columns[0], driver_version: columns[1], pci_bus_id: columns[2] })
  }
  return rows
}

function selectGpu(rows: GpuRow[], requestedBusId?: string): { row?: GpuRow; reason?: string } {
  if (rows.length === 0) return { reason: 'GPU_QUERY_EMPTY' }
  if (requestedBusId) {
    const matches = rows.filter((row) => row.pci_bus_id.toLowerCase() === requestedBusId.trim().toLowerCase())
    if (matches.length !== 1) return { reason: matches.length === 0 ? 'GPU_SELECTION_NOT_FOUND' : 'GPU_SELECTION_AMBIGUOUS' }
    return { row: matches[0] }
  }
  if (rows.length !== 1) return { reason: 'GPU_SELECTION_AMBIGUOUS' }
  return { row: rows[0] }
}

function validPluginPath(path: string): boolean {
  const basename = path.split(/[\\/]/).pop() ?? ''
  return /^sl\.dlss_nr(?:\.[A-Za-z0-9_-]+)?$/i.test(basename)
}

export function acquireDlss5Evidence(
  config: Dlss5AcquisitionConfig,
  io: Dlss5AcquisitionIo,
): Dlss5AcquisitionResult {
  const configReasons: string[] = []
  if (!COMMIT_SHA.test(config.candidate_sha)) configReasons.push('CANDIDATE_SHA_INVALID')
  if (!SHA256.test(config.capability_receipt_digest)) configReasons.push('CAPABILITY_RECEIPT_DIGEST_INVALID')
  if (!versionAtLeast2140(config.streamline_version)) configReasons.push('STREAMLINE_VERSION_UNSUPPORTED')
  if (!config.streamline_plugin_path || !validPluginPath(config.streamline_plugin_path)) configReasons.push('DLSS5_PLUGIN_PATH_INVALID')
  if (configReasons.length > 0) return blocked(configReasons)

  let query: ReturnType<Dlss5AcquisitionIo['queryGpu']>
  try {
    query = io.queryGpu()
  } catch {
    return blocked(['NVIDIA_SMI_UNAVAILABLE'])
  }
  if (!query.ok) return blocked(['NVIDIA_SMI_UNAVAILABLE'])

  const normalizedQuery = query.stdout.trim()
  const rows = parseGpuRows(normalizedQuery)
  if (!rows) return blocked(['GPU_QUERY_INVALID'])

  const selected = selectGpu(rows, config.gpu_pci_bus_id)
  if (!selected.row) return blocked([selected.reason ?? 'GPU_SELECTION_INVALID'])

  const gpu = selected.row
  if (!/\bgeforce\s+rtx\s+50/i.test(gpu.model)) return blocked(['DLSS5_HARDWARE_UNSUPPORTED'])
  if (!gpu.driver_version) return blocked(['DRIVER_VERSION_MISSING'])

  let pluginBytes: Uint8Array | null
  try {
    pluginBytes = io.readPlugin(config.streamline_plugin_path)
  } catch {
    return blocked(['DLSS5_PLUGIN_UNAVAILABLE'])
  }
  if (!pluginBytes) return blocked(['DLSS5_PLUGIN_UNAVAILABLE'])
  if (pluginBytes.byteLength === 0) return blocked(['DLSS5_PLUGIN_EMPTY'])

  const capturedAt = io.now()
  if (!Number.isFinite(Date.parse(capturedAt))) return blocked(['CAPTURE_TIMESTAMP_INVALID'])

  const pluginDigest = digest(pluginBytes)
  const gpuQueryDigest = digest(normalizedQuery)
  const observationBinding = {
    schema: 'AEGIS_DLSS5_PRE_RUNTIME_OBSERVATION_BINDING_V1',
    candidate_sha: config.candidate_sha,
    capability_receipt_digest: config.capability_receipt_digest,
    captured_at: capturedAt,
    gpu: {
      vendor: 'NVIDIA',
      model: gpu.model,
      driver_version: gpu.driver_version,
      pci_bus_id: gpu.pci_bus_id,
    },
    streamline: {
      version: config.streamline_version,
      plugin: 'sl.dlss_nr',
      plugin_digest: pluginDigest,
    },
    gpu_query_digest: gpuQueryDigest,
    checks: {
      hardware_eligible: true,
      plugin_present: true,
      feature_query: 'ERROR',
      evaluation_executed: false,
    },
  }
  const observationDigest = digest(canonicalize(observationBinding))

  const evidence: Dlss5RuntimeProbeEvidence = {
    schema: 'AEGIS_DLSS5_RUNTIME_PROBE_EVIDENCE_V1',
    candidate_sha: config.candidate_sha,
    capability_receipt_digest: config.capability_receipt_digest,
    observation_digest: observationDigest,
    captured_at: capturedAt,
    gpu: {
      vendor: 'NVIDIA',
      model: gpu.model,
      driver_version: gpu.driver_version,
    },
    streamline: {
      version: config.streamline_version,
      plugin: 'sl.dlss_nr',
      plugin_digest: pluginDigest,
    },
    checks: {
      hardware_eligible: true,
      plugin_present: true,
      feature_query: 'ERROR',
      evaluation_executed: false,
    },
  }

  const receiptPayload = {
    schema: 'AEGIS_DLSS5_ACQUISITION_RECEIPT_V1',
    candidate_sha: config.candidate_sha,
    capability_receipt_digest: config.capability_receipt_digest,
    observation_digest: observationDigest,
    gpu_pci_bus_id: gpu.pci_bus_id,
    gpu_query_digest: gpuQueryDigest,
    plugin_digest: pluginDigest,
    captured_at: capturedAt,
    runtime_claim: 'NOT_ESTABLISHED',
    rendering_claim: 'NOT_ESTABLISHED',
    authority_effect: 'NONE',
  }

  return {
    status: 'EVIDENCE_CAPTURED',
    execution_release: 'BLOCKED_PENDING_RUNTIME_EXECUTION',
    runtime_claim: 'NOT_ESTABLISHED',
    rendering_claim: 'NOT_ESTABLISHED',
    claim_promotion: 'BLOCKED',
    authority_effect: 'NONE',
    reason_codes: [],
    gpu_pci_bus_id: gpu.pci_bus_id,
    gpu_query_digest: gpuQueryDigest,
    acquisition_receipt_digest: digest(canonicalize(receiptPayload)),
    evidence,
  }
}
