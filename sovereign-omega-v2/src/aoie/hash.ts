// ============================================================
// AOIE Snapshot Hashing — deterministic identity fingerprints
// EPISTEMIC TIER: T1
// FNV-1a 32-bit hash (no crypto dependency, no async).
// Same pattern as src/environment/workspace/introspection.ts.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import type { RuntimeSnapshot } from './types.js'
import { canonicalizeSnapshot } from './canonicalize.js'

// FNV-1a 32-bit hash of a byte array.
function fnv1a32(bytes: Uint8Array): number {
  let hash = 2166136261
  for (let i = 0; i < bytes.length; i++) {
    const byte = bytes[i]
    /* c8 ignore next -- noUncheckedIndexedAccess artifact; i < bytes.length guarantees byte is defined */
    if (byte !== undefined) {
      hash ^= byte
      hash = (hash * 16777619) >>> 0
    }
  }
  return hash >>> 0
}

// Returns an SHA256Hex-branded string (FNV-1a fingerprint, not a real SHA-256).
// The brand documents structural intent; the value is deterministic and replay-safe.
export function hashSnapshot(s: RuntimeSnapshot): SHA256Hex {
  const bytes = canonicalizeSnapshot(s)
  const h = fnv1a32(bytes)
  return h.toString(16).padStart(8, '0').padEnd(64, '0') as SHA256Hex
}

export function snapshotsAreIdentical(a: RuntimeSnapshot, b: RuntimeSnapshot): boolean {
  return hashSnapshot(a) === hashSnapshot(b)
}

// [0,1] fraction of adjacent snapshot pairs with differing hashes.
export function computeIdentityDrift(snapshots: readonly RuntimeSnapshot[]): number {
  if (snapshots.length <= 1) return 0
  let drifted = 0
  for (let i = 1; i < snapshots.length; i++) {
    const prev = snapshots[i - 1]
    const curr = snapshots[i]
    if (prev !== undefined && curr !== undefined && !snapshotsAreIdentical(prev, curr)) {
      drifted++
    }
  }
  return drifted / (snapshots.length - 1)
}
