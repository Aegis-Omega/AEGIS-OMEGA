// ============================================================
// SOVEREIGN OMEGA — JS Semantic Particle Field
// EPISTEMIC TIER: T0
// Formalizes the JS semantic subset required for deterministic replay.
// A value is "replay-safe" iff canonicalizeJCS can serialize it without
// throwing AND produces byte-identical output across all JS runtimes.
//
// Boundary conditions derived from canonicalize.ts:
//   line 62: undefined → throws TypeError (not replay-safe)
//   line 70: NaN, Infinity → throws RangeError (not replay-safe)
//   line 57: undefined object values are dropped silently (not an error)
// ============================================================

export class ReplaySafetyViolation extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ReplaySafetyViolation'
  }
}

/**
 * True iff v is a finite IEEE 754 number.
 * NaN and ±Infinity are NOT replay-safe: canonicalize.ts throws on them.
 */
export function isFiniteNumber(v: number): boolean {
  return isFinite(v)
}

/**
 * Recursively check whether a value can be canonicalized without throwing.
 * Mirrors the exact acceptance set of canonicalizeJCS.
 *
 * Replay-safe: null, boolean, finite number, string, bigint,
 *              arrays of replay-safe values,
 *              objects with replay-safe non-undefined values.
 * Not safe:   NaN, ±Infinity, undefined (as standalone or array element),
 *             function, symbol, circular references.
 */
export function isReplaySafe(value: unknown, visited?: Set<object>): boolean {
  if (value === null || typeof value === 'boolean') return true
  if (typeof value === 'string') return true
  if (typeof value === 'bigint') return true
  if (typeof value === 'number') return isFinite(value)
  if (value === undefined || typeof value === 'function' || typeof value === 'symbol') return false

  /* c8 ignore next -- all non-object JS types are handled above; false arm is structurally impossible */
  if (typeof value === 'object') {
    const v = visited ?? new Set<object>()
    if (v.has(value)) return false  // circular reference
    v.add(value)
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item === undefined) return false  // undefined in arrays is not dropped
        if (!isReplaySafe(item, v)) return false
      }
      return true
    }
    for (const key of Object.keys(value)) {
      const child = (value as Record<string, unknown>)[key]
      if (child === undefined) continue  // undefined object values are silently dropped
      if (!isReplaySafe(child, v)) return false
    }
    return true
  }
  /* c8 ignore next -- all JS types handled above; structurally unreachable */
  return false
}

/**
 * Assert that a value is replay-safe.
 * Throws ReplaySafetyViolation if not.
 */
export function assertReplaySafe(value: unknown, label: string): void {
  if (!isReplaySafe(value)) {
    throw new ReplaySafetyViolation(
      `'${label}' contains a value that cannot be deterministically replayed. ` +
      `Check for NaN, Infinity, undefined, functions, symbols, or circular references.`
    )
  }
}

/**
 * Classify a number's replay status.
 * Used in Bernstein/VCG paths to guard against silent float corruption.
 */
export function classifyNumber(v: number): 'finite' | 'nan' | 'positive_infinity' | 'negative_infinity' {
  if (isNaN(v)) return 'nan'
  if (v === Infinity) return 'positive_infinity'
  if (v === -Infinity) return 'negative_infinity'
  return 'finite'
}
