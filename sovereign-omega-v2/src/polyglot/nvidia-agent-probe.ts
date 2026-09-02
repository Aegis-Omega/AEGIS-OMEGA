// ============================================================
// SOVEREIGN OMEGA — NVIDIA NeMo Agent-Plane Runtime Probes
// EPISTEMIC TIER: T2 · observation production only
//
// Probes current NeMo Platform/Fabric and legacy Agent Toolkit runtimes.
// All subprocesses are shell-free and observations remain authority-neutral.
// ============================================================

import { createHash } from 'node:crypto'
import { hashValue } from '../core/hashing.js'
import {
  NVIDIA_DETECTION_OBSERVATION_SCHEMA,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from './nvidia.js'
import {
  createNodeProbeRunner,
  type NvidiaProbeRunner,
} from './nvidia-probe.js'

const SHA256_RE = /^[0-9a-f]{64}$/

type NvidiaAgentCliConnectorId = 'nvidia-agent-toolkit' | 'nemo-platform'
type NvidiaAgentPythonConnectorId = 'nemo-fabric'

interface CliConnectorSpec {
  readonly command: string
  readonly version_args: readonly string[]
}

const CLI_CONNECTORS: Readonly<Record<NvidiaAgentCliConnectorId, CliConnectorSpec>> = {
  'nvidia-agent-toolkit': { command: 'nat', version_args: ['--version'] },
  'nemo-platform': { command: 'nemo', version_args: ['--version'] },
}

interface PythonConnectorSpec {
  readonly import_name: string
  readonly distribution_name: string
}

const PYTHON_CONNECTORS: Readonly<Record<NvidiaAgentPythonConnectorId, PythonConnectorSpec>> = {
  'nemo-fabric': { import_name: 'nemo_fabric', distribution_name: 'nemo-fabric' },
}

export class NvidiaAgentProbeError extends Error {
  override readonly name: string = 'NvidiaAgentProbeError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function normalizedText(value: string): string {
  return value.replace(/\r\n/g, '\n').trim()
}

function sha256Text(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex')
}

function negativeConnectorObservation(
  connectorId: NvidiaConnectorId,
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

export interface ProbeNvidiaCliConnectorRequest {
  readonly connector_id: NvidiaAgentCliConnectorId
  readonly runner?: NvidiaProbeRunner
  readonly python_executable?: string
}

interface CliProbePayload {
  readonly version: string
  readonly executable_path: string
  readonly executable_sha256: string
  readonly returncode: number
}

export async function probeNvidiaCliConnector(
  request: ProbeNvidiaCliConnectorRequest,
): Promise<NvidiaDetectionObservation> {
  const runner = request.runner ?? createNodeProbeRunner()
  const python = request.python_executable ?? 'python3'
  const spec = CLI_CONNECTORS[request.connector_id]

  const script = [
    'import hashlib, json, pathlib, shutil, subprocess, sys',
    'command = sys.argv[1]',
    'path = shutil.which(command)',
    'if path is None:',
    '    raise SystemExit(127)',
    'result = subprocess.run([path, *sys.argv[2:]], capture_output=True, text=True, check=False)',
    'version = (result.stdout or result.stderr).strip()',
    'if result.returncode != 0 or not version:',
    '    raise SystemExit(result.returncode or 1)',
    'resolved = pathlib.Path(path).resolve()',
    "print(json.dumps({'version': version, 'executable_path': str(resolved), 'executable_sha256': hashlib.sha256(resolved.read_bytes()).hexdigest(), 'returncode': result.returncode}, sort_keys=True))",
  ].join('\n')

  const result = await runner.run(
    python,
    ['-c', script, spec.command, ...spec.version_args],
  )
  if (result.exit_code !== 0 || result.timed_out) {
    return negativeConnectorObservation(request.connector_id)
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(normalizedText(result.stdout))
  } catch {
    throw new NvidiaAgentProbeError(`INVALID_CLI_PROBE_JSON:${request.connector_id}`)
  }
  if (typeof parsed !== 'object' || parsed === null) {
    throw new NvidiaAgentProbeError(`INVALID_CLI_PROBE_PAYLOAD:${request.connector_id}`)
  }

  const payload = parsed as Partial<CliProbePayload>
  if (
    typeof payload.version !== 'string'
    || payload.version.trim().length === 0
    || typeof payload.executable_path !== 'string'
    || payload.executable_path.trim().length === 0
    || typeof payload.executable_sha256 !== 'string'
    || !SHA256_RE.test(payload.executable_sha256)
    || payload.returncode !== 0
  ) {
    throw new NvidiaAgentProbeError(`INVALID_CLI_PROBE_EVIDENCE:${request.connector_id}`)
  }

  const connectorVersion = normalizedText(payload.version)
  const capabilityReceiptDigest = await hashValue({
    connector_id: request.connector_id,
    command: spec.command,
    version_args: spec.version_args,
    connector_version: connectorVersion,
    executable_path: payload.executable_path,
    executable_sha256: payload.executable_sha256,
    probe_stdout_sha256: sha256Text(normalizedText(result.stdout)),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return {
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: request.connector_id,
    detected: true,
    connector_version: connectorVersion,
    executable_digest_sha256: payload.executable_sha256,
    capability_receipt_digest: capabilityReceiptDigest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

export interface ProbeNvidiaAgentPythonConnectorRequest {
  readonly connector_id: NvidiaAgentPythonConnectorId
  readonly runner?: NvidiaProbeRunner
  readonly python_executable?: string
}

interface PythonProbePayload {
  readonly version: string
  readonly module_file_sha256: string
}

export async function probeNvidiaAgentPythonConnector(
  request: ProbeNvidiaAgentPythonConnectorRequest,
): Promise<NvidiaDetectionObservation> {
  const runner = request.runner ?? createNodeProbeRunner()
  const python = request.python_executable ?? 'python3'
  const spec = PYTHON_CONNECTORS[request.connector_id]

  const script = [
    'import hashlib, importlib, importlib.metadata, json, pathlib',
    `module = importlib.import_module(${JSON.stringify(spec.import_name)})`,
    'module_path = pathlib.Path(module.__file__).resolve()',
    `version = getattr(module, '__version__', None) or importlib.metadata.version(${JSON.stringify(spec.distribution_name)})`,
    "print(json.dumps({'version': str(version), 'module_file_sha256': hashlib.sha256(module_path.read_bytes()).hexdigest()}, sort_keys=True))",
  ].join('\n')

  const result = await runner.run(python, ['-c', script])
  if (result.exit_code !== 0 || result.timed_out) {
    return negativeConnectorObservation(request.connector_id)
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(normalizedText(result.stdout))
  } catch {
    throw new NvidiaAgentProbeError(`INVALID_PYTHON_PROBE_JSON:${request.connector_id}`)
  }
  if (typeof parsed !== 'object' || parsed === null) {
    throw new NvidiaAgentProbeError(`INVALID_PYTHON_PROBE_PAYLOAD:${request.connector_id}`)
  }

  const payload = parsed as Partial<PythonProbePayload>
  if (
    typeof payload.version !== 'string'
    || payload.version.trim().length === 0
    || typeof payload.module_file_sha256 !== 'string'
    || !SHA256_RE.test(payload.module_file_sha256)
  ) {
    throw new NvidiaAgentProbeError(`INVALID_PYTHON_PROBE_EVIDENCE:${request.connector_id}`)
  }

  const connectorVersion = payload.version.trim()
  const capabilityReceiptDigest = await hashValue({
    connector_id: request.connector_id,
    import_name: spec.import_name,
    distribution_name: spec.distribution_name,
    connector_version: connectorVersion,
    module_file_sha256: payload.module_file_sha256,
    probe_stdout_sha256: sha256Text(normalizedText(result.stdout)),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return {
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: request.connector_id,
    detected: true,
    connector_version: connectorVersion,
    executable_digest_sha256: payload.module_file_sha256,
    capability_receipt_digest: capabilityReceiptDigest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}
