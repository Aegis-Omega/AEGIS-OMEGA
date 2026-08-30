import { useEffect, useRef } from 'react'
import sigmaWGSL  from '../shaders/sigma.wgsl?raw'
import rhoWGSL    from '../shaders/rho.wgsl?raw'
import lambdaWGSL from '../shaders/lambda.wgsl?raw'
import renderWGSL from '../shaders/render.wgsl?raw'
import { gpuBus } from '../lib/gpuBus.js'

const SIM_W = 512
const SIM_H = 512
const DX = 64   // SIM_W / workgroup_x(8)
const DY = 64   // SIM_H / workgroup_y(8)
const UF_BYTES = 64  // uniform buffer padded to 64 bytes

// GPUTextureUsage / GPUBufferUsage flags are not reliably in scope as global
// values in all TypeScript DOM lib versions — use spec-defined numeric constants.
const TEX_USAGE = 0x1E  // TEXTURE_BINDING(0x4) | STORAGE_BINDING(0x8) | COPY_DST(0x2) | COPY_SRC(0x10)
const UNI_USAGE = 0x48  // UNIFORM(0x40) | COPY_DST(0x8)
const STA_USAGE = 0x09  // MAP_READ(0x1) | COPY_DST(0x8)
const STAGING_STRIDE = 256       // minimum bytesPerRow alignment
const SIM_CENTER_X = SIM_W >> 1
const SIM_CENTER_Y = SIM_H >> 1

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
  // x=-1 = off-screen (no glow); y ≥ 0 = click; y < 0 = hover encoded as -(y+1)
  const mouseRef = useRef({ x: -1.0, y: 0.0, pressed: false })
  const scrollRef = useRef(0)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas || !navigator.gpu) return

    let stopped = false
    let rafId = 0
    // Refs for resources created asynchronously — needed by cleanup and resize
    let deviceRef: GPUDevice | null = null
    let ctxRef: GPUCanvasContext | null = null
    let fmtRef: GPUTextureFormat | null = null

    // Canvas is pointer-events:none so we listen on window
    const onMouseMove  = (e: MouseEvent) => {
      mouseRef.current.x = e.clientX / window.innerWidth
      mouseRef.current.y = e.clientY / window.innerHeight
    }
    const onMouseDown  = (e: MouseEvent) => {
      mouseRef.current.x = e.clientX / window.innerWidth
      mouseRef.current.y = e.clientY / window.innerHeight
      mouseRef.current.pressed = true
    }
    const onMouseUp    = () => { mouseRef.current.pressed = false }
    const onMouseLeave = () => { mouseRef.current.x = -1.0; mouseRef.current.pressed = false }
    const onTouchStart = (e: TouchEvent) => {
      const t = e.touches[0]; if (!t) return
      mouseRef.current.x = t.clientX / window.innerWidth
      mouseRef.current.y = t.clientY / window.innerHeight
      mouseRef.current.pressed = true
    }
    const onTouchMove  = (e: TouchEvent) => {
      const t = e.touches[0]; if (!t) return
      mouseRef.current.x = t.clientX / window.innerWidth
      mouseRef.current.y = t.clientY / window.innerHeight
    }
    const onTouchEnd   = () => { mouseRef.current.pressed = false }
    const onScroll     = () => { scrollRef.current = window.scrollY }
    const onResize     = () => {
      if (!canvas || !ctxRef || !deviceRef || !fmtRef) return
      canvas.width  = Math.round(window.innerWidth  * Math.min(devicePixelRatio, 2))
      canvas.height = Math.round(window.innerHeight * Math.min(devicePixelRatio, 2))
      ctxRef.configure({ device: deviceRef, format: fmtRef, alphaMode: 'opaque' })
    }

    window.addEventListener('mousemove',  onMouseMove)
    window.addEventListener('mousedown',  onMouseDown)
    window.addEventListener('mouseup',    onMouseUp)
    window.addEventListener('mouseleave', onMouseLeave)
    window.addEventListener('touchstart', onTouchStart, { passive: true })
    window.addEventListener('touchmove',  onTouchMove,  { passive: true })
    window.addEventListener('touchend',   onTouchEnd)
    window.addEventListener('scroll',     onScroll,     { passive: true })
    window.addEventListener('resize',     onResize)

    async function run(): Promise<void> {
      if (!canvas) return

      const adapter = await navigator.gpu.requestAdapter()
      if (!adapter || stopped) return
      const device = await adapter.requestDevice()
      deviceRef = device
      if (stopped) { device.destroy(); return }

      const dpr = Math.min(devicePixelRatio, 2)
      canvas.width  = Math.round(window.innerWidth  * dpr)
      canvas.height = Math.round(window.innerHeight * dpr)

      const ctxMaybe = canvas.getContext('webgpu') as GPUCanvasContext | null
      if (!ctxMaybe) { device.destroy(); return }
      const ctx: GPUCanvasContext = ctxMaybe
      const fmt = navigator.gpu.getPreferredCanvasFormat()
      ctxRef = ctx
      fmtRef = fmt
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

      const stagingSig = device.createBuffer({ size: STAGING_STRIDE, usage: STA_USAGE })
      const stagingRho = device.createBuffer({ size: STAGING_STRIDE, usage: STA_USAGE })
      const stagingLam = device.createBuffer({ size: STAGING_STRIDE, usage: STA_USAGE })
      let fieldPending = false

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
      const ubRaw = new ArrayBuffer(UF_BYTES)
      const dv    = new DataView(ubRaw)

      function tick(): void {
        if (stopped || !canvas) return

        const t = frameN * 0.016
        // Scroll fraction [0,1] deepens field memory and injects perturbation
        const scroll = scrollRef.current
        const scrollFrac = scroll / Math.max(document.body.scrollHeight - window.innerHeight, 1)
        const aspect = canvas.width / Math.max(canvas.height, 1)

        const lambdaInfl   = 0.5 + scrollFrac * 1.5 + Math.sin(t * 0.05) * 0.2
        const sigmaPerturb = Math.sin(t * 0.013) * 0.04 + scrollFrac * 0.02

        // mouse_x < 0 → no glow; mouse_y ≥ 0 → click (kick+glow); mouse_y < 0 → hover (glow only)
        const { x: mx, y: my, pressed } = mouseRef.current
        const mouseX = mx
        const mouseY = mx < 0 ? -1.0 : pressed ? my : -(my + 1.0)

        dv.setFloat32( 0, 0.016,        true)  // dt
        dv.setUint32(  4, frameN,        true)  // frame
        dv.setFloat32( 8, lambdaInfl,    true)  // lambda_influence
        dv.setFloat32(12, sigmaPerturb,  true)  // sigma_perturb
        dv.setUint32( 16, SIM_W,         true)  // width
        dv.setUint32( 20, SIM_H,         true)  // height
        dv.setFloat32(24, mouseX,        true)  // mouse_x
        dv.setFloat32(28, mouseY,        true)  // mouse_y
        dv.setFloat32(32, aspect,        true)  // canvas_aspect
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

        // Field readback: copy center pixel of each field every 10 frames
        if (!fieldPending && frameN % 10 === 0) {
          const sigSrc = parity === 0 ? tSigB : tSigA
          const rhoSrc = parity === 0 ? tRhoB : tRhoA
          const lamSrc = parity === 0 ? tLamB : tLamA
          const origin = { x: SIM_CENTER_X, y: SIM_CENTER_Y, z: 0 }
          const sz     = { width: 1, height: 1, depthOrArrayLayers: 1 as const }
          enc.copyTextureToBuffer({ texture: sigSrc, origin }, { buffer: stagingSig, bytesPerRow: STAGING_STRIDE }, sz)
          enc.copyTextureToBuffer({ texture: rhoSrc, origin }, { buffer: stagingRho, bytesPerRow: STAGING_STRIDE }, sz)
          enc.copyTextureToBuffer({ texture: lamSrc, origin }, { buffer: stagingLam, bytesPerRow: STAGING_STRIDE }, sz)
          fieldPending = true
        }

        device.queue.submit([enc.finish()])

        if (fieldPending) {
          const capturedFrame = frameN
          void Promise.all([
            stagingSig.mapAsync(1),
            stagingRho.mapAsync(1),
            stagingLam.mapAsync(1),
          ]).then(() => {
            const sigma  = new Float32Array(stagingSig.getMappedRange())[0] ?? 0
            const rho    = new Float32Array(stagingRho.getMappedRange())[0] ?? 0
            const lambda = new Float32Array(stagingLam.getMappedRange())[0] ?? 0
            stagingSig.unmap()
            stagingRho.unmap()
            stagingLam.unmap()
            gpuBus.snapshot = { sigma, rho, lambda, frame: capturedFrame }
            fieldPending = false
          })
        }

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
      deviceRef?.destroy()
      window.removeEventListener('mousemove',  onMouseMove)
      window.removeEventListener('mousedown',  onMouseDown)
      window.removeEventListener('mouseup',    onMouseUp)
      window.removeEventListener('mouseleave', onMouseLeave)
      window.removeEventListener('touchstart', onTouchStart)
      window.removeEventListener('touchmove',  onTouchMove)
      window.removeEventListener('touchend',   onTouchEnd)
      window.removeEventListener('scroll',     onScroll)
      window.removeEventListener('resize',     onResize)
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
