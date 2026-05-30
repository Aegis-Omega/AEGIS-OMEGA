import { GPU_TEXTURE_USAGE } from './constants.js'

export const SIM_WIDTH  = 1024
export const SIM_HEIGHT = 1024

// rgba32float — supports both TEXTURE_BINDING (textureLoad) and STORAGE_BINDING (textureStore)
const SIM_FORMAT: GPUTextureFormat = 'rgba32float'

// Simulation textures need:
// TEXTURE_BINDING: readable via textureLoad in compute/fragment shaders
// STORAGE_BINDING: writable via textureStore in compute shaders
// COPY_DST:        allows initial data upload via writeTexture
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

// Seed σ with deterministic standing-wave pattern
export function seedSigmaTexture(device: GPUDevice, texture: GPUTexture): void {
  const data = new Float32Array(SIM_WIDTH * SIM_HEIGHT * 4)
  for (let y = 0; y < SIM_HEIGHT; y++) {
    for (let x = 0; x < SIM_WIDTH; x++) {
      const i = (y * SIM_WIDTH + x) * 4
      data[i]     = Math.sin(x * 0.05) * Math.cos(y * 0.05)
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

// Seed λ with gentle cosine pattern to create initial nebula cloud structure
export function seedLambdaTexture(device: GPUDevice, texture: GPUTexture): void {
  const data = new Float32Array(SIM_WIDTH * SIM_HEIGHT * 4)
  for (let y = 0; y < SIM_HEIGHT; y++) {
    for (let x = 0; x < SIM_WIDTH; x++) {
      const i = (y * SIM_WIDTH + x) * 4
      data[i]     = Math.cos(x * 0.03) * Math.sin(y * 0.03) * 0.1
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
