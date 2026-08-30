// ============================================================
// Agent Memory — append-only replay-reconstructable memory
// EPISTEMIC TIER: T0 (append-only invariant is constitutional)
// Pattern: identical to MutationLedger.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { AgentMemoryEntry } from '../types'
import { AgentCoordinationError } from '../types'

export class AgentMemory {
  private readonly _entries: readonly AgentMemoryEntry[]

  private constructor(entries: readonly AgentMemoryEntry[]) {
    this._entries = entries
  }

  static empty(): AgentMemory {
    return new AgentMemory(deepFreeze([]))
  }

  get entries(): readonly AgentMemoryEntry[] { return this._entries }
  get length(): number { return this._entries.length }

  store(entry: AgentMemoryEntry): AgentMemory {
    if (this._entries.length > 0) {
      const last = this._entries[this._entries.length - 1]
      if (last !== undefined && entry.sequence <= last.sequence) {
        throw new AgentCoordinationError(
          `Memory entry sequence ${entry.sequence} not strictly after ${last.sequence}`
        )
      }
    }
    return new AgentMemory(deepFreeze([...this._entries, deepFreeze(entry)]))
  }

  recall(agent_id: string, memory_type?: string): readonly AgentMemoryEntry[] {
    return this._entries.filter(
      e => e.agent_id === agent_id && (memory_type === undefined || e.memory_type === memory_type)
    )
  }

  // Fraction of entries that are replay-reconstructable.
  verifyReplayCompleteness(): number {
    if (this._entries.length === 0) return 1
    const reconstructable = this._entries.filter(e => e.is_replay_reconstructable).length
    return reconstructable / this._entries.length
  }
}
