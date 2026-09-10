import { createHash } from 'node:crypto'

export type Dlss5EnvironmentManifest = {
  schema: 'AEGIS_ENVIRONMENT_MANIFEST_V1'
  gpu: {
    vendor: string
    model: string
  }
  source_digest: string
  captured_at: string
}

export type Dlss5CapabilityStatus =
  | 'NOT_VERIFIED'
  | 'UNSUPPORTED'
  | 'ELIGIBLE_FOR_RUNTIME_PROBE'

export type Dlss5Capability = {
  status: Dlss5CapabilityStatus
  execution_release: 'BLOCKED' | 'BLOCKED_PENDING_RUNTIME_PROBE'
  claim_promotion: 'BLOCKED'
  authority_effect: 'NONE'
  reason_codes: string[]
  observed_gpu?: {
    vendor: string
    model: string
  }
  environment_source_digest?: string
}

export const DLSS5_REFERENCE = Object.freeze({
  schema: 'AEGIS_NVIDIA_DLSS5_REFERENCE_V1',
  technology: 'NVIDIA DLSS 5',
  feature: '3D-Guided Neural Rendering',
  release_date: '2026-09-01',
  supported_hardware_scope: 'GeForce RTX 50 Series GPUs',
  streamline: Object.freeze({
    plugin: 'sl.dlss_nr',
    first_supported_release: '2.14.0',
    tracked_release: '2.14.1',
  }),
  sources: Object.freeze([
    'https://www.nvidia.com/en-eu/geforce/news/dlss-5-3d-guided-neural-rendering/',
    'https://www.nvidia.com/en-us/geforce/technologies/dlss/',
    'https://github.com/NVIDIA-RTX/Streamline/releases/tag/v2.14.1',
  ]),
  evidence_status: 'REFERENCE_SNAPSHOT',
  authority_effect: 'NONE',
} as const)

const SHA256 = /^sha256:[0-9a-f]{64}$/

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isValidTimestamp(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0 && Number.isFinite(Date.parse(value))
}

function parseManifest(input: unknown): Dlss5EnvironmentManifest | null {
  if (!isRecord(input) || input['schema'] !== 'AEGIS_ENVIRONMENT_MANIFEST_V1') return null
  const gpu = input['gpu']
  if (!isRecord(gpu)) return null
  const vendor = gpu['vendor']
  const model = gpu['model']
  const sourceDigest = input['source_digest']
  const capturedAt = input['captured_at']

  if (typeof vendor !== 'string' || vendor.trim().length === 0) return null
  if (typeof model !== 'string' || model.trim().length === 0) return null
  if (typeof sourceDigest !== 'string' || !SHA256.test(sourceDigest)) return null
  if (!isValidTimestamp(capturedAt)) return null

  return {
    schema: 'AEGIS_ENVIRONMENT_MANIFEST_V1',
    gpu: { vendor: vendor.trim(), model: model.trim() },
    source_digest: sourceDigest,
    captured_at: capturedAt,
  }
}

function supportsDlss5Gpu(vendor: string, model: string): boolean {
  return /nvidia/i.test(vendor) && /\bgeforce\s+rtx\s+50/i.test(model)
}

export function evaluateDlss5Capability(input: unknown): Dlss5Capability {
  if (input === undefined || input === null) {
    return {
      status: 'NOT_VERIFIED',
      execution_release: 'BLOCKED',
      claim_promotion: 'BLOCKED',
      authority_effect: 'NONE',
      reason_codes: ['ENVIRONMENT_MANIFEST_MISSING'],
    }
  }

  const manifest = parseManifest(input)
  if (!manifest) {
    return {
      status: 'NOT_VERIFIED',
      execution_release: 'BLOCKED',
      claim_promotion: 'BLOCKED',
      authority_effect: 'NONE',
      reason_codes: ['ENVIRONMENT_MANIFEST_INVALID'],
    }
  }

  const base = {
    claim_promotion: 'BLOCKED' as const,
    authority_effect: 'NONE' as const,
    observed_gpu: manifest.gpu,
    environment_source_digest: manifest.source_digest,
  }

  if (!supportsDlss5Gpu(manifest.gpu.vendor, manifest.gpu.model)) {
    return {
      ...base,
      status: 'UNSUPPORTED',
      execution_release: 'BLOCKED',
      reason_codes: ['DLSS5_HARDWARE_UNSUPPORTED'],
    }
  }

  return {
    ...base,
    status: 'ELIGIBLE_FOR_RUNTIME_PROBE',
    execution_release: 'BLOCKED_PENDING_RUNTIME_PROBE',
    reason_codes: [],
  }
}

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`
  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== undefined)
    .sort(([a], [b]) => a.localeCompare(b))
  return `{${entries.map(([key, item]) => `${JSON.stringify(key)}:${canonicalize(item)}`).join(',')}}`
}

export function buildDlss5Receipt(input: unknown): {
  schema: 'AEGIS_DLSS5_CAPABILITY_RECEIPT_V1'
  canonicalization: 'AEGIS_SORTED_JSON_V1'
  reference: typeof DLSS5_REFERENCE
  capability: Dlss5Capability
  receipt_digest: string
  authority_effect: 'NONE'
} {
  const payload = {
    schema: 'AEGIS_DLSS5_CAPABILITY_RECEIPT_V1' as const,
    canonicalization: 'AEGIS_SORTED_JSON_V1' as const,
    reference: DLSS5_REFERENCE,
    capability: evaluateDlss5Capability(input),
    authority_effect: 'NONE' as const,
  }
  const receiptDigest = `sha256:${createHash('sha256').update(canonicalize(payload), 'utf8').digest('hex')}`
  return { ...payload, receipt_digest: receiptDigest }
}
