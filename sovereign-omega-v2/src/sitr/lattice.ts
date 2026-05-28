// ============================================================
// SITR Escalation Lattice — pure monotonic state ordering
// EPISTEMIC TIER: T0 (monotonic escalation is constitutional)
// No randomness. No wall-clock. All transitions deterministic.
// ============================================================

import type { SITRState } from './types.js'

export const SITR_ESCALATION_ORDER: readonly SITRState[] = Object.freeze([
  'STABLE',
  'DEGRADED',
  'UNSTABLE',
  'CONSTITUTIONAL_RISK',
  'CONTAINED',
  'COMPROMISED',
])

export function stateOrdinal(s: SITRState): number {
  const idx = SITR_ESCALATION_ORDER.indexOf(s)
  /* c8 ignore next -- TypeScript ensures s is always in SITR_ESCALATION_ORDER; idx === -1 is unreachable */
  return idx === -1 ? 0 : idx
}

// Only monotonic escalation is permitted. No de-escalation.
export function canEscalateTo(current: SITRState, next: SITRState): boolean {
  return stateOrdinal(next) > stateOrdinal(current)
}

// Returns the higher of current or the state implied by the trigger.
export function escalate(current: SITRState, next: SITRState): SITRState {
  return stateOrdinal(next) > stateOrdinal(current) ? next : current
}

// COMPROMISED is terminal — no further escalation paths.
export function isTerminalState(s: SITRState): boolean {
  return s === 'COMPROMISED'
}

// -1 if a < b, 0 if equal, 1 if a > b
export function compareStates(a: SITRState, b: SITRState): number {
  const diff = stateOrdinal(a) - stateOrdinal(b)
  return diff < 0 ? -1 : diff > 0 ? 1 : 0
}
