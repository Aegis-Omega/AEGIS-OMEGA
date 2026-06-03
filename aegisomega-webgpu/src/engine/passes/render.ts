import type { PassNode } from '../framegraph/pass.js'
import type { ResourceRegistry } from '../framegraph/resources.js'
import type { DeviceContext } from '../device.js'

export class RenderPass implements PassNode {
  readonly name   = 'RenderPass'
  readonly kind   = 'RENDER' as const
  readonly reads  = ['sigma-write', 'rho-write', 'lambda-write']
  readonly writes = ['canvas']

  private bindGroup: GPUBindGroup | null = null

  private readonly pipeline: GPURenderPipeline
  private readonly ctx: DeviceContext
  constructor(pipeline: GPURenderPipeline, ctx: DeviceContext) {
    this.pipeline = pipeline
    this.ctx = ctx
  }

  setBindGroup(bg: GPUBindGroup): void { this.bindGroup = bg }

  execute(encoder: GPUCommandEncoder, _registry: ResourceRegistry): void {
    if (!this.bindGroup) throw new Error('RenderPass: bind group not set')
    const colorAttachment: GPURenderPassColorAttachment = {
      view:       this.ctx.context.getCurrentTexture().createView(),
      loadOp:     'clear',
      storeOp:    'store',
      clearValue: { r: 0.008, g: 0.012, b: 0.042, a: 1.0 },
    }
    const pass = encoder.beginRenderPass({
      label: 'render-pass',
      colorAttachments: [colorAttachment],
    })
    pass.setPipeline(this.pipeline)
    pass.setBindGroup(0, this.bindGroup)
    pass.draw(3)
    pass.end()
  }
}
