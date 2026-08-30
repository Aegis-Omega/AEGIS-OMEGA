// ============================================================
// SOVEREIGN OMEGA — Verifier Independence Monitor
// EPISTEMIC TIER: T1
// Referenced in RALPH LOOP Ω.C.2
// Tracks empirical agreement rates between verifiers and
// applies dynamic correlation penalties via computeCorrelationPenalty.
// Prevents monoculture, collusion, and false convergence.
// ============================================================

import type { VerifierOutput } from './types.js'
import { CalibrationDomain as CD } from '../core/types.js'
import { toQ32, fromQ32, computeCorrelationPenalty, Q_ONE, type Q32_32 } from '../core/fixedpoint.js'

const BASELINE_INDEPENDENCE = toQ32(0.5) // expected agreement under independence
const MIN_SAMPLES_FOR_PENALTY = 20        // minimum agreement history before penalty applies

export interface VerifierPairRecord {
  readonly verifier_a: string
  readonly verifier_b: string
  agreements: number
  total: number
}

export interface IndependenceSnapshot {
  readonly pair: string
  readonly agreement_rate: number
  readonly penalty: number
  readonly weight_a: number
  readonly weight_b: number
  readonly samples: number
  readonly alert: boolean
}

/**
 * Monitors pairwise agreement between calibration-eligible verifiers.
 * Emits dynamic correlation penalties via the Q32.32 penalty function.
 * Alert threshold: agreement rate > 0.90 with sufficient samples.
 */
export class VerifierIndependenceMonitor {
  private readonly pairs = new Map<string, VerifierPairRecord>()
  private readonly weights = new Map<string, Q32_32>()

  update(outputs: readonly VerifierOutput[]): void {
    const eligible = outputs.filter(o =>
      o.trust_class === CD.GROUND_TRUTH ||
      o.trust_class === CD.RETRIEVAL_ASSISTED
    )

    // Update pairwise agreement records
    for (let i = 0; i < eligible.length; i++) {
      for (let j = i + 1; j < eligible.length; j++) {
        const a = eligible[i]!
        const b = eligible[j]!
        const key = [a.verifier_id, b.verifier_id].sort().join('::')

        if (!this.pairs.has(key)) {
          this.pairs.set(key, { verifier_a: a.verifier_id, verifier_b: b.verifier_id, agreements: 0, total: 0 })
        }
        const record = this.pairs.get(key)!
        record.total++
        if (a.passed === b.passed) record.agreements++

        // Recompute penalty and update weights for both verifiers
        if (record.total >= MIN_SAMPLES_FOR_PENALTY) {
          const agreement_rate = toQ32(record.agreements / record.total)
          const penalty = computeCorrelationPenalty(agreement_rate, BASELINE_INDEPENDENCE)

          // Apply penalty symmetrically to both verifiers
          for (const id of [a.verifier_id, b.verifier_id]) {
            const current = this.weights.get(id) ?? Q_ONE
            const penalised = (current * penalty) >> 32n
            this.weights.set(id, penalised < (Q_ONE >> 2n) ? (Q_ONE >> 2n) : penalised)
          }
        }
      }
    }
  }

  /**
   * Get the current dynamic weight for a verifier in Q32.32.
   * Returns Q_ONE (1.0) if no correlation data exists yet.
   */
  getWeight(verifierId: string): Q32_32 {
    return this.weights.get(verifierId) ?? Q_ONE
  }

  getSnapshot(): readonly IndependenceSnapshot[] {
    return [...this.pairs.entries()].map(([key, rec]) => {
      /* c8 ignore next -- total always > 0 when a record exists in this.pairs; `: 0` arm structurally unreachable */
      const agreement_rate = rec.total > 0 ? rec.agreements / rec.total : 0
      const penalty = rec.total >= MIN_SAMPLES_FOR_PENALTY
        ? fromQ32(computeCorrelationPenalty(toQ32(agreement_rate), BASELINE_INDEPENDENCE))
        : 1.0
      return Object.freeze({
        pair: key,
        agreement_rate,
        penalty,
        weight_a: fromQ32(this.weights.get(rec.verifier_a) ?? Q_ONE),
        weight_b: fromQ32(this.weights.get(rec.verifier_b) ?? Q_ONE),
        samples: rec.total,
        alert: agreement_rate > 0.90 && rec.total >= MIN_SAMPLES_FOR_PENALTY,
      })
    })
  }

  hasAlerts(): boolean {
    return this.getSnapshot().some(s => s.alert)
  }
}
