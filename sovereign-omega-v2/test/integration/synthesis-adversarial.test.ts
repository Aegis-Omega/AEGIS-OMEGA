// test/integration/synthesis-adversarial.test.ts
//
// Gate 184 — Synthesis Swarm Adversarial Integration
// EPISTEMIC TIER: T2 (engineering hypothesis)
//
// Proves the three non-COMMITTED synthesis paths:
//   REJECTED  — Gamma explicitly rejects regardless of Alpha/Beta convergence
//   DEADLOCK  — Gamma approves but Alpha/Beta structural fingerprints diverge (< 1/φ)
//   PARSE_ERR — Gamma returns malformed JSON → treated as REJECTED
//
// Also proves replay-certifiability for every outcome variant and that
// synthesis_hash values chain through AdaptiveLineage correctly.

import { describe, it, expect } from 'vitest'
import { runSynthesisSwarm } from '../../src/consensus/synthesis-swarm.js'
import type { SynthesisRequest, AgentRole } from '../../src/consensus/synthesis-swarm.js'
import { AdaptiveLineage, certifyAdaptiveLineage } from '../../src/frame/adaptive-lineage.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const baseReq = (n: number): SynthesisRequest => ({
  task: `adversarial-task-${n}`,
  context: '',
  constitutional_constraints: ['replay-certifiable', 'no-mutation'],
  sequence: seq(n),
})

// Mock gamma payloads
const GAMMA_COMMITTED = JSON.stringify({ verdict: 'COMMITTED', violations: [], rationale: 'ok' })
const GAMMA_REJECTED  = JSON.stringify({ verdict: 'REJECTED', violations: ['invariant-broken'], rationale: 'fail' })
const GAMMA_MALFORMED = 'not json { at all'

// Convergent code: identical Alpha & Beta output → structural_similarity = 1.0
const CONVERGENT_CODE = 'export function identity(x: number): number { return x }'

// Divergent Alpha: rich feature set — async, try/catch/throw new, types, const,
// early return, for-loop, destructuring, 2 exports → forces many divergent fields vs Beta.
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

// Divergent Beta: minimal — no async, no types, no const, no features, 1 fn, 0 exports.
const BETA_MINIMAL = 'function g() { return 0 }'

// ─── REJECTED path ───────────────────────────────────────────────────────────

describe('Gate 184 — Synthesis swarm adversarial scenarios', () => {

  describe('REJECTED path', () => {
    it('Gamma REJECTED verdict → verdict=REJECTED, committed_output_hash=null', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'gamma') return { output: GAMMA_REJECTED, backend: 'mock', latency_ms: 1 }
        return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
      }
      const rec = await runSynthesisSwarm(baseReq(1), agent)
      expect(rec.verdict).toBe('REJECTED')
      expect(rec.committed_output_hash).toBeNull()
      expect(rec.convergence.converged).toBe(true) // Alpha/Beta converged — Gamma still rejected
    })

    it('Gamma malformed JSON → treated as REJECTED', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'gamma') return { output: GAMMA_MALFORMED, backend: 'mock', latency_ms: 1 }
        return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
      }
      const rec = await runSynthesisSwarm(baseReq(2), agent)
      expect(rec.verdict).toBe('REJECTED')
      expect(rec.committed_output_hash).toBeNull()
    })

    it('REJECTED record is fully replay-certifiable', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'gamma') return { output: GAMMA_REJECTED, backend: 'mock', latency_ms: 1 }
        return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
      }
      const rec = await runSynthesisSwarm(baseReq(3), agent)
      expect(rec.synthesis_hash.length).toBe(64)
      expect(rec.task_hash.length).toBe(64)
      expect(rec.is_replay_reconstructable).toBe(true)
      expect(rec.schema_version).toBe('1.0.0')
      expect(rec.alpha_proposal.output_hash.length).toBe(64)
      expect(Object.isFrozen(rec)).toBe(true)
    })
  })

  // ─── DEADLOCK path ─────────────────────────────────────────────────────────

  describe('DEADLOCK path', () => {
    it('Gamma COMMITTED but Alpha/Beta fingerprints diverge → verdict=DEADLOCK', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'alpha') return { output: ALPHA_RICH, backend: 'mock', latency_ms: 1 }
        if (role === 'beta')  return { output: BETA_MINIMAL, backend: 'mock', latency_ms: 1 }
        return { output: GAMMA_COMMITTED, backend: 'mock', latency_ms: 1 }
      }
      const rec = await runSynthesisSwarm(baseReq(10), agent)
      // Alpha has async/try/catch/throw new/types/const/for/destructuring/2-exports
      // Beta has none → structural_similarity well below 1/φ ≈ 0.618
      expect(rec.convergence.structural_similarity).toBeLessThan(0.618034)
      expect(rec.convergence.converged).toBe(false)
      expect(rec.verdict).toBe('DEADLOCK')
      expect(rec.committed_output_hash).toBeNull()
    })

    it('DEADLOCK record is fully replay-certifiable', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'alpha') return { output: ALPHA_RICH, backend: 'mock', latency_ms: 1 }
        if (role === 'beta')  return { output: BETA_MINIMAL, backend: 'mock', latency_ms: 1 }
        return { output: GAMMA_COMMITTED, backend: 'mock', latency_ms: 1 }
      }
      const rec = await runSynthesisSwarm(baseReq(11), agent)
      expect(rec.synthesis_hash.length).toBe(64)
      expect(rec.is_replay_reconstructable).toBe(true)
      expect(Object.isFrozen(rec)).toBe(true)
      expect(Object.isFrozen(rec.convergence)).toBe(true)
    })

    it('divergent_patterns is non-empty on DEADLOCK', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'alpha') return { output: ALPHA_RICH, backend: 'mock', latency_ms: 1 }
        if (role === 'beta')  return { output: BETA_MINIMAL, backend: 'mock', latency_ms: 1 }
        return { output: GAMMA_COMMITTED, backend: 'mock', latency_ms: 1 }
      }
      const rec = await runSynthesisSwarm(baseReq(12), agent)
      expect(rec.convergence.divergent_patterns.length).toBeGreaterThan(0)
    })
  })

  // ─── COMMITTED path (sanity) ────────────────────────────────────────────────

  describe('COMMITTED path (reference)', () => {
    it('identical Alpha/Beta + Gamma COMMITTED → COMMITTED', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'gamma') return { output: GAMMA_COMMITTED, backend: 'mock', latency_ms: 1 }
        return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
      }
      const rec = await runSynthesisSwarm(baseReq(20), agent)
      expect(rec.verdict).toBe('COMMITTED')
      expect(rec.committed_output_hash).toBe(rec.alpha_proposal.output_hash)
      expect(rec.convergence.converged).toBe(true)
    })
  })

  // ─── Cross-record properties ────────────────────────────────────────────────

  describe('Cross-record replay invariants', () => {
    it('different tasks produce different synthesis_hashes and task_hashes', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'gamma') return { output: GAMMA_COMMITTED, backend: 'mock', latency_ms: 1 }
        return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
      }
      const r1 = await runSynthesisSwarm({ task: 'task-alpha', context: '', constitutional_constraints: [], sequence: seq(30) }, agent)
      const r2 = await runSynthesisSwarm({ task: 'task-beta',  context: '', constitutional_constraints: [], sequence: seq(30) }, agent)
      expect(r1.task_hash).not.toBe(r2.task_hash)
      expect(r1.synthesis_hash).not.toBe(r2.synthesis_hash)
    })

    it('same task + same sequence → same synthesis_hash (deterministic ×3)', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'gamma') return { output: GAMMA_COMMITTED, backend: 'mock', latency_ms: 1 }
        return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
      }
      const runs = await Promise.all([1, 2, 3].map(() => runSynthesisSwarm(baseReq(31), agent)))
      expect(runs[0]!.synthesis_hash).toBe(runs[1]!.synthesis_hash)
      expect(runs[1]!.synthesis_hash).toBe(runs[2]!.synthesis_hash)
    })
  })

  // ─── AdaptiveLineage chaining ───────────────────────────────────────────────

  describe('Synthesis records chain through AdaptiveLineage', () => {
    it('3 REJECTED synthesis_hashes → 3 CAPABILITY_EVOLUTION entries → chain valid', async () => {
      const agent = async (_s: string, _u: string, role: AgentRole) => {
        if (role === 'gamma') return { output: GAMMA_REJECTED, backend: 'mock', latency_ms: 1 }
        return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
      }
      let lineage = AdaptiveLineage.empty()
      for (let i = 0; i < 3; i++) {
        const rec = await runSynthesisSwarm(baseReq(40 + i), agent)
        expect(rec.verdict).toBe('REJECTED')
        const { lineage: next } = await lineage.append(
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict: 'REJECTED' },
          seq(40 + i),
        )
        lineage = next
      }
      expect(lineage.length).toBe(3)
      const cert = await certifyAdaptiveLineage(lineage.getAll())
      expect(cert.is_valid).toBe(true)
      expect(cert.entry_count).toBe(3)
      expect(cert.certificate_hash.length).toBe(64)
    })

    it('mixed COMMITTED/REJECTED chain → certifyAdaptiveLineage is_valid=true', async () => {
      const agents = [
        async (_s: string, _u: string, role: AgentRole) => {
          if (role === 'gamma') return { output: GAMMA_COMMITTED, backend: 'mock', latency_ms: 1 }
          return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
        },
        async (_s: string, _u: string, role: AgentRole) => {
          if (role === 'gamma') return { output: GAMMA_REJECTED, backend: 'mock', latency_ms: 1 }
          return { output: CONVERGENT_CODE, backend: 'mock', latency_ms: 1 }
        },
      ]
      let lineage = AdaptiveLineage.empty()
      for (let i = 0; i < 4; i++) {
        const agent = agents[i % 2]!
        const rec = await runSynthesisSwarm(baseReq(50 + i), agent)
        const verdict = rec.verdict === 'COMMITTED' ? 'APPROVED' : 'REJECTED'
        const { lineage: next } = await lineage.append(
          { kind: 'CAPABILITY_EVOLUTION', proposal_id: rec.synthesis_hash as SHA256Hex, verdict },
          seq(50 + i),
        )
        lineage = next
      }
      const cert = await certifyAdaptiveLineage(lineage.getAll())
      expect(cert.is_valid).toBe(true)
      expect(cert.entry_count).toBe(4)
    })
  })
})
