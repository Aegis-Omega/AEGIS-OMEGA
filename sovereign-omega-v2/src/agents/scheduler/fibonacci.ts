// ============================================================
// Fibonacci Scheduler — deterministic interval computation
// EPISTEMIC TIER: T1
// F_{n+2} = F_{n+1} + F_n; F_1 = F_2 = 1
// Intervals capped at FIBONACCI_CAP to prevent unbounded spacing.
// Identical inputs ALWAYS produce identical intervals. No Date.now(). No randomness.
// ============================================================

export const FIBONACCI_SCHEMA_VERSION = '1.0.0' as const

// F_11 = 89. Caps agent spacing — prevents geometric explosion in large swarms.
export const FIBONACCI_CAP = 89

// Returns the n-th Fibonacci number (1-indexed), capped at FIBONACCI_CAP.
// n=1→1, n=2→1, n=3→2, n=4→3, n=5→5, n=6→8, n=7→13, n=8→21,
// n=9→34, n=10→55, n=11+→89 (cap applied).
export function fibonacciInterval(n: number): number {
  if (n <= 1) return 1
  let a = 1
  let b = 1
  for (let i = 2; i < n; i++) {
    const next = a + b
    a = b
    b = next
  }
  return Math.min(b, FIBONACCI_CAP)
}

// Returns the first `length` Fibonacci numbers: [F_1, F_2, ..., F_length].
export function fibonacciSequence(length: number): readonly number[] {
  if (length <= 0) return Object.freeze([])
  return Object.freeze(Array.from({ length }, (_, i) => fibonacciInterval(i + 1)))
}

// Returns `count` cumulative Fibonacci offsets beginning at 0:
// [0, F_1, F_1+F_2, F_1+F_2+F_3, ...]
// Element at index i is the sequence slot offset for the i-th agent.
export function cumulativeFibonacci(count: number): readonly number[] {
  if (count <= 0) return Object.freeze([])
  const result: number[] = [0]
  for (let i = 1; i < count; i++) {
    /* c8 ignore next -- noUncheckedIndexedAccess artifact; result always has i elements at loop step i */
    result.push((result[i - 1] ?? 0) + fibonacciInterval(i))
  }
  return Object.freeze(result)
}
