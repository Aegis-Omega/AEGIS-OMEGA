// ============================================================
// SOVEREIGN OMEGA — NVIDIA Agentic BioNeMo Cross-Receipt Admission
// EPISTEMIC TIER: T2 · execution evidence composition only
//
// Composes an already-admitted current NeMo Platform agent run with an
// already-admitted BioNeMo Inference Runtime GPU execution. Composition never
// grants canonical knowledge authority and rejects cross-task/receipt splicing.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  NVIDIA_AGENT_RUN_RECEIPT_SCHEMA,
  type NvidiaAgentRunReceipt,
} from './nvidia-agent-execution.js'
import {
  BIONEMO_EXECUTION_RECEIPT_SCHEMA,
  type BioNemoExecutionReceipt,
} from './nvidia-execution.js'

export const NVIDIA_AGENTIC_BIONEMO_OBSERVATION_SCHEMA =
  'AEGIS-NVIDIA-AGENTIC-BIONEMO-OBSERVATION-V1' as const
export const NVIDIA_AGENTIC_BIONEMO_RECEIPT_SCHEMA =
  'AEGIS-NVIDIA-AGENTIC-BIONEMO-RECEIPT-V1' as const

const SHA256_RE = /^[0-9a-f]{64}$/

export interface NvidiaAgenticBioNemoObservation {
  readonly schema_version: typeof NVIDIA_AGENTIC_BIONEMO_OBSERVATION_SCHEMA
  readonly task_id: string
  readonly agent_run_receipt_digest: string
  readonly bionemo_execution_receipt_digest: string
  readonly handoff_trace_digest_sha256: string
  readonly terminal_state: 'SUCCEEDED' | 'FAILED'
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface NvidiaAgenticBioNemoReceipt {
  readonly schema_version: typeof NVIDIA_AGENTIC_BIONEMO_RECEIPT_SCHEMA
  readonly task_id: string
  readonly stack: 'NEMO_PLATFORM_BIONEMO_IR'
  readonly agent_execution: 'ESTABLISHED_FOR_THIS_RECEIPT'
  readonly gpu_execution: 'ESTABLISHED_FOR_THIS_RECEIPT'
  readonly agent_run_receipt_digest: string
  readonly bionemo_execution_receipt_digest: string
  readonly handoff_trace_digest_sha256: string
  readonly bionemo_model_id: string
  readonly bionemo_model_artifact_digest_sha256: string
  readonly bionemo_input_digest_sha256: string
  readonly bionemo_output_digest_sha256: string
  readonly knowledge_admission: 'NOT_ESTABLISHED'
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
  readonly receipt_digest: string
}

export interface NvidiaAgenticBioNemoAdmissionRequest {
  readonly observation: NvidiaAgenticBioNemoObservation
  readonly agent_run: NvidiaAgentRunReceipt
  readonly bionemo_execution: BioNemoExecutionReceipt
}

export class NvidiaAgenticBioNemoError extends Error {
  override readonly name: string = 'NvidiaAgenticBioNemoError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function assertSha256(value: string, code: string): void {
  if (!SHA256_RE.test(value)) {
    throw new NvidiaAgenticBioNemoError(code)
  }
}

async function assertAgentRunReceipt(receipt: NvidiaAgentRunReceipt): Promise<void> {
  if (receipt.schema_version !== NVIDIA_AGENT_RUN_RECEIPT_SCHEMA) {
    throw new NvidiaAgenticBioNemoError('AGENT_RUN_RECEIPT_SCHEMA_MISMATCH')
  }
  if (receipt.authority_class !== 'NONE' || receipt.authority_effect !== 'NONE') {
    throw new NvidiaAgenticBioNemoError('AUTHORITY_SPLICE_REJECTED:agent-run-receipt')
  }
  assertSha256(receipt.receipt_digest, 'INVALID_AGENT_RUN_RECEIPT_DIGEST')
  const { receipt_digest, ...payload } = receipt
  if (await hashValue(payload) !== receipt_digest) {
    throw new NvidiaAgenticBioNemoError('AGENT_RUN_RECEIPT_DIGEST_MISMATCH')
  }
  if (receipt.outcome !== 'EXECUTION_ADMITTED' || receipt.terminal_state !== 'SUCCEEDED') {
    throw new NvidiaAgenticBioNemoError('AGENT_RUN_NOT_ADMITTED')
  }
  if (receipt.knowledge_admission !== 'NOT_ESTABLISHED') {
    throw new NvidiaAgenticBioNemoError('AGENT_KNOWLEDGE_AUTHORITY_SPLICE_REJECTED')
  }
}

async function assertBioNemoExecutionReceipt(
  receipt: BioNemoExecutionReceipt,
): Promise<void> {
  if (receipt.schema_version !== BIONEMO_EXECUTION_RECEIPT_SCHEMA) {
    throw new NvidiaAgenticBioNemoError('BIONEMO_RECEIPT_SCHEMA_MISMATCH')
  }
  if (receipt.authority_class !== 'NONE' || receipt.authority_effect !== 'NONE') {
    throw new NvidiaAgenticBioNemoError('AUTHORITY_SPLICE_REJECTED:bionemo-receipt')
  }
  assertSha256(receipt.receipt_digest, 'INVALID_BIONEMO_RECEIPT_DIGEST')
  const { receipt_digest, ...payload } = receipt
  if (await hashValue(payload) !== receipt_digest) {
    throw new NvidiaAgenticBioNemoError('BIONEMO_RECEIPT_DIGEST_MISMATCH')
  }
  if (
    receipt.status !== 'EXECUTED'
    || receipt.gpu_execution !== 'ESTABLISHED_FOR_THIS_RECEIPT'
  ) {
    throw new NvidiaAgenticBioNemoError('BIONEMO_GPU_EXECUTION_NOT_ESTABLISHED')
  }
}

export async function admitNvidiaAgenticBioNemoExecution(
  request: NvidiaAgenticBioNemoAdmissionRequest,
): Promise<NvidiaAgenticBioNemoReceipt> {
  const { observation, agent_run, bionemo_execution } = request

  if (observation.schema_version !== NVIDIA_AGENTIC_BIONEMO_OBSERVATION_SCHEMA) {
    throw new NvidiaAgenticBioNemoError('AGENTIC_BIONEMO_SCHEMA_MISMATCH')
  }
  if (observation.authority_class !== 'NONE' || observation.authority_effect !== 'NONE') {
    throw new NvidiaAgenticBioNemoError('AUTHORITY_SPLICE_REJECTED:agentic-bionemo')
  }
  if (observation.task_id.trim().length === 0) {
    throw new NvidiaAgenticBioNemoError('EMPTY_AGENTIC_BIONEMO_TASK_ID')
  }
  if (observation.terminal_state !== 'SUCCEEDED') {
    throw new NvidiaAgenticBioNemoError('AGENTIC_BIONEMO_EXECUTION_NOT_SUCCESSFUL')
  }
  assertSha256(observation.agent_run_receipt_digest, 'INVALID_AGENT_RUN_BINDING_DIGEST')
  assertSha256(
    observation.bionemo_execution_receipt_digest,
    'INVALID_BIONEMO_EXECUTION_BINDING_DIGEST',
  )
  assertSha256(observation.handoff_trace_digest_sha256, 'INVALID_HANDOFF_TRACE_DIGEST')

  await assertAgentRunReceipt(agent_run)
  await assertBioNemoExecutionReceipt(bionemo_execution)

  if (agent_run.runtime_kind !== 'NEMO_PLATFORM') {
    throw new NvidiaAgenticBioNemoError('CURRENT_NEMO_PLATFORM_REQUIRED')
  }
  if (
    observation.task_id !== agent_run.task_id
    || observation.task_id !== bionemo_execution.task_id
  ) {
    throw new NvidiaAgenticBioNemoError('TASK_BINDING_MISMATCH')
  }
  if (observation.agent_run_receipt_digest !== agent_run.receipt_digest) {
    throw new NvidiaAgenticBioNemoError('AGENT_RUN_RECEIPT_BINDING_MISMATCH')
  }
  if (observation.bionemo_execution_receipt_digest !== bionemo_execution.receipt_digest) {
    throw new NvidiaAgenticBioNemoError('BIONEMO_RECEIPT_BINDING_MISMATCH')
  }

  const payload: Omit<NvidiaAgenticBioNemoReceipt, 'receipt_digest'> = {
    schema_version: NVIDIA_AGENTIC_BIONEMO_RECEIPT_SCHEMA,
    task_id: observation.task_id,
    stack: 'NEMO_PLATFORM_BIONEMO_IR',
    agent_execution: 'ESTABLISHED_FOR_THIS_RECEIPT',
    gpu_execution: 'ESTABLISHED_FOR_THIS_RECEIPT',
    agent_run_receipt_digest: agent_run.receipt_digest,
    bionemo_execution_receipt_digest: bionemo_execution.receipt_digest,
    handoff_trace_digest_sha256: observation.handoff_trace_digest_sha256,
    bionemo_model_id: bionemo_execution.model_id,
    bionemo_model_artifact_digest_sha256: bionemo_execution.model_artifact_digest_sha256,
    bionemo_input_digest_sha256: bionemo_execution.input_digest_sha256,
    bionemo_output_digest_sha256: bionemo_execution.output_digest_sha256,
    knowledge_admission: 'NOT_ESTABLISHED',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    is_replay_reconstructable: true,
  }

  return deepFreeze<NvidiaAgenticBioNemoReceipt>({
    ...payload,
    receipt_digest: await hashValue(payload),
  })
}
