// ============================================================
// SOVEREIGN OMEGA — Polyglot Toolchain Detection Boundary
// EPISTEMIC TIER: T2 · capability evidence admission only
//
// The runtime planner never launches probes from this module. A harness or
// adapter-specific sandbox performs tool discovery and returns a typed
// observation. This module validates that observation and converts it into
// authority-neutral capability evidence, failing closed on absence or drift.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import {
  POLYGLOT_CAPABILITY_EVIDENCE_SCHEMA,
  POLYGLOT_FRONTIER_CATALOG,
  type ToolchainCapabilityEvidence,
} from './fabric.js'

export const POLYGLOT_DETECTION_OBSERVATION_SCHEMA =
  'AEGIS-POLYGLOT-DETECTION-OBSERVATION-V1' as const

export interface ToolchainDetectorSpec {
  readonly toolchain_id: string
  readonly probe_locator: string
  readonly version_probe: readonly string[]
  readonly digest_algorithm: 'SHA-256'
  readonly capability_receipt_required: true
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface ToolchainDetectionObservation {
  readonly schema_version: typeof POLYGLOT_DETECTION_OBSERVATION_SCHEMA
  readonly toolchain_id: string
  readonly detected: boolean
  readonly toolchain_version: string | null
  readonly executable_digest_sha256: string | null
  readonly capability_receipt_digest: string | null
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

const SHA256_RE = /^[0-9a-f]{64}$/

const DETECTOR_DETAILS: Readonly<Record<string, {
  readonly probe_locator: string
  readonly version_probe: readonly string[]
}>> = deepFreeze({
  unison: { probe_locator: 'unison', version_probe: ['--version'] },
  egg: { probe_locator: 'egg', version_probe: ['--version'] },
  cvc5: { probe_locator: 'cvc5', version_probe: ['--version'] },
  'turing-jl': { probe_locator: 'julia:Turing', version_probe: ['package-version', 'Turing'] },
  lean4: { probe_locator: 'lean', version_probe: ['--version'] },
  rocq: { probe_locator: 'rocq', version_probe: ['--version'] },
  verus: { probe_locator: 'verus', version_probe: ['--version'] },
  triton: { probe_locator: 'python:triton', version_probe: ['package-version', 'triton'] },
  mlir: { probe_locator: 'mlir-opt', version_probe: ['--version'] },
  cudaq: { probe_locator: 'python:cudaq', version_probe: ['package-version', 'cudaq'] },
  lava: { probe_locator: 'python:lava', version_probe: ['package-version', 'lava-nc'] },
  sciml: { probe_locator: 'julia:SciMLBase', version_probe: ['package-version', 'SciMLBase'] },
  enzyme: { probe_locator: 'julia:Enzyme', version_probe: ['package-version', 'Enzyme'] },
})

export const TOOLCHAIN_DETECTOR_REGISTRY: readonly ToolchainDetectorSpec[] = deepFreeze(
  POLYGLOT_FRONTIER_CATALOG.map(entry => {
    const details = DETECTOR_DETAILS[entry.toolchain_id]
    if (!details) {
      throw new Error(`POLYGLOT_DETECTOR_SPEC_MISSING:${entry.toolchain_id}`)
    }
    return {
      toolchain_id: entry.toolchain_id,
      probe_locator: details.probe_locator,
      version_probe: [...details.version_probe],
      digest_algorithm: 'SHA-256' as const,
      capability_receipt_required: true as const,
      authority_class: 'NONE' as const,
      authority_effect: 'NONE' as const,
    }
  }),
)

const DETECTOR_BY_ID = new Map(
  TOOLCHAIN_DETECTOR_REGISTRY.map(spec => [spec.toolchain_id, spec] as const),
)

export class ToolchainDetectionError extends Error {
  override readonly name: string = 'ToolchainDetectionError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export class ToolchainUnavailableError extends ToolchainDetectionError {
  override readonly name = 'ToolchainUnavailableError'
  readonly code = 'TOOLCHAIN_UNAVAILABLE' as const

  constructor(toolchain_id: string) {
    super(`TOOLCHAIN_UNAVAILABLE:${toolchain_id}`)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export function buildToolchainDetectionSpec(toolchain_id: string): ToolchainDetectorSpec {
  const spec = DETECTOR_BY_ID.get(toolchain_id)
  if (!spec) {
    throw new ToolchainDetectionError(`UNKNOWN_TOOLCHAIN:${toolchain_id}`)
  }
  return spec
}

export function admitDetectedToolchain(
  observation: ToolchainDetectionObservation,
): ToolchainCapabilityEvidence {
  if (observation.schema_version !== POLYGLOT_DETECTION_OBSERVATION_SCHEMA) {
    throw new ToolchainDetectionError(`SCHEMA_MISMATCH:${observation.toolchain_id}`)
  }
  if (!DETECTOR_BY_ID.has(observation.toolchain_id)) {
    throw new ToolchainDetectionError(`UNKNOWN_TOOLCHAIN:${observation.toolchain_id}`)
  }
  if (observation.authority_class !== 'NONE' || observation.authority_effect !== 'NONE') {
    throw new ToolchainDetectionError(`AUTHORITY_SPLICE_REJECTED:${observation.toolchain_id}`)
  }
  if (!observation.detected) {
    throw new ToolchainUnavailableError(observation.toolchain_id)
  }
  if (
    observation.toolchain_version === null ||
    observation.toolchain_version.trim().length === 0
  ) {
    throw new ToolchainDetectionError(`INVALID_TOOLCHAIN_VERSION:${observation.toolchain_id}`)
  }
  if (
    observation.executable_digest_sha256 === null ||
    !SHA256_RE.test(observation.executable_digest_sha256)
  ) {
    throw new ToolchainDetectionError(`INVALID_EXECUTABLE_DIGEST:${observation.toolchain_id}`)
  }
  if (
    observation.capability_receipt_digest === null ||
    !SHA256_RE.test(observation.capability_receipt_digest)
  ) {
    throw new ToolchainDetectionError(`INVALID_CAPABILITY_RECEIPT:${observation.toolchain_id}`)
  }

  return deepFreeze<ToolchainCapabilityEvidence>({
    schema_version: POLYGLOT_CAPABILITY_EVIDENCE_SCHEMA,
    toolchain_id: observation.toolchain_id,
    status: 'VERIFIED_AVAILABLE',
    toolchain_version: observation.toolchain_version,
    executable_digest_sha256: observation.executable_digest_sha256,
    source_receipt_digest: observation.capability_receipt_digest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })
}
