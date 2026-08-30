// ============================================================
// SOVEREIGN OMEGA — Q32.32 Fixed-Point Arithmetic
// EPISTEMIC TIER: T0
// Ω-1B: Eliminates IEEE 754 ULP divergence across JS runtimes,
// CPU architectures, and WASM environments.
// ALL Bernstein, VCG, confidence accumulation, harmonic spending,
// and decay computations MUST route through Q32.32.
//
// Scale-domain boundary (settled — NOT the same scale as Python):
// Q32.32 here is the JS<->WASM governance-math domain only. The Python
// hardware-inference layer (python/hardware_config.py) uses Q16.16
// (INT_SCALE = 1<<16), and so does TS's entropy-budget code
// (environment/workspace/introspection.ts FIXED_SCALE = 1<<16) — those two
// share a scale and agree. Q32.32 and Q16.16 never need to match: no raw
// fixed-point crosses the Python bridge (it exchanges floats). Do not try to
// "reconcile" the scales — they are deliberately separate determinism domains.
// ============================================================

export type Q32_32 = bigint

export const Q_SCALE = 1n << 32n
export const Q_ONE   = Q_SCALE           // 1.0 in Q32.32
export const Q_HALF  = Q_SCALE >> 1n     // 0.5
export const Q_ZERO  = 0n
export const Q_MAX   = (1n << 63n) - 1n  // signed 64-bit max

export function toQ32(v: number): Q32_32 {
  if (!isFinite(v)) throw new RangeError(`toQ32: non-finite input ${v}`)
  return BigInt(Math.round(v * Number(Q_SCALE)))
}

export function fromQ32(v: Q32_32): number {
  return Number(v) / Number(Q_SCALE)
}

export function mulQ32(a: Q32_32, b: Q32_32): Q32_32 {
  return (a * b) >> 32n
}

export function divQ32(a: Q32_32, b: Q32_32): Q32_32 {
  if (b === 0n) throw new Error('FIXED_POINT_DIV_ZERO')
  return (a << 32n) / b
}

export function clampQ32(v: Q32_32, min: Q32_32, max: Q32_32): Q32_32 {
  return v < min ? min : v > max ? max : v
}

export function addQ32(a: Q32_32, b: Q32_32): Q32_32 { return a + b }
export function subQ32(a: Q32_32, b: Q32_32): Q32_32 { return a - b }
export function absQ32(v: Q32_32): Q32_32 { return v < 0n ? -v : v }

/** Compute |a - b| in Q32.32. */
export function absDiffQ32(a: Q32_32, b: Q32_32): Q32_32 { return absQ32(a - b) }

/**
 * Compute the verifier correlation penalty.
 * Ω-4: Dynamic empirical correlation penalty.
 * Minimum floor: 0.25 (prevents complete trust collapse under correlated verifiers).
 */
export function computeCorrelationPenalty(
  agreement_rate: Q32_32,
  baseline_independence: Q32_32
): Q32_32 {
  const excess = agreement_rate - baseline_independence
  if (excess <= 0n) return Q_ONE
  const denom = Q_ONE - baseline_independence
  if (denom <= 0n) return Q_ONE >> 2n
  const penalty_ratio = divQ32(excess, denom)
  return clampQ32(Q_ONE - penalty_ratio, Q_ONE >> 2n, Q_ONE)
}

/**
 * Empirical Bernstein LCB in Q32.32.
 * Replaces the float version in hoeffding.ts for cross-runtime determinism.
 * alpha must be in (0, 1) expressed as Q32.32.
 */
export function bernsteinLCBQ32(
  sum: Q32_32,
  sumSq: Q32_32,
  n: bigint,
  alpha: Q32_32
): Q32_32 {
  if (n === 0n) return -(Q_ONE << 10n) // -Infinity proxy
  // mean = Σq_i / n — plain integer division keeps result in Q32.32 scale
  const mean = sum / n
  // sample variance: s² = (Σq_i² - (Σq_i)²/n) / (n-1)
  // sumSq is Σ(q_i²) in Q32.32; mulQ32(sum,sum) gives (Σq_i)² >> 32 in Q32.32
  const sumSqMean = mulQ32(sum, sum) / n
  const rawVariance = sumSq - sumSqMean
  const variance = n > 1n && rawVariance > 0n ? rawVariance / (n - 1n) : Q_ZERO
  // logTerm = ln(2/alpha) in Q32.32
  const logTermF = Math.log(2 / fromQ32(alpha))
  if (!isFinite(logTermF)) throw new RangeError(`bernsteinLCBQ32: non-finite log — alpha=${fromQ32(alpha)}`)
  const logTerm = toQ32(logTermF)
  // varianceTerm = sqrt(2 * variance * logTerm / n)
  const varianceTermF = Math.sqrt(2 * fromQ32(variance) * fromQ32(logTerm) / Number(n))
  if (!isFinite(varianceTermF)) throw new RangeError(`bernsteinLCBQ32: non-finite variance term`)
  const varianceTerm = toQ32(varianceTermF)
  // biasTerm = 2 * logTerm / (3 * n)
  const biasTerm = divQ32(2n * logTerm, 3n * BigInt(Number(n)) << 32n)
  return mean - varianceTerm - biasTerm
}
