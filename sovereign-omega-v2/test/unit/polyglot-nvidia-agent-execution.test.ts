import { describe, expect, it } from 'vitest'
import {
  NVIDIA_AGENT_RUN_OBSERVATION_SCHEMA,
  NvidiaAgentExecutionError,
  admitNvidiaAgentRun,
  type NvidiaAgentRunObservation,
} from '../../src/polyglot/nvidia-agent-execution'
import {
  admitNvidiaConnector,
  type NvidiaConnectorEvidence,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from '../../src/polyglot/nvidia'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)
const SHA_C = 'c'.repeat(64)
const SHA_D = 'd'.repeat(64)
const SHA_E = 'e'.repeat(64)

function connectorEvidence(connector_id: NvidiaConnectorId): NvidiaConnectorEvidence {
  const observation: NvidiaDetectionObservation = {
    schema_version: 'AEGIS-NVIDIA-DETECTION-OBSERVATION-V1',
    connector_id,
    detected: true,
    connector_version: `${connector_id}-test`,
    executable_digest_sha256: SHA_A,
    capability_receipt_digest: SHA_B,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
  return admitNvidiaConnector(observation)
}

function observation(
  overrides: Partial<NvidiaAgentRunObservation> = {},
): NvidiaAgentRunObservation {
  return {
    schema_version: NVIDIA_AGENT_RUN_OBSERVATION_SCHEMA,
    task_id: 'agent-task-001',
    runtime_kind: 'NEMO_PLATFORM',
    connector_evidence: [
      connectorEvidence('nemo-platform'),
      connectorEvidence('nemo-fabric'),
    ],
    agent_config_digest_sha256: SHA_A,
    input_digest_sha256: SHA_C,
    output_digest_sha256: SHA_D,
    execution_trace_digest_sha256: SHA_E,
    terminal_state: 'SUCCEEDED',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

describe('NVIDIA NeMo agent execution admission', () => {
  it('admits current NeMo Platform execution only from exact Platform + Fabric evidence', async () => {
    const receipt = await admitNvidiaAgentRun(observation())

    expect(receipt.runtime_kind).toBe('NEMO_PLATFORM')
    expect(receipt.connector_ids).toEqual(['nemo-platform', 'nemo-fabric'])
    expect(receipt.outcome).toBe('EXECUTION_ADMITTED')
    expect(receipt.terminal_state).toBe('SUCCEEDED')
    expect(receipt.knowledge_admission).toBe('NOT_ESTABLISHED')
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
    expect(receipt.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(receipt.is_replay_reconstructable).toBe(true)
  })

  it('rejects a NeMo Platform run when Fabric evidence is absent', async () => {
    await expect(admitNvidiaAgentRun(observation({
      connector_evidence: [connectorEvidence('nemo-platform')],
    }))).rejects.toThrow(/REQUIRED_NVIDIA_CONNECTOR_MISSING:nemo-fabric/)
  })

  it('does not allow legacy NAT evidence to satisfy current NeMo Platform execution', async () => {
    await expect(admitNvidiaAgentRun(observation({
      connector_evidence: [connectorEvidence('nvidia-agent-toolkit')],
    }))).rejects.toThrow(NvidiaAgentExecutionError)
  })

  it('admits legacy NAT as a separate runtime contract', async () => {
    const receipt = await admitNvidiaAgentRun(observation({
      runtime_kind: 'NAT_LEGACY',
      connector_evidence: [connectorEvidence('nvidia-agent-toolkit')],
    }))

    expect(receipt.runtime_kind).toBe('NAT_LEGACY')
    expect(receipt.connector_ids).toEqual(['nvidia-agent-toolkit'])
    expect(receipt.outcome).toBe('EXECUTION_ADMITTED')
    expect(receipt.knowledge_admission).toBe('NOT_ESTABLISHED')
  })

  it('rejects failed agent executions instead of admitting their output', async () => {
    await expect(admitNvidiaAgentRun(observation({
      terminal_state: 'FAILED',
    }))).rejects.toThrow(/AGENT_EXECUTION_NOT_SUCCESSFUL/)
  })

  it('rejects duplicate connector evidence and malformed execution digests', async () => {
    await expect(admitNvidiaAgentRun(observation({
      connector_evidence: [
        connectorEvidence('nemo-platform'),
        connectorEvidence('nemo-platform'),
        connectorEvidence('nemo-fabric'),
      ],
    }))).rejects.toThrow(/DUPLICATE_CONNECTOR_EVIDENCE:nemo-platform/)

    await expect(admitNvidiaAgentRun(observation({
      output_digest_sha256: 'bad',
    }))).rejects.toThrow(/INVALID_AGENT_OUTPUT_DIGEST/)
  })

  it('rejects authority-bearing observations', async () => {
    await expect(admitNvidiaAgentRun(observation({
      authority_effect: 'KNOWLEDGE_ADMISSION' as never,
    }))).rejects.toThrow(/AUTHORITY_SPLICE_REJECTED/)
  })

  it('is deterministic across independent receipt constructions', async () => {
    const first = await admitNvidiaAgentRun(observation())
    const second = await admitNvidiaAgentRun(observation())
    const third = await admitNvidiaAgentRun(observation())

    expect(first).toEqual(second)
    expect(second).toEqual(third)
  })
})
