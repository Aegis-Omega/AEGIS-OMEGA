// test/unit/game-theory.test.ts
// Gate 186 — Shapley Value Attribution Unit Tests
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import { computeSynthesisShapley, GAME_THEORY_SCHEMA_VERSION } from '../../src/consensus/game-theory.js'
import { runSynthesisSwarm } from '../../src/consensus/synthesis-swarm.js'
import type { AgentRole } from '../../src/consensus/synthesis-swarm.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const CODE = 'export function identity(x: number): number { return x }'
const COMMITTED_GAMMA = JSON.stringify({ verdict: 'COMMITTED', violations: [], rationale: 'ok' })
const REJECTED_GAMMA  = JSON.stringify({ verdict: 'REJECTED',  violations: ['x'], rationale: 'no' })

const ALPHA_RICH = `\
export async function process(items: readonly string[]): Promise<string[]> {
  try {
    const [first, ...rest] = items
    const out: string[] = []
    for (const item of rest) {
      if (!item) { return [] }
      out.push(item)
    }
    return [first ?? '', ...out]
  } catch (e) {
    throw new Error('fail')
  }
}
export function check(x: string): boolean { return x.length > 0 }`

const BETA_MINIMAL = 'function g() { return 0 }'

async function committed(n: number) {
  return runSynthesisSwarm(
    { task: `t${n}`, context: '', constitutional_constraints: [], sequence: seq(n) },
    async (_s, _u, role: AgentRole) => {
      if (role === 'gamma') return { output: COMMITTED_GAMMA, backend: 'mock', latency_ms: 1 }
      return { output: CODE, backend: 'mock', latency_ms: 1 }
    },
  )
}

async function rejected(n: number) {
  return runSynthesisSwarm(
    { task: `t${n}`, context: '', constitutional_constraints: [], sequence: seq(n) },
    async (_s, _u, role: AgentRole) => {
      if (role === 'gamma') return { output: REJECTED_GAMMA, backend: 'mock', latency_ms: 1 }
      return { output: CODE, backend: 'mock', latency_ms: 1 }
    },
  )
}

async function deadlock(n: number) {
  return runSynthesisSwarm(
    { task: `t${n}`, context: '', constitutional_constraints: [], sequence: seq(n) },
    async (_s, _u, role: AgentRole) => {
      if (role === 'alpha') return { output: ALPHA_RICH, backend: 'mock', latency_ms: 1 }
      if (role === 'beta')  return { output: BETA_MINIMAL, backend: 'mock', latency_ms: 1 }
      return { output: COMMITTED_GAMMA, backend: 'mock', latency_ms: 1 }
    },
  )
}

describe('Gate 186 — Shapley attribution for synthesis swarm', () => {

  describe('Schema constants', () => {
    it('GAME_THEORY_SCHEMA_VERSION is 1.0.0', () => {
      expect(GAME_THEORY_SCHEMA_VERSION).toBe('1.0.0')
    })
  })

  describe('COMMITTED outcome (sim=1.0)', () => {
    it('attribution is frozen and replay-certifiable', async () => {
      const rec = await committed(1)
      const att = await computeSynthesisShapley(rec)
      expect(Object.isFrozen(att)).toBe(true)
      expect(att.is_replay_reconstructable).toBe(true)
      expect(att.schema_version).toBe('1.0.0')
      expect(att.attribution_hash.length).toBe(64)
    })

    it('efficiency: phi_A + phi_B + phi_G = total_value', async () => {
      const rec = await committed(2)
      const att = await computeSynthesisShapley(rec)
      expect(att.is_efficient).toBe(true)
      expect(Math.abs(att.alpha_credit + att.beta_credit + att.gamma_credit - att.total_value)).toBeLessThan(1e-9)
    })

    it('total_value = 1.0 for COMMITTED', async () => {
      const rec = await committed(3)
      const att = await computeSynthesisShapley(rec)
      expect(att.total_value).toBeCloseTo(1.0, 9)
    })

    it('alpha gets the largest share (most pivotal)', async () => {
      const rec = await committed(4)
      const att = await computeSynthesisShapley(rec)
      expect(att.alpha_credit).toBeGreaterThan(att.beta_credit)
      expect(att.alpha_credit).toBeGreaterThan(att.gamma_credit)
    })

    it('beta gets more than gamma (adversarial testing > certification)', async () => {
      const rec = await committed(5)
      const att = await computeSynthesisShapley(rec)
      expect(att.beta_credit).toBeGreaterThan(att.gamma_credit)
    })

    it('all credits are non-negative', async () => {
      const rec = await committed(6)
      const att = await computeSynthesisShapley(rec)
      expect(att.alpha_credit).toBeGreaterThanOrEqual(0)
      expect(att.beta_credit).toBeGreaterThanOrEqual(0)
      expect(att.gamma_credit).toBeGreaterThanOrEqual(0)
    })

    it('COMMITTED sim=1.0 exact values: alpha≈7/12, beta≈4/12, gamma≈1/12', async () => {
      const rec = await committed(7)
      const att = await computeSynthesisShapley(rec)
      // sim=1.0, committed=true, outcome=1.0
      // phi_A = 1/6 + 1/12 + 1/3 = 2/12 + 1/12 + 4/12 = 7/12
      // phi_B = 1/6 + 1/3 - 1/6 = 1/3 = 4/12
      // phi_G = 1/12 + 0 = 1/12
      expect(att.alpha_credit).toBeCloseTo(7 / 12, 9)
      expect(att.beta_credit).toBeCloseTo(4 / 12, 9)
      expect(att.gamma_credit).toBeCloseTo(1 / 12, 9)
    })

    it('attribution_hash is deterministic (same record → same hash ×3)', async () => {
      const rec = await committed(8)
      const [a1, a2, a3] = await Promise.all([
        computeSynthesisShapley(rec),
        computeSynthesisShapley(rec),
        computeSynthesisShapley(rec),
      ])
      expect(a1!.attribution_hash).toBe(a2!.attribution_hash)
      expect(a2!.attribution_hash).toBe(a3!.attribution_hash)
    })
  })

  describe('REJECTED outcome', () => {
    it('total_value = structural_similarity for REJECTED', async () => {
      const rec = await rejected(10)
      const att = await computeSynthesisShapley(rec)
      expect(att.total_value).toBeCloseTo(rec.convergence.structural_similarity, 9)
    })

    it('gamma_credit = 0 for REJECTED (certification produced nothing)', async () => {
      const rec = await rejected(11)
      const att = await computeSynthesisShapley(rec)
      expect(att.gamma_credit).toBeCloseTo(0, 9)
    })

    it('alpha = beta for REJECTED with sim=1.0 (symmetric when Gamma withholds)', async () => {
      // Identical code (sim=1.0), Gamma rejects → outcome=1.0... wait: REJECTED → outcome=sim
      // outcome = sim = 1.0 for identical code; gamma_credit = 0; alpha = beta = sim/2 = 0.5
      const rec = await rejected(12)
      const att = await computeSynthesisShapley(rec)
      // phi_A = sim/6 + 0 + sim/3 = sim/2; phi_B = sim/6 + sim/3 = sim/2
      expect(att.alpha_credit).toBeCloseTo(att.beta_credit, 9)
      expect(att.alpha_credit).toBeCloseTo(rec.convergence.structural_similarity / 2, 9)
    })

    it('efficiency holds for REJECTED', async () => {
      const rec = await rejected(13)
      const att = await computeSynthesisShapley(rec)
      expect(att.is_efficient).toBe(true)
    })
  })

  describe('DEADLOCK outcome', () => {
    it('gamma_credit = 0 for DEADLOCK (convergence failed — Gamma did not add value)', async () => {
      const rec = await deadlock(20)
      expect(rec.verdict).toBe('DEADLOCK')
      const att = await computeSynthesisShapley(rec)
      expect(att.gamma_credit).toBeCloseTo(0, 9)
    })

    it('total_value = structural_similarity for DEADLOCK', async () => {
      const rec = await deadlock(21)
      const att = await computeSynthesisShapley(rec)
      expect(att.total_value).toBeCloseTo(rec.convergence.structural_similarity, 9)
    })

    it('efficiency holds for DEADLOCK', async () => {
      const rec = await deadlock(22)
      const att = await computeSynthesisShapley(rec)
      expect(att.is_efficient).toBe(true)
    })
  })

  describe('Attribution hash distinguishes different records', () => {
    it('COMMITTED and REJECTED records produce different attribution hashes', async () => {
      const c = await committed(30)
      const r = await rejected(31)
      const ca = await computeSynthesisShapley(c)
      const ra = await computeSynthesisShapley(r)
      expect(ca.attribution_hash).not.toBe(ra.attribution_hash)
    })

    it('verdict echoed correctly in attestation', async () => {
      const c = await committed(32)
      const r = await rejected(33)
      const d = await deadlock(34)
      expect((await computeSynthesisShapley(c)).verdict).toBe('COMMITTED')
      expect((await computeSynthesisShapley(r)).verdict).toBe('REJECTED')
      expect((await computeSynthesisShapley(d)).verdict).toBe('DEADLOCK')
    })
  })
})
