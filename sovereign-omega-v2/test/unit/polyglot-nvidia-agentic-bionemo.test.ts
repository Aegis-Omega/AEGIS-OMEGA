import { describe, expect, it } from 'vitest'
import {
  NVIDIA_AGENTIC_BIONEMO_OBSERVATION_SCHEMA,
  NvidiaAgenticBioNemoError,
  admitNvidiaAgenticBioNemoExecution,
  type NvidiaAgenticBioNemoObservation,
} from '../../src/polyglot/nvidia-agentic-bionemo'
import {
  NVIDIA_AGENT_RUN_OBSERVATION_SCHEMA,
  admitNvidiaAgentRun,
} from '../../src/polyglot/nvidia-agent-execution'
import {
  BIONEMO_EXECUTION_OBSERVATION_SCHEMA,
  NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA,
  admitBioNemoExecution,
  admitNvidiaGpuEnvironment,
} from '../../src/polyglot/nvidia-execution'
import {
  admitNvidiaConnector,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from '../../src/polyglot/nvidia'

const A = 'a'.repeat(64)
const B = 'b'.repeat(64)
const C = 'c'.repeat(64)
const D = 'd'.repeat(64)
const E = 'e'.repeat(64)
const F = 'f'.repeat(64)

function connector(connector_id: NvidiaConnectorId) {
  const observation: NvidiaDetectionObservation = {
    schema_version: 'AEGIS-NVIDIA-DETECTION-OBSERVATION-V1',
    connector_id,
    detected: true,
    connector_version: `${connector_id}-test`,
    executable_digest_sha256: A,
    capability_receipt_digest: B,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
  return admitNvidiaConnector(observation)
}

async function fixtures(runtime_kind: 'NEMO_PLATFORM' | 'NAT_LEGACY' = 'NEMO_PLATFORM') {
  const gpu = await admitNvidiaGpuEnvironment({
    schema_version: NVIDIA_GPU_ENVIRONMENT_OBSERVATION_SCHEMA,
    detected: true,
    gpu_count: 1,
    driver_version: '580.65.06',
    cuda_driver_version: '13.0',
    gpu_architectures: ['H100@compute-capability-9.0'],
    device_inventory_digest_sha256: C,
    capability_receipt_digest: D,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })

  const bio = await admitBioNemoExecution({
    bionemo_evidence: connector('bionemo-ir'),
    gpu_environment: gpu,
    observation: {
      schema_version: BIONEMO_EXECUTION_OBSERVATION_SCHEMA,
      task_id: 'agentic-bio-001',
      completed: true,
      gpu_environment_receipt_digest: gpu.receipt_digest,
      model_id: 'boltz2',
      model_artifact_digest_sha256: D,
      input_digest_sha256: E,
      output_digest_sha256: F,
      execution_receipt_digest: A,
      authority_class: 'NONE',
      authority_effect: 'NONE',
    },
  })

  const agent = await admitNvidiaAgentRun({
    schema_version: NVIDIA_AGENT_RUN_OBSERVATION_SCHEMA,
    task_id: 'agentic-bio-001',
    runtime_kind,
    connector_evidence: runtime_kind === 'NEMO_PLATFORM'
      ? [connector('nemo-platform'), connector('nemo-fabric')]
      : [connector('nvidia-agent-toolkit')],
    agent_config_digest_sha256: A,
    input_digest_sha256: B,
    output_digest_sha256: C,
    execution_trace_digest_sha256: D,
    terminal_state: 'SUCCEEDED',
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })

  return { gpu, bio, agent }
}

function joinObservation(
  agentReceiptDigest: string,
  bioReceiptDigest: string,
  overrides: Partial<NvidiaAgenticBioNemoObservation> = {},
): NvidiaAgenticBioNemoObservation {
  return {
    schema_version: NVIDIA_AGENTIC_BIONEMO_OBSERVATION_SCHEMA,
    task_id: 'agentic-bio-001',
    agent_run_receipt_digest: agentReceiptDigest,
    bionemo_execution_receipt_digest: bioReceiptDigest,
    handoff_trace_digest_sha256: E,
    terminal_state: 'SUCCEEDED',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

describe('NVIDIA agentic BioNeMo cross-receipt admission', () => {
  it('admits exact NeMo Platform + BioIR GPU execution for one task without knowledge authority', async () => {
    const { agent, bio } = await fixtures()
    const receipt = await admitNvidiaAgenticBioNemoExecution({
      observation: joinObservation(agent.receipt_digest, bio.receipt_digest),
      agent_run: agent,
      bionemo_execution: bio,
    })

    expect(receipt.stack).toBe('NEMO_PLATFORM_BIONEMO_IR')
    expect(receipt.task_id).toBe('agentic-bio-001')
    expect(receipt.agent_execution).toBe('ESTABLISHED_FOR_THIS_RECEIPT')
    expect(receipt.gpu_execution).toBe('ESTABLISHED_FOR_THIS_RECEIPT')
    expect(receipt.agent_run_receipt_digest).toBe(agent.receipt_digest)
    expect(receipt.bionemo_execution_receipt_digest).toBe(bio.receipt_digest)
    expect(receipt.knowledge_admission).toBe('NOT_ESTABLISHED')
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
    expect(receipt.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(receipt.is_replay_reconstructable).toBe(true)
  })

  it('rejects legacy NAT as a substitute for current NeMo Platform execution', async () => {
    const { agent, bio } = await fixtures('NAT_LEGACY')
    await expect(admitNvidiaAgenticBioNemoExecution({
      observation: joinObservation(agent.receipt_digest, bio.receipt_digest),
      agent_run: agent,
      bionemo_execution: bio,
    })).rejects.toThrow(/CURRENT_NEMO_PLATFORM_REQUIRED/)
  })

  it('rejects task and receipt splicing', async () => {
    const { agent, bio } = await fixtures()

    await expect(admitNvidiaAgenticBioNemoExecution({
      observation: joinObservation(A, bio.receipt_digest),
      agent_run: agent,
      bionemo_execution: bio,
    })).rejects.toThrow(/AGENT_RUN_RECEIPT_BINDING_MISMATCH/)

    await expect(admitNvidiaAgenticBioNemoExecution({
      observation: joinObservation(agent.receipt_digest, bio.receipt_digest, {
        task_id: 'other-task',
      }),
      agent_run: agent,
      bionemo_execution: bio,
    })).rejects.toThrow(/TASK_BINDING_MISMATCH/)
  })

  it('rejects malformed handoff traces, failed joins and authority-bearing observations', async () => {
    const { agent, bio } = await fixtures()

    await expect(admitNvidiaAgenticBioNemoExecution({
      observation: joinObservation(agent.receipt_digest, bio.receipt_digest, {
        handoff_trace_digest_sha256: 'bad',
      }),
      agent_run: agent,
      bionemo_execution: bio,
    })).rejects.toThrow(/INVALID_HANDOFF_TRACE_DIGEST/)

    await expect(admitNvidiaAgenticBioNemoExecution({
      observation: joinObservation(agent.receipt_digest, bio.receipt_digest, {
        terminal_state: 'FAILED',
      }),
      agent_run: agent,
      bionemo_execution: bio,
    })).rejects.toThrow(/AGENTIC_BIONEMO_EXECUTION_NOT_SUCCESSFUL/)

    await expect(admitNvidiaAgenticBioNemoExecution({
      observation: joinObservation(agent.receipt_digest, bio.receipt_digest, {
        authority_effect: 'KNOWLEDGE_ADMISSION' as never,
      }),
      agent_run: agent,
      bionemo_execution: bio,
    })).rejects.toThrow(NvidiaAgenticBioNemoError)
  })

  it('is deterministic across independent join admissions', async () => {
    const { agent, bio } = await fixtures()
    const request = {
      observation: joinObservation(agent.receipt_digest, bio.receipt_digest),
      agent_run: agent,
      bionemo_execution: bio,
    }

    const first = await admitNvidiaAgenticBioNemoExecution(request)
    const second = await admitNvidiaAgenticBioNemoExecution(request)
    const third = await admitNvidiaAgenticBioNemoExecution(request)

    expect(first).toEqual(second)
    expect(second).toEqual(third)
  })
})
