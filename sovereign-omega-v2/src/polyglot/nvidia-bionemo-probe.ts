// ============================================================
// SOVEREIGN OMEGA — NVIDIA BioNeMo Framework Runtime Probe
// EPISTEMIC TIER: T2 · observation production only
//
// BioNeMo Framework and BioNeMo Inference Runtime are intentionally probed
// separately. Framework presence never implies BioIR/GPU execution.
// ============================================================

import { createHash } from 'node:crypto'
import { hashValue } from '../core/hashing.js'
import {
  NVIDIA_DETECTION_OBSERVATION_SCHEMA,
  type NvidiaDetectionObservation,
} from './nvidia.js'
import {
  createNodeProbeRunner,
  type NvidiaProbeRunner,
} from './nvidia-probe.js'

const SHA256_RE = /^[0-9a-f]{64}$/
const IMPORT_NAME = 'bionemo.fw' as const
const DISTRIBUTION_NAME = 'bionemo-fw' as const

export class BioNemoFrameworkProbeError extends Error {
  override readonly name: string = 'BioNemoFrameworkProbeError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface ProbeBioNemoFrameworkRequest {
  readonly runner?: NvidiaProbeRunner
  readonly python_executable?: string
}

function normalizedText(value: string): string {
  return value.replace(/\r\n/g, '\n').trim()
}

function sha256Text(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex')
}

function negativeObservation(): NvidiaDetectionObservation {
  return {
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: 'bionemo-framework',
    detected: false,
    connector_version: null,
    executable_digest_sha256: null,
    capability_receipt_digest: null,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

export async function probeBioNemoFramework(
  request: ProbeBioNemoFrameworkRequest = {},
): Promise<NvidiaDetectionObservation> {
  const runner = request.runner ?? createNodeProbeRunner()
  const python = request.python_executable ?? 'python3'
  const script = [
    'import hashlib, importlib, importlib.metadata, json, pathlib',
    `module = importlib.import_module(${JSON.stringify(IMPORT_NAME)})`,
    'module_path = pathlib.Path(module.__file__).resolve()',
    `version = getattr(module, '__version__', None) or importlib.metadata.version(${JSON.stringify(DISTRIBUTION_NAME)})`,
    "print(json.dumps({'version': str(version), 'module_file_sha256': hashlib.sha256(module_path.read_bytes()).hexdigest()}, sort_keys=True))",
  ].join('\n')

  const result = await runner.run(python, ['-c', script])
  if (result.exit_code !== 0 || result.timed_out) {
    return negativeObservation()
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(normalizedText(result.stdout))
  } catch {
    throw new BioNemoFrameworkProbeError('INVALID_BIONEMO_FRAMEWORK_PROBE_JSON')
  }
  if (typeof parsed !== 'object' || parsed === null) {
    throw new BioNemoFrameworkProbeError('INVALID_BIONEMO_FRAMEWORK_PROBE_PAYLOAD')
  }

  const payload = parsed as { version?: unknown; module_file_sha256?: unknown }
  if (typeof payload.version !== 'string' || payload.version.trim().length === 0) {
    throw new BioNemoFrameworkProbeError('INVALID_BIONEMO_FRAMEWORK_VERSION')
  }
  if (
    typeof payload.module_file_sha256 !== 'string'
    || !SHA256_RE.test(payload.module_file_sha256)
  ) {
    throw new BioNemoFrameworkProbeError('INVALID_BIONEMO_FRAMEWORK_MODULE_DIGEST')
  }

  const connectorVersion = payload.version.trim()
  const capabilityReceiptDigest = await hashValue({
    connector_id: 'bionemo-framework' as const,
    import_name: IMPORT_NAME,
    distribution_name: DISTRIBUTION_NAME,
    connector_version: connectorVersion,
    module_file_sha256: payload.module_file_sha256,
    probe_stdout_sha256: sha256Text(normalizedText(result.stdout)),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return {
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: 'bionemo-framework',
    detected: true,
    connector_version: connectorVersion,
    executable_digest_sha256: payload.module_file_sha256,
    capability_receipt_digest: capabilityReceiptDigest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}
