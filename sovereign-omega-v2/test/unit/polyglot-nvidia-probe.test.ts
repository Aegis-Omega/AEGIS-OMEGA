import { describe, expect, it } from 'vitest'
import {
  createNodeProbeRunner,
  probeCudaQBackend,
  probeNvidiaGpuEnvironment,
  probeNvidiaPythonConnector,
  type NvidiaProbeCommandResult,
  type NvidiaProbeRunner,
} from '../../src/polyglot/nvidia-probe'

class ScriptedProbeRunner implements NvidiaProbeRunner {
  readonly calls: Array<{ command: string; args: readonly string[] }> = []
  private index = 0

  constructor(private readonly results: readonly NvidiaProbeCommandResult[]) {}

  async run(command: string, args: readonly string[]): Promise<NvidiaProbeCommandResult> {
    this.calls.push({ command, args: [...args] })
    const result = this.results[this.index]
    this.index += 1
    if (!result) throw new Error('SCRIPTED_PROBE_RESULT_MISSING')
    return result
  }
}

const ok = (stdout: string): NvidiaProbeCommandResult => ({
  exit_code: 0,
  stdout,
  stderr: '',
  timed_out: false,
})

const missing = (): NvidiaProbeCommandResult => ({
  exit_code: 127,
  stdout: '',
  stderr: 'not found',
  timed_out: false,
})

describe('NVIDIA runtime probe harness', () => {
  it('executes a real child process without a shell through the production runner', async () => {
    const runner = createNodeProbeRunner({ timeout_ms: 5_000 })
    const result = await runner.run(process.execPath, ['-e', "process.stdout.write('probe-ok')"])

    expect(result.exit_code).toBe(0)
    expect(result.stdout).toBe('probe-ok')
    expect(result.stderr).toBe('')
    expect(result.timed_out).toBe(false)
  })

  it('produces a deterministic authority-neutral GPU observation from nvidia-smi', async () => {
    const inventory = [
      'GPU-aaaa, NVIDIA H100 80GB HBM3, 580.65.06, 9.0',
      'GPU-bbbb, NVIDIA H100 80GB HBM3, 580.65.06, 9.0',
    ].join('\n')
    const banner = '| NVIDIA-SMI 580.65.06 Driver Version: 580.65.06 CUDA Version: 13.0 |'
    const runner = new ScriptedProbeRunner([ok(inventory), ok(banner)])

    const first = await probeNvidiaGpuEnvironment({ runner })
    const secondRunner = new ScriptedProbeRunner([ok(inventory), ok(banner)])
    const second = await probeNvidiaGpuEnvironment({ runner: secondRunner })

    expect(first).toEqual(second)
    expect(first.detected).toBe(true)
    expect(first.gpu_count).toBe(2)
    expect(first.driver_version).toBe('580.65.06')
    expect(first.cuda_driver_version).toBe('13.0')
    expect(first.gpu_architectures).toEqual([
      'NVIDIA H100 80GB HBM3@compute-capability-9.0',
      'NVIDIA H100 80GB HBM3@compute-capability-9.0',
    ])
    expect(first.device_inventory_digest_sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(first.capability_receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(first.authority_class).toBe('NONE')
    expect(first.authority_effect).toBe('NONE')
    expect(runner.calls[0]).toEqual({
      command: 'nvidia-smi',
      args: [
        '--query-gpu=uuid,name,driver_version,compute_cap',
        '--format=csv,noheader,nounits',
      ],
    })
  })

  it('fails closed to a negative GPU observation instead of synthesizing hardware', async () => {
    const runner = new ScriptedProbeRunner([missing()])
    const observation = await probeNvidiaGpuEnvironment({ runner })

    expect(observation).toEqual({
      schema_version: 'AEGIS-NVIDIA-GPU-ENVIRONMENT-OBSERVATION-V1',
      detected: false,
      gpu_count: 0,
      driver_version: null,
      cuda_driver_version: null,
      gpu_architectures: [],
      device_inventory_digest_sha256: null,
      capability_receipt_digest: null,
      authority_class: 'NONE',
      authority_effect: 'NONE',
    })
  })

  it('probes BioNeMo, CUDA-Q and cuQuantum through a digest-bound Python package observation', async () => {
    for (const [connector_id, import_name, distribution_name] of [
      ['bionemo-ir', 'bionemo_ir', 'bionemo-ir'],
      ['cudaq', 'cudaq', 'cudaq'],
      ['cuquantum', 'cuquantum', 'cuquantum-python'],
    ] as const) {
      const runner = new ScriptedProbeRunner([ok(JSON.stringify({
        version: '1.2.3',
        module_file_sha256: 'a'.repeat(64),
      }))])

      const observation = await probeNvidiaPythonConnector({
        connector_id,
        runner,
        python_executable: 'python3',
      })

      expect(observation.connector_id).toBe(connector_id)
      expect(observation.detected).toBe(true)
      expect(observation.connector_version).toBe('1.2.3')
      expect(observation.executable_digest_sha256).toBe('a'.repeat(64))
      expect(observation.capability_receipt_digest).toMatch(/^[0-9a-f]{64}$/)
      expect(observation.authority_class).toBe('NONE')
      expect(observation.authority_effect).toBe('NONE')
      expect(runner.calls[0]?.command).toBe('python3')
      expect(runner.calls[0]?.args.join(' ')).toContain(import_name)
      expect(runner.calls[0]?.args.join(' ')).toContain(distribution_name)
    }
  })

  it('classifies CUDA-Q simulator properties without claiming physical QPU access', async () => {
    const runner = new ScriptedProbeRunner([ok(JSON.stringify({
      name: 'nvidia',
      simulator: 'custatevec',
      platform: 'default',
      description: 'NVIDIA GPU simulator',
      num_qpus: 1,
      is_remote: false,
      is_emulated: false,
    }))])

    const observation = await probeCudaQBackend({
      runner,
      target_name: 'nvidia',
      python_executable: 'python3',
    })

    expect(observation.target_name).toBe('nvidia')
    expect(observation.backend_kind).toBe('SIMULATOR')
    expect(observation.qpu_count).toBe(1)
    expect(observation.is_remote).toBe(false)
    expect(observation.is_emulated).toBe(false)
    expect(observation.platform_properties_digest_sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.capability_receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.authority_class).toBe('NONE')
    expect(observation.authority_effect).toBe('NONE')
  })

  it('classifies a CUDA-Q target with no simulator as hardware while preserving authority NONE', async () => {
    const runner = new ScriptedProbeRunner([ok(JSON.stringify({
      name: 'remote-qpu',
      simulator: '',
      platform: 'remote-rest',
      description: 'remote hardware',
      num_qpus: 2,
      is_remote: true,
      is_emulated: false,
    }))])

    const observation = await probeCudaQBackend({
      runner,
      target_name: 'remote-qpu',
      python_executable: 'python3',
    })

    expect(observation.backend_kind).toBe('HARDWARE')
    expect(observation.qpu_count).toBe(2)
    expect(observation.is_remote).toBe(true)
    expect(observation.is_emulated).toBe(false)
    expect(observation.authority_class).toBe('NONE')
    expect(observation.authority_effect).toBe('NONE')
  })
})
