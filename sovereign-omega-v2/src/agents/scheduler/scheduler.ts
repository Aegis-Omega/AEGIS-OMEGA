// ============================================================
// Agent Scheduler — pure deterministic scheduling functions
// EPISTEMIC TIER: T1
// All scheduling is sequence-based. No Date.now(). No randomness.
// Identical inputs ALWAYS produce identical schedules.
// ============================================================

import type { AgentManifest } from '../types.js'
import { cumulativeFibonacci } from './fibonacci.js'

export interface ScheduleEntry {
  readonly agent_id: string
  readonly sequence: number
  readonly priority: number
}

// Deterministic: sorts by agent_type then agent_id, assigns sequences from startSequence.
// Running this 3× with the same inputs produces byte-identical results.
export function buildSchedule(
  agents: readonly AgentManifest[],
  startSequence: number
): readonly ScheduleEntry[] {
  const active = agents.filter(a => a.status === 'registered' || a.status === 'active')
  const sorted = [...active].sort((a, b) => {
    if (a.agent_type < b.agent_type) return -1
    if (a.agent_type > b.agent_type) return 1
    if (a.agent_id < b.agent_id) return -1
    return 1  // agent_ids are unique; equal type+id is impossible
  })
  const offsets = cumulativeFibonacci(sorted.length)
  return Object.freeze(
    sorted.map((agent, idx) =>
      Object.freeze({
        agent_id: agent.agent_id,
        /* c8 ignore next -- noUncheckedIndexedAccess artifact; cumulativeFibonacci guarantees length === sorted.length */
        sequence: startSequence + (offsets[idx] ?? 0),
        priority: idx,
      })
    )
  )
}

// Fraction of schedule entries whose sequence is > currentSequence (not yet executed).
export function computeSchedulePressure(
  schedule: readonly ScheduleEntry[],
  currentSequence: number
): number {
  if (schedule.length === 0) return 0
  const pending = schedule.filter(e => e.sequence > currentSequence).length
  return Math.min(1, pending / schedule.length)
}
