// ============================================================
// SOVEREIGN OMEGA — Constitutional Martingale
// EPISTEMIC TIER: T1 · Gate 61
//
// Implements E[S_{n+1} | F_n] = S_n — the martingale constitutional
// form. A governance process is constitutionally admissible iff its
// certified replay states form a martingale under the replay filtration.
//
// Holonic triad governed by 1/φ across all three scales:
//   SUBATOMIC (gate/hoeffding.ts)    — E[E_n] ≤ 1 under H₀ (betting martingale)
//   MOLECULAR (this module)          — E[S_{n+1}|F_n] = S_n (constitutional martingale)
//   ORGANISM  (consensus/swarm.ts)   — ≥ 1/φ nodes converge (consensus martingale)
//
// Constitutional consequence: if adaptive_ratio > MUTATION_RATE_LIMIT,
// mutation authority suspends and convergence quarantine activates.
//
// primitive_mapping: HASH · replay_mapping: HARMONIZE
// topology_mapping: LINEAGE
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  certifyAdaptiveLineage,
  type AdaptiveLineageEntry,
} from '../frame/adaptive-lineage.js'

export const MARTINGALE_SCHEMA_VERSION = '1.0.0' as const

// 1/φ — golden ratio reciprocal. Defined independently of swarm.ts
// to avoid cross-layer coupling. Equality proven in test/unit/martingale.test.ts.
export const MUTATION_RATE_LIMIT = (Math.sqrt(5) - 1) / 2

export interface MartingaleCertificate {
  readonly is_anchored: boolean          // hash chain valid → drift = 0 → E[S_{n+1}|F_n] = S_n
  readonly drift_bounded: boolean        // equivalent to is_anchored (zero drift iff chain valid)
  readonly entropy_bounded: boolean      // adaptive_power / replay_verifiability ≤ 1/φ
  readonly adaptive_power: number        // count of APPROVED CAPABILITY_EVOLUTION entries
  readonly replay_verifiability: number  // chain length (all entries are replay-certified)
  readonly adaptive_ratio: number        // adaptive_power / max(replay_verifiability, 1)
  readonly mutation_rate_limit: number   // MUTATION_RATE_LIMIT constant (1/φ)
  readonly terminal_hash: SHA256Hex | null
  readonly certificate_hash: SHA256Hex
  readonly schema_version: typeof MARTINGALE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class MartingaleViolation extends Error {
  override readonly name = 'MartingaleViolation'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export async function certifyMartingale(
  entries: readonly AdaptiveLineageEntry[],
): Promise<MartingaleCertificate> {
  const { is_valid, terminal_hash } = await certifyAdaptiveLineage(entries)

  let adaptive_power = 0
  for (const e of entries) {
    if (e.event.kind === 'CAPABILITY_EVOLUTION' && e.event.verdict === 'APPROVED') {
      adaptive_power++
    }
  }

  const replay_verifiability = entries.length
  const adaptive_ratio = replay_verifiability > 0 ? adaptive_power / replay_verifiability : 0
  const entropy_bounded = adaptive_ratio <= MUTATION_RATE_LIMIT
  const is_anchored = is_valid
  const drift_bounded = is_valid

  const certificate_hash = await hashValue({
    is_anchored,
    drift_bounded,
    entropy_bounded,
    adaptive_power,
    replay_verifiability,
    adaptive_ratio,
    mutation_rate_limit: MUTATION_RATE_LIMIT,
    terminal_hash: terminal_hash ?? 'genesis',
  })

  return deepFreeze<MartingaleCertificate>({
    is_anchored,
    drift_bounded,
    entropy_bounded,
    adaptive_power,
    replay_verifiability,
    adaptive_ratio,
    mutation_rate_limit: MUTATION_RATE_LIMIT,
    terminal_hash,
    certificate_hash,
    schema_version: MARTINGALE_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

// Enforcement layer: throws MartingaleViolation if any constitutional
// condition is violated. Operational consequence: mutation authority
// suspends and convergence quarantine activates.
export function assertMartingaleAnchored(cert: MartingaleCertificate): void {
  if (!cert.is_anchored) {
    throw new MartingaleViolation(
      'Replay divergence: chain integrity violated — E[S_{n+1}|F_n] ≠ S_n',
    )
  }
  if (!cert.drift_bounded) {
    throw new MartingaleViolation(
      'Constitutional stability violated: unbounded expectation drift detected',
    )
  }
  if (!cert.entropy_bounded) {
    throw new MartingaleViolation(
      `Mutation authority exceeded: adaptive_ratio ${cert.adaptive_ratio.toFixed(6)} > 1/φ ${MUTATION_RATE_LIMIT.toFixed(6)}`,
    )
  }
}
