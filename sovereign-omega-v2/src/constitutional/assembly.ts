// ============================================================
// SOVEREIGN OMEGA — Constitutional Assembly
// EPISTEMIC TIER: T0 · Gate 13
//
// Append-only governance decision log. Immutable functional update
// pattern — each observe() returns a new ConstitutionalAssembly.
// Consumes SITR state, AOIE global state, and invariant results;
// produces GovernanceDecision[] as the authoritative verdict record.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { InvariantCheckResult } from '../core/invariant-checker.js'
import type { SITRState } from '../sitr/types.js'
import type { GlobalState } from '../aoie/types.js'
import type { ConstitutionalVerdict, GovernanceDecision, ConstAssemblyState } from './types.js'
import { CONSTITUTIONAL_SCHEMA_VERSION } from './types.js'
import { computeVerdict, verdictReason } from './verdict.js'

export class ConstitutionalAssembly {
  private constructor(
    private readonly _decisions: readonly GovernanceDecision[],
    private readonly _rejectCount: number,
    private readonly _escalationCount: number,
    private readonly _lastSequence: number,
  ) {}

  static empty(): ConstitutionalAssembly {
    return new ConstitutionalAssembly([], 0, 0, 0)
  }

  /**
   * Observe a new governance signal and return an updated assembly with the
   * resulting GovernanceDecision appended. Source unchanged (functional update).
   */
  observe(params: {
    readonly sitr_state: SITRState
    readonly aoie_global_state: GlobalState
    readonly invariant_result: InvariantCheckResult
    readonly sequence: number
    readonly decision_id: string
  }): ConstitutionalAssembly {
    const verdict = computeVerdict(
      params.sitr_state,
      params.aoie_global_state,
      params.invariant_result,
    )
    const reason = verdictReason(
      params.sitr_state,
      params.aoie_global_state,
      params.invariant_result,
    )
    const decision = deepFreeze<GovernanceDecision>({
      decision_id: params.decision_id,
      verdict,
      sequence: params.sequence,
      sitr_state: params.sitr_state,
      aoie_global_state: params.aoie_global_state,
      invariant_passed: params.invariant_result.passed,
      has_t0_violation: params.invariant_result.violations.some(v => v.severity === 'T0_ABORT'),
      reason,
      schema_version: CONSTITUTIONAL_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })

    return new ConstitutionalAssembly(
      Object.freeze([...this._decisions, decision]),
      this._rejectCount + (verdict === 'REJECT' ? 1 : 0),
      this._escalationCount + (verdict === 'ESCALATE' ? 1 : 0),
      params.sequence,
    )
  }

  currentVerdict(): ConstitutionalVerdict {
    const last = this._decisions[this._decisions.length - 1]
    return last?.verdict ?? 'PERMIT'
  }

  decisions(): readonly GovernanceDecision[] {
    return this._decisions
  }

  getState(): Readonly<ConstAssemblyState> {
    return deepFreeze<ConstAssemblyState>({
      current_verdict: this.currentVerdict(),
      decision_count: this._decisions.length,
      reject_count: this._rejectCount,
      escalation_count: this._escalationCount,
      last_sequence: this._lastSequence,
      schema_version: CONSTITUTIONAL_SCHEMA_VERSION,
    })
  }
}
