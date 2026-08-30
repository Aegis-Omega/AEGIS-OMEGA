// ============================================================
// Gate 199 — Multi-Model Constitutional Swarm Router Tests
// EPISTEMIC TIER: T2
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  ModelRegistry,
  buildSwarmTask,
  routeSwarmResponses,
  SwarmRouterError,
  SWARM_ROUTER_SCHEMA_VERSION,
  type ModelResponse,
} from '../../src/agents/coordination/swarm-router.js'
import { DEFAULT_QUORUM_THRESHOLD } from '../../src/consensus/swarm.js'
import type { SequenceNumber } from '../../src/core/types.js'

const seq = (n: number): SequenceNumber => BigInt(n) as SequenceNumber

// ─── ModelRegistry ────────────────────────────────────────

describe('ModelRegistry', () => {
  it('empty registry has size 0', () => {
    expect(ModelRegistry.empty().size).toBe(0)
  })

  it('register adds a model', () => {
    const reg = ModelRegistry.empty().register({
      model_id: 'qwen-plus', provider: 'dashscope',
      endpoint_url: 'https://dashscope.example.com', weight: 1000, is_active: true,
    })
    expect(reg.size).toBe(1)
    expect(reg.get('qwen-plus')?.provider).toBe('dashscope')
  })

  it('registry is immutable — original unchanged after register', () => {
    const r0 = ModelRegistry.empty()
    const r1 = r0.register({ model_id: 'qwen-plus', provider: 'dashscope', endpoint_url: '', weight: 1000, is_active: true })
    expect(r0.size).toBe(0)
    expect(r1.size).toBe(1)
  })

  it('activeModels returns only is_active=true entries', () => {
    const reg = ModelRegistry.empty()
      .register({ model_id: 'qwen-plus', provider: 'dashscope', endpoint_url: '', weight: 1000, is_active: true })
      .register({ model_id: 'old-model', provider: 'local', endpoint_url: '', weight: 0, is_active: false })
    expect(reg.activeModels().length).toBe(1)
    expect(reg.activeModels()[0]!.model_id).toBe('qwen-plus')
  })

  it('sorted iteration — BTreeMap order preserved', () => {
    const reg = ModelRegistry.empty()
      .register({ model_id: 'qwen-plus', provider: 'dashscope', endpoint_url: '', weight: 1000, is_active: true })
      .register({ model_id: 'claude-opus-4-7', provider: 'anthropic', endpoint_url: '', weight: 1000, is_active: true })
      .register({ model_id: 'deepseek-v3', provider: 'openai', endpoint_url: '', weight: 1000, is_active: true })
    const ids = reg.activeModels().map(m => m.model_id)
    expect(ids).toEqual([...ids].sort()) // must be alphabetical
  })
})

// ─── buildSwarmTask ───────────────────────────────────────

describe('buildSwarmTask', () => {
  it('produces a frozen task with 64-char hex task_id', async () => {
    const task = await buildSwarmTask(new TextEncoder().encode('test prompt'), seq(1))
    expect(task.task_id).toHaveLength(64)
    expect(task.prompt_hash).toHaveLength(64)
    expect(task.schema_version).toBe(SWARM_ROUTER_SCHEMA_VERSION)
    expect(task.is_replay_reconstructable).toBe(true)
    expect(() => { (task as { task_id: string }).task_id = 'hack' }).toThrow()
  })

  it('deterministic ×3 for same prompt + sequence', async () => {
    const make = () => buildSwarmTask(new TextEncoder().encode('hello'), seq(1))
    const [t1, t2, t3] = await Promise.all([make(), make(), make()])
    expect(t1!.task_id).toBe(t2!.task_id)
    expect(t2!.task_id).toBe(t3!.task_id)
  })

  it('different prompts → different task_id', async () => {
    const a = await buildSwarmTask(new TextEncoder().encode('prompt A'), seq(1))
    const b = await buildSwarmTask(new TextEncoder().encode('prompt B'), seq(1))
    expect(a.task_id).not.toBe(b.task_id)
  })

  it('different sequence → different task_id', async () => {
    const enc = new TextEncoder().encode('same')
    const a = await buildSwarmTask(enc, seq(1))
    const b = await buildSwarmTask(enc, seq(2))
    expect(a.task_id).not.toBe(b.task_id)
  })
})

// ─── routeSwarmResponses — quorum logic ───────────────────

describe('routeSwarmResponses', () => {
  const makeTask = () => buildSwarmTask(new TextEncoder().encode('route this'), seq(42))

  const fakeHash = (s: string) => s.padEnd(64, '0') as import('../../src/core/types.js').SHA256Hex

  it('throws SwarmRouterError on empty responses', async () => {
    const task = await makeTask()
    await expect(routeSwarmResponses(task, [])).rejects.toBeInstanceOf(SwarmRouterError)
  })

  it('throws on task_id mismatch', async () => {
    const task = await makeTask()
    const bad: ModelResponse = {
      model_id: 'qwen', response_hash: fakeHash('a'),
      task_id: fakeHash('wrong-task'), sequence: seq(42),
    }
    await expect(routeSwarmResponses(task, [bad])).rejects.toBeInstanceOf(SwarmRouterError)
  })

  it('throws on sequence mismatch', async () => {
    const task = await makeTask()
    const bad: ModelResponse = {
      model_id: 'qwen', response_hash: fakeHash('a'),
      task_id: task.task_id, sequence: seq(99),
    }
    await expect(routeSwarmResponses(task, [bad])).rejects.toBeInstanceOf(SwarmRouterError)
  })

  it('single model always reaches quorum', async () => {
    const task = await makeTask()
    const r: ModelResponse = { model_id: 'qwen', response_hash: fakeHash('resp'), task_id: task.task_id, sequence: task.sequence }
    const result = await routeSwarmResponses(task, [r])
    expect(result.quorum_reached).toBe(true)
    expect(result.consensus_response_hash).toBe(fakeHash('resp'))
  })

  it('5/8 identical responses → quorum reached (5/8 = 0.625 > 1/φ)', async () => {
    const task = await makeTask()
    const agree = fakeHash('agreed')
    const dissent = fakeHash('dissent')
    const responses: ModelResponse[] = [
      ...Array(5).fill(null).map((_, i) => ({ model_id: `m${i}`, response_hash: agree, task_id: task.task_id, sequence: task.sequence })),
      ...Array(3).fill(null).map((_, i) => ({ model_id: `n${i}`, response_hash: dissent, task_id: task.task_id, sequence: task.sequence })),
    ]
    const result = await routeSwarmResponses(task, responses)
    expect(result.quorum_reached).toBe(true)
    expect(result.consensus_response_hash).toBe(agree)
    expect(result.vote_count).toBe(5)
    expect(result.total_responses).toBe(8)
  })

  it('4/8 identical responses → no quorum (4/8 = 0.5 < 1/φ)', async () => {
    const task = await makeTask()
    const agree = fakeHash('majority')
    const responses: ModelResponse[] = [
      ...Array(4).fill(null).map((_, i) => ({ model_id: `m${i}`, response_hash: agree, task_id: task.task_id, sequence: task.sequence })),
      ...Array(4).fill(null).map((_, i) => ({ model_id: `n${i}`, response_hash: fakeHash(`other${i}`), task_id: task.task_id, sequence: task.sequence })),
    ]
    const result = await routeSwarmResponses(task, responses)
    expect(result.quorum_reached).toBe(false)
    expect(result.consensus_response_hash).toBeNull()
  })

  it('no quorum → consensus_response_hash is null', async () => {
    const task = await makeTask()
    // All different responses — no model agrees with another
    const responses: ModelResponse[] = Array(5).fill(null).map((_, i) => ({
      model_id: `m${i}`, response_hash: fakeHash(`unique${i}`), task_id: task.task_id, sequence: task.sequence,
    }))
    const result = await routeSwarmResponses(task, responses)
    expect(result.quorum_reached).toBe(false)
    expect(result.consensus_response_hash).toBeNull()
  })

  it('result is frozen — immutable after creation', async () => {
    const task = await makeTask()
    const r: ModelResponse = { model_id: 'qwen', response_hash: fakeHash('r'), task_id: task.task_id, sequence: task.sequence }
    const result = await routeSwarmResponses(task, [r])
    expect(() => { (result as { quorum_reached: boolean }).quorum_reached = false }).toThrow()
  })

  it('result_hash is 64-char hex', async () => {
    const task = await makeTask()
    const r: ModelResponse = { model_id: 'qwen', response_hash: fakeHash('x'), task_id: task.task_id, sequence: task.sequence }
    const result = await routeSwarmResponses(task, [r])
    expect(result.result_hash).toHaveLength(64)
  })

  it('deterministic ×3 — same responses produce same result_hash', async () => {
    const task = await makeTask()
    const responses: ModelResponse[] = [
      { model_id: 'qwen', response_hash: fakeHash('a'), task_id: task.task_id, sequence: task.sequence },
      { model_id: 'claude', response_hash: fakeHash('a'), task_id: task.task_id, sequence: task.sequence },
    ]
    const [r1, r2, r3] = await Promise.all([
      routeSwarmResponses(task, responses),
      routeSwarmResponses(task, responses),
      routeSwarmResponses(task, responses),
    ])
    expect(r1!.result_hash).toBe(r2!.result_hash)
    expect(r2!.result_hash).toBe(r3!.result_hash)
  })

  it('is_replay_reconstructable = true on all records', async () => {
    const task = await makeTask()
    const r: ModelResponse = { model_id: 'qwen', response_hash: fakeHash('y'), task_id: task.task_id, sequence: task.sequence }
    const result = await routeSwarmResponses(task, [r])
    expect(result.is_replay_reconstructable).toBe(true)
    expect(result.convergence.is_replay_reconstructable).toBe(true)
  })

  it('quorum_threshold matches DEFAULT_QUORUM_THRESHOLD = 1/φ', async () => {
    const task = await makeTask()
    const r: ModelResponse = { model_id: 'qwen', response_hash: fakeHash('z'), task_id: task.task_id, sequence: task.sequence }
    const result = await routeSwarmResponses(task, [r])
    expect(result.quorum_threshold).toBeCloseTo(DEFAULT_QUORUM_THRESHOLD)
  })

  it('schema_version is correct', async () => {
    const task = await makeTask()
    expect(task.schema_version).toBe('1.0.0')
  })

  it('SwarmRouterError is Error subclass', () => {
    expect(new SwarmRouterError('x')).toBeInstanceOf(Error)
    expect(new SwarmRouterError('x').name).toBe('SwarmRouterError')
  })
})

// ─── Holonic triad: 1/φ boundary ─────────────────────────
// The same 61/62 boundary that governs martingale entropy and
// swarm consensus also governs the swarm router.

describe('swarm router 1/φ holonic boundary', () => {
  it('62/100 > 1/φ → quorum reached', async () => {
    const task = await buildSwarmTask(new TextEncoder().encode('boundary'), seq(100))
    const agree = 'a'.repeat(64) as import('../../src/core/types.js').SHA256Hex
    const responses: ModelResponse[] = [
      ...Array(62).fill(null).map((_, i) => ({ model_id: `m${i}`, response_hash: agree, task_id: task.task_id, sequence: task.sequence })),
      ...Array(38).fill(null).map((_, i) => ({ model_id: `n${i}`, response_hash: 'b'.repeat(64) as import('../../src/core/types.js').SHA256Hex, task_id: task.task_id, sequence: task.sequence })),
    ]
    const result = await routeSwarmResponses(task, responses)
    expect(result.quorum_reached).toBe(true) // 62/100 = 0.62 > 0.6180...
  })

  it('61/100 < 1/φ → no quorum', async () => {
    const task = await buildSwarmTask(new TextEncoder().encode('boundary-low'), seq(101))
    const agree = 'c'.repeat(64) as import('../../src/core/types.js').SHA256Hex
    const responses: ModelResponse[] = [
      ...Array(61).fill(null).map((_, i) => ({ model_id: `m${i}`, response_hash: agree, task_id: task.task_id, sequence: task.sequence })),
      ...Array(39).fill(null).map((_, i) => ({ model_id: `n${i}`, response_hash: 'd'.repeat(64) as import('../../src/core/types.js').SHA256Hex, task_id: task.task_id, sequence: task.sequence })),
    ]
    const result = await routeSwarmResponses(task, responses)
    expect(result.quorum_reached).toBe(false) // 61/100 = 0.61 < 0.6180...
  })
})
