// ============================================================
// SOVEREIGN OMEGA — Constitutional Runtime
// EPISTEMIC TIER: T0 · Gate 13
//
// Top-level composition entry point for the Constitutional Governance
// Surface. Wires SITRRuntime + AOIEClassification + InvariantSnapshot
// through the ConstitutionalAssembly, producing GovernanceDecision[]
// and Guardian E5 event payloads. Immutable functional update.
// ============================================================

import { checkInvariants } from '../core/invariant-checker.js'
import type { RuntimeSnapshot as InvariantRuntimeSnapshot } from '../core/invariant-checker.js'
import type { SITRRuntime } from '../sitr/runtime.js'
import type { AOIEClassification } from '../aoie/types.js'
import type { UUIDv7 } from '../core/types.js'
import type { ConstitutionalVerdict, GovernanceDecision, ConstitutionalTelemetry } from './types.js'
import { CONSTITUTIONAL_SCHEMA_VERSION } from './types.js'
import { ConstitutionalAssembly } from './assembly.js'
import { ConvergenceSurface } from './convergence.js'
import {
  buildGuardianInvokedPayload,
  buildGuardianVerdictPayload,
} from './guardian.js'
import { governanceThroughput } from '../core/ralph-loop.js'

export class ConstitutionalRuntime {
  private constructor(
    private readonly _assembly: ConstitutionalAssembly,
    private readonly _convergence: ConvergenceSurface,
    private readonly _decisionCount: number,
    private readonly _startSequence: number,
  ) {}

  static empty(startSequence = 0): ConstitutionalRuntime {
    return new ConstitutionalRuntime(
      ConstitutionalAssembly.empty(),
      ConvergenceSurface.create(1.0),
      0,
      startSequence,
    )
  }

  /**
   * Evaluate the current governance signals. Runs invariant check internally,
   * classifies verdict, appends decision, and records convergence cycle.
   * Returns updated ConstitutionalRuntime — source unchanged.
   */
  evaluate(params: {
    readonly sitr: SITRRuntime
    readonly aoie: AOIEClassification
    readonly invariantSnapshot: InvariantRuntimeSnapshot
    readonly sequence: number
    readonly decision_id: string
  }): ConstitutionalRuntime {
    const invariantResult = checkInvariants(params.invariantSnapshot)
    const sitrState = params.sitr.currentState()
    const aoieGlobal = params.aoie.global_state

    const newAssembly = this._assembly.observe({
      sitr_state: sitrState,
      aoie_global_state: aoieGlobal,
      invariant_result: invariantResult,
      sequence: params.sequence,
      decision_id: params.decision_id,
    })

    const gateResult = newAssembly.currentVerdict() === 'PERMIT' ? 'PASS' : 'FAIL'
    this._convergence.recordCycle({
      sitr_state: sitrState,
      aoie_global_state: aoieGlobal,
      invariant_result: invariantResult,
      sequence: params.sequence,
      gate_result: gateResult,
    })

    return new ConstitutionalRuntime(
      newAssembly,
      this._convergence,
      this._decisionCount + 1,
      this._startSequence,
    )
  }

  currentVerdict(): ConstitutionalVerdict {
    return this._assembly.currentVerdict()
  }

  decisions(): readonly GovernanceDecision[] {
    return this._assembly.decisions()
  }

  convergenceDepth(): number {
    return this._convergence.convergenceDepth()
  }

  telemetry(currentSequence: number): Readonly<ConstitutionalTelemetry> {
    const state = this._assembly.getState()
    const span = currentSequence - this._startSequence
    return Object.freeze({
      verdict: state.current_verdict,
      decision_count: state.decision_count,
      reject_count: state.reject_count,
      escalation_count: state.escalation_count,
      convergence_depth: this._convergence.convergenceDepth(),
      governance_throughput: governanceThroughput(this._decisionCount, span),
      schema_version: CONSTITUTIONAL_SCHEMA_VERSION,
    })
  }

  guardianInvokedPayload(params: {
    readonly invoked_by: string
    readonly files_under_review: readonly string[]
  }) {
    const last = this._assembly.decisions().at(-1)
    return buildGuardianInvokedPayload({
      invoked_by: params.invoked_by,
      check_reason: last?.reason ?? 'Constitutional governance check',
      files_under_review: params.files_under_review,
    })
  }

  guardianVerdictPayload(params: {
    readonly location: string
    readonly invocation_event_id: UUIDv7
  }) {
    const last = this._assembly.decisions().at(-1)
    return buildGuardianVerdictPayload({
      verdict: last?.verdict ?? 'PERMIT',
      location: params.location,
      reason: last?.reason ?? 'Constitutional governance check',
      invocation_event_id: params.invocation_event_id,
    })
  }
}
