// ============================================================
// SOVEREIGN OMEGA — Policy Amendment Engine
// EPISTEMIC TIER: T0 · Gate 21
//
// Bounded policy amendment lifecycle:
//   PROPOSED → UNDER_REVIEW → APPROVED | REJECTED → APPLIED
//
// Hard constraints:
//   1. Amendment requires Guardian APPROVED verdict.
//   2. No invariant regression allowed at apply time.
//   3. Runtime never modifies constitutional primitives directly.
//      All changes are E5 events consumed by the enforcement engine.
//
// Immutable functional update pattern — each mutating method
// returns a new PolicyAmendmentEngine instance.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { CONSTITUTIONAL_SCHEMA_VERSION } from './types.js'
import { type PolicyAmendment, PolicyAmendmentError } from './amendment.js'

// ─── Deterministic ID ──────────────────────────────────────

function fnv1a32(s: string): string {
  let hash = 2166136261
  for (let i = 0; i < s.length; i++) {
    hash ^= s.charCodeAt(i)
    hash = (hash * 16777619) >>> 0
  }
  return hash.toString(16).padStart(8, '0')
}

function makeAmendmentId(target: string, constraintDelta: string, sequence: number): string {
  return `amd_${fnv1a32(`${target}:${constraintDelta}:${sequence}`)}`
}

// ─── Engine ────────────────────────────────────────────────

export class PolicyAmendmentEngine {
  private constructor(
    private readonly _amendments: readonly PolicyAmendment[],
  ) {}

  static empty(): PolicyAmendmentEngine {
    return new PolicyAmendmentEngine([])
  }

  // ─── Queries ─────────────────────────────────────────────

  getAll(): readonly PolicyAmendment[] {
    return this._amendments
  }

  getById(id: string): PolicyAmendment | null {
    return this._amendments.find(a => a.amendment_id === id) ?? null
  }

  get count(): number {
    return this._amendments.length
  }

  // ─── Transitions ─────────────────────────────────────────

  /**
   * Submit a new amendment proposal. Status: PROPOSED.
   * Returns a new engine with the amendment appended.
   * amendment_id is deterministic: FNV-1a(target + delta + sequence).
   */
  propose(params: {
    readonly target: string
    readonly description: string
    readonly constraint_delta: string
    readonly at_sequence: number
  }): { engine: PolicyAmendmentEngine; amendment: PolicyAmendment } {
    const amendment = deepFreeze<PolicyAmendment>({
      amendment_id: makeAmendmentId(params.target, params.constraint_delta, params.at_sequence),
      proposed_at_sequence: params.at_sequence,
      target: params.target,
      description: params.description,
      constraint_delta: params.constraint_delta,
      status: 'PROPOSED',
      is_replay_reconstructable: true,
      schema_version: CONSTITUTIONAL_SCHEMA_VERSION,
    })
    const engine = new PolicyAmendmentEngine(
      Object.freeze([...this._amendments, amendment]),
    )
    return { engine, amendment }
  }

  /**
   * Record Guardian verdict for an amendment.
   * APPROVED → status APPROVED; VETOED → status REJECTED.
   * Throws PolicyAmendmentError if amendment_id not found or
   * amendment is not in PROPOSED or UNDER_REVIEW state.
   */
  recordVerdict(
    amendmentId: string,
    verdict: 'APPROVED' | 'VETOED',
  ): PolicyAmendmentEngine {
    const idx = this._amendments.findIndex(a => a.amendment_id === amendmentId)
    if (idx === -1) {
      throw new PolicyAmendmentError(`Amendment ${amendmentId} not found`)
    }

    const existing = this._amendments[idx]!
    if (existing.status !== 'PROPOSED' && existing.status !== 'UNDER_REVIEW') {
      throw new PolicyAmendmentError(
        `Amendment ${amendmentId} is ${existing.status} — cannot record verdict`,
      )
    }

    const updated = deepFreeze<PolicyAmendment>({
      ...existing,
      status: verdict === 'APPROVED' ? 'APPROVED' : 'REJECTED',
      guardian_verdict: verdict,
    })

    const newAmendments = Object.freeze([
      ...this._amendments.slice(0, idx),
      updated,
      ...this._amendments.slice(idx + 1),
    ])

    return new PolicyAmendmentEngine(newAmendments)
  }

  /**
   * Apply an approved amendment. Requires:
   *   1. status === 'APPROVED'
   *   2. invariantsPassed === true (no regression)
   * Returns new engine with amendment in APPLIED state.
   * Throws PolicyAmendmentError on any precondition failure.
   */
  apply(
    amendmentId: string,
    params: {
      readonly at_sequence: number
      readonly invariants_passed: boolean
    },
  ): PolicyAmendmentEngine {
    const idx = this._amendments.findIndex(a => a.amendment_id === amendmentId)
    if (idx === -1) {
      throw new PolicyAmendmentError(`Amendment ${amendmentId} not found`)
    }

    const existing = this._amendments[idx]!

    if (existing.status !== 'APPROVED') {
      throw new PolicyAmendmentError(
        `Amendment ${amendmentId} must be APPROVED before applying (current: ${existing.status})`,
      )
    }

    if (!params.invariants_passed) {
      throw new PolicyAmendmentError(
        `Amendment ${amendmentId} rejected: invariant regression detected`,
      )
    }

    const applied = deepFreeze<PolicyAmendment>({
      ...existing,
      status: 'APPLIED',
      applied_at_sequence: params.at_sequence,
    })

    const newAmendments = Object.freeze([
      ...this._amendments.slice(0, idx),
      applied,
      ...this._amendments.slice(idx + 1),
    ])

    return new PolicyAmendmentEngine(newAmendments)
  }
}
