// ============================================================
// Agent Coordinator — deterministic sequential scheduling
// EPISTEMIC TIER: T0 (replay-determinism is constitutional)
// NO nondeterministic parallel mutation. All coordination is
// sequential via monotonically increasing sequence numbers.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { CoordinationFrame } from '../types'
import { AgentCoordinationError } from '../types'

interface ScheduleSlot {
  readonly agent_id: string
  readonly sequence: number
  readonly priority: number
}

export class AgentCoordinator {
  private readonly _schedule: readonly ScheduleSlot[]
  private readonly _frames: readonly CoordinationFrame[]

  private constructor(
    schedule: readonly ScheduleSlot[],
    frames: readonly CoordinationFrame[]
  ) {
    this._schedule = schedule
    this._frames = frames
  }

  get frames(): readonly CoordinationFrame[] { return this._frames }
  get scheduleLength(): number { return this._schedule.length }

  scheduleAgent(agent_id: string, sequence: number, priority = 0): AgentCoordinator {
    const slot: ScheduleSlot = deepFreeze({ agent_id, sequence, priority })
    return new AgentCoordinator(
      deepFreeze([...this._schedule, slot]),
      this._frames
    )
  }

  // Pure function: lowest sequence first, then lowest priority. Deterministic.
  nextAgent(atSequence: number): string | undefined {
    const eligible = this._schedule.filter(s => s.sequence <= atSequence)
    if (eligible.length === 0) return undefined
    const sorted = [...eligible].sort((a, b) =>
      a.sequence !== b.sequence ? a.sequence - b.sequence : a.priority - b.priority
    )
    return sorted[0]?.agent_id
  }

  recordFrame(frame: CoordinationFrame): AgentCoordinator {
    if (this._frames.length > 0) {
      const last = this._frames[this._frames.length - 1]
      if (last !== undefined && frame.sequence <= last.sequence) {
        throw new AgentCoordinationError(
          `Frame sequence ${frame.sequence} not strictly after ${last.sequence}`
        )
      }
    }
    return new AgentCoordinator(
      this._schedule,
      deepFreeze([...this._frames, deepFreeze(frame)])
    )
  }

  verifyDeterminism(): boolean {
    for (let i = 1; i < this._frames.length; i++) {
      const curr = this._frames[i]
      const prev = this._frames[i - 1]
      /* c8 ignore next -- noUncheckedIndexedAccess artifact; recordFrame() validates monotonicity so this is never true */
      if (curr !== undefined && prev !== undefined && curr.sequence <= prev.sequence) {
        return false
      }
    }
    return true
  }

  coordinationStability(): number {
    if (this._frames.length === 0) return 1
    let monotonic = 0
    for (let i = 1; i < this._frames.length; i++) {
      const curr = this._frames[i]
      const prev = this._frames[i - 1]
      /* c8 ignore next -- same as above; frames are always monotonic */
      if (curr !== undefined && prev !== undefined && curr.sequence > prev.sequence) monotonic++
    }
    return this._frames.length <= 1 ? 1 : monotonic / (this._frames.length - 1)
  }

  static empty(): AgentCoordinator {
    return new AgentCoordinator(deepFreeze([]), deepFreeze([]))
  }
}

export function createAgentCoordinator(): AgentCoordinator {
  return AgentCoordinator.empty()
}
