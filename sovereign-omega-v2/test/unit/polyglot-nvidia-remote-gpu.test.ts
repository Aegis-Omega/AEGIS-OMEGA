import { describe, expect, it } from 'vitest'
import {
  NvidiaRemoteGpuError,
  buildRemoteNvidiaGpuObservation,
  type RemoteNvidiaGpuProbePayload,
} from '../../src/polyglot/nvidia-remote-gpu'
import { admitNvidiaGpuEnvironment } from '../../src/polyglot/nvidia-execution'

const CANDIDATE = 'a'.repeat(40)

function payload(
  overrides: Partial<RemoteNvidiaGpuProbePayload> = {},
): RemoteNvidiaGpuProbePayload {
  return {
    schema_version: 'AEGIS-NVIDIA-REMOTE-GPU-PROBE-V1',
    provider: 'GCP_VERTEX',
    provider_job_id: 'projects/aegisomegav1/locations/us-central1/customJobs/123',
    candidate_sha: CANDIDATE,
    cuda_driver_version: '13.0',
    inventory: [
      {
        uuid: 'GPU-b',
        name: 'NVIDIA A100-SXM4-80GB',
        driver_version: '595.58.03',
        compute_capability: '8.0',
      },
      {
        uuid: 'GPU-a',
        name: 'NVIDIA A100-SXM4-80GB',
        driver_version: '595.58.03',
        compute_capability: '8.0',
      },
    ],
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

describe('remote NVIDIA GPU evidence binding', () => {
  it('normalizes remote Vertex raw evidence into the existing GPU admission boundary', async () => {
    const observation = await buildRemoteNvidiaGpuObservation(payload(), CANDIDATE)
    const receipt = await admitNvidiaGpuEnvironment(observation)

    expect(observation.detected).toBe(true)
    expect(observation.gpu_count).toBe(2)
    expect(observation.driver_version).toBe('595.58.03')
    expect(observation.cuda_driver_version).toBe('13.0')
    expect(observation.gpu_architectures).toEqual([
      'NVIDIA A100-SXM4-80GB@compute-capability-8.0',
      'NVIDIA A100-SXM4-80GB@compute-capability-8.0',
    ])
    expect(observation.device_inventory_digest_sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(observation.capability_receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(receipt.bioir_driver_compatible).toBe(true)
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
  })

  it('is deterministic when provider inventory arrives in a different order', async () => {
    const first = await buildRemoteNvidiaGpuObservation(payload(), CANDIDATE)
    const second = await buildRemoteNvidiaGpuObservation(payload({
      inventory: [...payload().inventory].reverse(),
    }), CANDIDATE)

    expect(second).toEqual(first)
  })

  it('rejects candidate-SHA splicing', async () => {
    await expect(buildRemoteNvidiaGpuObservation(payload(), 'b'.repeat(40)))
      .rejects.toThrow(/CANDIDATE_BINDING_MISMATCH/)
  })

  it('rejects authority widening and mixed driver observations', async () => {
    await expect(buildRemoteNvidiaGpuObservation(payload({
      authority_effect: 'KNOWLEDGE_ADMISSION' as never,
    }), CANDIDATE)).rejects.toThrow(/AUTHORITY_SPLICE_REJECTED/)

    await expect(buildRemoteNvidiaGpuObservation(payload({
      inventory: [
        payload().inventory[0]!,
        { ...payload().inventory[1]!, driver_version: '580.105.08' },
      ],
    }), CANDIDATE)).rejects.toThrow(NvidiaRemoteGpuError)
  })

  it('rejects unsupported providers instead of silently treating them as Vertex', async () => {
    await expect(buildRemoteNvidiaGpuObservation(payload({
      provider: 'UNKNOWN' as never,
    }), CANDIDATE)).rejects.toThrow(/UNSUPPORTED_REMOTE_GPU_PROVIDER/)
  })
})
