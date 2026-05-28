// ============================================================
// SOVEREIGN OMEGA — UUIDv7 Generation
// EPISTEMIC TIER: T0
// UUIDv7 is time-ordered, monotonic, and suitable for
// use as event_id with lexicographic ordering guarantees.
// ============================================================

import type { UUIDv7 } from '../core/types.js'

let lastMs = 0
let seq = 0
let randBHex = '' // 8 bytes, frozen per ms; top 2 bits become variant=10

/**
 * Generate a time-ordered UUIDv7 (RFC 9562).
 * Layout: 48-bit ms | ver(4) | seq(12) | var(2) | rand_b(62)
 * rand_b is frozen per millisecond so seq alone governs ordering within the same ms.
 * Supports 4096 unique IDs per millisecond before seq overflow.
 */
export function generateUUIDv7(): UUIDv7 {
  let now = Date.now()  // Only permitted use of Date.now() — for UUID generation only
  if (now <= lastMs) {
    now = lastMs  // enforce monotonicity; absorbs clock regression
    seq++
    /* c8 ignore next -- overflow requires 4097 UUID calls within the same millisecond */
    if (seq > 0xfff) {
      // Sequence overflow: advance virtual millisecond to preserve uniqueness
      lastMs++
      now = lastMs
      seq = 0
      const rand = new Uint8Array(8)
      crypto.getRandomValues(rand)
      randBHex = Array.from(rand).map(b => b.toString(16).padStart(2, '0')).join('')
    }
  } else {
    lastMs = now
    seq = 0
    const rand = new Uint8Array(8)
    crypto.getRandomValues(rand)
    randBHex = Array.from(rand).map(b => b.toString(16).padStart(2, '0')).join('')
  }

  const msHex = now.toString(16).padStart(12, '0')
  // seq is guaranteed ≤ 0xFFF after overflow handling — no mask needed
  const seqHex = seq.toString(16).padStart(3, '0')
  // Apply RFC 4122 variant bits (10xx) to first byte of rand_b
  const variantHex = (parseInt(randBHex.slice(0, 2), 16) & 0x3f | 0x80).toString(16).padStart(2, '0')

  // UUIDv7 format: xxxxxxxx-xxxx-7xxx-yxxx-xxxxxxxxxxxx
  const uuid = [
    msHex.slice(0, 8),                       // 32-bit ts high
    msHex.slice(8, 12),                      // 16-bit ts low
    '7' + seqHex,                            // ver(4) + seq(12)
    variantHex + randBHex.slice(2, 4),       // var(2)+rand_b[0:14]
    randBHex.slice(4, 16),                   // rand_b[14:62]
  ].join('-')

  return uuid as UUIDv7
}
