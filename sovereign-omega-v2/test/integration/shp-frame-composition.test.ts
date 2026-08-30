// ============================================================
// Gate 81 — SHP Frame Composition (Integration)
// ~18 tests: Full RALPH cycle integration — RalphLoop drives
//   DFA transition machine; LOCK boundary enforcement; 10-cycle
//   convergence depth; archive export determinism.
// ============================================================

import { describe, it, expect } from 'vitest'
import { RalphLoop, estimateSystemEntropy } from '../../src/core/ralph-loop.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { HolonicScale } from '../../src/core/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function h(c: string): SHA256Hex { return c.repeat(64) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

async function runFullDFATrace(seqN: number) {
  let machine = initialMachine(seq(seqN))
  const records = []
  for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
    const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
    machine = next
    records.push(record)
  }
  return certifyExecution(records, seq(seqN))
}

// ─── RALPH cycle integration ──────────────────────────────

describe('SHP RALPH: full cycle integration', () => {
  it('10 PASS cycles → convergenceDepth()=10', async () => {
    const loop = new RalphLoop(HolonicScale.MOLECULAR, estimateSystemEntropy(0.95))
    for (let i = 1; i <= 10; i++) {
      const cert = await runFullDFATrace(i)
      expect(cert.is_valid).toBe(true)
      const builder = loop.beginCycle(seq(i))
      builder.addAnalysisNote(`DFA cert valid: ${cert.is_valid}`)
      builder.addFinding({ description: 'DFA complete', severity: 'informational', scale: HolonicScale.MOLECULAR, tier: 'T0' as any })
      builder.harmonize('PASS')
    }
    expect(loop.convergenceDepth()).toBe(10)
  })

  it('FAIL cycle resets convergence depth to 0', async () => {
    const loop = new RalphLoop(HolonicScale.MOLECULAR, estimateSystemEntropy(0.9))
    for (let i = 1; i <= 5; i++) {
      const builder = loop.beginCycle(seq(i))
      builder.harmonize('PASS')
    }
    expect(loop.convergenceDepth()).toBe(5)
    const builder = loop.beginCycle(seq(6))
    builder.harmonize('FAIL')
    expect(loop.convergenceDepth()).toBe(0)
  })

  it('DFA cert + RALPH harmonize: PASS when is_valid=true', async () => {
    const loop = new RalphLoop(HolonicScale.MOLECULAR, estimateSystemEntropy(0.95))
    const cert = await runFullDFATrace(1)
    const builder = loop.beginCycle(seq(1))
    builder.addAnalysisNote(`cert: ${cert.certificate_hash}`)
    const cycle = builder.harmonize(cert.is_valid ? 'PASS' : 'FAIL')
    expect(cycle.harmonization_result).toBe('COHERENT')
    expect(cycle.gate_result).toBe('PASS')
    expect(loop.convergenceDepth()).toBe(1)
  })

  it('invalid DFA trace (4 records) → FAIL cycle', async () => {
    const loop = new RalphLoop(HolonicScale.MOLECULAR, estimateSystemEntropy(0.9))
    let machine = initialMachine(seq(1))
    const records = []
    for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE'] as const) {  // only 4 phases
      const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
      machine = next; records.push(record)
    }
    const cert = await certifyExecution(records, seq(1))
    expect(cert.is_valid).toBe(false)
    const builder = loop.beginCycle(seq(1))
    const cycle = builder.harmonize(cert.is_valid ? 'PASS' : 'FAIL')
    expect(cycle.harmonization_result).toBe('INCOHERENT')
    expect(loop.convergenceDepth()).toBe(0)
  })
})

// ─── Archive export ───────────────────────────────────────

describe('SHP RALPH: archive export', () => {
  it('archive has correct total_cycles and convergence_depth', () => {
    const loop = new RalphLoop(HolonicScale.ORGANISM, estimateSystemEntropy(0.95))
    for (let i = 1; i <= 5; i++) {
      loop.beginCycle(seq(i)).harmonize('PASS')
    }
    const archive = loop.exportArchive(5)
    expect(archive.total_cycles).toBe(5)
    expect(archive.convergence_depth).toBe(5)
    expect(archive.cycles).toHaveLength(5)
  })

  it('archive is frozen', () => {
    const loop = new RalphLoop(HolonicScale.ORGANISM, estimateSystemEntropy(0.9))
    loop.beginCycle(seq(1)).harmonize('PASS')
    const archive = loop.exportArchive(1)
    expect(Object.isFrozen(archive)).toBe(true)
  })

  it('estimateSystemEntropy returns value in [0, 1]', () => {
    for (const rate of [0, 0.5, 0.9, 1.0]) {
      const entropy = estimateSystemEntropy(rate)
      expect(entropy).toBeGreaterThanOrEqual(0)
      expect(entropy).toBeLessThanOrEqual(1)
    }
  })
})

// ─── LOCK boundary enforcement via DFA ────────────────────

describe('SHP RALPH: LOCK boundary via DFA', () => {
  it('LOCK phase produces highest-stakes transition record', async () => {
    let machine = initialMachine(seq(1))
    const { machine: m1 } = await transition(machine, 'READ', h('r'))
    const { machine: m2 } = await transition(m1, 'ASSESS', h('a'))
    const { record: r3 } = await transition(m2, 'LOCK', h('l'))
    expect(r3.from_phase).toBe('ASSESS')
    expect(r3.to_phase).toBe('LOCK')
    expect(r3.transition_hash).toHaveLength(64)
  })

  it('each phase has unique transition_hash', async () => {
    let machine = initialMachine(seq(1))
    const hashes = new Set<string>()
    for (const phase of ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const) {
      const { machine: next, record } = await transition(machine, phase, h(phase[0]!.toLowerCase()))
      machine = next
      hashes.add(record.transition_hash)
    }
    expect(hashes.size).toBe(5)
  })
})
