// ============================================================
// Gate 28 — SHP Transition Certifier (Replay DFA) Tests
// ~28 tests: transition validity, LOCK boundary, hash chaining,
//   error cases, certifyExecution, determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  initialMachine,
  transition,
  certifyExecution,
  SHPExecutionError,
  type SHPTransitionMachine,
  type FrameTransitionRecord,
} from '../../src/frame/dfa.js'

// ─── Helpers ───────────────────────────────────────────────

const SEQ = 1n as SequenceNumber
const H0 = '0'.repeat(64) as SHA256Hex
const H1 = '1'.repeat(64) as SHA256Hex
const H2 = '2'.repeat(64) as SHA256Hex
const H3 = '3'.repeat(64) as SHA256Hex
const H4 = '4'.repeat(64) as SHA256Hex

/** Execute all 5 transitions in order. Returns [records, final machine]. */
async function fullTrace(seq: SequenceNumber = SEQ): Promise<[FrameTransitionRecord[], SHPTransitionMachine]> {
  let m = initialMachine(seq)
  const records: FrameTransitionRecord[] = []
  const stateHashes = [H0, H1, H2, H3, H4]
  const phases = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const
  for (let i = 0; i < phases.length; i++) {
    const { machine, record } = await transition(m, phases[i]!, stateHashes[i]!)
    records.push(record)
    m = machine
  }
  return [records, m]
}

// ─── initialMachine ────────────────────────────────────────

describe('initialMachine', () => {
  it('starts in IDLE phase', () => {
    const m = initialMachine(SEQ)
    expect(m.current_phase).toBe('IDLE')
  })

  it('has null last_transition_hash', () => {
    const m = initialMachine(SEQ)
    expect(m.last_transition_hash).toBeNull()
  })

  it('step_count is 0', () => {
    const m = initialMachine(SEQ)
    expect(m.step_count).toBe(0)
  })

  it('is frozen', () => {
    expect(Object.isFrozen(initialMachine(SEQ))).toBe(true)
  })
})

// ─── Valid transitions ─────────────────────────────────────

describe('transition — valid sequence', () => {
  it('IDLE → READ succeeds', async () => {
    const m = initialMachine(SEQ)
    const { machine, record } = await transition(m, 'READ', H0)
    expect(machine.current_phase).toBe('READ')
    expect(machine.step_count).toBe(1)
    expect(record.from_phase).toBe('IDLE')
    expect(record.to_phase).toBe('READ')
  })

  it('full R→A→L→P→H sequence completes without error', async () => {
    const [records, final] = await fullTrace()
    expect(records).toHaveLength(5)
    expect(final.current_phase).toBe('HARMONIZE')
    expect(final.step_count).toBe(5)
  })

  it('each record is frozen', async () => {
    const [records] = await fullTrace()
    for (const rec of records) {
      expect(Object.isFrozen(rec)).toBe(true)
    }
  })

  it('each machine snapshot is frozen', async () => {
    let m = initialMachine(SEQ)
    const { machine } = await transition(m, 'READ', H0)
    expect(Object.isFrozen(machine)).toBe(true)
  })

  it('transition_hash is 64-char hex', async () => {
    const m = initialMachine(SEQ)
    const { record } = await transition(m, 'READ', H0)
    expect(record.transition_hash).toHaveLength(64)
    expect(/^[0-9a-f]{64}$/.test(record.transition_hash)).toBe(true)
  })

  it('is_replay_reconstructable is true on all records', async () => {
    const [records] = await fullTrace()
    for (const rec of records) {
      expect(rec.is_replay_reconstructable).toBe(true)
    }
  })
})

// ─── Invalid transitions ───────────────────────────────────

describe('transition — invalid transitions throw SHPExecutionError', () => {
  it('IDLE → ASSESS (skip READ) throws', async () => {
    const m = initialMachine(SEQ)
    await expect(transition(m, 'ASSESS', H0)).rejects.toThrow(SHPExecutionError)
  })

  it('IDLE → LOCK (skip READ+ASSESS) throws', async () => {
    const m = initialMachine(SEQ)
    await expect(transition(m, 'LOCK', H0)).rejects.toThrow(SHPExecutionError)
  })

  it('READ → LOCK (skip ASSESS) throws', async () => {
    const m = initialMachine(SEQ)
    const { machine: m1 } = await transition(m, 'READ', H0)
    await expect(transition(m1, 'LOCK', H1)).rejects.toThrow(SHPExecutionError)
  })

  it('LOCK → ASSESS (reversal) throws — LOCK is irreversible', async () => {
    let m = initialMachine(SEQ)
    const phases = ['READ', 'ASSESS', 'LOCK'] as const
    for (const phase of phases) {
      const result = await transition(m, phase, H0)
      m = result.machine
    }
    await expect(transition(m, 'ASSESS', H0)).rejects.toThrow(SHPExecutionError)
  })

  it('HARMONIZE → READ (repeat cycle without reset) throws', async () => {
    const [, final] = await fullTrace()
    await expect(transition(final, 'READ', H0)).rejects.toThrow(SHPExecutionError)
  })

  it('error message identifies invalid transition', async () => {
    const m = initialMachine(SEQ)
    const err = await transition(m, 'HARMONIZE', H0).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(SHPExecutionError)
    expect((err as Error).message).toContain('IDLE')
    expect((err as Error).message).toContain('HARMONIZE')
  })
})

// ─── Hash chaining ─────────────────────────────────────────

describe('transition_hash chaining', () => {
  it('transition_hash changes with each phase', async () => {
    const [records] = await fullTrace()
    const hashes = records.map(r => r.transition_hash)
    const unique = new Set(hashes)
    expect(unique.size).toBe(5)
  })

  it('last_transition_hash on machine matches record transition_hash', async () => {
    let m = initialMachine(SEQ)
    const { machine, record } = await transition(m, 'READ', H0)
    expect(machine.last_transition_hash).toBe(record.transition_hash)
  })

  it('transition_hash is deterministic — same inputs → same hash × 3', async () => {
    const m = initialMachine(SEQ)
    const h1 = (await transition(m, 'READ', H0)).record.transition_hash
    const h2 = (await transition(m, 'READ', H0)).record.transition_hash
    const h3 = (await transition(m, 'READ', H0)).record.transition_hash
    expect(h1).toBe(h2)
    expect(h2).toBe(h3)
  })

  it('different state_hash → different transition_hash', async () => {
    const m = initialMachine(SEQ)
    const { record: r1 } = await transition(m, 'READ', H0)
    const { record: r2 } = await transition(m, 'READ', H1)
    expect(r1.transition_hash).not.toBe(r2.transition_hash)
  })

  it('different sequence → different transition_hash', async () => {
    const m1 = initialMachine(1n as SequenceNumber)
    const m2 = initialMachine(2n as SequenceNumber)
    const { record: r1 } = await transition(m1, 'READ', H0)
    const { record: r2 } = await transition(m2, 'READ', H0)
    expect(r1.transition_hash).not.toBe(r2.transition_hash)
  })
})

// ─── certifyExecution ──────────────────────────────────────

describe('certifyExecution', () => {
  it('valid full trace → is_valid: true', async () => {
    const [records] = await fullTrace()
    const cert = await certifyExecution(records, SEQ)
    expect(cert.is_valid).toBe(true)
    expect(cert.step_count).toBe(5)
    expect(cert.certificate_hash).toHaveLength(64)
    expect(cert.is_replay_reconstructable).toBe(true)
  })

  it('certificate is frozen', async () => {
    const [records] = await fullTrace()
    const cert = await certifyExecution(records, SEQ)
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('certificate_hash is deterministic × 3', async () => {
    const [records] = await fullTrace()
    const c1 = await certifyExecution(records, SEQ)
    const c2 = await certifyExecution(records, SEQ)
    const c3 = await certifyExecution(records, SEQ)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('empty records → is_valid: false', async () => {
    const cert = await certifyExecution([], SEQ)
    expect(cert.is_valid).toBe(false)
  })

  it('partial trace (4 steps) → is_valid: false', async () => {
    const [records] = await fullTrace()
    const cert = await certifyExecution(records.slice(0, 4), SEQ)
    expect(cert.is_valid).toBe(false)
    expect(cert.step_count).toBe(4)
  })

  it('tampered transition_hash → is_valid: false', async () => {
    const [records] = await fullTrace()
    const tampered = [
      ...records.slice(0, 2),
      Object.freeze({ ...records[2]!, transition_hash: H3 }),
      ...records.slice(3),
    ]
    const cert = await certifyExecution(tampered, SEQ)
    expect(cert.is_valid).toBe(false)
  })

  it('different sequence produces different certificate_hash', async () => {
    const [r1] = await fullTrace(1n as SequenceNumber)
    const [r2] = await fullTrace(2n as SequenceNumber)
    const c1 = await certifyExecution(r1, 1n as SequenceNumber)
    const c2 = await certifyExecution(r2, 2n as SequenceNumber)
    expect(c1.certificate_hash).not.toBe(c2.certificate_hash)
  })
})
