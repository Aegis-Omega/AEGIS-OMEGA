// ============================================================
// SOVEREIGN OMEGA — NVIDIA Runtime Probe Harness
// EPISTEMIC TIER: T2 · sandbox observation production only
//
// This module performs narrow, shell-free runtime probes and emits typed
// observations for the existing NVIDIA admission boundaries. Probe success is
// evidence of the exact observed runtime only; it grants no execution,
// knowledge-admission, proof, QPU, or quantum-advantage authority.
// ============================================================

import { execFile } from 'node:child_process'
import { createHash } from 'node:crypto'
import { hashValue } from '../core/hashing.js'
import {
  NVIDIA_DETECTION_OBSERVATION_SCHEMA,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from './nvidia.js'
import {
  CUDAQ_BACKEND_OBSERVATION_SCHEMA,
  NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA,
  type CudaQBackendObservation,
  type NvidiaGpuEnvironmentObservation,
} from './nvidia-execution.js'

const SHA256_RE = /^[0-9a-f]{64}$/
const DEFAULT_TIMEOUT_MS = 15_000
const DEFAULT_MAX_BUFFER_BYTES = 1024 * 1024

export interface NvidiaProbeCommandResult {
  readonly exit_code: number
  readonly stdout: string
  readonly stderr: string
  readonly timed_out: boolean
}

export interface NvidiaProbeRunner {
  run(command: string, args: readonly string[]): Promise<NvidiaProbeCommandResult>
}

export interface NodeProbeRunnerOptions {
  readonly timeout_ms?: number
  readonly max_buffer_bytes?: number
}

export class NvidiaProbeError extends Error {
  override readonly name: string = 'NvidiaProbeError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function sha256Text(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex')
}

function normalizedText(value: string): string {
  return value.replace(/\r\n/g, '\n').trim()
}

export function createNodeProbeRunner(
  options: NodeProbeRunnerOptions = {},
): NvidiaProbeRunner {
  const timeout = options.timeout_ms ?? DEFAULT_TIMEOUT_MS
  const maxBuffer = options.max_buffer_bytes ?? DEFAULT_MAX_BUFFER_BYTES

  if (!Number.isInteger(timeout) || timeout <= 0) {
    throw new NvidiaProbeError('INVALID_PROBE_TIMEOUT')
  }
  if (!Number.isInteger(maxBuffer) || maxBuffer <= 0) {
    throw new NvidiaProbeError('INVALID_PROBE_MAX_BUFFER')
  }

  return {
    run(command: string, args: readonly string[]): Promise<NvidiaProbeCommandResult> {
      if (command.trim().length === 0) {
        return Promise.reject(new NvidiaProbeError('EMPTY_PROBE_COMMAND'))
      }

      return new Promise(resolve => {
        execFile(
          command,
          [...args],
          {
            encoding: 'utf8',
            shell: false,
            timeout,
            maxBuffer,
            windowsHide: true,
          },
          (error, stdout, stderr) => {
            if (!error) {
              resolve({
                exit_code: 0,
                stdout: String(stdout),
                stderr: String(stderr),
                timed_out: false,
              })
              return
            }

            const code = error.code
            const timedOut = error.killed === true && error.signal !== null
            const exitCode = typeof code === 'number'
              ? code
              : code === 'ENOENT'
                ? 127
                : 1

            resolve({
              exit_code: exitCode,
              stdout: String(stdout ?? ''),
              stderr: String(stderr ?? error.message),
              timed_out: timedOut,
            })
          },
        )
      })
    },
  }
}

function negativeGpuObservation(): NvidiaGpuEnvironmentObservation {
  return {
    schema_version: NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA,
    detected: false,
    gpu_count: 0,
    driver_version: null,
    cuda_driver_version: null,
    gpu_architectures: [],
    device_inventory_digest_sha256: null,
    capability_receipt_digest: null,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

interface ParsedGpuRow {
  readonly uuid: string
  readonly name: string
  readonly driver_version: string
  readonly compute_capability: string
}

function parseGpuInventory(stdout: string): ParsedGpuRow[] {
  const rows = normalizedText(stdout)
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => {
      const fields = line.split(',').map(field => field.trim())
      if (fields.length !== 4) {
        throw new NvidiaProbeError('INVALID_NVIDIA_SMI_INVENTORY_ROW')
      }
      const [uuid, name, driverVersion, computeCapability] = fields
      if (!uuid || !name || !driverVersion || !computeCapability) {
        throw new NvidiaProbeError('INVALID_NVIDIA_SMI_INVENTORY_ROW')
      }
      return {
        uuid,
        name,
        driver_version: driverVersion,
        compute_capability: computeCapability,
      }
    })

  rows.sort((left, right) => left.uuid.localeCompare(right.uuid))
  return rows
}

export interface ProbeNvidiaGpuEnvironmentRequest {
  readonly runner?: NvidiaProbeRunner
}

export async function probeNvidiaGpuEnvironment(
  request: ProbeNvidiaGpuEnvironmentRequest = {},
): Promise<NvidiaGpuEnvironmentObservation> {
  const runner = request.runner ?? createNodeProbeRunner()
  const queryArgs = [
    '--query-gpu=uuid,name,driver_version,compute_cap',
    '--format=csv,noheader,nounits',
  ] as const

  const inventoryResult = await runner.run('nvidia-smi', queryArgs)
  if (
    inventoryResult.exit_code !== 0
    || inventoryResult.timed_out
    || normalizedText(inventoryResult.stdout).length === 0
  ) {
    return negativeGpuObservation()
  }

  const rows = parseGpuInventory(inventoryResult.stdout)
  if (rows.length === 0) return negativeGpuObservation()

  const driverVersions = new Set(rows.map(row => row.driver_version))
  if (driverVersions.size !== 1) {
    throw new NvidiaProbeError('GPU_DRIVER_VERSION_INCONSISTENT')
  }

  const bannerResult = await runner.run('nvidia-smi', [])
  if (bannerResult.exit_code !== 0 || bannerResult.timed_out) {
    return negativeGpuObservation()
  }
  const cudaMatch = normalizedText(bannerResult.stdout).match(/CUDA Version:\s*([0-9]+(?:\.[0-9]+)*)/)
  const cudaDriverVersion = cudaMatch?.[1]
  if (!cudaDriverVersion) {
    throw new NvidiaProbeError('CUDA_DRIVER_VERSION_NOT_OBSERVED')
  }

  const canonicalInventory = rows.map(row => ({
    uuid: row.uuid,
    name: row.name,
    driver_version: row.driver_version,
    compute_capability: row.compute_capability,
  }))
  const inventoryDigest = await hashValue(canonicalInventory)
  const capabilityReceiptDigest = await hashValue({
    probe: 'nvidia-smi',
    query_args: queryArgs,
    inventory_digest_sha256: inventoryDigest,
    inventory_stdout_sha256: sha256Text(normalizedText(inventoryResult.stdout)),
    banner_stdout_sha256: sha256Text(normalizedText(bannerResult.stdout)),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return {
    schema_version: NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA,
    detected: true,
    gpu_count: rows.length,
    driver_version: rows[0]!.driver_version,
    cuda_driver_version: cudaDriverVersion,
    gpu_architectures: rows.map(
      row => `${row.name}@compute-capability-${row.compute_capability}`,
    ),
    device_inventory_digest_sha256: inventoryDigest,
    capability_receipt_digest: capabilityReceiptDigest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

interface PythonConnectorSpec {
  readonly import_name: string
  readonly distribution_name: string
}

const PYTHON_CONNECTORS: Readonly<Partial<Record<NvidiaConnectorId, PythonConnectorSpec>>> = {
  'bionemo-ir': { import_name: 'bionemo_ir', distribution_name: 'bionemo-ir' },
  cudaq: { import_name: 'cudaq', distribution_name: 'cudaq' },
  cuquantum: { import_name: 'cuquantum', distribution_name: 'cuquantum-python' },
}

export interface ProbeNvidiaPythonConnectorRequest {
  readonly connector_id: 'bionemo-ir' | 'cudaq' | 'cuquantum'
  readonly runner?: NvidiaProbeRunner
  readonly python_executable?: string
}

function negativeConnectorObservation(
  connectorId: ProbeNvidiaPythonConnectorRequest['connector_id'],
): NvidiaDetectionObservation {
  return {
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: connectorId,
    detected: false,
    connector_version: null,
    executable_digest_sha256: null,
    capability_receipt_digest: null,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

export async function probeNvidiaPythonConnector(
  request: ProbeNvidiaPythonConnectorRequest,
): Promise<NvidiaDetectionObservation> {
  const runner = request.runner ?? createNodeProbeRunner()
  const python = request.python_executable ?? 'python3'
  const spec = PYTHON_CONNECTORS[request.connector_id]
  if (!spec) {
    throw new NvidiaProbeError(`UNSUPPORTED_PYTHON_CONNECTOR:${request.connector_id}`)
  }

  const script = [
    'import hashlib, importlib, importlib.metadata, json, pathlib',
    `m=importlib.import_module(${JSON.stringify(spec.import_name)})`,
    'p=pathlib.Path(m.__file__).resolve()',
    `v=getattr(m,'__version__',None) or importlib.metadata.version(${JSON.stringify(spec.distribution_name)})`,
    "print(json.dumps({'version':str(v),'module_file_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},sort_keys=True))",
  ].join(';')

  const result = await runner.run(python, ['-c', script])
  if (result.exit_code !== 0 || result.timed_out) {
    return negativeConnectorObservation(request.connector_id)
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(normalizedText(result.stdout))
  } catch {
    throw new NvidiaProbeError(`INVALID_PYTHON_PROBE_JSON:${request.connector_id}`)
  }
  if (typeof parsed !== 'object' || parsed === null) {
    throw new NvidiaProbeError(`INVALID_PYTHON_PROBE_PAYLOAD:${request.connector_id}`)
  }

  const payload = parsed as { version?: unknown; module_file_sha256?: unknown }
  if (typeof payload.version !== 'string' || payload.version.trim().length === 0) {
    throw new NvidiaProbeError(`INVALID_PYTHON_PROBE_VERSION:${request.connector_id}`)
  }
  if (
    typeof payload.module_file_sha256 !== 'string'
    || !SHA256_RE.test(payload.module_file_sha256)
  ) {
    throw new NvidiaProbeError(`INVALID_PYTHON_MODULE_DIGEST:${request.connector_id}`)
  }

  const capabilityReceiptDigest = await hashValue({
    connector_id: request.connector_id,
    import_name: spec.import_name,
    distribution_name: spec.distribution_name,
    connector_version: payload.version,
    module_file_sha256: payload.module_file_sha256,
    probe_stdout_sha256: sha256Text(normalizedText(result.stdout)),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return {
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: request.connector_id,
    detected: true,
    connector_version: payload.version,
    executable_digest_sha256: payload.module_file_sha256,
    capability_receipt_digest: capabilityReceiptDigest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

interface CudaQTargetProbePayload {
  readonly name: string
  readonly simulator: string
  readonly platform: string
  readonly description: string
  readonly num_qpus: number
  readonly is_remote: boolean
  readonly is_emulated: boolean
}

export interface ProbeCudaQBackendRequest {
  readonly runner?: NvidiaProbeRunner
  readonly target_name?: string
  readonly python_executable?: string
}

export async function probeCudaQBackend(
  request: ProbeCudaQBackendRequest = {},
): Promise<CudaQBackendObservation> {
  const runner = request.runner ?? createNodeProbeRunner()
  const python = request.python_executable ?? 'python3'
  const targetName = request.target_name ?? 'default'
  if (targetName.trim().length === 0) {
    throw new NvidiaProbeError('EMPTY_CUDAQ_TARGET')
  }

  const targetExpression = targetName === 'default'
    ? 'cudaq.get_target()'
    : `cudaq.get_target(${JSON.stringify(targetName)})`
  const script = [
    'import cudaq, json',
    `t=${targetExpression}`,
    "p={'name':t.name,'simulator':t.simulator,'platform':t.platform,'description':t.description,'num_qpus':t.num_qpus(),'is_remote':t.is_remote(),'is_emulated':t.is_emulated()}",
    'print(json.dumps(p,sort_keys=True))',
  ].join(';')

  const result = await runner.run(python, ['-c', script])
  if (result.exit_code !== 0 || result.timed_out) {
    throw new NvidiaProbeError(`CUDAQ_BACKEND_PROBE_FAILED:${targetName}`)
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(normalizedText(result.stdout))
  } catch {
    throw new NvidiaProbeError(`INVALID_CUDAQ_BACKEND_JSON:${targetName}`)
  }
  if (typeof parsed !== 'object' || parsed === null) {
    throw new NvidiaProbeError(`INVALID_CUDAQ_BACKEND_PAYLOAD:${targetName}`)
  }

  const payload = parsed as Partial<CudaQTargetProbePayload>
  if (
    typeof payload.name !== 'string'
    || payload.name.trim().length === 0
    || (targetName !== 'default' && payload.name !== targetName)
  ) {
    throw new NvidiaProbeError(`CUDAQ_TARGET_BINDING_MISMATCH:${targetName}`)
  }
  if (
    typeof payload.simulator !== 'string'
    || typeof payload.platform !== 'string'
    || typeof payload.description !== 'string'
    || typeof payload.num_qpus !== 'number'
    || !Number.isInteger(payload.num_qpus)
    || payload.num_qpus <= 0
    || typeof payload.is_remote !== 'boolean'
    || typeof payload.is_emulated !== 'boolean'
  ) {
    throw new NvidiaProbeError(`INVALID_CUDAQ_BACKEND_PROPERTIES:${targetName}`)
  }

  const backendKind = payload.simulator.trim().length > 0 || payload.is_emulated
    ? 'SIMULATOR' as const
    : 'HARDWARE' as const
  const canonicalProperties: CudaQTargetProbePayload = {
    name: payload.name,
    simulator: payload.simulator,
    platform: payload.platform,
    description: payload.description,
    num_qpus: payload.num_qpus,
    is_remote: payload.is_remote,
    is_emulated: payload.is_emulated,
  }
  const propertiesDigest = await hashValue(canonicalProperties)
  const capabilityReceiptDigest = await hashValue({
    target_name: payload.name,
    platform_properties_digest_sha256: propertiesDigest,
    probe_stdout_sha256: sha256Text(normalizedText(result.stdout)),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return {
    schema_version: CUDAQ_BACKEND_OBSERVATION_SCHEMA,
    target_name: payload.name,
    backend_kind: backendKind,
    qpu_count: payload.num_qpus,
    is_remote: payload.is_remote,
    is_emulated: payload.is_emulated,
    platform_properties_digest_sha256: propertiesDigest,
    capability_receipt_digest: capabilityReceiptDigest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}
