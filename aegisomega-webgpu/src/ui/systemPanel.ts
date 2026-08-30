import type { FrameState } from '../engine/simulation.js'
import type { FieldValues } from '../engine/fieldSampler.js'

export class SystemPanel {
  private readonly elFrame:  HTMLElement
  private readonly elDt:     HTMLElement
  private readonly elLambda: HTMLElement
  private readonly elSigma:  HTMLElement
  private readonly elScroll: HTMLElement
  private readonly elRho:    HTMLElement

  constructor() {
    this.elFrame  = this.el('val-frame')
    this.elDt     = this.el('val-dt')
    this.elLambda = this.el('val-lambda')
    this.elSigma  = this.el('val-sigma')
    this.elScroll = this.el('val-scroll')
    this.elRho    = this.el('val-rho')
  }

  private el(id: string): HTMLElement {
    const el = document.getElementById(id)
    if (!el) throw new Error(`SystemPanel: element #${id} not found`)
    return el
  }

  update(state: FrameState, scrollFraction: number, fields: FieldValues): void {
    this.elFrame.textContent  = String(state.frame)
    this.elDt.textContent     = state.dt.toFixed(4)
    this.elSigma.textContent  = fields.sigma.toFixed(4)
    this.elRho.textContent    = fields.rho.toFixed(4)
    this.elLambda.textContent = fields.lambda.toFixed(4)
    this.elScroll.textContent = scrollFraction.toFixed(3)
  }
}
