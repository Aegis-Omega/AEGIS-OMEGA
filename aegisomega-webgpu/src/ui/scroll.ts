import type { SimParams } from '../engine/simulation.js'

export class ScrollController {
  private scrollY: number
  private maxScroll: number

  constructor() {
    this.scrollY   = window.scrollY
    this.maxScroll = Math.max(document.body.scrollHeight - window.innerHeight, 1)

    window.addEventListener('scroll', () => {
      this.scrollY   = window.scrollY
      this.maxScroll = Math.max(document.body.scrollHeight - window.innerHeight, 1)
    }, { passive: true })
  }

  getParams(): SimParams {
    const fraction = Math.min(this.scrollY / this.maxScroll, 1.0)
    const lambdaInfluence = 0.5 + fraction * 1.5
    const sigmaPerturb = Math.sin(this.scrollY * 0.001) * 0.05
    return Object.freeze({ lambdaInfluence, sigmaPerturb })
  }

  getScrollFraction(): number {
    return Math.min(this.scrollY / this.maxScroll, 1.0)
  }
}
