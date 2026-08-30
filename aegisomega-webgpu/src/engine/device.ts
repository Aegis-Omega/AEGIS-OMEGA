export interface DeviceContext {
  readonly device: GPUDevice
  readonly queue: GPUQueue
  readonly canvasFormat: GPUTextureFormat
  readonly context: GPUCanvasContext
}

export function configureCanvas(device: GPUDevice, canvas: HTMLCanvasElement): DeviceContext {
  const context = canvas.getContext('webgpu') as GPUCanvasContext | null
  if (!context) throw new Error('Failed to get WebGPU canvas context')
  const canvasFormat = navigator.gpu.getPreferredCanvasFormat()
  context.configure({ device, format: canvasFormat, alphaMode: 'opaque' })
  return Object.freeze({ device, queue: device.queue, canvasFormat, context })
}

export function resizeCanvas(
  ctx: DeviceContext,
  canvas: HTMLCanvasElement,
  width: number,
  height: number,
): void {
  canvas.width  = width
  canvas.height = height
  ctx.context.configure({ device: ctx.device, format: ctx.canvasFormat, alphaMode: 'opaque' })
}
