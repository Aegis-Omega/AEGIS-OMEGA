// ============================================================
// SOVEREIGN OMEGA — SHP Transition DFA tests
// EPISTEMIC TIER: T0
//
// Tests for frame/dfa.ts:
//   SHPExecutionError — error subclass
//   initialMachine    — frozen IDLE state
//   transition        — valid steps, invalid step throws, chained hash
//   certifyExecution  — valid 5-step trace, incomplete, phase mismatch
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  SHPExecutionError,
  initialMachine,
  transition,
  certifyExecution,
} from '../../src/frame/dfa.js'
import type { FrameTransitionRecord } from '../../src/frame/dfa.js'
import type { Phase } from '../../src/shp/types.js'
import type { SequenceNumber, SHA256Hex } from '../../src/core/types.js'

const SEQ = (n: number) => BigInt(n) as unknown as SequenceNumber
const H = '0'.repeat(64) as SHA256Hex

// ── SHPExecutionError ──────────────────────────────────────

describe('SHPExecutionError', () => {
  it('is an Error subclass with correct name', () => {
    const e = new SHPExecutionError('bad transition')
    expect(e).toBeInstanceOf(Error)
    expect(e.name).toBe('SHPExecutionError')
    expect(e.message).toBe('bad transition')
  })
})

// ── initialMachine ─────────────────────────────────────────

describe('initialMachine', () => {
  it('returns a frozen machine in IDLE state with step_count=0', () => {
    const m = initialMachine(SEQ(1))
    expect(Object.isFrozen(m)).toBe(true)
    expect(m.current_phase).toBe('IDLE')
    expect(m.step_count).toBe(0)
    expect(m.last_transition_hash).toBeNull()
  })

  it('preserves the provided sequence', () => {
    const m = initialMachine(SEQ(42))
    expect(m.sequence).toBe(SEQ(42))
  })
})

// ── transition ─────────────────────────────────────────────

describe('transition', () => {
  it('IDLE → READ produces frozen machine and record', async () => {
    const m0 = initialMachine(SEQ(1))
    const { machine: m1, record } = await transition(m0, 'READ', H)
    expect(Object.isFrozen(m1)).toBe(true)
    expect(Object.isFrozen(record)).toBe(true)
    expect(m1.current_phase).toBe('READ')
    expect(m1.step_count).toBe(1)
    expect(record.from_phase).toBe('IDLE')
    expect(record.to_phase).toBe('READ')
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('transition_hash is a 64-char hex string', async () => {
    const m0 = initialMachine(SEQ(1))
    const { record } = await transition(m0, 'READ', H)
    expect(record.transition_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('chained transitions: each last_transition_hash matches previous record', async () => {
    const m0 = initialMachine(SEQ(1))
    const { machine: m1, record: r1 } = await transition(m0, 'READ', H)
    const { machine: m2, record: r2 } = await transition(m1, 'ASSESS', H)
    expect(r2.from_phase).toBe('READ')
    expect(m2.last_transition_hash).toBe(r2.transition_hash)
    expect(m1.last_transition_hash).toBe(r1.transition_hash)
  })

  it('throws SHPExecutionError for invalid phase (skipping ASSESS)', async () => {
    const m0 = initialMachine(SEQ(1))
    const { machine: m1 } = await transition(m0, 'READ', H)
    await expect(transition(m1, 'LOCK', H)).rejects.toThrow(SHPExecutionError)
  })

  it('throws SHPExecutionError when repeating the same phase', async () => {
    const m0 = initialMachine(SEQ(1))
    const { machine: m1 } = await transition(m0, 'READ', H)
    await expect(transition(m1, 'READ', H)).rejects.toThrow(SHPExecutionError)
  })

  it('full 5-step trace IDLE→READ→ASSESS→LOCK→PROPAGATE→HARMONIZE succeeds', async () => {
    let m = initialMachine(SEQ(1))
    const phases: Phase[] = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE']
    for (const p of phases) {
      const result = await transition(m, p, H)
      m = result.machine
    }
    expect(m.current_phase).toBe('HARMONIZE')
    expect(m.step_count).toBe(5)
  })
})

// ── certifyExecution ────────────────────────────────────────

async function buildFullTrace(seq: SequenceNumber): Promise<FrameTransitionRecord[]> {
  let m = initialMachine(seq)
  const records: FrameTransitionRecord[] = []
  for (const p of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as Phase[]) {
    const result = await transition(m, p, H)
    m = result.machine
    records.push(result.record)
  }
  return records
}

describe('certifyExecution', () => {
  it('valid 5-step trace → is_valid=true, step_count=5', async () => {
    const records = await buildFullTrace(SEQ(1))
    const cert = await certifyExecution(records, SEQ(1))
    expect(cert.is_valid).toBe(true)
    expect(cert.step_count).toBe(5)
    expect(cert.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(cert)).toBe(true)
  })

  it('certificate_hash is a 64-char hex string', async () => {
    const cert = await certifyExecution(await buildFullTrace(SEQ(1)), SEQ(1))
    expect(cert.certificate_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('incomplete trace (3 records) → is_valid=false', async () => {
    const records = await buildFullTrace(SEQ(1))
    const cert = await certifyExecution(records.slice(0, 3), SEQ(1))
    expect(cert.is_valid).toBe(false)
    expect(cert.step_count).toBe(3)
  })

  it('empty trace → is_valid=false', async () => {
    const cert = await certifyExecution([], SEQ(1))
    expect(cert.is_valid).toBe(false)
  })

  it('tampered from_phase causes is_valid=false', async () => {
    const records = await buildFullTrace(SEQ(1))
    const tampered: FrameTransitionRecord[] = [
      records[0]!,
      { ...records[1]!, from_phase: 'IDLE' },  // should be 'READ'
      records[2]!,
      records[3]!,
      records[4]!,
    ]
    const cert = await certifyExecution(tampered, SEQ(1))
    expect(cert.is_valid).toBe(false)
  })

  it('tampered transition_hash causes is_valid=false', async () => {
    const records = await buildFullTrace(SEQ(1))
    const tampered: FrameTransitionRecord[] = [
      { ...records[0]!, transition_hash: 'f'.repeat(64) as SHA256Hex },
      records[1]!,
      records[2]!,
      records[3]!,
      records[4]!,
    ]
    const cert = await certifyExecution(tampered, SEQ(1))
    expect(cert.is_valid).toBe(false)
  })

  it('is deterministic — three certifications produce equal certificate_hash', async () => {
    const records = await buildFullTrace(SEQ(1))
    const [c1, c2, c3] = await Promise.all([
      certifyExecution(records, SEQ(1)),
      certifyExecution(records, SEQ(1)),
      certifyExecution(records, SEQ(1)),
    ])
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})
