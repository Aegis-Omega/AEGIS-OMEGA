// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH — attribution_hash is hashValue over Shapley credit allocation
//   replay_mapping:    HARMONIZE — Shapley is the credit-allocation step after LOCK
//   topology_mapping:  CONSENSUS — operates on SynthesisRecord convergence output
//   epistemic_tier:    T2 — Shapley axioms are T0-proven; this application is engineering hypothesis
//
// Shapley value attribution for the three-agent BFT synthesis game.
// Characteristic function encodes the game-theoretic value of each agent coalition.
//
// Characteristic function v (3 agents: Alpha, Beta, Gamma):
//   v({})     = 0         — no value without agents
//   v({A})    = 0         — code without adversarial test and certification has no certified value
//   v({B})    = 0         — adversarial tests without implementation have no value
//   v({G})    = 0         — certification without implementation has no value
//   v({A, B}) = sim       — Alpha+Beta produce convergent code (structural_similarity)
//   v({A, G}) = 0.5 if COMMITTED, else 0  — certified code without adversarial testing (½ credit)
//   v({B, G}) = 0         — cannot produce useful output without Alpha's implementation
//   v({A,B,G})= 1.0 if COMMITTED, else sim  — full synthesis outcome
//
// Closed-form Shapley formulas for n=3 (derived from Σ_{S ⊆ N\{i}} (|S|!(n-|S|-1)!/n!) Δv):
//   φ_Alpha = sim/6 + (committed ? 1/12 : 0) + outcome/3
//   φ_Beta  = sim/6 + outcome/3 − (committed ? 1/6 : 0)
//   φ_Gamma = (committed ? 1/12 : 0) + (outcome − sim) / 3
//
// Efficiency: φ_A + φ_B + φ_G = v(N) = outcome. Proven algebraically.

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex } from '../core/types.js'
import type { SynthesisRecord } from './synthesis-swarm.js'

export const GAME_THEORY_SCHEMA_VERSION = '1.0.0' as const

export interface ShapleyAttestation {
  readonly alpha_credit: number    // Shapley φ_Alpha ∈ [0, 1]
  readonly beta_credit: number     // Shapley φ_Beta  ∈ [0, 1]
  readonly gamma_credit: number    // Shapley φ_Gamma ∈ [0, 1]
  readonly total_value: number     // v(N) = grand coalition value (outcome)
  readonly is_efficient: boolean   // |φ_A + φ_B + φ_G − total_value| < 1e-9
  readonly verdict: string         // echoed from SynthesisRecord for auditability
  readonly structural_similarity: number
  readonly attribution_hash: SHA256Hex
  readonly schema_version: typeof GAME_THEORY_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class GameTheoryError extends Error {
  override readonly name = 'GameTheoryError'
}

/**
 * Compute Shapley value credit attribution for a three-agent synthesis record.
 * Returns a frozen, replay-certifiable ShapleyAttestation.
 *
 * Interpretation:
 *  - COMMITTED, sim=1.0 → φ_A≈0.583, φ_B≈0.333, φ_G≈0.083
 *    (Alpha is most pivotal; Beta essential; Gamma modest contribution)
 *  - REJECTED/DEADLOCK, any sim → φ_G=0 (certification produced no committed output)
 *    (Alpha and Beta share credit for convergence value achieved)
 *  - COMMITTED, sim→0 → φ_A dominates (even weak convergence, Alpha+Gamma drove the commit)
 */
export async function computeSynthesisShapley(
  record: SynthesisRecord,
): Promise<ShapleyAttestation> {
  const committed = record.verdict === 'COMMITTED'
  const sim = record.convergence.structural_similarity
  const outcome = committed ? 1.0 : sim

  // Shapley closed-form (algebraically verified to sum to outcome):
  const alpha_credit = sim / 6 + (committed ? 1 / 12 : 0) + outcome / 3
  const beta_credit  = sim / 6 + outcome / 3 - (committed ? 1 / 6 : 0)
  const gamma_credit = (committed ? 1 / 12 : 0) + (outcome - sim) / 3

  const is_efficient = Math.abs(alpha_credit + beta_credit + gamma_credit - outcome) < 1e-9

  const attribution_hash = await hashValue({
    alpha_credit,
    beta_credit,
    gamma_credit,
    total_value: outcome,
    verdict: record.verdict,
    synthesis_hash: record.synthesis_hash,
  }) as SHA256Hex

  return deepFreeze({
    alpha_credit,
    beta_credit,
    gamma_credit,
    total_value: outcome,
    is_efficient,
    verdict: record.verdict,
    structural_similarity: sim,
    attribution_hash,
    schema_version: GAME_THEORY_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })
}
