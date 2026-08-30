import type { PassNode } from '../framegraph/pass.js'
import type { ResourceRegistry } from '../framegraph/resources.js'
import { SIM_WIDTH, SIM_HEIGHT } from '../textures.js'

const DISPATCH_X = Math.ceil(SIM_WIDTH  / 8)
const DISPATCH_Y = Math.ceil(SIM_HEIGHT / 8)

export class SigmaPass implements PassNode {
  readonly name   = 'SigmaPass'
  readonly kind   = 'COMPUTE' as const
  readonly reads  = ['sigma-read', 'lambda-read']
  readonly writes = ['sigma-write']

  private bindGroup: GPUBindGroup | null = null

  private readonly pipeline: GPUComputePipeline
  constructor(pipeline: GPUComputePipeline) { this.pipeline = pipeline }

  setBindGroup(bg: GPUBindGroup): void { this.bindGroup = bg }

  execute(encoder: GPUCommandEncoder, _registry: ResourceRegistry): void {
    if (!this.bindGroup) throw new Error('SigmaPass: bind group not set')
    const pass = encoder.beginComputePass({ label: 'sigma-compute' })
    pass.setPipeline(this.pipeline)
    pass.setBindGroup(0, this.bindGroup)
    pass.dispatchWorkgroups(DISPATCH_X, DISPATCH_Y)
    pass.end()
  }
}
