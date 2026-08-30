// ============================================================
// SOVEREIGN OMEGA — Risk Budget & Harmonic Spending
// EPISTEMIC TIER: T0
// Finite risk budget with Confirm-Triggered Harmonic Spending.
// Budget decay uses event-derived timestamps — never Date.now().
// K-bound enforcement: capacity exceeded = reject without test.
// ============================================================

import type { RiskBudget, GateDecisionPayload, BoundedDelta } from '../core/types.js'
import { normalizeDelta } from '../core/types.js'
import { ConfidenceSequence } from './hoeffding.js'
import { capacityRegistry } from '../verifier/registry.js'

const DEFAULT_GLOBAL_BUDGET = 1.0
const DEFAULT_DECAY_LAMBDA = 0.05 / (60 * 60 * 1000)  // 0.05 per hour in ms
const DEFAULT_MAX_ROUNDS = 1000
const BUDGET_SUSPEND_FLOOR = 0.01  // delta_min

export class RiskBudgetManager {
  private budget: RiskBudget
  private suspended = false
  private frozen = false

  constructor(
    epochStartMs: number,  // from event substrate, never Date.now()
    globalBudget = DEFAULT_GLOBAL_BUDGET,
    maxRounds = DEFAULT_MAX_ROUNDS,
    decayLambda = DEFAULT_DECAY_LAMBDA
  ) {
    this.budget = Object.freeze({
      global_budget: globalBudget,
      decay_lambda: decayLambda,
      epoch_start_ms: epochStartMs,
      spent: 0,
      round_number: 0,
      max_rounds: maxRounds,
    })
  }

  /**
   * Evaluate whether a proposed modification should be accepted.
   * The gate accepts when LCB > 0 AND budget permits AND K is within bounds.
   *
   * Returns the full gate decision payload for event logging.
   * All decisions are logged — audit trail is complete.
   */
  evaluate(
    proposalId: string,
    componentId: string,
    samples: readonly number[],
    deltaK: number,
    currentMs: number  // from event substrate
  ): GateDecisionPayload {
    if (this.frozen) {
      return this.makeDecision(proposalId, componentId, false, 0, 0, samples.length, 0, 'BUDGET_EXHAUSTED', currentMs)
    }

    // K-bound check — reject without statistical testing
    if (!capacityRegistry.checkKBound(componentId, deltaK)) {
      return this.makeDecision(proposalId, componentId, false, 0, 0, samples.length, 0, 'CAPACITY_EXCEEDED', currentMs)
    }

    // Set suspension state if budget has fallen below floor
    if (this.currentBudget(currentMs) < BUDGET_SUSPEND_FLOOR) {
      this.suspended = true
    }

    if (this.suspended) {
      return this.makeDecision(proposalId, componentId, false, 0, 0, samples.length, 0, 'BUDGET_EXHAUSTED', currentMs)
    }

    const k = this.budget.round_number + 1
    const harmonicNumber = harmonicSum(this.budget.max_rounds)
    const deltaAlpha = this.currentBudget(currentMs) / (k * harmonicNumber)

    // Compute Bernstein LCB and e-value
    const seq = new ConfidenceSequence(deltaAlpha)
    for (const s of samples) {
      seq.update(normalizeDelta(s) as BoundedDelta)
    }
    const lcb = seq.lcb()
    const eValue = seq.eValue()

    const accepted = lcb > 0

    if (accepted) {
      const riskSpent = deltaAlpha
      const newBudget = Object.freeze({
        ...this.budget,
        spent: this.budget.spent + riskSpent,
        round_number: k,
      })
      this.budget = newBudget

      if (this.currentBudget(currentMs) < BUDGET_SUSPEND_FLOOR) {
        this.suspended = true
      }
    }

    return this.makeDecision(
      proposalId, componentId, accepted, lcb, eValue,
      samples.length, deltaAlpha, accepted ? undefined : 'LCB_FAIL', currentMs
    )
  }

  /**
   * Current available budget, accounting for time-decay.
   * Decay uses event-derived timestamp — never wall clock.
   */
  currentBudget(currentMs: number): number {
    const ageMs = currentMs - this.budget.epoch_start_ms
    const decayed = this.budget.global_budget * Math.exp(-this.budget.decay_lambda * ageMs)
    return Math.max(0, decayed - this.budget.spent)
  }

  isSuspended(): boolean { return this.suspended }
  isFrozen(): boolean { return this.frozen }

  /**
   * Reset budget — requires external oversight event.
   * epochStartMs MUST come from the oversight event's timestamp_ms.
   */
  reset(newBudget: number, epochStartMs: number): void {
    this.suspended = false
    this.frozen = false
    this.budget = Object.freeze({
      global_budget: newBudget,
      decay_lambda: this.budget.decay_lambda,
      epoch_start_ms: epochStartMs,
      spent: 0,
      round_number: 0,
      max_rounds: this.budget.max_rounds,
    })
  }

  freeze(): void { this.frozen = true }

  getBudgetSnapshot(): Readonly<RiskBudget> { return this.budget }

  private makeDecision(
    proposalId: string,
    componentId: string,
    accepted: boolean,
    lcb: number,
    eValue: number,
    sampleSize: number,
    riskSpent: number,
    rejectionReason: GateDecisionPayload['rejection_reason'],
    currentMs: number
  ): GateDecisionPayload {
    return Object.freeze({
      proposal_id: proposalId,
      component_id: componentId,
      lcb_value: lcb,
      e_value: eValue,
      delta_metric: lcb,
      sample_size: sampleSize,
      accepted,
      risk_spent: riskSpent,
      budget_remaining: this.currentBudget(currentMs),
      freeze_triggered: this.frozen,
      method: 'anytime_valid_bernstein' as const,
      ...(rejectionReason !== undefined ? { rejection_reason: rejectionReason } : {}),
    })
  }
}

function harmonicSum(n: number): number {
  let sum = 0
  for (let k = 1; k <= n; k++) sum += 1 / k
  return sum
}
