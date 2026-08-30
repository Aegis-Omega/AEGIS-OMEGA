// ============================================================
// SOVEREIGN OMEGA — T3 Omega Dynamics Research Harness
// EPISTEMIC TIER: T3 (research conjecture)
//
// Observes T0 telemetry and computes spectral stability metrics.
// ZERO write-back. ZERO production coupling. Read-only.
// Output is for empirical measurement only.
//
// Research questions this harness addresses (T3):
// - Does γ (spectral gap) correlate with calibration stability?
// - Does λ (phase parameter) predict gate rejection bursts?
// - Does martingale drift predict VCG window exhaustion?
// ============================================================

import type { TelemetryWindow, ResearchState } from './types.js'
import { T3_RESEARCH_ONLY, WRITE_BACK_AUTHORITY } from './types.js'

export class OmegaDynamicsHarness {
  private readonly buffer: TelemetryWindow[] = []
  private readonly maxBuffer = 100

  ingest(w: TelemetryWindow): ResearchState {
    this.buffer.push(w)
    if (this.buffer.length > this.maxBuffer) this.buffer.shift()

    // γ — spectral gap: proxy for ergodic stability of the gate process
    // Higher γ → more stable convergence under perturbation
    const gamma = Math.max(0, 1 - (w.gate_rejection_variance + w.vcg_ci_width))

    // κ* — complexity frontier: calibration-variance ratio
    const kappa = (w.gate_rejection_variance + w.vcg_ci_width ** 2) / Math.max(gamma, 1e-4)

    // Λ — phase parameter: normalised to γ*κ
    const lambda = (w.gate_rejection_variance + w.vcg_ci_width ** 2) / (kappa * Math.max(gamma, 1e-4))

    // Regime classification (T3 conjecture — not a production control signal)
    const regime: ResearchState['regime'] =
      gamma <= 1e-4 ? 'CHAOTIC' :
      lambda < 0.5 ? 'ERGODIC' :
      lambda <= 1.5 ? 'METASTABLE' : 'CHAOTIC'

    // Lyapunov delta: change in state-diff norm between windows
    const prev = this.buffer.at(-2)
    const lyapunov_delta = w.state_diff_norm ** 2 - (prev?.state_diff_norm ?? 0) ** 2

    // Martingale drift: signed change in VCG error
    const martingale_drift = w.avg_vcg_error - (prev?.avg_vcg_error ?? 0)

    return Object.freeze({
      x: Object.freeze([w.avg_vcg_error, w.gate_lcb_mean, w.divergence_mean, w.risk_utilization]),
      gamma,
      kappa_star: kappa,
      lambda,
      lyapunov_delta,
      martingale_drift,
      regime,
      t3_research_only: T3_RESEARCH_ONLY,
      write_back_authority: WRITE_BACK_AUTHORITY,
    })
  }

  getBuffer(): readonly TelemetryWindow[] { return Object.freeze([...this.buffer]) }
  bufferLength(): number { return this.buffer.length }
}
