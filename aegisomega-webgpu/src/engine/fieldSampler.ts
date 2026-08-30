import { GPU_BUFFER_USAGE } from './constants.js'
import { SIM_WIDTH, SIM_HEIGHT } from './textures.js'

const SAMPLE_INTERVAL = 10
const STAGING_STRIDE = 256
const GPU_MAP_READ = 0x0001 as GPUMapModeFlags

const CENTER_X = Math.floor(SIM_WIDTH  / 2)
const CENTER_Y = Math.floor(SIM_HEIGHT / 2)

export interface FieldValues {
  readonly sigma: number
  readonly rho: number
  readonly lambda: number
}

export class FieldSampler {
  private readonly stagingSigma:  GPUBuffer
  private readonly stagingRho:    GPUBuffer
  private readonly stagingLambda: GPUBuffer
  private last: FieldValues = { sigma: 0, rho: 0, lambda: 0 }
  private pending = false

  constructor(device: GPUDevice) {
    const desc: GPUBufferDescriptor = {
      size:  STAGING_STRIDE,
      usage: GPU_BUFFER_USAGE.MAP_READ | GPU_BUFFER_USAGE.COPY_DST,
    }
    this.stagingSigma  = device.createBuffer({ ...desc, label: 'staging-sigma' })
    this.stagingRho    = device.createBuffer({ ...desc, label: 'staging-rho' })
    this.stagingLambda = device.createBuffer({ ...desc, label: 'staging-lambda' })
  }

  sample(
    encoder: GPUCommandEncoder,
    sigmaTexture:  GPUTexture,
    rhoTexture:    GPUTexture,
    lambdaTexture: GPUTexture,
  ): void {
    if (this.pending) return

    const copyPixel = (src: GPUTexture, dst: GPUBuffer): void => {
      encoder.copyTextureToBuffer(
        { texture: src, origin: { x: CENTER_X, y: CENTER_Y, z: 0 } },
        { buffer: dst, bytesPerRow: STAGING_STRIDE },
        { width: 1, height: 1, depthOrArrayLayers: 1 },
      )
    }
    copyPixel(sigmaTexture,  this.stagingSigma)
    copyPixel(rhoTexture,    this.stagingRho)
    copyPixel(lambdaTexture, this.stagingLambda)

    this.pending = true
  }

  resolveAsync(): void {
    if (!this.pending) return

    const read = async (): Promise<void> => {
      await Promise.all([
        this.stagingSigma.mapAsync(GPU_MAP_READ),
        this.stagingRho.mapAsync(GPU_MAP_READ),
        this.stagingLambda.mapAsync(GPU_MAP_READ),
      ])

      const sigma  = new Float32Array(this.stagingSigma.getMappedRange())[0]
      const rho    = new Float32Array(this.stagingRho.getMappedRange())[0]
      const lambda = new Float32Array(this.stagingLambda.getMappedRange())[0]

      this.stagingSigma.unmap()
      this.stagingRho.unmap()
      this.stagingLambda.unmap()

      this.last    = Object.freeze({ sigma, rho, lambda })
      this.pending = false
    }

    void read()
  }

  getValues(): FieldValues { return this.last }

  shouldSample(frame: number): boolean {
    return !this.pending && frame % SAMPLE_INTERVAL === 0
  }
}
