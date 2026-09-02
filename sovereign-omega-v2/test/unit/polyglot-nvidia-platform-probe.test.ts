import { describe, expect, it } from 'vitest'
import {
  probeNvidiaAgentPythonConnector,
  probeNvidiaCliConnector,
} from '../../src/polyglot/nvidia-agent-probe'
import {
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

describe('NVIDIA NeMo runtime probes', () => {
  it('probes current nemo CLI through a shell-free digest-bound executable observation', async () => {
    const runner = new ScriptedProbeRunner([ok(JSON.stringify({
      version: 'nemo-platform 1.4.0',
      executable_path: '/opt/nvidia/bin/nemo',
      executable_sha256: 'a'.repeat(64),
      returncode: 0,
    }))])

    const observation = await probeNvidiaCliConnector({
      connector_id: 'nemo-platform',
      runner,
      python_executable: 'python3',
    })

    expect(observation.connector_id).toBe('nemo-platform')
    expect(observation.detected).toBe(true)
    expect(observation.connector_version).toBe('nemo-platform 1.4.0')
    expect(observation.executable_digest_sha256).toBe('a'.repeat(64))
    expect(observation.capability_receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.authority_class).toBe('NONE')
    expect(observation.authority_effect).toBe('NONE')
    expect(runner.calls).toHaveLength(1)
    expect(runner.calls[0]?.command).toBe('python3')
    expect(runner.calls[0]?.args.join(' ')).toContain('shutil.which')
    expect(runner.calls[0]?.args.join(' ')).toContain('subprocess.run')
    expect(runner.calls[0]?.args.join(' ')).toContain('nemo')
  })

  it('fails closed to a negative nemo-platform observation when the CLI is unavailable', async () => {
    const runner = new ScriptedProbeRunner([missing()])
    const observation = await probeNvidiaCliConnector({
      connector_id: 'nemo-platform',
      runner,
    })

    expect(observation).toEqual({
      schema_version: 'AEGIS-NVIDIA-DETECTION-OBSERVATION-V1',
      connector_id: 'nemo-platform',
      detected: false,
      connector_version: null,
      executable_digest_sha256: null,
      capability_receipt_digest: null,
      authority_class: 'NONE',
      authority_effect: 'NONE',
    })
  })

  it('keeps legacy NAT as a separately evidenced CLI runtime', async () => {
    const runner = new ScriptedProbeRunner([ok(JSON.stringify({
      version: 'nat 1.2.0',
      executable_path: '/opt/nvidia/bin/nat',
      executable_sha256: 'b'.repeat(64),
      returncode: 0,
    }))])

    const observation = await probeNvidiaCliConnector({
      connector_id: 'nvidia-agent-toolkit',
      runner,
    })

    expect(observation.connector_id).toBe('nvidia-agent-toolkit')
    expect(observation.connector_version).toBe('nat 1.2.0')
    expect(observation.executable_digest_sha256).toBe('b'.repeat(64))
  })

  it('probes nemo-fabric as an exact Python package instead of inferring it from nemo CLI presence', async () => {
    const runner = new ScriptedProbeRunner([ok(JSON.stringify({
      version: '1.4.0',
      module_file_sha256: 'c'.repeat(64),
    }))])

    const observation = await probeNvidiaAgentPythonConnector({
      connector_id: 'nemo-fabric',
      runner,
      python_executable: 'python3',
    })

    expect(observation.connector_id).toBe('nemo-fabric')
    expect(observation.detected).toBe(true)
    expect(observation.connector_version).toBe('1.4.0')
    expect(observation.executable_digest_sha256).toBe('c'.repeat(64))
    expect(runner.calls[0]?.args.join(' ')).toContain('nemo_fabric')
    expect(runner.calls[0]?.args.join(' ')).toContain('nemo-fabric')
  })
})
