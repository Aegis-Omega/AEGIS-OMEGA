// ============================================================
// SOVEREIGN OMEGA — Gate Type Re-exports
// ============================================================
// Gate types are defined in src/core/types.ts.
// This module re-exports them for ergonomic imports within
// the gate module without crossing architectural boundaries.

export type {
  GateDecisionPayload,
  RiskBudget,
  BoundedDelta,
  CapacityDeclaration,
  MutationOperatorMetadata,
} from '../core/types.js'

export { normalizeDelta, assertBoundedDelta } from '../core/types.js'
