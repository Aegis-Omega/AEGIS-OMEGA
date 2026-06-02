export class ShaderView {
  readonly canvas: HTMLCanvasElement

  private readonly onResize: (w: number, h: number) => void
  constructor(onResize: (w: number, h: number) => void) {
    this.onResize = onResize
    const canvas = document.getElementById('gpu-canvas')
    if (!(canvas instanceof HTMLCanvasElement)) {
      throw new Error('ShaderView: #gpu-canvas not found or not a canvas')
    }
    this.canvas = canvas
    this.resize()

    const ro = new ResizeObserver(() => { this.resize() })
    ro.observe(canvas.parentElement ?? document.body)
    window.addEventListener('resize', () => { this.resize() }, { passive: true })
  }

  private resize(): void {
    const w = window.innerWidth
    const h = window.innerHeight
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width  = w
      this.canvas.height = h
      this.onResize(w, h)
    }
  }
}
