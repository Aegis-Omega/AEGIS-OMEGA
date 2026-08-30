// ============================================================
// SOVEREIGN OMEGA — T3 Research Harness Types
// EPISTEMIC TIER: T3 (research conjecture)
// STRICT ISOLATION: Read-only telemetry sink.
// ZERO write-back authority. ZERO production coupling.
// ============================================================

export const T3_RESEARCH_ONLY = true as const
export const WRITE_BACK_AUTHORITY = false as const

export interface TelemetryWindow {
  readonly sequence: bigint
  readonly avg_vcg_error: number
  readonly vcg_ci_width: number
  readonly gate_lcb_mean: number
  readonly gate_rejection_variance: number
  readonly risk_utilization: number
  readonly k_bound_utilization: number
  readonly divergence_mean: number
  readonly verifier_correlation: number
  readonly state_diff_norm: number
  readonly epoch: number
}

/**
 * T3 research state. Contains spectral stability metrics (γ, κ*, Λ),
 * martingale drift, and Lyapunov delta. These are observational
 * measures derived from T0 telemetry — NOT control signals.
 *
 * γ (gamma): spectral gap estimate — proxy for ergodic stability
 * κ* (kappa_star): complexity frontier — calibration/variance ratio
 * Λ (lambda): phase parameter — regime classifier
 */
export interface ResearchState {
  readonly x: readonly number[]
  readonly gamma: number
  readonly kappa_star: number
  readonly lambda: number
  readonly lyapunov_delta: number
  readonly martingale_drift: number
  readonly regime: 'ERGODIC' | 'METASTABLE' | 'CHAOTIC'
  readonly t3_research_only: typeof T3_RESEARCH_ONLY
  readonly write_back_authority: typeof WRITE_BACK_AUTHORITY
}
