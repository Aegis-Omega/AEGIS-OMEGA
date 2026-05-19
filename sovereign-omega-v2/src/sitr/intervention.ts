// ============================================================
// SITR Intervention Log — append-only monotonic record
// EPISTEMIC TIER: T0 (append-only invariant is constitutional)
// Pattern: identical to AgentMemory / MutationLedger.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { InterventionRecord } from './types.js'
import { SITRConstraintError } from './types.js'

export class InterventionLog {
  private readonly _records: readonly InterventionRecord[]

  private constructor(records: readonly InterventionRecord[]) {
    this._records = records
  }

  static empty(): InterventionLog {
    return new InterventionLog(deepFreeze([]))
  }

  get length(): number { return this._records.length }
  getAll(): readonly InterventionRecord[] { return this._records }

  append(record: InterventionRecord): InterventionLog {
    if (this._records.length > 0) {
      const last = this._records[this._records.length - 1]
      if (last !== undefined && record.sequence <= last.sequence) {
        throw new SITRConstraintError(
          `Intervention sequence ${record.sequence} not strictly after ${last.sequence}`
        )
      }
    }
    return new InterventionLog(deepFreeze([...this._records, deepFreeze(record)]))
  }
}
