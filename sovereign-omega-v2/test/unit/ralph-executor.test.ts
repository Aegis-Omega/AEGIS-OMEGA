import { describe, it, expect } from 'vitest'
import { RalphExecutor, RalphExecutorError, RALPH_SCHEMA_VERSION } from '../../src/agents/executor/loop.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { FIBONACCI_CAP } from '../../src/agents/scheduler/fibonacci.js'

// ============================================================
// Gate 127 — RALPH Executor Tests
// Verifies: Fibonacci pacing, phase hash-chaining, immutable
// executor pattern, certify() chain validation.
// ============================================================

const CTX = 'a'.repeat(64) as SHA256Hex
const seq = (n: number) => BigInt(n) as SequenceNumber

describe('RALPH_SCHEMA_VERSION', () => {
  it('is 1.0.0', () => { expect(RALPH_SCHEMA_VERSION).toBe('1.0.0') })
})

describe('RalphExecutor.create', () => {
  it('starts with loopCount=0', () => {
    expect(RalphExecutor.create('agent-1').loopCount).toBe(0)
  })
  it('lastRecord is null on empty executor', () => {
    expect(RalphExecutor.create('agent-1').lastRecord).toBeNull()
  })
  it('throws RalphExecutorError for empty agent_id', () => {
    expect(() => RalphExecutor.create('')).toThrow(RalphExecutorError)
  })
})

describe('executeLoop — first loop', () => {
  it('loop_index=1, fibonacci_interval=1', async () => {
    const { record } = await RalphExecutor.create('a1').executeLoop(CTX, seq(1))
    expect(record.loop_index).toBe(1)
    expect(record.fibonacci_interval).toBe(1)
  })

  it('all five phase hashes are 64-char hex', async () => {
    const { record } = await RalphExecutor.create('a1').executeLoop(CTX, seq(1))
    expect(record.phase_read_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.phase_assess_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.phase_lock_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.phase_propagate_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.phase_harmonize_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('loop_hash is 64-char hex', async () => {
    const { record } = await RalphExecutor.create('a1').executeLoop(CTX, seq(1))
    expect(record.loop_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is_anchored=true', async () => {
    const { record } = await RalphExecutor.create('a1').executeLoop(CTX, seq(1))
    expect(record.is_anchored).toBe(true)
  })

  it('record is frozen', async () => {
    const { record } = await RalphExecutor.create('a1').executeLoop(CTX, seq(1))
    expect(Object.isFrozen(record)).toBe(true)
  })

  it('schema_version=1.0.0 and is_replay_reconstructable=true', async () => {
    const { record } = await RalphExecutor.create('a1').executeLoop(CTX, seq(1))
    expect(record.schema_version).toBe('1.0.0')
    expect(record.is_replay_reconstructable).toBe(true)
  })
})

describe('executeLoop — Fibonacci pacing sequence', () => {
  it('first 5 loops have intervals [1, 1, 2, 3, 5]', async () => {
    let ex = RalphExecutor.create('fib-5')
    const intervals: number[] = []
    for (let i = 0; i < 5; i++) {
      const { executor, record } = await ex.executeLoop(CTX, seq(i + 1))
      intervals.push(record.fibonacci_interval)
      ex = executor
    }
    expect(intervals).toEqual([1, 1, 2, 3, 5])
  })

  it('loop 11: fibonacci_interval=89 (F_11)', async () => {
    let ex = RalphExecutor.create('fib-11')
    let rec
    for (let i = 0; i < 11; i++) {
      const r = await ex.executeLoop(CTX, seq(i + 1))
      ex = r.executor
      rec = r.record
    }
    expect(rec?.fibonacci_interval).toBe(89)
  })

  it('loop 12: fibonacci_interval=89 (cap applied)', async () => {
    let ex = RalphExecutor.create('fib-cap')
    let rec
    for (let i = 0; i < 12; i++) {
      const r = await ex.executeLoop(CTX, seq(i + 1))
      ex = r.executor
      rec = r.record
    }
    expect(rec?.fibonacci_interval).toBe(FIBONACCI_CAP)
  })
})

describe('executeLoop — immutable pattern', () => {
  it('original executor is unchanged after executeLoop', async () => {
    const original = RalphExecutor.create('immut')
    await original.executeLoop(CTX, seq(1))
    expect(original.loopCount).toBe(0)
  })

  it('returned executor has loopCount+1', async () => {
    const { executor } = await RalphExecutor.create('count').executeLoop(CTX, seq(1))
    expect(executor.loopCount).toBe(1)
  })

  it('second loop has loop_index=2', async () => {
    const { executor: ex1 } = await RalphExecutor.create('chain').executeLoop(CTX, seq(1))
    const { record: r2 } = await ex1.executeLoop(CTX, seq(2))
    expect(r2.loop_index).toBe(2)
    expect(r2.agent_id).toBe('chain')
  })
})

describe('executeLoop — determinism', () => {
  it('same inputs → identical loop_hash ×3', async () => {
    const [r1, r2, r3] = await Promise.all([
      RalphExecutor.create('det').executeLoop(CTX, seq(1)),
      RalphExecutor.create('det').executeLoop(CTX, seq(1)),
      RalphExecutor.create('det').executeLoop(CTX, seq(1)),
    ])
    expect(r1.record.loop_hash).toBe(r2.record.loop_hash)
    expect(r2.record.loop_hash).toBe(r3.record.loop_hash)
  })

  it('different context_hash → different loop_hash', async () => {
    const ctxB = 'b'.repeat(64) as SHA256Hex
    const { record: r1 } = await RalphExecutor.create('diff').executeLoop(CTX, seq(1))
    const { record: r2 } = await RalphExecutor.create('diff').executeLoop(ctxB, seq(1))
    expect(r1.loop_hash).not.toBe(r2.loop_hash)
  })
})

describe('certify', () => {
  it('empty executor: loop_count=0, is_valid=true, terminal_hash=null', async () => {
    const cert = await RalphExecutor.create('empty').certify()
    expect(cert.loop_count).toBe(0)
    expect(cert.is_valid).toBe(true)
    expect(cert.terminal_hash).toBeNull()
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(cert.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('3-loop executor: terminal_hash = last loop_hash', async () => {
    let ex = RalphExecutor.create('cert-3')
    let lastHash = '' as SHA256Hex
    for (let i = 0; i < 3; i++) {
      const { executor, record } = await ex.executeLoop(CTX, seq(i + 1))
      ex = executor
      lastHash = record.loop_hash
    }
    const cert = await ex.certify()
    expect(cert.loop_count).toBe(3)
    expect(cert.is_valid).toBe(true)
    expect(cert.terminal_hash).toBe(lastHash)
  })

  it('certificate_hash is deterministic ×3', async () => {
    const [c1, c2, c3] = await Promise.all([
      RalphExecutor.create('det-cert').certify(),
      RalphExecutor.create('det-cert').certify(),
      RalphExecutor.create('det-cert').certify(),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})

describe('RalphExecutorError', () => {
  it('is an Error subclass with correct name', () => {
    const err = new RalphExecutorError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('RalphExecutorError')
  })
})
