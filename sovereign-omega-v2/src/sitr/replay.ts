// ============================================================
// SITR Replay Violation Log — permanent append-only record
// EPISTEMIC TIER: T0 (replay violations are irreversible once recorded)
// Once a violation is recorded it cannot be removed or amended.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { ReplayViolation } from './types.js'

export class ReplayViolationLog {
  private readonly _violations: readonly ReplayViolation[]

  private constructor(violations: readonly ReplayViolation[]) {
    this._violations = violations
  }

  static empty(): ReplayViolationLog {
    return new ReplayViolationLog(deepFreeze([]))
  }

  get violationCount(): number { return this._violations.length }

  getAll(): readonly ReplayViolation[] { return this._violations }

  hasViolations(): boolean { return this._violations.length > 0 }

  record(v: ReplayViolation): ReplayViolationLog {
    return new ReplayViolationLog(deepFreeze([...this._violations, deepFreeze(v)]))
  }
}
