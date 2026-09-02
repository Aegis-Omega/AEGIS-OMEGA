// ============================================================
// SOVEREIGN OMEGA — CUDA-Q Simulator Smoke Execution
// EPISTEMIC TIER: T2 · bounded local-simulator execution evidence
//
// This module performs one fixed Bell-state sampling smoke test on an already
// attested CUDA-Q simulator backend. It deliberately rejects hardware and
// remote targets before process launch. The output is an authority-neutral
// NvidiaQuantumExecutionObservation for the existing admission boundary.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  CUDAQ_BACKEND_RECEIPT_SCHEMA,
  NVIDIA_QUANTUM_EXECUTION_OBSERVATION_SCHEMA,
  type CudaQBackendReceipt,
  type NvidiaQuantumExecutionObservation,
} from './nvidia-execution.js'
import {
  createNodeProbeRunner,
  type NvidiaProbeRunner,
} from './nvidia-probe.js'

const SHA256_RE = /^[0-9a-f]{64}$/
const BELL_BITSTRING_RE = /^[01]{2}$/
const MAX_SMOKE_SHOTS = 4096

const BELL_KERNEL_SPEC = deepFreeze({
  schema_version: 'AEGIS-CUDAQ-BELL-SMOKE-KERNEL-V1' as const,
  qubits: 2,
  operations: [
    { gate: 'h', target: 0 },
    { gate: 'x', control: 0, target: 1 },
    { gate: 'mz', targets: [0, 1] },
  ] as const,
})

export class NvidiaQuantumSmokeError extends Error {
  override readonly name: string = 'NvidiaQuantumSmokeError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export interface ExecuteCudaQSimulatorSmokeRequest {
  readonly task_id: string
  readonly backend: CudaQBackendReceipt
  readonly runner?: NvidiaProbeRunner
  readonly python_executable?: string
  readonly shots_count: number
}

interface CudaQSmokePayload {
  readonly target_name: string
  readonly counts: Record<string, number>
}

function normalizeText(value: string): string {
  return value.replace(/\r\n/g, '\n').trim()
}

function assertSha256(value: string, code: string): void {
  if (!SHA256_RE.test(value)) {
    throw new NvidiaQuantumSmokeError(code)
  }
}

async function assertBackendReceipt(backend: CudaQBackendReceipt): Promise<void> {
  if (backend.schema_version !== CUDAQ_BACKEND_RECEIPT_SCHEMA) {
    throw new NvidiaQuantumSmokeError('CUDAQ_BACKEND_RECEIPT_SCHEMA_MISMATCH')
  }
  if (backend.authority_class !== 'NONE' || backend.authority_effect !== 'NONE') {
    throw new NvidiaQuantumSmokeError('CUDAQ_BACKEND_AUTHORITY_SPLICE_REJECTED')
  }
  assertSha256(backend.receipt_digest, 'INVALID_CUDAQ_BACKEND_RECEIPT_DIGEST')

  const { receipt_digest, ...payload } = backend
  if (await hashValue(payload) !== receipt_digest) {
    throw new NvidiaQuantumSmokeError('CUDAQ_BACKEND_RECEIPT_DIGEST_MISMATCH')
  }
}

function buildBellSmokeScript(targetName: string, shotsCount: number): string {
  const targetLiteral = JSON.stringify(targetName)

  return [
    'import cudaq, json',
    `cudaq.set_target(${targetLiteral})`,
    'kernel = cudaq.make_kernel()',
    'q = kernel.qalloc(2)',
    'kernel.h(q[0])',
    'kernel.cx(q[0], q[1])',
    'kernel.mz(q)',
    `result = cudaq.sample(kernel, shots_count=${shotsCount})`,
    "counts = {str(bits): int(count) for bits, count in result.items()}",
    "payload = {'target_name': cudaq.get_target().name, 'counts': counts}",
    "print(json.dumps(payload, sort_keys=True, separators=(',', ':')))",
  ].join('\n')
}

function parseSmokePayload(
  stdout: string,
  expectedTarget: string,
  expectedShots: number,
): CudaQSmokePayload {
  let parsed: unknown
  try {
    parsed = JSON.parse(normalizeText(stdout))
  } catch {
    throw new NvidiaQuantumSmokeError('INVALID_CUDAQ_SMOKE_JSON')
  }

  if (typeof parsed !== 'object' || parsed === null) {
    throw new NvidiaQuantumSmokeError('INVALID_CUDAQ_SMOKE_PAYLOAD')
  }

  const candidate = parsed as { target_name?: unknown; counts?: unknown }
  if (candidate.target_name !== expectedTarget) {
    throw new NvidiaQuantumSmokeError('CUDAQ_SMOKE_TARGET_BINDING_MISMATCH')
  }
  if (
    typeof candidate.counts !== 'object'
    || candidate.counts === null
    || Array.isArray(candidate.counts)
  ) {
    throw new NvidiaQuantumSmokeError('INVALID_CUDAQ_SAMPLE_COUNTS')
  }

  const entries = Object.entries(candidate.counts)
  if (entries.length === 0) {
    throw new NvidiaQuantumSmokeError('INVALID_CUDAQ_SAMPLE_COUNTS')
  }

  let totalShots = 0
  const canonicalCounts: Record<string, number> = Object.create(null) as Record<string, number>
  for (const [bitstring, rawCount] of entries.sort(([left], [right]) => left.localeCompare(right))) {
    if (!BELL_BITSTRING_RE.test(bitstring)) {
      throw new NvidiaQuantumSmokeError('INVALID_CUDAQ_SAMPLE_BITSTRING')
    }
    if (typeof rawCount !== 'number' || !Number.isSafeInteger(rawCount) || rawCount < 0) {
      throw new NvidiaQuantumSmokeError('INVALID_CUDAQ_SAMPLE_COUNT')
    }
    canonicalCounts[bitstring] = rawCount
    totalShots += rawCount
  }

  if (totalShots !== expectedShots) {
    throw new NvidiaQuantumSmokeError('CUDAQ_SAMPLE_SHOT_COUNT_MISMATCH')
  }

  return {
    target_name: expectedTarget,
    counts: canonicalCounts,
  }
}

export async function executeCudaQSimulatorSmoke(
  request: ExecuteCudaQSimulatorSmokeRequest,
): Promise<NvidiaQuantumExecutionObservation> {
  const { backend } = request

  if (request.task_id.trim().length === 0) {
    throw new NvidiaQuantumSmokeError('EMPTY_CUDAQ_SMOKE_TASK_ID')
  }
  if (!Number.isSafeInteger(request.shots_count) || request.shots_count <= 0) {
    throw new NvidiaQuantumSmokeError('INVALID_CUDAQ_SMOKE_SHOTS')
  }
  if (request.shots_count > MAX_SMOKE_SHOTS) {
    throw new NvidiaQuantumSmokeError('CUDAQ_SMOKE_SHOTS_EXCEED_BOUND')
  }

  await assertBackendReceipt(backend)

  if (backend.backend_kind === 'HARDWARE') {
    throw new NvidiaQuantumSmokeError('HARDWARE_EXECUTION_REQUIRES_EXPLICIT_GATE')
  }
  if (backend.is_remote) {
    throw new NvidiaQuantumSmokeError('REMOTE_EXECUTION_REQUIRES_EXPLICIT_GATE')
  }
  if (backend.target_name.trim().length === 0) {
    throw new NvidiaQuantumSmokeError('EMPTY_CUDAQ_SMOKE_TARGET')
  }

  const python = request.python_executable ?? 'python3'
  if (python.trim().length === 0) {
    throw new NvidiaQuantumSmokeError('EMPTY_CUDAQ_SMOKE_PYTHON_EXECUTABLE')
  }
  const runner = request.runner ?? createNodeProbeRunner()
  const script = buildBellSmokeScript(backend.target_name, request.shots_count)

  const result = await runner.run(python, ['-c', script])
  if (result.timed_out) {
    throw new NvidiaQuantumSmokeError('CUDAQ_SMOKE_EXECUTION_TIMED_OUT')
  }
  if (result.exit_code !== 0) {
    throw new NvidiaQuantumSmokeError(`CUDAQ_SMOKE_EXECUTION_FAILED:${result.exit_code}`)
  }

  const output = parseSmokePayload(
    result.stdout,
    backend.target_name,
    request.shots_count,
  )

  const kernelDigest = await hashValue(BELL_KERNEL_SPEC)
  const inputDigest = await hashValue({
    schema_version: 'AEGIS-CUDAQ-SIMULATOR-SMOKE-INPUT-V1',
    backend_receipt_digest: backend.receipt_digest,
    target_name: backend.target_name,
    shots_count: request.shots_count,
    kernel_digest_sha256: kernelDigest,
  })
  const outputDigest = await hashValue({
    schema_version: 'AEGIS-CUDAQ-SIMULATOR-SMOKE-OUTPUT-V1',
    target_name: output.target_name,
    counts: output.counts,
  })
  const executionReceiptDigest = await hashValue({
    schema_version: 'AEGIS-CUDAQ-SIMULATOR-SMOKE-SOURCE-RECEIPT-V1',
    backend_receipt_digest: backend.receipt_digest,
    target_name: backend.target_name,
    shots_count: request.shots_count,
    kernel_digest_sha256: kernelDigest,
    input_digest_sha256: inputDigest,
    output_digest_sha256: outputDigest,
    normalized_stdout_digest_sha256: await hashValue(normalizeText(result.stdout)),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
  })

  return deepFreeze<NvidiaQuantumExecutionObservation>({
    schema_version: NVIDIA_QUANTUM_EXECUTION_OBSERVATION_SCHEMA,
    task_id: request.task_id,
    completed: true,
    backend_receipt_digest: backend.receipt_digest,
    execution_kind: 'SAMPLE',
    kernel_digest_sha256: kernelDigest,
    input_digest_sha256: inputDigest,
    output_digest_sha256: outputDigest,
    execution_receipt_digest: executionReceiptDigest,
    shots_count: request.shots_count,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })
}
