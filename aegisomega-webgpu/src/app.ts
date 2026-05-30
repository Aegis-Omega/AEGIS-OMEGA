import { initGPU } from './engine/gpu.js'
import { configureCanvas, resizeCanvas } from './engine/device.js'
import { SimulationEngine } from './engine/simulation.js'
import { ScrollController } from './ui/scroll.js'
import { SystemPanel } from './ui/systemPanel.js'
import { ShaderView } from './ui/shaderView.js'
import { Navigation } from './ui/navigation.js'
import { StateOverlay } from './ui/stateOverlay.js'

export class App {
  private sim!: SimulationEngine
  private scroll!: ScrollController
  private panel!: SystemPanel
  private nav!: Navigation
  private overlay!: StateOverlay
  private running = false
  private rafId   = 0

  async init(): Promise<void> {
    const { device } = await initGPU()

    this.scroll  = new ScrollController()
    this.panel   = new SystemPanel()
    this.nav     = new Navigation()
    this.overlay = new StateOverlay()

    const view = new ShaderView((w, h) => {
      if (this.sim) resizeCanvas(ctx, view.canvas, w, h)
    })

    const ctx = configureCanvas(device, view.canvas)
    this.sim = await SimulationEngine.create(ctx)

    this.wireMouseEvents(view.canvas)
  }

  private wireMouseEvents(canvas: HTMLCanvasElement): void {
    let pressed = false

    const toNorm = (e: PointerEvent): [number, number] => {
      const r = canvas.getBoundingClientRect()
      return [
        (e.clientX - r.left) / r.width,
        (e.clientY - r.top)  / r.height,
      ]
    }

    canvas.addEventListener('pointerdown', (e) => {
      pressed = true
      const [x, y] = toNorm(e)
      this.sim.setMouse(x, y, true)
      canvas.setPointerCapture(e.pointerId)
    })

    canvas.addEventListener('pointermove', (e) => {
      if (!pressed) return
      const [x, y] = toNorm(e)
      this.sim.setMouse(x, y, true)
    })

    const release = (): void => {
      pressed = false
      this.sim.setMouse(0, 0, false)
    }
    canvas.addEventListener('pointerup',     release)
    canvas.addEventListener('pointercancel', release)
  }

  start(): void {
    if (this.running) return
    this.running = true
    const loop = (): void => {
      const params = this.scroll.getParams()
      this.sim.tick(params)
      const state = this.sim.getFrameState()
      this.panel.update(state, this.scroll.getScrollFraction(), this.sim.getFieldValues())
      this.nav.updateFrame(state.frame)
      this.overlay.update(state)
      this.rafId = requestAnimationFrame(loop)
    }
    this.rafId = requestAnimationFrame(loop)
  }

  stop(): void {
    this.running = false
    cancelAnimationFrame(this.rafId)
  }
}
