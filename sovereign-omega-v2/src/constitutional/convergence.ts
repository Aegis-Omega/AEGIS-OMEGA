// ============================================================
// SOVEREIGN OMEGA — Convergence Surface
// EPISTEMIC TIER: T1 · Gate 13
//
// Full-system governance observer. Wraps RalphLoop (ORGANISM scale)
// and tracks consecutive PASS cycles for convergence depth measurement.
// Stateful observer — recordCycle() mutates the internal loop but
// returns this for chaining. systemHealth() is always current-state.
// ============================================================

import { RalphLoop, estimateSystemEntropy, governanceThroughput } from '../core/ralph-loop.js'
import { HolonicScale, EpistemicTier, type SequenceNumber } from '../core/types.js'
import { hasT0Violation } from '../core/invariant-checker.js'
import type { InvariantCheckResult } from '../core/invariant-checker.js'
import type { SITRState } from '../sitr/types.js'
import type { GlobalState } from '../aoie/types.js'
import { deepFreeze } from '../core/immutable.js'
import type { SystemHealthSnapshot } from './types.js'
import { computeVerdict } from './verdict.js'

export class ConvergenceSurface {
  private _cycleCount = 0
  private _consecutivePassCount = 0
  private _lastSitrState: SITRState = 'STABLE'
  private _lastAoieGlobal: GlobalState = 'SECURE'
  private _lastInvariantResult: InvariantCheckResult | null = null

  private constructor(private readonly _loop: RalphLoop) {}

  static create(gateAcceptanceRate: number): ConvergenceSurface {
    const entropy = estimateSystemEntropy(gateAcceptanceRate)
    return new ConvergenceSurface(new RalphLoop(HolonicScale.ORGANISM, entropy))
  }

  /**
   * Record a governance cycle result. Updates the Ralph loop with findings
   * from the current SITR/AOIE/invariant signals.
   */
  recordCycle(params: {
    readonly sitr_state: SITRState
    readonly aoie_global_state: GlobalState
    readonly invariant_result: InvariantCheckResult
    readonly sequence: number
    readonly gate_result: 'PASS' | 'FAIL'
  }): this {
    const seqNum = BigInt(params.sequence) as SequenceNumber
    const builder = this._loop.beginCycle(seqNum)
    builder.addAnalysisNote(`SITR: ${params.sitr_state}`)
    builder.addAnalysisNote(`AOIE: ${params.aoie_global_state}`)

    for (const v of params.invariant_result.violations) {
      builder.addFinding({
        description: `${v.invariant_id}: ${v.description}`,
        severity: v.severity === 'T0_ABORT'
          ? 'critical'
          : v.severity === 'T1_ALERT' ? 'important' : 'informational',
        scale: v.holonic_scale,
        tier: v.tier as EpistemicTier,
      })
    }

    builder.harmonize(params.gate_result)

    this._cycleCount++
    if (params.gate_result === 'PASS') {
      this._consecutivePassCount++
    } else {
      this._consecutivePassCount = 0
    }
    this._lastSitrState = params.sitr_state
    this._lastAoieGlobal = params.aoie_global_state
    this._lastInvariantResult = params.invariant_result

    return this
  }

  /** Consecutive PASS cycles — analogous to Python convergence_epochs(). */
  convergenceDepth(): number {
    return this._consecutivePassCount
  }

  /** Governance cycles per sequence unit. */
  throughput(sequenceSpan: number): number {
    return governanceThroughput(this._cycleCount, sequenceSpan)
  }

  /** Point-in-time system health from the latest recorded signals. */
  systemHealth(sequence: number): Readonly<SystemHealthSnapshot> {
    const inv = this._lastInvariantResult
    const verdict = inv
      ? computeVerdict(this._lastSitrState, this._lastAoieGlobal, inv)
      : 'PERMIT'
    const t0 = inv ? hasT0Violation(inv) : false

    return deepFreeze<SystemHealthSnapshot>({
      sitr_state: this._lastSitrState,
      aoie_global_state: this._lastAoieGlobal,
      current_verdict: verdict,
      convergence_depth: this._consecutivePassCount,
      sequence,
      is_coherent: !t0 && this._lastSitrState === 'STABLE' && this._lastAoieGlobal === 'SECURE',
    })
  }
}
