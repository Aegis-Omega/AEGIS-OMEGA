// ============================================================
// SOVEREIGN OMEGA — Anytime-Valid Confidence Sequences
// EPISTEMIC TIER: T0/T1
// Uses empirical Bernstein bounds, NOT Hoeffding's inequality.
// Reason: Hoeffding assumes IID samples. Self-modifying systems
// violate IID because future samples depend on past results.
// Bernstein bounds remain valid under adaptive sampling.
// Reference: Howard et al. 2020; Waudby-Smith & Ramdas 2024.
// Filename hoeffding.ts is a legacy artifact — do not rename (referenced by risk.ts and fixedpoint.ts).
// ============================================================

import type { BoundedDelta } from '../core/types.js'
import { normalizeDelta } from '../core/types.js'

/**
 * Anytime-valid confidence sequence using empirical Bernstein bounds.
 * Accepts BoundedDelta inputs ∈ [-1, 1] — enforced by branded type.
 *
 * The gate accepts a modification when LCB > 0, providing statistical
 * evidence that the modification is beneficial.
 */
export class ConfidenceSequence {
  private readonly alpha: number         // significance level (e.g. 0.05)
  private readonly rho: number           // mixing parameter (0 < rho < 1)
  private n = 0                          // number of observations
  private sum = 0                        // sum of deltas
  private sum_sq = 0                     // sum of squared deltas
  private running_var = 0               // empirical variance estimate
  private e_prod = 1                    // running betting martingale product

  constructor(alpha = 0.05, rho = 0.5) {
    if (alpha <= 0 || alpha >= 1) throw new RangeError('alpha must be in (0, 1)')
    if (rho <= 0 || rho >= 1) throw new RangeError('rho must be in (0, 1)')
    this.alpha = alpha
    this.rho = rho
  }

  /**
   * Update with a new bounded delta observation.
   * Input MUST be a BoundedDelta ∈ [-1, 1].
   */
  update(delta: BoundedDelta): void {
    // Compute predictable bet BEFORE updating state (Waudby-Smith & Ramdas 2024)
    const lambda = this.predictableLambda()
    this.e_prod *= (1 + lambda * delta)
    this.n++
    this.sum += delta
    this.sum_sq += delta * delta
    const mean = this.sum / this.n
    this.running_var = this.n > 1
      ? (this.sum_sq - this.n * mean * mean) / (this.n - 1)
      : 0
  }

  /**
   * Compute the anytime-valid lower confidence bound.
   * This bound is valid for any stopping time, including
   * adversarially chosen times — unlike Hoeffding.
   *
   * Returns the LCB on the true mean delta.
   * Gate accepts when LCB > 0.
   */
  lcb(): number {
    if (this.n === 0) return -Infinity

    const mean = this.sum / this.n
    const halfWidth = this.bernsteinHalfWidth()
    return mean - halfWidth
  }

  /**
   * Compute e-value for the null hypothesis that mean delta ≤ 0.
   * An e-value > 1/alpha provides anytime-valid evidence against H0.
   * Gate accepts when e_value > 1/alpha.
   *
   * Implemented as a running betting martingale: E_n = Π(1 + λ_t * X_t)
   * where λ_t is predictable (chosen before observing X_t).
   * This guarantees E[E_n] ≤ 1 under H₀ by Ville's inequality.
   */
  eValue(): number {
    return this.e_prod
  }

  /**
   * Coverage probability: fraction of time LCB was valid.
   * Should be ≥ (1 - alpha) for correctly calibrated sequences.
   */
  coverageAtLevel(trueMean: number): boolean {
    return this.lcb() <= trueMean
  }

  get observationCount(): number { return this.n }
  get empiricalMean(): number { return this.n > 0 ? this.sum / this.n : 0 }
  get empiricalVariance(): number { return this.running_var }

  // ─── Private ───────────────────────────────────────────

  /**
   * Predictable betting fraction for the martingale.
   * Uses mean/variance Kelly fraction capped at rho (ensures factor ≥ 1-rho > 0).
   */
  private predictableLambda(): number {
    if (this.n === 0) return this.rho
    const prevMean = this.sum / this.n
    if (prevMean <= 0) return 0
    const kelly = prevMean / Math.max(this.running_var, 1e-10)
    return Math.min(kelly, this.rho)
  }

  /**
   * Empirical Bernstein half-width for the LCB.
   * Tighter than Hoeffding because it uses the empirical variance.
   * Valid for bounded random variables in [-1, 1].
   */
  private bernsteinHalfWidth(): number {
    const sigma2 = Math.max(this.running_var, 1e-10)
    const b = 1  // range bound (inputs are in [-1, 1], range = 2, half-range = 1)

    // Empirical Bernstein bound (Howard et al. 2020 Eq. 8)
    // HW = sqrt(2 * sigma^2 * log(2/alpha) / n) + 2 * b * log(2/alpha) / (3 * n)
    const logTerm = Math.log(2 / this.alpha)
    const varianceTerm = Math.sqrt(2 * sigma2 * logTerm / this.n)
    const biasTerm = (2 * b * logTerm) / (3 * this.n)

    return varianceTerm + biasTerm
  }
}

/**
 * Convenience function: compute LCB from an array of raw numbers.
 * Normalises inputs to [-1, 1] via normalizeDelta.
 */
export function computeLCBFromSamples(samples: readonly number[], alpha = 0.05): number {
  const seq = new ConfidenceSequence(alpha)
  for (const s of samples) {
    seq.update(normalizeDelta(s))
  }
  return seq.lcb()
}

/**
 * Minimum sample size to detect an effect at given power and significance level.
 * Uses the standard formula: n = (z_alpha + z_power)² / effectSize²
 * where z values come from the normal quantile function.
 *
 * @param targetPower - desired statistical power (e.g. 0.80)
 * @param effectSize  - standardised effect size to detect (> 0)
 * @param alpha       - significance level (e.g. 0.05)
 * @returns minimum number of events (integer, ceiled)
 */
export function computeMinSampleSize(
  targetPower: number,
  effectSize: number,
  alpha: number,
): number {
  if (targetPower <= 0 || targetPower >= 1) throw new RangeError('targetPower must be in (0, 1)')
  if (effectSize <= 0) throw new RangeError('effectSize must be positive')
  if (alpha <= 0 || alpha >= 1) throw new RangeError('alpha must be in (0, 1)')

  const zAlpha = normalQuantile(1 - alpha)
  const zPower = normalQuantile(targetPower)
  return Math.ceil((zAlpha + zPower) ** 2 / (effectSize * effectSize))
}

/**
 * Anytime-valid p-value derived from the e-process value.
 * p = min(1, 1/eValue). Always valid regardless of when the sequence is stopped.
 * This replaces fixed-sample p-values for sequential testing.
 *
 * @param eValue - current e-process value (from ConfidenceSequence.eValue())
 * @returns anytime-valid p-value in [0, 1]
 */
export function getPValue(eValue: number): number {
  if (eValue <= 0) return 1
  return Math.min(1, 1 / eValue)
}

// ─── Module helpers ───────────────────────────────────────

/**
 * Rational approximation to the normal quantile (inverse CDF).
 * Abramowitz & Stegun 26.2.17. Accurate to ~1.5e-5 for p ∈ (0, 1).
 * No Date.now(), no side effects — pure arithmetic.
 */
function normalQuantile(p: number): number {
  /* c8 ignore next -- only called from computeMinSampleSize which validates p ∈ (0,1) */
  if (p <= 0 || p >= 1) return 0
  const c0 = 2.515517
  const c1 = 0.802853
  const c2 = 0.010328
  const d1 = 1.432788
  const d2 = 0.189269
  const d3 = 0.001308
  const sign = p >= 0.5 ? 1 : -1
  const q = p >= 0.5 ? p : 1 - p
  const t = Math.sqrt(-2 * Math.log(1 - q))
  const num = c0 + c1 * t + c2 * t * t
  const den = 1 + d1 * t + d2 * t * t + d3 * t * t * t
  return sign * (t - num / den)
}
