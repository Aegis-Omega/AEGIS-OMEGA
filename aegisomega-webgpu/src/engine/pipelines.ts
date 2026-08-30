import sigmaWgsl  from '../shaders/sigma.wgsl?raw'
import rhoWgsl    from '../shaders/rho.wgsl?raw'
import lambdaWgsl from '../shaders/lambda.wgsl?raw'
import renderWgsl from '../shaders/render.wgsl?raw'

export interface ComputePipelines {
  readonly sigma : GPUComputePipeline
  readonly rho   : GPUComputePipeline
  readonly lambda: GPUComputePipeline
}

export interface RenderPipelineSet {
  readonly render: GPURenderPipeline
}

async function compileShader(device: GPUDevice, code: string, label: string): Promise<GPUShaderModule> {
  const mod = device.createShaderModule({ label, code })
  const info = await mod.getCompilationInfo()
  for (const msg of info.messages) {
    if (msg.type === 'error') {
      throw new Error(`Shader compile error [${label}] line ${msg.lineNum}: ${msg.message}`)
    }
  }
  return mod
}

export async function createComputePipelines(device: GPUDevice): Promise<ComputePipelines> {
  const [sigmaMod, rhoMod, lambdaMod] = await Promise.all([
    compileShader(device, sigmaWgsl,  'sigma-shader'),
    compileShader(device, rhoWgsl,    'rho-shader'),
    compileShader(device, lambdaWgsl, 'lambda-shader'),
  ])
  const [sigma, rho, lambda] = await Promise.all([
    device.createComputePipelineAsync({
      label: 'sigma-pipeline',
      layout: 'auto',
      compute: { module: sigmaMod,  entryPoint: 'main' },
    }),
    device.createComputePipelineAsync({
      label: 'rho-pipeline',
      layout: 'auto',
      compute: { module: rhoMod,    entryPoint: 'main' },
    }),
    device.createComputePipelineAsync({
      label: 'lambda-pipeline',
      layout: 'auto',
      compute: { module: lambdaMod, entryPoint: 'main' },
    }),
  ])
  return Object.freeze({ sigma, rho, lambda })
}

export async function createRenderPipeline(
  device: GPUDevice,
  canvasFormat: GPUTextureFormat,
): Promise<RenderPipelineSet> {
  const renderMod = await compileShader(device, renderWgsl, 'render-shader')
  const render = await device.createRenderPipelineAsync({
    label: 'render-pipeline',
    layout: 'auto',
    vertex:   { module: renderMod, entryPoint: 'vs_main' },
    fragment: {
      module: renderMod,
      entryPoint: 'fs_main',
      targets: [{ format: canvasFormat }],
    },
    primitive: { topology: 'triangle-list' },
  })
  return Object.freeze({ render })
}
