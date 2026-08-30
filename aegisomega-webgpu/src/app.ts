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
  private canvas!: HTMLCanvasElement
  private canvasSection!: HTMLElement
  private pauseEl!: HTMLElement
  private running = false
  private paused  = false
  private rafId   = 0

  async init(): Promise<void> {
    const { device } = await initGPU()

    this.scroll  = new ScrollController()
    this.panel   = new SystemPanel()
    this.nav     = new Navigation()
    this.overlay = new StateOverlay()
    this.canvasSection = document.getElementById('canvas-section') ?? document.body
    this.pauseEl = document.getElementById('pause-indicator') ?? document.createElement('div')

    const view = new ShaderView((w, h) => {
      if (this.sim) resizeCanvas(ctx, view.canvas, w, h)
    })
    this.canvas = view.canvas

    const ctx = configureCanvas(device, view.canvas)
    this.sim = await SimulationEngine.create(ctx)

    this.wireMouseEvents(view.canvas)
    this.wireKeyEvents()
  }

  private wireKeyEvents(): void {
    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space') {
        e.preventDefault()
        this.paused = !this.paused
        if (this.paused) {
          this.pauseEl.removeAttribute('hidden')
        } else {
          this.pauseEl.setAttribute('hidden', '')
        }
      }
      if (e.code === 'KeyR') {
        this.sim.reset()
      }
    })
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
      const [x, y] = toNorm(e)
      this.sim.setMouse(x, y, pressed)
    })

    canvas.addEventListener('pointerup', (e) => {
      pressed = false
      const [x, y] = toNorm(e)
      this.sim.setMouse(x, y, false)
    })

    canvas.addEventListener('pointercancel', () => {
      pressed = false
      this.sim.clearMouse()
    })

    canvas.addEventListener('pointerleave', () => {
      if (!pressed) this.sim.clearMouse()
    })
  }

  start(): void {
    if (this.running) return
    this.running = true
    const loop = (): void => {
      const params   = this.scroll.getParams()
      const fraction = this.scroll.getScrollFraction()
      const aspect   = this.canvas.width / Math.max(this.canvas.height, 1)
      if (!this.paused) this.sim.tick(params, aspect)
      const state  = this.sim.getFrameState()
      const fields = this.sim.getFieldValues()
      this.panel.update(state, fraction, fields)
      this.nav.updateFrame(state.frame, this.paused)
      this.overlay.update(state, fields)
      const brightness = 1.0 + fraction * 0.5
      this.canvasSection.style.filter = `brightness(${brightness.toFixed(3)})`
      this.rafId = requestAnimationFrame(loop)
    }
    this.rafId = requestAnimationFrame(loop)
  }

  stop(): void {
    this.running = false
    cancelAnimationFrame(this.rafId)
  }
}
