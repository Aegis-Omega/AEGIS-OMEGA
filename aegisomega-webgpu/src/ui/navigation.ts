export class Navigation {
  private readonly subEl: HTMLElement | null
  private frameCount  = 0
  private lastFpsTime = 0
  private fps         = 60

  constructor() {
    this.subEl = document.querySelector('.nav-sub')
  }

  updateFrame(frame: number, paused: boolean): void {
    if (!paused) {
      const now = performance.now()
      if (this.lastFpsTime === 0) this.lastFpsTime = now
      this.frameCount++
      if (now - this.lastFpsTime >= 1000) {
        this.fps = Math.round(this.frameCount * 1000 / (now - this.lastFpsTime))
        this.frameCount  = 0
        this.lastFpsTime = now
      }
    }
    if (this.subEl) {
      const status = paused ? '⏸ paused' : `${this.fps} fps`
      this.subEl.textContent = `σ/ρ/λ Field Engine · frame ${frame} · ${status}`
    }
  }
}
