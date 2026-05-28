// ============================================================
// Agent Coordinator Extended Tests — agents/coordination/AgentCoordinator.ts
// Targets uncovered branches:
//   nextAgent: non-empty schedule but no agent eligible at sequence
//   coordinationStability: 1 frame (length <= 1 → returns 1)
//   coordinationStability: 2+ frames (length > 1 → computes ratio)
// ============================================================

import { describe, it, expect } from 'vitest'
import { createAgentCoordinator } from '../../src/agents/coordination/AgentCoordinator.js'
import type { CoordinationFrame } from '../../src/agents/types.js'
function makeFrame(seq: number): CoordinationFrame {
  return {
    frame_id: `frame-${seq}`,
    sequence: seq,
    agent_id: `agent-${seq}`,
    action_type: 'READ',
    mutation_ids: [],
    replay_safe: true,
  }
}

// ─── nextAgent: eligible filter returns empty ─────────────

describe('nextAgent: non-empty schedule but sequence not yet reached', () => {
  it('returns undefined when all scheduled agents have sequence > atSequence', () => {
    const c = createAgentCoordinator()
      .scheduleAgent('agent-future', 100, 0)
    expect(c.nextAgent(5)).toBeUndefined()
  })

  it('returns agent when at least one has sequence <= atSequence', () => {
    const c = createAgentCoordinator()
      .scheduleAgent('agent-future', 100, 0)
      .scheduleAgent('agent-now', 3, 0)
    expect(c.nextAgent(5)).toBe('agent-now')
  })
})

// ─── coordinationStability: 1 frame ──────────────────────

describe('coordinationStability: single frame', () => {
  it('returns 1 with exactly 1 frame (length <= 1 branch)', () => {
    const c = createAgentCoordinator()
      .recordFrame(makeFrame(1))
    expect(c.coordinationStability()).toBe(1)
  })
})

// ─── coordinationStability: 2+ frames ────────────────────

describe('coordinationStability: multiple frames', () => {
  it('returns 1.0 for two strictly monotonic frames', () => {
    const c = createAgentCoordinator()
      .recordFrame(makeFrame(1))
      .recordFrame(makeFrame(2))
    expect(c.coordinationStability()).toBe(1)
  })

  it('returns 1.0 for three strictly monotonic frames', () => {
    const c = createAgentCoordinator()
      .recordFrame(makeFrame(1))
      .recordFrame(makeFrame(2))
      .recordFrame(makeFrame(10))
    expect(c.coordinationStability()).toBe(1)
  })

  it('coordinationStability denominator = frames.length - 1', () => {
    // 4 frames, all monotonic → 3 monotonic pairs / 3 = 1.0
    const c = createAgentCoordinator()
      .recordFrame(makeFrame(1))
      .recordFrame(makeFrame(2))
      .recordFrame(makeFrame(3))
      .recordFrame(makeFrame(4))
    expect(c.coordinationStability()).toBeCloseTo(1.0, 6)
  })

  it('scheduleLength reflects all scheduled agents', () => {
    const c = createAgentCoordinator()
      .scheduleAgent('a1', 1)
      .scheduleAgent('a2', 2)
      .scheduleAgent('a3', 3)
    expect(c.scheduleLength).toBe(3)
  })
})

// ─── verifyDeterminism: with valid frames ─────────────────

describe('verifyDeterminism: frames added via public API always pass', () => {
  it('verifyDeterminism returns true with 3 monotonic frames', () => {
    const c = createAgentCoordinator()
      .recordFrame(makeFrame(1))
      .recordFrame(makeFrame(5))
      .recordFrame(makeFrame(10))
    expect(c.verifyDeterminism()).toBe(true)
  })

  it('empty coordinator verifyDeterminism = true', () => {
    expect(createAgentCoordinator().verifyDeterminism()).toBe(true)
  })
})
