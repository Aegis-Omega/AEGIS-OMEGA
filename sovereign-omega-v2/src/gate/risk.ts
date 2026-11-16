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
   * The gate accepts when LCB > 0, an independently anytime-valid e-process
   * crosses its per-round 1/deltaAlpha threshold, and budget/K permit.
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

    // Harmonic error allocation is over *tested proposals*, not only
    // accepted proposals. Otherwise rejected independent null tests reuse
    // alpha_1 without limit, violating any claimed family-wise risk bound.
    if (
      !Number.isSafeInteger(this.budget.max_rounds) ||
      this.budget.max_rounds <= 0 ||
      this.budget.round_number >= this.budget.max_rounds
    ) {
      this.suspended = true
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

    // Invalid measurements or alpha cannot create valid statistical evidence.
    // Fail closed *before* normalizing, so Infinity is never clamped to +1.
    if (
      samples.length === 0 ||
      samples.some(s => !Number.isFinite(s))
    ) {
      return this.makeDecision(
        proposalId, componentId, false, 0, 0, samples.length, 0,
        'VERIFIER_INTEGRITY', currentMs
      )
    }
    if (!Number.isFinite(deltaAlpha) || deltaAlpha <= 0 || deltaAlpha >= 1) {
      return this.makeDecision(
        proposalId, componentId, false, 0, 0, samples.length, 0,
        'BUDGET_EXHAUSTED', currentMs
      )
    }

    // Compute Bernstein LCB and e-value
    const seq = new ConfidenceSequence(deltaAlpha)
    for (const s of samples) {
      seq.update(normalizeDelta(s) as BoundedDelta)
    }
    const lcb = seq.lcb()
    const eValue = seq.eValue()

    // The pointwise empirical-Bernstein half-width in ConfidenceSequence.lcb()
    // is not itself an anytime-valid confidence sequence. Keep the legacy
    // LCB > 0 requirement, but it cannot alone authorize sequential mutation.
    // Under bounded, conditionally mean-nonpositive deltas, the predictable
    // nonnegative betting process provides Ville's anytime-valid test.
    const lcbPass = Number.isFinite(lcb) && lcb > 0
    const eThreshold = 1 / deltaAlpha
    const evidencePass = Number.isFinite(eValue)
      && Number.isFinite(eThreshold)
      && eValue >= eThreshold
    const accepted = lcbPass && evidencePass

    // One error-budget slot is consumed by every statistically evaluated
    // candidate, including failed candidates. Only confirmed modifications
    // consume the separate "spent" monetary-like risk reservoir.
    this.budget = Object.freeze({
      ...this.budget,
      spent: this.budget.spent + (accepted ? deltaAlpha : 0),
      round_number: k,
    })
    if (
      this.budget.round_number >= this.budget.max_rounds ||
      this.currentBudget(currentMs) < BUDGET_SUSPEND_FLOOR
    ) {
      this.suspended = true
    }

    return this.makeDecision(
      proposalId, componentId, accepted,
      Number.isFinite(lcb) ? lcb : 0,
      Number.isFinite(eValue) ? eValue : 0,
      samples.length, accepted ? deltaAlpha : 0,
      accepted ? undefined : (!lcbPass ? 'LCB_FAIL' : 'E_VALUE_FAIL'), currentMs
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
