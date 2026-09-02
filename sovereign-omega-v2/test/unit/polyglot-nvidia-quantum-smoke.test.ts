import { describe, expect, it } from 'vitest'
import { admitNvidiaConnector, NVIDIA_DETECTION_OBSERVATION_SCHEMA } from '../../src/polyglot/nvidia'
import {
  admitCudaQBackend,
  CUDAQ_BACKEND_OBSERVATION_SCHEMA,
  type CudaQBackendReceipt,
} from '../../src/polyglot/nvidia-execution'
import {
  type NvidiaProbeCommandResult,
  type NvidiaProbeRunner,
} from '../../src/polyglot/nvidia-probe'
import {
  executeCudaQSimulatorSmoke,
  NvidiaQuantumSmokeError,
} from '../../src/polyglot/nvidia-quantum-smoke'

class ScriptedRunner implements NvidiaProbeRunner {
  readonly calls: Array<{ command: string; args: readonly string[] }> = []
  private index = 0

  constructor(private readonly results: readonly NvidiaProbeCommandResult[]) {}

  async run(command: string, args: readonly string[]): Promise<NvidiaProbeCommandResult> {
    this.calls.push({ command, args: [...args] })
    const result = this.results[this.index]
    this.index += 1
    if (!result) throw new Error('SCRIPTED_RESULT_MISSING')
    return result
  }
}

const ok = (stdout: string): NvidiaProbeCommandResult => ({
  exit_code: 0,
  stdout,
  stderr: '',
  timed_out: false,
})

async function simulatorBackend(targetName = 'qpp-cpu'): Promise<CudaQBackendReceipt> {
  const cudaqEvidence = admitNvidiaConnector({
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: 'cudaq',
    detected: true,
    connector_version: '0.14.0',
    executable_digest_sha256: 'a'.repeat(64),
    capability_receipt_digest: 'b'.repeat(64),
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })

  return admitCudaQBackend({
    cudaq_evidence: cudaqEvidence,
    observation: {
      schema_version: CUDAQ_BACKEND_OBSERVATION_SCHEMA,
      target_name: targetName,
      backend_kind: 'SIMULATOR',
      qpu_count: 1,
      is_remote: false,
      is_emulated: false,
      platform_properties_digest_sha256: 'c'.repeat(64),
      capability_receipt_digest: 'd'.repeat(64),
      authority_class: 'NONE',
      authority_effect: 'NONE',
    },
  })
}

async function hardwareBackend(): Promise<CudaQBackendReceipt> {
  const cudaqEvidence = admitNvidiaConnector({
    schema_version: NVIDIA_DETECTION_OBSERVATION_SCHEMA,
    connector_id: 'cudaq',
    detected: true,
    connector_version: '0.14.0',
    executable_digest_sha256: 'a'.repeat(64),
    capability_receipt_digest: 'b'.repeat(64),
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })

  return admitCudaQBackend({
    cudaq_evidence: cudaqEvidence,
    observation: {
      schema_version: CUDAQ_BACKEND_OBSERVATION_SCHEMA,
      target_name: 'remote-qpu',
      backend_kind: 'HARDWARE',
      qpu_count: 1,
      is_remote: true,
      is_emulated: false,
      platform_properties_digest_sha256: 'c'.repeat(64),
      capability_receipt_digest: 'd'.repeat(64),
      authority_class: 'NONE',
      authority_effect: 'NONE',
    },
  })
}

describe('CUDA-Q simulator smoke execution', () => {
  it('executes a bounded Bell sample and emits an authority-neutral execution observation', async () => {
    const backend = await simulatorBackend()
    const runner = new ScriptedRunner([ok(JSON.stringify({
      target_name: 'qpp-cpu',
      counts: { '00': 5, '11': 3 },
    }))])

    const observation = await executeCudaQSimulatorSmoke({
      task_id: 'cudaq-smoke-1',
      backend,
      runner,
      python_executable: 'python3',
      shots_count: 8,
    })

    expect(observation.schema_version).toBe('AEGIS-NVIDIA-QUANTUM-EXECUTION-OBSERVATION-V1')
    expect(observation.task_id).toBe('cudaq-smoke-1')
    expect(observation.completed).toBe(true)
    expect(observation.backend_receipt_digest).toBe(backend.receipt_digest)
    expect(observation.execution_kind).toBe('SAMPLE')
    expect(observation.shots_count).toBe(8)
    expect(observation.kernel_digest_sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.input_digest_sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.output_digest_sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.execution_receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.authority_class).toBe('NONE')
    expect(observation.authority_effect).toBe('NONE')

    expect(runner.calls).toHaveLength(1)
    expect(runner.calls[0]?.command).toBe('python3')
    const script = runner.calls[0]?.args.join(' ') ?? ''
    expect(script).toContain('cudaq.set_target("qpp-cpu")')
    expect(script).toContain('cudaq.make_kernel()')
    expect(script).toContain('kernel.qalloc(2)')
    expect(script).toContain('kernel.h(q[0])')
    expect(script).toContain('kernel.cx(q[0], q[1])')
    expect(script).not.toContain('@cudaq.kernel')
    expect(script).toContain('cudaq.sample')
    expect(script).toContain('shots_count=8')
  })

  it('rejects hardware backends before launching any process', async () => {
    const backend = await hardwareBackend()
    const runner = new ScriptedRunner([])

    await expect(executeCudaQSimulatorSmoke({
      task_id: 'must-not-run-hardware',
      backend,
      runner,
      shots_count: 8,
    })).rejects.toThrow('HARDWARE_EXECUTION_REQUIRES_EXPLICIT_GATE')

    expect(runner.calls).toHaveLength(0)
  })

  it('fails closed when reported counts do not sum to the requested shots', async () => {
    const backend = await simulatorBackend()
    const runner = new ScriptedRunner([ok(JSON.stringify({
      target_name: 'qpp-cpu',
      counts: { '00': 2, '11': 2 },
    }))])

    await expect(executeCudaQSimulatorSmoke({
      task_id: 'bad-counts',
      backend,
      runner,
      shots_count: 8,
    })).rejects.toThrow('CUDAQ_SAMPLE_SHOT_COUNT_MISMATCH')
  })

  it('fails closed on process failure instead of synthesizing an execution receipt', async () => {
    const backend = await simulatorBackend()
    const runner = new ScriptedRunner([{
      exit_code: 1,
      stdout: '',
      stderr: 'cudaq runtime failed',
      timed_out: false,
    }])

    await expect(executeCudaQSimulatorSmoke({
      task_id: 'failed-runtime',
      backend,
      runner,
      shots_count: 8,
    })).rejects.toBeInstanceOf(NvidiaQuantumSmokeError)
  })
})
