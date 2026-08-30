import { GPU_TEXTURE_USAGE } from './constants.js'

export const SIM_WIDTH  = 1024
export const SIM_HEIGHT = 1024

const SIM_FORMAT: GPUTextureFormat = 'rgba32float'

const SIM_USAGE: GPUTextureUsageFlags =
  GPU_TEXTURE_USAGE.TEXTURE_BINDING |
  GPU_TEXTURE_USAGE.STORAGE_BINDING |
  GPU_TEXTURE_USAGE.COPY_SRC  |
  GPU_TEXTURE_USAGE.COPY_DST

export interface PingPongField {
  readonly a: GPUTexture
  readonly b: GPUTexture
}

export function createPingPongField(device: GPUDevice, label: string): PingPongField {
  const desc: GPUTextureDescriptor = {
    size: { width: SIM_WIDTH, height: SIM_HEIGHT },
    format: SIM_FORMAT,
    usage: SIM_USAGE,
  }
  return Object.freeze({
    a: device.createTexture({ ...desc, label: `${label}-A` }),
    b: device.createTexture({ ...desc, label: `${label}-B` }),
  })
}

export function seedSigmaTexture(device: GPUDevice, texture: GPUTexture): void {
  const data = new Float32Array(SIM_WIDTH * SIM_HEIGHT * 4)
  const cx = SIM_WIDTH  / 2
  const cy = SIM_HEIGHT / 2
  for (let y = 0; y < SIM_HEIGHT; y++) {
    for (let x = 0; x < SIM_WIDTH; x++) {
      const i  = (y * SIM_WIDTH + x) * 4
      const dx = x - cx
      const dy = y - cy
      const f0 = Math.sin(x * 0.050) * Math.cos(y * 0.050)
      const f1 = Math.sin(x * 0.130 + 1.21) * Math.cos(y * 0.110 + 0.73) * 0.45
      const f2 = Math.sin(x * 0.037 + y * 0.024 + 2.1) * 0.25
      const r  = Math.sqrt(dx * dx + dy * dy)
      const f3 = Math.cos(r * 0.016) * 0.20
      data[i]     = f0 + f1 + f2 + f3
      data[i + 3] = 1.0
    }
  }
  device.queue.writeTexture(
    { texture },
    data,
    { bytesPerRow: SIM_WIDTH * 4 * 4 },
    { width: SIM_WIDTH, height: SIM_HEIGHT },
  )
}

export function seedLambdaTexture(device: GPUDevice, texture: GPUTexture): void {
  const data = new Float32Array(SIM_WIDTH * SIM_HEIGHT * 4)
  const cx = SIM_WIDTH  / 2
  const cy = SIM_HEIGHT / 2
  for (let y = 0; y < SIM_HEIGHT; y++) {
    for (let x = 0; x < SIM_WIDTH; x++) {
      const i  = (y * SIM_WIDTH + x) * 4
      const dx = x - cx
      const dy = y - cy
      const r  = Math.sqrt(dx * dx + dy * dy)
      const f0 = Math.cos(x * 0.030) * Math.sin(y * 0.030) * 0.10
      const f1 = Math.cos(r * 0.012) * 0.06
      data[i]     = f0 + f1
      data[i + 3] = 1.0
    }
  }
  device.queue.writeTexture(
    { texture },
    data,
    { bytesPerRow: SIM_WIDTH * 4 * 4 },
    { width: SIM_WIDTH, height: SIM_HEIGHT },
  )
}

export function zeroTexture(device: GPUDevice, texture: GPUTexture): void {
  const data = new Float32Array(SIM_WIDTH * SIM_HEIGHT * 4)
  device.queue.writeTexture(
    { texture },
    data,
    { bytesPerRow: SIM_WIDTH * 4 * 4 },
    { width: SIM_WIDTH, height: SIM_HEIGHT },
  )
}
