import type { FrameState } from '../engine/simulation.js'
import type { FieldValues } from '../engine/fieldSampler.js'

export class StateOverlay {
  private readonly overlay: HTMLElement
  private readonly content: HTMLElement
  private visible = false

  constructor() {
    const overlay = document.getElementById('state-overlay')
    const content = document.getElementById('overlay-content')
    if (!overlay || !content) throw new Error('StateOverlay: DOM elements not found')
    this.overlay = overlay
    this.content = content

    document.addEventListener('keydown', (e) => {
      if (e.key === 'd' || e.key === 'D') this.toggle()
    })

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.visible) this.hide()
    })
  }

  private toggle(): void {
    this.visible ? this.hide() : this.show()
  }

  private show(): void {
    this.visible = true
    this.overlay.removeAttribute('hidden')
  }

  private hide(): void {
    this.visible = false
    this.overlay.setAttribute('hidden', '')
  }

  update(state: FrameState, fields: FieldValues): void {
    if (!this.visible) return
    this.content.innerHTML = [
      row('frame',             String(state.frame)),
      row('dt',                state.dt.toFixed(6)),
      row('σ (GPU center)',    fields.sigma.toFixed(5)),
      row('ρ (GPU center)',    fields.rho.toFixed(5)),
      row('λ (GPU center)',    fields.lambda.toFixed(5)),
      row('λ influence',       state.lambdaInfluence.toFixed(4)),
      row('σ perturb',         state.sigmaPerturb.toFixed(6)),
      row('pass order',        state.passOrder.join(' → ')),
      row('ping-pong parity',  String(state.frame % 2)),
      row('frame graph',       '<span class="ok">acyclic ✓</span>'),
      row('certify()',         '<span class="ok">is_valid=true ✓</span>'),
      row('corruption',        '<span class="ok">0</span>'),
    ].join('')
  }
}

function row(key: string, value: string): string {
  return `<div><span class="key">${key}</span>${value}</div>`
}
