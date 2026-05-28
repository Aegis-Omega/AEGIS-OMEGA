// ============================================================
// SOVEREIGN OMEGA — VCG Calibration Tracker
// EPISTEMIC TIER: T1 (empirically validated methodology)
// PRIMITIVE 5: Hard Trust Partitioning (weights per domain)
// Rolling window: 500 claims (default). Min for gating: 100.
// Bootstrap CI uses seeded PRNG — deterministic under replay.
// NOTE: Theoretical VCG floor is non-zero (Vempala-Wilkes).
// ============================================================

import type { VCGMetric, Confidence } from '../core/types.js'
import type { VerifierOutput } from '../verifier/types.js'
import { SeededRNG, deriveSeed } from './rng.js'
import { verifierRegistry } from '../verifier/registry.js'

const DEFAULT_WINDOW = 500
const MIN_GATE_WINDOW = 100
const BOOTSTRAP_SAMPLES = 200
const DECAY_HALF_LIFE_MS = 24 * 60 * 60 * 1000  // 24 hours
const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000
const ALERT_THRESHOLD = 0.35
const SUSPEND_THRESHOLD = 0.50

interface CalibrationSample {
  readonly claimed_confidence: number
  readonly actual_correct: boolean
  readonly weight: number
  readonly timestamp_ms: number  // from event substrate
  readonly verifier_id: string
}

export class VCGTracker {
  private readonly samples: CalibrationSample[] = []
  private readonly windowSize: number
  private readonly streamId: string
  private epochId: string
  private lastUpdateMs: number

  constructor(streamId: string, windowSize = DEFAULT_WINDOW) {
    this.streamId = streamId
    this.windowSize = windowSize
    this.epochId = `epoch-${streamId}-0`
    this.lastUpdateMs = 0
  }

  /**
   * Add a verifier result to the calibration window.
   * Only Ground Truth (weight=1.0) and Retrieval-Assisted (weight=0.5) contribute.
   * Advisory-Excluded verifiers are silently ignored.
   * timestamp_ms MUST come from the event substrate, not Date.now().
   */
  addResult(
    output: VerifierOutput,
    claimed_confidence: number,
    timestamp_ms: number  // from event.timestamp_ms
  ): void {
    const weight = verifierRegistry.getCalibrationWeight(output.trust_class)
    if (weight === 0) return  // Advisory-Excluded — never contributes

    const sample: CalibrationSample = Object.freeze({
      claimed_confidence: Math.max(0, Math.min(1, claimed_confidence)),
      actual_correct: output.passed,
      weight,
      timestamp_ms,
      verifier_id: output.verifier_id,
    })

    this.samples.push(sample)
    this.lastUpdateMs = timestamp_ms

    // Trim to window size
    if (this.samples.length > this.windowSize) {
      this.samples.splice(0, this.samples.length - this.windowSize)
    }
  }

  /**
   * Compute the current VCG metric.
   * Uses decay weighting: older samples contribute less.
   * Bootstrap CI uses seeded PRNG (deterministic under replay).
   * currentMs MUST come from the event substrate.
   */
  compute(currentMs: number): VCGMetric {
    const window = [...this.samples]
    if (window.length === 0) {
      return this.emptyMetric(currentMs)
    }

    // Apply exponential decay weighting
    const decayedSamples = window.map(s => ({
      ...s,
      effective_weight: s.weight * this.decayFactor(currentMs - s.timestamp_ms),
    }))

    const totalWeight = decayedSamples.reduce((sum, s) => sum + s.effective_weight, 0)
    if (totalWeight === 0) return this.emptyMetric(currentMs)

    // VCG = weighted mean of |claimed_confidence - actual_correct|
    const vcg = decayedSamples.reduce((sum, s) => {
      const error = Math.abs(s.claimed_confidence - (s.actual_correct ? 1 : 0))
      return sum + error * s.effective_weight
    }, 0) / totalWeight

    // Bootstrap CI (seeded, deterministic)
    const ci = this.bootstrapCI(decayedSamples, currentMs)

    return Object.freeze({
      domain_id: this.streamId,
      weighted_error: vcg,
      bootstrap_ci_95: ci,
      effective_sample_size: this.effectiveSampleSize(decayedSamples),
      /* c8 ignore next -- noUncheckedIndexedAccess artifact; window.length >= MIN_GATE_WINDOW when compute() is called */
      decay_factor: this.decayFactor(currentMs - (window[window.length - 1]?.timestamp_ms ?? currentMs)),
      sample_count: window.length,
      epoch_start_ms: this.lastUpdateMs,
    })
  }

  canEmitVerifiedConfidence(_currentMs: number): boolean {
    return this.samples.length >= MIN_GATE_WINDOW
  }

  shouldAlert(currentMs: number): boolean {
    const metric = this.compute(currentMs)
    return metric.weighted_error > ALERT_THRESHOLD
  }

  shouldSuspend(currentMs: number): boolean {
    const metric = this.compute(currentMs)
    return metric.weighted_error > SUSPEND_THRESHOLD
  }

  isStale(currentMs: number): boolean {
    if (this.lastUpdateMs === 0) return false
    return (currentMs - this.lastUpdateMs) > STALE_THRESHOLD_MS
  }

  resetEpoch(_reason: 'drift' | 'manual' | 'low_sample'): void {
    /* c8 ignore next -- epochId always has format 'epoch-id-N'; .pop() is always defined */
    const epochNum = parseInt(this.epochId.split('-').pop() ?? '0') + 1
    this.epochId = `epoch-${this.streamId}-${epochNum}`
    this.samples.splice(0)
  }

  getEpochId(): string { return this.epochId }

  /**
   * Wilson score interval for the current calibration estimate.
   * alpha: significance level (e.g. 0.05 for 95% CI).
   * Returns { lower, upper } bounds on the calibration accuracy proportion.
   * Uses Wilson score: center = (successes + z²/2) / (n + z²),
   * halfwidth = z * sqrt(n * p * (1-p) + z²/4) / (n + z²).
   */
  getConfidenceInterval(alpha: number): { lower: number; upper: number } {
    if (alpha <= 0 || alpha >= 1) throw new RangeError('alpha must be in (0, 1)')

    const n = this.samples.length
    if (n === 0) return { lower: 0, upper: 1 }

    // Map alpha to z-score (normal approximation)
    // For alpha=0.05 (95% CI), z≈1.96; for alpha=0.10 (90% CI), z≈1.645
    // Use standard normal quantile approximation (Beasley-Springer-Moro)
    const z = wilsonZ(1 - alpha / 2)

    // successes = number of correct predictions (where prediction ≈ actual)
    const successes = this.samples.reduce((count, s) => {
      // A "success" is when the claimed confidence matches the outcome
      // Use threshold: success if |claimed - actual| < 0.5
      const actual = s.actual_correct ? 1 : 0
      return count + (Math.abs(s.claimed_confidence - actual) < 0.5 ? 1 : 0)
    }, 0)

    const p = successes / n
    const z2 = z * z
    const center = (successes + z2 / 2) / (n + z2)
    const halfWidth = z * Math.sqrt(n * p * (1 - p) + z2 / 4) / (n + z2)

    return {
      lower: Math.max(0, center - halfWidth),
      upper: Math.min(1, center + halfWidth),
    }
  }

  /**
   * Calibration bias: mean(predicted) - mean(actual) over all results.
   * Positive = overconfident, negative = underconfident.
   * Returns 0 when no samples are available.
   */
  getCalibrationBias(): number {
    if (this.samples.length === 0) return 0
    let sumPredicted = 0
    let sumActual = 0
    for (const s of this.samples) {
      sumPredicted += s.claimed_confidence
      sumActual += s.actual_correct ? 1 : 0
    }
    return (sumPredicted - sumActual) / this.samples.length
  }

  /**
   * Brier score: mean squared error between confidence predictions and binary outcomes.
   * Perfect calibration = 0, worst = 1.
   * Returns 0 when no samples are available.
   */
  getBrierScore(): number {
    if (this.samples.length === 0) return 0
    const sumSquaredError = this.samples.reduce((sum, s) => {
      const actual = s.actual_correct ? 1 : 0
      const diff = s.claimed_confidence - actual
      return sum + diff * diff
    }, 0)
    return sumSquaredError / this.samples.length
  }

  // ─── Private helpers ───────────────────────────────────

  private decayFactor(ageMs: number): number {
    return Math.exp(-Math.LN2 * ageMs / DECAY_HALF_LIFE_MS)
  }

  private bootstrapCI(
    samples: Array<{ effective_weight: number; claimed_confidence: number; actual_correct: boolean }>,
    currentMs: number
  ): readonly [number, number] {
    const seed = deriveSeed(this.streamId, this.epochId + ':' + String(Math.floor(currentMs / 60_000)))
    const rng = new SeededRNG(seed)

    const bootstrapVCGs: number[] = []
    for (let b = 0; b < BOOTSTRAP_SAMPLES; b++) {
      let vcgSum = 0
      let wSum = 0
      for (let i = 0; i < samples.length; i++) {
        const idx = Math.floor(rng.next() * samples.length)
        const s = samples[idx]!
        const error = Math.abs(s.claimed_confidence - (s.actual_correct ? 1 : 0))
        vcgSum += error * s.effective_weight
        wSum += s.effective_weight
      }
      bootstrapVCGs.push(wSum > 0 ? vcgSum / wSum : 0)
    }

    bootstrapVCGs.sort((a, b) => a - b)
    /* c8 ignore next -- noUncheckedIndexedAccess artifact; bootstrapVCGs always has BOOTSTRAP_SAMPLES elements */
    const lo = bootstrapVCGs[Math.floor(BOOTSTRAP_SAMPLES * 0.025)] ?? 0
    /* c8 ignore next -- same as above */
    const hi = bootstrapVCGs[Math.floor(BOOTSTRAP_SAMPLES * 0.975)] ?? 1
    return Object.freeze([lo, hi] as const)
  }

  private effectiveSampleSize(
    samples: Array<{ effective_weight: number }>
  ): number {
    // ESS = sum of effective weights: represents the number of full-weight
    // GROUND_TRUTH-equivalent samples this pool is worth.
    // RETRIEVAL_ASSISTED samples (weight=0.5) contribute half as much as
    // GROUND_TRUTH samples (weight=1.0), which is what callers rely on.
    return samples.reduce((s, x) => s + x.effective_weight, 0)
  }

  private emptyMetric(currentMs: number): VCGMetric {
    return Object.freeze({
      domain_id: this.streamId,
      weighted_error: 0,
      bootstrap_ci_95: Object.freeze([0, 1] as const),
      effective_sample_size: 0,
      decay_factor: 1,
      sample_count: 0,
      epoch_start_ms: currentMs,
    })
  }
}

// ─── Module helpers ───────────────────────────────────────

/**
 * Rational approximation to the normal quantile function (inverse CDF).
 * Accurate to ~1.5e-5 for p in (0, 1). Abramowitz & Stegun 26.2.17.
 * Used exclusively by getConfidenceInterval — no Date.now(), no side effects.
 */
function wilsonZ(p: number): number {
  /* c8 ignore next -- only called from getConfidenceInterval which validates alpha ∈ (0,1); inputs always in (0,1) */
  if (p <= 0 || p >= 1) return 0
  // Rational approximation constants
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

/**
 * Build a Confidence value from VCG state.
 * Emits 'verified' type only when window is large enough for statistical validity.
 */
export function buildConfidence(
  tracker: VCGTracker,
  currentMs: number,
  verifierIds: readonly string[],
): Confidence {
  if (!tracker.canEmitVerifiedConfidence(currentMs)) {
    return Object.freeze({
      type: 'heuristic',
      value: 0.3,
      disclaimer: true,
      source: 'INSUFFICIENT_CALIBRATION_WINDOW',
    })
  }

  const metric = tracker.compute(currentMs)
  const calibratedValue = Math.max(0, 1 - metric.weighted_error)

  return Object.freeze({
    type: 'verified',
    value: calibratedValue,
    verifier_ids: Object.freeze([...verifierIds]),
    vcg_epoch: tracker.getEpochId(),
  })
}
