import { describe, expect, it } from 'vitest'
import {
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

describe('NVIDIA BioNeMo Framework runtime probe', () => {
  it('probes bionemo.fw and binds the bionemo-fw distribution independently from BioIR', async () => {
    const runner = new ScriptedProbeRunner([ok(JSON.stringify({
      version: '2.7.0',
      module_file_sha256: 'f'.repeat(64),
    }))])

    const observation = await probeNvidiaPythonConnector({
      connector_id: 'bionemo-framework',
      runner,
      python_executable: 'python3',
    })

    expect(observation.connector_id).toBe('bionemo-framework')
    expect(observation.detected).toBe(true)
    expect(observation.connector_version).toBe('2.7.0')
    expect(observation.executable_digest_sha256).toBe('f'.repeat(64))
    expect(observation.capability_receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.authority_class).toBe('NONE')
    expect(observation.authority_effect).toBe('NONE')
    expect(runner.calls).toHaveLength(1)
    expect(runner.calls[0]?.command).toBe('python3')
    expect(runner.calls[0]?.args.join(' ')).toContain('bionemo.fw')
    expect(runner.calls[0]?.args.join(' ')).toContain('bionemo-fw')
    expect(runner.calls[0]?.args.join(' ')).not.toContain('bionemo_ir')
  })
})
