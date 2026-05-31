import { useEffect, useRef } from 'react'
import sigmaWGSL  from '../shaders/sigma.wgsl?raw'
import rhoWGSL    from '../shaders/rho.wgsl?raw'
import lambdaWGSL from '../shaders/lambda.wgsl?raw'
import renderWGSL from '../shaders/render.wgsl?raw'

const SIM_W = 512
const SIM_H = 512
const DX = 64   // SIM_W / workgroup_x(8)
const DY = 64   // SIM_H / workgroup_y(8)
const UF_BYTES = 64  // uniform buffer padded to 64 bytes

// GPUTextureUsage / GPUBufferUsage flags are not reliably in scope as global
// values in all TypeScript DOM lib versions — use spec-defined numeric constants.
const TEX_USAGE = 0x0E  // TEXTURE_BINDING(0x4) | STORAGE_BINDING(0x8) | COPY_DST(0x2)
const UNI_USAGE = 0x48  // UNIFORM(0x40) | COPY_DST(0x8)

function seedField(fn: (x: number, y: number) => number): Float32Array {
  const d = new Float32Array(SIM_W * SIM_H * 4)
  for (let y = 0; y < SIM_H; y++)
    for (let x = 0; x < SIM_W; x++) {
      const i = (y * SIM_W + x) * 4
      d[i] = fn(x, y)
      d[i + 3] = 1
    }
  return d
}

export function WebGPUBackground() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !navigator.gpu) return

    let stopped = false
    let rafId = 0

    async function run(): Promise<void> {
      // Re-check inside async closure for TypeScript narrowing
      if (!canvas) return

      const adapter = await navigator.gpu.requestAdapter()
      if (!adapter || stopped) return
      const device = await adapter.requestDevice()
      if (stopped) { device.destroy(); return }

      const dpr = Math.min(devicePixelRatio, 2)
      canvas.width  = Math.round(window.innerWidth  * dpr)
      canvas.height = Math.round(window.innerHeight * dpr)

      // Cast to GPUCanvasContext — getContext('webgpu') returns the generic
      // RenderingContext union in TypeScript's DOM overloads.
      const ctxMaybe = canvas.getContext('webgpu') as GPUCanvasContext | null
      if (!ctxMaybe) { device.destroy(); return }
      const ctx: GPUCanvasContext = ctxMaybe  // pinned non-null for closure capture
      const fmt = navigator.gpu.getPreferredCanvasFormat()
      ctx.configure({ device, format: fmt, alphaMode: 'opaque' })

      function mkTex(label: string): GPUTexture {
        return device.createTexture({
          label,
          size: { width: SIM_W, height: SIM_H },
          format: 'rgba32float',
          usage: TEX_USAGE,
        })
      }

      const tSigA = mkTex('sigA'), tSigB = mkTex('sigB')
      const tRhoA = mkTex('rhoA'), tRhoB = mkTex('rhoB')
      const tLamA = mkTex('lamA'), tLamB = mkTex('lamB')

      const row     = SIM_W * 16
      const sz      = { width: SIM_W, height: SIM_H }
      const sigSeed = seedField((x, y) => Math.sin(x * 0.05) * Math.cos(y * 0.05))
      const lamSeed = seedField((x, y) => Math.cos(x * 0.03) * Math.sin(y * 0.03) * 0.1)

      device.queue.writeTexture({ texture: tSigA }, sigSeed, { bytesPerRow: row }, sz)
      device.queue.writeTexture({ texture: tSigB }, sigSeed, { bytesPerRow: row }, sz)
      device.queue.writeTexture({ texture: tLamA }, lamSeed, { bytesPerRow: row }, sz)
      device.queue.writeTexture({ texture: tLamB }, lamSeed, { bytesPerRow: row }, sz)

      const ubuf = device.createBuffer({ size: UF_BYTES, usage: UNI_USAGE })

      async function mkComputePipeline(wgsl: string): Promise<GPUComputePipeline> {
        const mod  = device.createShaderModule({ code: wgsl })
        const info = await mod.getCompilationInfo()
        for (const m of info.messages) if (m.type === 'error') throw new Error(`WGSL: ${m.message}`)
        return device.createComputePipeline({ layout: 'auto', compute: { module: mod, entryPoint: 'main' } })
      }

      const pSig = await mkComputePipeline(sigmaWGSL)
      const pRho = await mkComputePipeline(rhoWGSL)
      const pLam = await mkComputePipeline(lambdaWGSL)

      const rMod  = device.createShaderModule({ code: renderWGSL })
      const pRend = device.createRenderPipeline({
        layout: 'auto',
        vertex:    { module: rMod, entryPoint: 'vs_main' },
        fragment:  { module: rMod, entryPoint: 'fs_main', targets: [{ format: fmt }] },
        primitive: { topology: 'triangle-list' },
      })

      // ── Bind group factories ────────────────────────────────────────────────
      // sigma:  @0=sigma_in  @1=sigma_out  @2=lambda_in  @3=uniforms
      function mkSigBG(p: number): GPUBindGroup {
        const [si, so, li] = p === 0 ? [tSigA, tSigB, tLamA] : [tSigB, tSigA, tLamB]
        return device.createBindGroup({ layout: pSig.getBindGroupLayout(0), entries: [
          { binding: 0, resource: si.createView() },
          { binding: 1, resource: so.createView() },
          { binding: 2, resource: li.createView() },
          { binding: 3, resource: { buffer: ubuf } },
        ]})
      }
      // rho:    @0=sigma_in  @1=rho_out  @2=uniforms
      function mkRhoBG(p: number): GPUBindGroup {
        const [si, ro] = p === 0 ? [tSigB, tRhoB] : [tSigA, tRhoA]
        return device.createBindGroup({ layout: pRho.getBindGroupLayout(0), entries: [
          { binding: 0, resource: si.createView() },
          { binding: 1, resource: ro.createView() },
          { binding: 2, resource: { buffer: ubuf } },
        ]})
      }
      // lambda: @0=lambda_in  @1=lambda_out  @2=sigma_in  @3=uniforms
      function mkLamBG(p: number): GPUBindGroup {
        const [li, lo, si] = p === 0 ? [tLamA, tLamB, tSigB] : [tLamB, tLamA, tSigA]
        return device.createBindGroup({ layout: pLam.getBindGroupLayout(0), entries: [
          { binding: 0, resource: li.createView() },
          { binding: 1, resource: lo.createView() },
          { binding: 2, resource: si.createView() },
          { binding: 3, resource: { buffer: ubuf } },
        ]})
      }
      // render: @0=sigma  @1=rho  @2=lambda  @3=uniforms — reads write-side
      function mkRendBG(p: number): GPUBindGroup {
        const [si, ro, li] = p === 0 ? [tSigB, tRhoB, tLamB] : [tSigA, tRhoA, tLamA]
        return device.createBindGroup({ layout: pRend.getBindGroupLayout(0), entries: [
          { binding: 0, resource: si.createView() },
          { binding: 1, resource: ro.createView() },
          { binding: 2, resource: li.createView() },
          { binding: 3, resource: { buffer: ubuf } },
        ]})
      }

      const sigBG  = [mkSigBG(0),  mkSigBG(1)]
      const rhoBG  = [mkRhoBG(0),  mkRhoBG(1)]
      const lamBG  = [mkLamBG(0),  mkLamBG(1)]
      const rendBG = [mkRendBG(0), mkRendBG(1)]

      let frameN = 0
      let parity = 0
      const ubRaw  = new ArrayBuffer(UF_BYTES)
      const dv     = new DataView(ubRaw)
      const aspect = canvas.width / Math.max(canvas.height, 1)

      function tick(): void {
        if (stopped) return

        const t = frameN * 0.016
        // Autonomous slow evolution — no mouse press (mouse_y = -1 disables kick)
        dv.setFloat32( 0, 0.016,                             true)  // dt
        dv.setUint32(  4, frameN,                            true)  // frame
        dv.setFloat32( 8, 0.8 + Math.sin(t * 0.05) * 0.4,  true)  // lambda_influence
        dv.setFloat32(12, Math.sin(t * 0.013) * 0.04,       true)  // sigma_perturb
        dv.setUint32( 16, SIM_W,                             true)  // width
        dv.setUint32( 20, SIM_H,                             true)  // height
        dv.setFloat32(24, 0.5,                               true)  // mouse_x (unused)
        dv.setFloat32(28, -1.0,                              true)  // mouse_y < 0 = no click
        dv.setFloat32(32, aspect,                            true)  // canvas_aspect
        device.queue.writeBuffer(ubuf, 0, ubRaw)

        const enc = device.createCommandEncoder()

        // Separate passes guarantee synchronisation between dependent dispatches
        const c1 = enc.beginComputePass()
        c1.setPipeline(pSig); c1.setBindGroup(0, sigBG[parity]); c1.dispatchWorkgroups(DX, DY); c1.end()

        const c2 = enc.beginComputePass()
        c2.setPipeline(pRho); c2.setBindGroup(0, rhoBG[parity]); c2.dispatchWorkgroups(DX, DY); c2.end()

        const c3 = enc.beginComputePass()
        c3.setPipeline(pLam); c3.setBindGroup(0, lamBG[parity]); c3.dispatchWorkgroups(DX, DY); c3.end()

        const rp = enc.beginRenderPass({
          colorAttachments: [{
            view: ctx.getCurrentTexture().createView(),
            loadOp: 'clear', storeOp: 'store',
            clearValue: { r: 0, g: 0, b: 0, a: 1 },
          }],
        })
        rp.setPipeline(pRend)
        rp.setBindGroup(0, rendBG[parity])
        rp.draw(3)
        rp.end()

        device.queue.submit([enc.finish()])
        parity ^= 1
        frameN++
        rafId = requestAnimationFrame(tick)
      }

      tick()
    }

    run().catch(console.error)

    return () => {
      stopped = true
      cancelAnimationFrame(rafId)
    }
  }, [])

  // mix-blend-mode: screen — dark GPU pixels (space bg) become invisible,
  // bright features (nebula, stars, portal) glow over the page content.
  return (
    <canvas
      ref={ref}
      style={{
        position: 'fixed',
        inset: 0,
        width: '100%',
        height: '100%',
        mixBlendMode: 'screen',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    />
  )
}
