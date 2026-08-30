// ============================================================
// SOVEREIGN OMEGA — Locale-Independent Byte-Wise Ordering
// EPISTEMIC TIER: T0
// Ω-1A: Replaces localeCompare() which introduces ICU/runtime
// drift across Node versions, browsers, and WASM environments.
// All deterministic ordering paths MUST use compareUtf8.
// ============================================================

const encoder = new TextEncoder()

/**
 * Compare two strings by their NFC-normalised UTF-8 byte sequences.
 * Produces identical results across all JS runtimes and locales.
 * MANDATORY: use this instead of localeCompare() everywhere.
 */
export function compareUtf8(a: string, b: string): number {
  const ab = encoder.encode(a.normalize('NFC'))
  const bb = encoder.encode(b.normalize('NFC'))
  const len = Math.min(ab.length, bb.length)
  for (let i = 0; i < len; i++) {
    if (ab[i] !== bb[i]) return (ab[i] as number) - (bb[i] as number)
  }
  return ab.length - bb.length
}

/**
 * Sort an array of strings using byte-wise UTF-8 ordering.
 * Returns a new sorted array; never mutates the input.
 */
export function sortUtf8<T>(arr: readonly T[], key: (x: T) => string): T[] {
  return [...arr].sort((a, b) => compareUtf8(key(a), key(b)))
}

/**
 * Sort object keys by byte-wise UTF-8 order.
 * Used in RFC 8785 canonicalization — must match the canonicalize.ts implementation.
 */
export function sortObjectKeys(obj: Record<string, unknown>): string[] {
  return Object.keys(obj).sort(compareUtf8)
}
