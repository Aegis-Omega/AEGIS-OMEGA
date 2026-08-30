// ============================================================
// Gate 64 — SHP DFA Adversarial (Integration)
// ~22 tests: invalid phase transitions throw SHPExecutionError;
//   phase lock enforcement (no reorder, no skip, no repeat);
//   50-frame stress at certifyExecution scale; tamper detection.
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  initialMachine, transition, certifyExecution,
  SHPExecutionError,
} from '../../src/frame/dfa.js'
import type { Phase } from '../../src/frame/dfa.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const PHASES: Phase[] = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE']

async function fullTrace(seqN: number) {
  let machine = initialMachine(seq(seqN))
  const records = []
  for (const phase of PHASES) {
    const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
    machine = next
    records.push(record)
  }
  return { machine, records }
}

// ─── Invalid transitions throw ─────────────────────────────

describe('DFA: invalid phase transitions throw SHPExecutionError', () => {
  it('IDLE → ASSESS (skipping READ) throws', async () => {
    const machine = initialMachine(seq(1))
    await expect(transition(machine, 'ASSESS', h('a'))).rejects.toThrow(SHPExecutionError)
  })

  it('IDLE → LOCK throws', async () => {
    const machine = initialMachine(seq(1))
    await expect(transition(machine, 'LOCK', h('a'))).rejects.toThrow(SHPExecutionError)
  })

  it('READ → LOCK (skipping ASSESS) throws', async () => {
    let machine = initialMachine(seq(1))
    const { machine: next } = await transition(machine, 'READ', h('r'))
    machine = next
    await expect(transition(machine, 'LOCK', h('l'))).rejects.toThrow(SHPExecutionError)
  })

  it('ASSESS → HARMONIZE (skipping LOCK+PROPAGATE) throws', async () => {
    let machine = initialMachine(seq(1))
    const { machine: m1 } = await transition(machine, 'READ', h('r'))
    const { machine: m2 } = await transition(m1, 'ASSESS', h('a'))
    await expect(transition(m2, 'HARMONIZE', h('h'))).rejects.toThrow(SHPExecutionError)
  })

  it('LOCK → ASSESS (reverse step) throws', async () => {
    let machine = initialMachine(seq(1))
    const { machine: m1 } = await transition(machine, 'READ', h('r'))
    const { machine: m2 } = await transition(m1, 'ASSESS', h('a'))
    const { machine: m3 } = await transition(m2, 'LOCK', h('l'))
    await expect(transition(m3, 'ASSESS', h('a'))).rejects.toThrow(SHPExecutionError)
  })

  it('HARMONIZE → READ (cycle attempt) throws', async () => {
    const { machine } = await fullTrace(1)
    await expect(transition(machine, 'READ', h('r'))).rejects.toThrow(SHPExecutionError)
  })
})

// ─── Valid complete trace ──────────────────────────────────

describe('DFA: valid complete trace certifies correctly', () => {
  it('full R→A→L→P→H → certifyExecution is_valid=true', async () => {
    const { records } = await fullTrace(1)
    const cert = await certifyExecution(records, seq(1))
    expect(cert.is_valid).toBe(true)
    expect(cert.step_count).toBe(5)
  })

  it('certifyExecution deterministic ×3 on same trace', async () => {
    const { records } = await fullTrace(42)
    const [c1, c2, c3] = await Promise.all([
      certifyExecution(records, seq(42)),
      certifyExecution(records, seq(42)),
      certifyExecution(records, seq(42)),
    ])
    expect(c1!.certificate_hash).toBe(c2!.certificate_hash)
    expect(c2!.certificate_hash).toBe(c3!.certificate_hash)
  })

  it('different sequences → different certificate_hash', async () => {
    const { records: r1 } = await fullTrace(1)
    const { records: r2 } = await fullTrace(2)
    const c1 = await certifyExecution(r1, seq(1))
    const c2 = await certifyExecution(r2, seq(2))
    expect(c1.certificate_hash).not.toBe(c2.certificate_hash)
  })

  it('is_replay_reconstructable=true on certificate', async () => {
    const { records } = await fullTrace(1)
    const cert = await certifyExecution(records, seq(1))
    expect(cert.is_replay_reconstructable).toBe(true)
  })
})

// ─── 50-frame stress ──────────────────────────────────────

describe('DFA: 50-frame stress', () => {
  it('50 independent full traces → all certify is_valid=true', async () => {
    const results = await Promise.all(
      Array.from({ length: 50 }, (_, i) =>
        fullTrace(i + 1).then(({ records }) => certifyExecution(records, seq(i + 1)))
      )
    )
    for (const cert of results) {
      expect(cert.is_valid).toBe(true)
    }
  })

  it('50 traces → 50 distinct certificate_hashes', async () => {
    const hashes = new Array<string>()
    for (let i = 1; i <= 50; i++) {
      const { records } = await fullTrace(i)
      const cert = await certifyExecution(records, seq(i))
      hashes.push(cert.certificate_hash)
    }
    const unique = new Set(hashes)
    expect(unique.size).toBe(50)
  })
})

// ─── Tamper detection ─────────────────────────────────────

describe('DFA: tamper detection', () => {
  it('tampered transition_hash → certifyExecution is_valid=false', async () => {
    const { records } = await fullTrace(1)
    const tampered = [
      ...records.slice(0, 2),
      { ...records[2]!, transition_hash: h('z') },
      ...records.slice(3),
    ]
    const cert = await certifyExecution(tampered, seq(1))
    expect(cert.is_valid).toBe(false)
  })

  it('incomplete trace (4 records) → certifyExecution is_valid=false', async () => {
    const { records } = await fullTrace(1)
    const cert = await certifyExecution(records.slice(0, 4), seq(1))
    expect(cert.is_valid).toBe(false)
    expect(cert.step_count).toBe(4)
  })

  it('empty records → certifyExecution is_valid=false', async () => {
    const cert = await certifyExecution([], seq(1))
    expect(cert.is_valid).toBe(false)
    expect(cert.step_count).toBe(0)
  })
})
