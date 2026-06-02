import { GPU_TEXTURE_USAGE } from './constants.js'
import type { DeviceContext } from './device.js'
import { SIM_WIDTH, SIM_HEIGHT, createPingPongField, seedSigmaTexture, seedLambdaTexture, zeroTexture } from './textures.js'
import type { PingPongField } from './textures.js'
import { createComputePipelines, createRenderPipeline } from './pipelines.js'
import {
  createUniformBuffer,
  writeUniforms,
  createSigmaBindGroups,
  createRhoBindGroups,
  createLambdaBindGroups,
  createRenderBindGroups,
} from './bindgroups.js'
import { ResourceRegistry } from './framegraph/resources.js'
import { FrameGraph } from './framegraph/graph.js'
import { Executor } from './framegraph/executor.js'
import { SigmaPass } from './passes/sigma.js'
import { RhoPass } from './passes/rho.js'
import { LambdaPass } from './passes/lambda.js'
import { RenderPass } from './passes/render.js'
import { FieldSampler } from './fieldSampler.js'
import type { FieldValues } from './fieldSampler.js'

export interface SimParams {
  readonly lambdaInfluence: number
  readonly sigmaPerturb: number
}

export interface FrameState {
  readonly frame: number
  readonly dt: number
  readonly lambdaInfluence: number
  readonly sigmaPerturb: number
  readonly passOrder: readonly string[]
}

const DT = 1 / 60

export class SimulationEngine {
  private readonly device: GPUDevice
  private readonly uniformBuffer: GPUBuffer
  private readonly registry: ResourceRegistry
  private readonly executor: Executor
  private readonly sigmaPass: SigmaPass
  private readonly rhoPass: RhoPass
  private readonly lambdaPass: LambdaPass
  private readonly renderPass: RenderPass

  private readonly sigmaBGs: readonly [GPUBindGroup, GPUBindGroup]
  private readonly rhoBGs: readonly [GPUBindGroup, GPUBindGroup]
  private readonly lambdaBGs: readonly [GPUBindGroup, GPUBindGroup]
  private readonly renderBGs: readonly [GPUBindGroup, GPUBindGroup]
  private readonly sampler: FieldSampler
  private readonly sigmaField: PingPongField
  private readonly rhoField:   PingPongField
  private readonly lambdaField: PingPongField

  private parity = 0
  private frame  = 0
  private lastParams: SimParams = { lambdaInfluence: 0.5, sigmaPerturb: 0 }
  private mouseX = -1
  private mouseY = 0
  private readonly passOrder: readonly string[]

  private constructor(
    ctx: DeviceContext,
    uniformBuffer: GPUBuffer,
    registry: ResourceRegistry,
    executor: Executor,
    sigmaPass: SigmaPass,
    rhoPass: RhoPass,
    lambdaPass: LambdaPass,
    renderPass: RenderPass,
    sigmaBGs: readonly [GPUBindGroup, GPUBindGroup],
    rhoBGs: readonly [GPUBindGroup, GPUBindGroup],
    lambdaBGs: readonly [GPUBindGroup, GPUBindGroup],
    renderBGs: readonly [GPUBindGroup, GPUBindGroup],
    sigmaField: PingPongField,
    rhoField:   PingPongField,
    lambdaField: PingPongField,
  ) {
    this.device        = ctx.device
    this.uniformBuffer = uniformBuffer
    this.registry      = registry
    this.executor      = executor
    this.sigmaPass     = sigmaPass
    this.rhoPass       = rhoPass
    this.lambdaPass    = lambdaPass
    this.renderPass    = renderPass
    this.sigmaBGs      = sigmaBGs
    this.rhoBGs        = rhoBGs
    this.lambdaBGs     = lambdaBGs
    this.renderBGs     = renderBGs
    this.passOrder     = executor.passNames
    this.sigmaField    = sigmaField
    this.rhoField      = rhoField
    this.lambdaField   = lambdaField
    this.sampler       = new FieldSampler(ctx.device)
  }

  static async create(ctx: DeviceContext): Promise<SimulationEngine> {
    const { device } = ctx

    const sigma  = createPingPongField(device, 'sigma')
    const rho    = createPingPongField(device, 'rho')
    const lambda = createPingPongField(device, 'lambda')

    seedSigmaTexture(device, sigma.a)
    seedLambdaTexture(device, lambda.a)
    zeroTexture(device, rho.a)
    zeroTexture(device, sigma.b)
    zeroTexture(device, rho.b)
    zeroTexture(device, lambda.b)

    const [computePipelines, renderPipelineSet] = await Promise.all([
      createComputePipelines(device),
      createRenderPipeline(device, ctx.canvasFormat),
    ])

    const uniformBuffer = createUniformBuffer(device)

    const sigmaBGsObj  = createSigmaBindGroups(device, computePipelines, sigma, lambda, uniformBuffer)
    const rhoBGsObj    = createRhoBindGroups(device, computePipelines, sigma, rho, uniformBuffer)
    const lambdaBGsObj = createLambdaBindGroups(device, computePipelines, lambda, sigma, uniformBuffer)
    const renderBGsObj = createRenderBindGroups(device, renderPipelineSet, sigma, rho, lambda, uniformBuffer)

    const sigmaPass  = new SigmaPass(computePipelines.sigma)
    const rhoPass    = new RhoPass(computePipelines.rho)
    const lambdaPass = new LambdaPass(computePipelines.lambda)
    const renderPass = new RenderPass(renderPipelineSet.render, ctx)

    const graph = new FrameGraph()
    graph.addPass(sigmaPass)
    graph.addPass(rhoPass)
    graph.addPass(lambdaPass)
    graph.addPass(renderPass)
    const executor = new Executor(graph)

    const registry = new ResourceRegistry()
    registry.register('sigma-read',   sigma.a)
    registry.register('sigma-write',  sigma.b)
    registry.register('rho-write',    rho.b)
    registry.register('lambda-read',  lambda.a)
    registry.register('lambda-write', lambda.b)
    const dummyCanvas = device.createTexture({
      size: [1, 1],
      format: ctx.canvasFormat,
      usage: GPU_TEXTURE_USAGE.RENDER_ATTACHMENT,
    })
    registry.register('canvas', dummyCanvas)

    const sigmaBGs:  readonly [GPUBindGroup, GPUBindGroup] = [sigmaBGsObj.atob,   sigmaBGsObj.btoa]
    const rhoBGs:    readonly [GPUBindGroup, GPUBindGroup] = [rhoBGsObj.atob,     rhoBGsObj.btoa]
    const lambdaBGs: readonly [GPUBindGroup, GPUBindGroup] = [lambdaBGsObj.atob,  lambdaBGsObj.btoa]
    const renderBGs: readonly [GPUBindGroup, GPUBindGroup] = [renderBGsObj.readB, renderBGsObj.readA]

    return new SimulationEngine(
      ctx, uniformBuffer, registry, executor,
      sigmaPass, rhoPass, lambdaPass, renderPass,
      sigmaBGs, rhoBGs, lambdaBGs, renderBGs,
      sigma, rho, lambda,
    )
  }

  reset(): void {
    seedSigmaTexture(this.device, this.sigmaField.a)
    zeroTexture(this.device, this.sigmaField.b)
    seedLambdaTexture(this.device, this.lambdaField.a)
    zeroTexture(this.device, this.lambdaField.b)
    zeroTexture(this.device, this.rhoField.a)
    zeroTexture(this.device, this.rhoField.b)
    this.frame  = 0
    this.parity = 0
  }

  setMouse(x: number, y: number, pressed: boolean): void {
    this.mouseX = x
    this.mouseY = pressed ? y : -(y + 1.0)
  }

  clearMouse(): void {
    this.mouseX = -1
    this.mouseY = 0
  }

  tick(params: SimParams, canvasAspect: number): void {
    this.lastParams = params

    writeUniforms(
      this.device,
      this.uniformBuffer,
      DT,
      this.frame,
      params.lambdaInfluence,
      params.sigmaPerturb,
      SIM_WIDTH,
      SIM_HEIGHT,
      this.mouseX,
      this.mouseY,
      canvasAspect,
    )

    this.sigmaPass.setBindGroup(this.sigmaBGs[this.parity])
    this.rhoPass.setBindGroup(this.rhoBGs[this.parity])
    this.lambdaPass.setBindGroup(this.lambdaBGs[this.parity])
    this.renderPass.setBindGroup(this.renderBGs[this.parity])

    const encoder = this.device.createCommandEncoder({ label: `frame-${this.frame}` })
    this.executor.execute(encoder, this.registry)

    const doSample = this.sampler.shouldSample(this.frame)
    if (doSample) {
      const ws = (f: PingPongField) => this.parity === 0 ? f.b : f.a
      this.sampler.sample(encoder, ws(this.sigmaField), ws(this.rhoField), ws(this.lambdaField))
    }

    this.device.queue.submit([encoder.finish()])
    if (doSample) this.sampler.resolveAsync()

    this.parity ^= 1
    this.frame++
  }

  getFieldValues(): FieldValues { return this.sampler.getValues() }

  getFrameState(): FrameState {
    return Object.freeze({
      frame: this.frame,
      dt: DT,
      lambdaInfluence: this.lastParams.lambdaInfluence,
      sigmaPerturb: this.lastParams.sigmaPerturb,
      passOrder: this.passOrder,
    })
  }
}
