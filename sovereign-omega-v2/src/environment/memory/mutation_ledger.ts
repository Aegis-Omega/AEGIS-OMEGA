// ============================================================
// Mutation Ledger — append-only environment mutation record (RULE-01)
// Every environment mutation is persisted before taking effect.
// EPISTEMIC TIER: T0 (append-only invariant is constitutional)
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { EnvironmentMutation, ReplayFrame } from '../types'
import type { SHA256Hex } from '../../core/types'
import { MutationRejectedError } from '../types'

const GENESIS_HASH = '0'.repeat(64) as SHA256Hex

export class MutationLedger {
  private readonly _mutations: readonly EnvironmentMutation[]
  private readonly _frames: readonly ReplayFrame[]

  private constructor(
    mutations: readonly EnvironmentMutation[],
    frames: readonly ReplayFrame[]
  ) {
    this._mutations = mutations
    this._frames = frames
  }

  static empty(): MutationLedger {
    return new MutationLedger(deepFreeze([]), deepFreeze([]))
  }

  get mutations(): readonly EnvironmentMutation[] { return this._mutations }
  get frames(): readonly ReplayFrame[] { return this._frames }
  get length(): number { return this._mutations.length }

  append(mutation: EnvironmentMutation, environmentStateHash: SHA256Hex): MutationLedger {
    // Sequence must be monotonically increasing
    if (this._mutations.length > 0) {
      const last = this._mutations[this._mutations.length - 1]
      if (last !== undefined && mutation.sequence <= last.sequence) {
        throw new MutationRejectedError(
          `Mutation sequence ${mutation.sequence} not strictly after ${last.sequence}`
        )
      }
    }

    const frame: ReplayFrame = deepFreeze({
      frame_sequence: mutation.sequence,
      environment_state_hash: environmentStateHash,
      mutation_hash: mutation.mutation_id as SHA256Hex,  // mutation ID serves as frame hash
      capability_grants_hash: mutation.admitted_by as SHA256Hex,
      invariant_outcomes_hash: GENESIS_HASH,  // populated by invariant-checker on replay
    })

    return new MutationLedger(
      deepFreeze([...this._mutations, deepFreeze(mutation)]),
      deepFreeze([...this._frames, frame])
    )
  }

  // Verify structural integrity: sequence contiguity within the ledger.
  verifyStructural(): { valid: boolean; failedAt?: number } {
    for (let i = 1; i < this._mutations.length; i++) {
      const curr = this._mutations[i]
      const prev = this._mutations[i - 1]
      /* c8 ignore next -- noUncheckedIndexedAccess requires undefined checks; bounds i < length guarantee non-null */
      if (curr !== undefined && prev !== undefined && curr.sequence <= prev.sequence) {
        return { valid: false, failedAt: i }
      }
    }
    return { valid: true }
  }

  // Reconstruct all mutations of a given type for replay.
  filterByType(type: EnvironmentMutation['mutation_type']): readonly EnvironmentMutation[] {
    return this._mutations.filter(m => m.mutation_type === type)
  }

  mutationVelocity(windowSize: number): number {
    if (windowSize <= 0 || this._mutations.length === 0) return 0
    const recent = this._mutations.slice(-windowSize)
    return recent.length
  }
}
