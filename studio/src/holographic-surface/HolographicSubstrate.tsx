// EPISTEMIC TIER: T3 — holographic correspondence; shader itself T2
import { useEffect, useRef } from 'react'
import { HOLOGRAPHIC_SHADER_WGSL } from './shader.js'

// GPUBufferUsage not exposed as a runtime global in the TS DOM lib — use spec values
const GPU_BUFFER_USAGE_UNIFORM  = 0x0040
const GPU_BUFFER_USAGE_COPY_DST = 0x0008

export function HolographicSubstrate() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const hasWebGPU = typeof navigator !== 'undefined' && 'gpu' in navigator

  useEffect(() => {
    if (!hasWebGPU) return
    const canvas = canvasRef.current
    if (!canvas) return

    let rafId: number
    let destroyed = false

    ;(async () => {
      const gpu = (navigator as Navigator & { gpu: GPU }).gpu
      const adapter = await gpu.requestAdapter()
      if (!adapter || destroyed) return
      const device = await adapter.requestDevice()
      if (destroyed) { device.destroy(); return }

      const context = canvas.getContext('webgpu') as GPUCanvasContext | null
      if (!context) return
      const format = gpu.getPreferredCanvasFormat()
      context.configure({ device, format })

      const shaderModule = device.createShaderModule({ code: HOLOGRAPHIC_SHADER_WGSL })

      const pipeline = device.createRenderPipeline({
        layout: 'auto',
        vertex:   { module: shaderModule, entryPoint: 'vs_main' },
        fragment: { module: shaderModule, entryPoint: 'fs_main', targets: [{ format }] },
        primitive: { topology: 'triangle-strip', stripIndexFormat: 'uint32' },
      })

      const uniformBuf = device.createBuffer({
        size: 16,
        usage: GPU_BUFFER_USAGE_UNIFORM | GPU_BUFFER_USAGE_COPY_DST,
      })

      const bindGroup = device.createBindGroup({
        layout: pipeline.getBindGroupLayout(0),
        entries: [{ binding: 0, resource: { buffer: uniformBuf } }],
      })

      const uniforms = new Float32Array(4)
      const start = performance.now()

      const frame = () => {
        if (destroyed) return
        const w = canvas.clientWidth  || canvas.width
        const h = canvas.clientHeight || canvas.height
        if (canvas.width !== w || canvas.height !== h) {
          canvas.width = w; canvas.height = h
          context.configure({ device, format })
        }
        uniforms[0] = (performance.now() - start) / 1000
        uniforms[1] = w
        uniforms[2] = h
        uniforms[3] = 0
        device.queue.writeBuffer(uniformBuf, 0, uniforms)

        const encoder = device.createCommandEncoder()
        const pass = encoder.beginRenderPass({
          colorAttachments: [{
            view: context.getCurrentTexture().createView(),
            clearValue: { r: 0, g: 0, b: 0, a: 1 },
            loadOp: 'clear', storeOp: 'store',
          }],
        })
        pass.setPipeline(pipeline)
        pass.setBindGroup(0, bindGroup)
        pass.draw(4)
        pass.end()
        device.queue.submit([encoder.finish()])
        rafId = requestAnimationFrame(frame)
      }
      rafId = requestAnimationFrame(frame)
    })()

    return () => { destroyed = true; cancelAnimationFrame(rafId) }
  }, [hasWebGPU])

  if (!hasWebGPU) {
    return (
      <div className="flex items-center justify-center h-full text-aegis-muted font-mono text-xs">
        WebGPU not supported in this browser
      </div>
    )
  }

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full block"
      style={{ background: '#000' }}
    />
  )
}
