import type { PassNode } from '../framegraph/pass.js'
import type { ResourceRegistry } from '../framegraph/resources.js'
import { SIM_WIDTH, SIM_HEIGHT } from '../textures.js'

const DISPATCH_X = Math.ceil(SIM_WIDTH  / 8)
const DISPATCH_Y = Math.ceil(SIM_HEIGHT / 8)

export class RhoPass implements PassNode {
  readonly name   = 'RhoPass'
  readonly kind   = 'COMPUTE' as const
  readonly reads  = ['sigma-write']
  readonly writes = ['rho-write']

  private bindGroup: GPUBindGroup | null = null

  private readonly pipeline: GPUComputePipeline
  constructor(pipeline: GPUComputePipeline) { this.pipeline = pipeline }

  setBindGroup(bg: GPUBindGroup): void { this.bindGroup = bg }

  execute(encoder: GPUCommandEncoder, _registry: ResourceRegistry): void {
    if (!this.bindGroup) throw new Error('RhoPass: bind group not set')
    const pass = encoder.beginComputePass({ label: 'rho-compute' })
    pass.setPipeline(this.pipeline)
    pass.setBindGroup(0, this.bindGroup)
    pass.dispatchWorkgroups(DISPATCH_X, DISPATCH_Y)
    pass.end()
  }
}
