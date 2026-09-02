// ============================================================
// SOVEREIGN OMEGA — NVIDIA NeMo Agent Execution Admission
// EPISTEMIC TIER: T2 · execution evidence only
//
// This module admits already-observed NVIDIA agent executions. It does not
// launch agents and it never promotes agent output into canonical knowledge.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  NVIDIA_CONNECTOR_EVIDENCE_SCHEMA,
  type NvidiaConnectorEvidence,
  type NvidiaConnectorId,
} from './nvidia.js'

export const NVIDIA_AGENT_RUN_OBSERVATION_SCHEMA =
  'AEGIS-NVIDIA-AGENT-RUN-OBSERVATION-V1' as const
export const NVIDIA_AGENT_RUN_RECEIPT_SCHEMA =
  'AEGIS-NVIDIA-AGENT-RUN-RECEIPT-V1' as const

export type NvidiaAgentRuntimeKind = 'NEMO_PLATFORM' | 'NAT_LEGACY'
export type NvidiaAgentTerminalState = 'SUCCEEDED' | 'FAILED'

export interface NvidiaAgentRunObservation {
  readonly schema_version: typeof NVIDIA_AGENT_RUN_OBSERVATION_SCHEMA
  readonly task_id: string
  readonly runtime_kind: NvidiaAgentRuntimeKind
  readonly connector_evidence: readonly NvidiaConnectorEvidence[]
  readonly agent_config_digest_sha256: string
  readonly input_digest_sha256: string
  readonly output_digest_sha256: string
  readonly execution_trace_digest_sha256: string
  readonly terminal_state: NvidiaAgentTerminalState
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface NvidiaAgentRunReceipt {
  readonly schema_version: typeof NVIDIA_AGENT_RUN_RECEIPT_SCHEMA
  readonly task_id: string
  readonly runtime_kind: NvidiaAgentRuntimeKind
  readonly connector_ids: readonly NvidiaConnectorId[]
  readonly connector_bindings: readonly {
    readonly connector_id: NvidiaConnectorId
    readonly connector_version: string
    readonly executable_digest_sha256: string
    readonly source_receipt_digest: string
  }[]
  readonly agent_config_digest_sha256: string
  readonly input_digest_sha256: string
  readonly output_digest_sha256: string
  readonly execution_trace_digest_sha256: string
  readonly terminal_state: 'SUCCEEDED'
  readonly outcome: 'EXECUTION_ADMITTED'
  readonly knowledge_admission: 'NOT_ESTABLISHED'
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly receipt_digest: string
  readonly is_replay_reconstructable: true
}

export class NvidiaAgentExecutionError extends Error {
  override readonly name: string = 'NvidiaAgentExecutionError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const SHA256_RE = /^[0-9a-f]{64}$/

const REQUIRED_CONNECTORS: Readonly<Record<NvidiaAgentRuntimeKind, readonly NvidiaConnectorId[]>> = {
  NEMO_PLATFORM: ['nemo-platform', 'nemo-fabric'],
  NAT_LEGACY: ['nvidia-agent-toolkit'],
}

function assertSha256(value: string, code: string): void {
  if (!SHA256_RE.test(value)) {
    throw new NvidiaAgentExecutionError(code)
  }
}

function assertConnectorEvidence(evidence: NvidiaConnectorEvidence): void {
  if (evidence.schema_version !== NVIDIA_CONNECTOR_EVIDENCE_SCHEMA) {
    throw new NvidiaAgentExecutionError(`CONNECTOR_SCHEMA_MISMATCH:${evidence.connector_id}`)
  }
  if (evidence.status !== 'VERIFIED_AVAILABLE' && evidence.status !== 'EXECUTION_ADMITTED') {
    throw new NvidiaAgentExecutionError(`UNVERIFIED_NVIDIA_CONNECTOR:${evidence.connector_id}`)
  }
  if (evidence.authority_class !== 'NONE' || evidence.authority_effect !== 'NONE') {
    throw new NvidiaAgentExecutionError(`AUTHORITY_SPLICE_REJECTED:${evidence.connector_id}`)
  }
  if (evidence.connector_version.trim().length === 0) {
    throw new NvidiaAgentExecutionError(`INVALID_CONNECTOR_VERSION:${evidence.connector_id}`)
  }
  assertSha256(
    evidence.executable_digest_sha256,
    `INVALID_CONNECTOR_EXECUTABLE_DIGEST:${evidence.connector_id}`,
  )
  assertSha256(
    evidence.source_receipt_digest,
    `INVALID_CONNECTOR_RECEIPT_DIGEST:${evidence.connector_id}`,
  )
}

export async function admitNvidiaAgentRun(
  observation: NvidiaAgentRunObservation,
): Promise<NvidiaAgentRunReceipt> {
  if (observation.schema_version !== NVIDIA_AGENT_RUN_OBSERVATION_SCHEMA) {
    throw new NvidiaAgentExecutionError('AGENT_RUN_SCHEMA_MISMATCH')
  }
  if (observation.task_id.trim().length === 0) {
    throw new NvidiaAgentExecutionError('EMPTY_AGENT_TASK_ID')
  }
  if (observation.authority_class !== 'NONE' || observation.authority_effect !== 'NONE') {
    throw new NvidiaAgentExecutionError('AUTHORITY_SPLICE_REJECTED:agent-run')
  }
  if (observation.terminal_state !== 'SUCCEEDED') {
    throw new NvidiaAgentExecutionError('AGENT_EXECUTION_NOT_SUCCESSFUL')
  }

  assertSha256(observation.agent_config_digest_sha256, 'INVALID_AGENT_CONFIG_DIGEST')
  assertSha256(observation.input_digest_sha256, 'INVALID_AGENT_INPUT_DIGEST')
  assertSha256(observation.output_digest_sha256, 'INVALID_AGENT_OUTPUT_DIGEST')
  assertSha256(observation.execution_trace_digest_sha256, 'INVALID_AGENT_TRACE_DIGEST')

  const required = REQUIRED_CONNECTORS[observation.runtime_kind]
  if (!required) {
    throw new NvidiaAgentExecutionError(`UNKNOWN_AGENT_RUNTIME:${String(observation.runtime_kind)}`)
  }

  const evidenceById = new Map<NvidiaConnectorId, NvidiaConnectorEvidence>()
  for (const evidence of observation.connector_evidence) {
    assertConnectorEvidence(evidence)
    if (evidenceById.has(evidence.connector_id)) {
      throw new NvidiaAgentExecutionError(`DUPLICATE_CONNECTOR_EVIDENCE:${evidence.connector_id}`)
    }
    evidenceById.set(evidence.connector_id, evidence)
  }

  for (const connectorId of required) {
    if (!evidenceById.has(connectorId)) {
      throw new NvidiaAgentExecutionError(`REQUIRED_NVIDIA_CONNECTOR_MISSING:${connectorId}`)
    }
  }
  for (const connectorId of evidenceById.keys()) {
    if (!required.includes(connectorId)) {
      throw new NvidiaAgentExecutionError(
        `AGENT_RUNTIME_CONNECTOR_SPLICE_REJECTED:${observation.runtime_kind}:${connectorId}`,
      )
    }
  }

  const connectorBindings = required.map(connectorId => {
    const evidence = evidenceById.get(connectorId)!
    return {
      connector_id: connectorId,
      connector_version: evidence.connector_version,
      executable_digest_sha256: evidence.executable_digest_sha256,
      source_receipt_digest: evidence.source_receipt_digest,
    }
  })

  const digestPayload = {
    schema_version: NVIDIA_AGENT_RUN_RECEIPT_SCHEMA,
    task_id: observation.task_id,
    runtime_kind: observation.runtime_kind,
    connector_ids: [...required],
    connector_bindings: connectorBindings,
    agent_config_digest_sha256: observation.agent_config_digest_sha256,
    input_digest_sha256: observation.input_digest_sha256,
    output_digest_sha256: observation.output_digest_sha256,
    execution_trace_digest_sha256: observation.execution_trace_digest_sha256,
    terminal_state: 'SUCCEEDED' as const,
    outcome: 'EXECUTION_ADMITTED' as const,
    knowledge_admission: 'NOT_ESTABLISHED' as const,
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }

  const receiptDigest = await hashValue(digestPayload)
  return deepFreeze<NvidiaAgentRunReceipt>({
    ...digestPayload,
    receipt_digest: receiptDigest,
  })
}
