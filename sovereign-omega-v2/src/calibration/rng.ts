// ============================================================
// SOVEREIGN OMEGA — Seeded Deterministic PRNG
// EPISTEMIC TIER: T0
// Any computation involving randomness uses a seeded PRNG
// whose seed derives from the event stream, never from
// environmental entropy (crypto.getRandomValues).
// ============================================================

/**
 * xoshiro128** — fast, high-quality 32-bit seeded PRNG.
 * Deterministic: same seed always produces same sequence.
 * Used exclusively for bootstrap CI computation in VCGTracker.
 */
export class SeededRNG {
  private s: [number, number, number, number]

  constructor(seed: number) {
    // Splitmix32 initialization using Math.imul for correct 32-bit multiplication.
    // The original 64-bit splitmix constants (0xbf58476d1ce4e5b9, 0x94d049bb133111eb)
    // are silently truncated to doubles with ~42-bit rounding error when used in JS,
    // causing ALL seeds to collapse to the same state via floating-point precision loss.
    // Math.imul enforces 32-bit integer semantics — low 32 bits of the 64-bit constants.
    this.s = [0, 0, 0, 0]
    let z = seed >>> 0
    z = Math.imul(z ^ (z >>> 16), 0x45d9f3b)
    z = Math.imul(z ^ (z >>> 16), 0x45d9f3b)
    z = z ^ (z >>> 16)
    this.s[0] = z | 0
    this.s[1] = Math.imul(z ^ 0xdeadbeef, 0x9e3779b9) | 0
    this.s[2] = Math.imul(z ^ 0xbeefdead, 0x6c62272e) | 0
    this.s[3] = Math.imul(z ^ 0xf0e1d2c3, 0x4b3a2c1d) | 0
  }

  /** Return a float in [0, 1). */
  next(): number {
    /* c8 ignore start -- noUncheckedIndexedAccess artifact; this.s is a [number,number,number,number] tuple, all 4 elements always defined */
    const result = this.rotl(this.s[1]! * 5, 7) * 9
    const t = this.s[1]! << 9
    this.s[2]! ^= this.s[0]!
    this.s[3]! ^= this.s[1]!
    this.s[1]! ^= this.s[2]!
    this.s[0]! ^= this.s[3]!
    this.s[2]! ^= t
    this.s[3] = this.rotl(this.s[3]!, 11)
    /* c8 ignore stop */
    return ((result >>> 0) / 0x100000000)
  }

  /** Sample n integers from [0, max) without replacement. */
  sampleIndices(n: number, max: number): number[] {
    const indices: number[] = []
    const pool = Array.from({ length: max }, (_, i) => i)
    for (let i = 0; i < n && pool.length > 0; i++) {
      const j = Math.floor(this.next() * pool.length)
      /* c8 ignore next -- noUncheckedIndexedAccess artifact; j = Math.floor(next * pool.length) guarantees j < pool.length */
      indices.push(pool[j]!)
      pool.splice(j, 1)
    }
    return indices
  }

  private rotl(x: number, k: number): number {
    return ((x << k) | (x >>> (32 - k))) | 0
  }
}

/**
 * Derive a deterministic seed from a stream ID and epoch identifier.
 * The seed is derived from the event substrate, never from wall time.
 */
export function deriveSeed(streamId: string, epochId: string): number {
  let hash = 0x811c9dc5
  const str = `${streamId}:${epochId}`
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i)
    hash = (hash * 0x01000193) >>> 0
  }
  return hash
}
