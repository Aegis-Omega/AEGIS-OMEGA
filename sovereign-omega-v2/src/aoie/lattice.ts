// ============================================================
// AOIE Classification Lattice — global state composition
// EPISTEMIC TIER: T1
// Pure functions. Monotonic severity ordering.
// COMPROMISED > ALERT > SECURE.
// ============================================================

import type {
  GlobalState, ArbitrationState, IdentityContinuityState, ConstitutionalDriftState,
} from './types.js'

export const AOIE_SEVERITY_ORDER: readonly GlobalState[] = Object.freeze([
  'SECURE',
  'ALERT',
  'COMPROMISED',
])

export function globalStateOrdinal(s: GlobalState): number {
  return AOIE_SEVERITY_ORDER.indexOf(s)
}

export function compareGlobalStates(a: GlobalState, b: GlobalState): number {
  const diff = globalStateOrdinal(a) - globalStateOrdinal(b)
  return diff < 0 ? -1 : diff > 0 ? 1 : 0
}

export function classifyGlobalState(
  arbitration: ArbitrationState,
  identity: IdentityContinuityState,
  drift: ConstitutionalDriftState
): GlobalState {
  if (arbitration === 'DEADLOCKED' || identity === 'BROKEN' || drift === 'DIVERGED') {
    return 'COMPROMISED'
  }
  if (arbitration === 'CONTESTED' || identity === 'DRIFTED' || drift === 'DRIFTING') {
    return 'ALERT'
  }
  return 'SECURE'
}
