import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  buildRemoteNvidiaGpuObservation,
  type RemoteNvidiaGpuProbePayload,
} from '../../src/polyglot/nvidia-remote-gpu'
import { admitNvidiaGpuEnvironment } from '../../src/polyglot/nvidia-execution'

const live = process.env.AEGIS_NVIDIA_VERTEX_LIVE === '1' ? it : it.skip

describe('Vertex NVIDIA live receipt', () => {
  live('admits exact-candidate remote GPU evidence through the canonical NVIDIA GPU boundary', async () => {
    const expectedSha = process.env.AEGIS_EXPECTED_SHA?.trim()
    const probePath = process.env.AEGIS_NVIDIA_REMOTE_PROBE_PATH?.trim()
    const receiptPath = process.env.AEGIS_NVIDIA_GPU_RECEIPT_PATH?.trim()

    if (!expectedSha) throw new Error('AEGIS_EXPECTED_SHA_REQUIRED')
    if (!probePath) throw new Error('AEGIS_NVIDIA_REMOTE_PROBE_PATH_REQUIRED')
    if (!receiptPath) throw new Error('AEGIS_NVIDIA_GPU_RECEIPT_PATH_REQUIRED')

    const raw = await readFile(resolve(probePath), 'utf8')
    const payload = JSON.parse(raw) as RemoteNvidiaGpuProbePayload
    const observation = await buildRemoteNvidiaGpuObservation(payload, expectedSha)
    const receipt = await admitNvidiaGpuEnvironment(observation)

    expect(receipt.status).toBe('VERIFIED_AVAILABLE')
    expect(receipt.bioir_driver_compatible).toBe(true)
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
    expect(receipt.receipt_digest).toMatch(/^[0-9a-f]{64}$/)

    const output = resolve(receiptPath)
    await mkdir(dirname(output), { recursive: true })
    await writeFile(output, `${JSON.stringify(receipt, null, 2)}\n`, 'utf8')
  })
})
