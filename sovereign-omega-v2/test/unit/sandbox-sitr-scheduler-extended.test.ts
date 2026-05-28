// ============================================================
// Sandbox + SITR + Scheduler Extended Tests
// Targets:
//   sandbox/sandbox.ts: is_isolated=false throw, entropy exceeded throw,
//     computeSandboxEntropyRatio with zero budget
//   sitr/orchestration.ts: anomalyToRequiredState medium/low arms
//   agents/scheduler/scheduler.ts: active-status agent filter
// ============================================================

import { describe, it, expect } from 'vitest'

// ─── Sandbox ─────────────────────────────────────────────────

import {
  createSandbox,
  checkSandboxAllows,
  computeSandboxEntropyRatio,
} from '../../src/extensions/sandbox/sandbox.js'
import { SandboxViolationError } from '../../src/extensions/types.js'

const FIXED_SCALE = 65536

describe('checkSandboxAllows: is_isolated=false throws', () => {
  it('throws SandboxViolationError when is_isolated is false', () => {
    const sb = createSandbox({
      plugin_id: 'test-plugin',
      allowed_capability_ids: ['cap-a'],
      allowed_paths: ['/workspace'],
      entropy_budget_fixed: 100 * FIXED_SCALE,
      max_mutation_count: 10,
    })
    // Manually override is_isolated (using spread to simulate a non-isolated sandbox)
    const nonIsolated = Object.freeze({ ...sb, is_isolated: false })
    expect(() => checkSandboxAllows(nonIsolated, 'cap-a', '/workspace/file')).toThrow(SandboxViolationError)
    expect(() => checkSandboxAllows(nonIsolated, 'cap-a', '/workspace/file')).toThrow(/not isolated/)
  })
})

describe('checkSandboxAllows: entropy budget exceeded throws', () => {
  it('throws SandboxViolationError when entropy_used >= entropy_budget', () => {
    const sb = createSandbox({
      plugin_id: 'test-plugin',
      allowed_capability_ids: ['cap-a'],
      allowed_paths: ['/workspace'],
      entropy_budget_fixed: 10 * FIXED_SCALE,
      max_mutation_count: 100,
    })
    // Create a sandbox where entropy is fully used
    const exhausted = Object.freeze({
      ...sb,
      entropy_used_fixed: 10 * FIXED_SCALE,  // === entropy_budget_fixed
    })
    expect(() => checkSandboxAllows(exhausted, 'cap-a', '/workspace/file')).toThrow(SandboxViolationError)
    expect(() => checkSandboxAllows(exhausted, 'cap-a', '/workspace/file')).toThrow(/entropy budget/)
  })
})

describe('computeSandboxEntropyRatio: zero entropy budget returns 0', () => {
  it('returns 0 when entropy_budget_fixed is 0', () => {
    const sb = createSandbox({
      plugin_id: 'p',
      allowed_capability_ids: [],
      allowed_paths: [],
      entropy_budget_fixed: 0,
      max_mutation_count: 0,
    })
    expect(computeSandboxEntropyRatio(sb)).toBe(0)
  })
})

// ─── SITR Orchestration ───────────────────────────────────────

import { anomalyToRequiredState } from '../../src/sitr/orchestration.js'
import type { OrchestrationAnomaly } from '../../src/sitr/types.js'

function makeAnomaly(severity: OrchestrationAnomaly['severity']): OrchestrationAnomaly {
  return Object.freeze({
    anomaly_id: `anm-${severity}-1`,
    sequence: 1,
    anomaly_type: 'non_replay_safe_frame',
    affected_agent_id: 'agent-1',
    severity,
  })
}

describe('anomalyToRequiredState: all severity arms', () => {
  it('medium severity → DEGRADED', () => {
    expect(anomalyToRequiredState(makeAnomaly('medium'))).toBe('DEGRADED')
  })

  it('low severity → STABLE', () => {
    expect(anomalyToRequiredState(makeAnomaly('low'))).toBe('STABLE')
  })

  it('high severity → UNSTABLE (sanity check)', () => {
    expect(anomalyToRequiredState(makeAnomaly('high'))).toBe('UNSTABLE')
  })
})

// ─── Agent Scheduler ─────────────────────────────────────────

import { buildSchedule } from '../../src/agents/scheduler/scheduler.js'
import { AGENT_MANIFEST_SCHEMA_VERSION } from '../../src/agents/types.js'
import type { AgentManifest } from '../../src/agents/types.js'
import { EpistemicTier } from '../../src/core/types.js'

function makeAgent(
  agent_id: string,
  agent_type: AgentManifest['agent_type'],
  status: AgentManifest['status'] = 'registered'
): AgentManifest {
  return Object.freeze({
    schema_version: AGENT_MANIFEST_SCHEMA_VERSION,
    agent_id,
    name: `Agent ${agent_id}`,
    agent_type,
    epistemic_tier: EpistemicTier.T2,
    capability_manifest: Object.freeze({
      capability_ids: [],
      invariant_bindings: [],
      telemetry_schema_version: '1.0.0',
    }),
    is_replay_safe: true,
    entropy_budget_fixed: 0,
    workspace_boundary: [],
    status,
  })
}

describe('buildSchedule: active-status agents are included', () => {
  it('includes agents with status=active (right arm of || filter)', () => {
    const agents = [
      makeAgent('a1', 'ResearchAgent', 'active'),
      makeAgent('a2', 'ResearchAgent', 'registered'),
    ]
    const schedule = buildSchedule(agents, 0)
    expect(schedule).toHaveLength(2)
  })

  it('excludes agents with status=suspended', () => {
    const agents = [
      makeAgent('a1', 'ResearchAgent', 'suspended'),
      makeAgent('a2', 'ResearchAgent', 'registered'),
    ]
    const schedule = buildSchedule(agents, 0)
    expect(schedule).toHaveLength(1)
    expect(schedule[0]?.agent_id).toBe('a2')
  })

  it('only active agents: all-active list produces a full schedule', () => {
    const agents = [
      makeAgent('b1', 'DocumentationAgent', 'active'),
      makeAgent('b2', 'DocumentationAgent', 'active'),
      makeAgent('b3', 'DocumentationAgent', 'active'),
    ]
    const schedule = buildSchedule(agents, 10)
    expect(schedule).toHaveLength(3)
  })
})

describe('buildSchedule: same agent_type sort by agent_id', () => {
  it('sorts by agent_id when types are equal (covers agent_id comparison arms)', () => {
    const agents = [
      makeAgent('z-agent', 'ResearchAgent', 'registered'),
      makeAgent('a-agent', 'ResearchAgent', 'registered'),
    ]
    const schedule = buildSchedule(agents, 0)
    expect(schedule[0]?.agent_id).toBe('a-agent')
    expect(schedule[1]?.agent_id).toBe('z-agent')
  })
})
