// ============================================================
// AOIE Freeze Helpers — typed deepFreeze wrappers
// EPISTEMIC TIER: T1
// Typed wrappers clarify intent: AOIE outputs are always frozen.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { AOIEClassification, RuntimeSnapshot } from './types.js'

export function freezeClassification(c: AOIEClassification): Readonly<AOIEClassification> {
  return deepFreeze(c)
}

export function freezeSnapshot(s: RuntimeSnapshot): Readonly<RuntimeSnapshot> {
  return deepFreeze({ ...s, panel_sequence_numbers: deepFreeze([...s.panel_sequence_numbers]) })
}
