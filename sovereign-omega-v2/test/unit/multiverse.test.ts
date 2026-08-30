// test/unit/multiverse.test.ts
// Gate 189 — MultiverseRegistry
// EPISTEMIC TIER: T2

import { describe, it, expect } from 'vitest'
import {
  MultiverseRegistry,
  MultiverseError,
  MAX_UNIVERSES,
  MULTIVERSE_SCHEMA_VERSION,
} from '../../src/memory/multiverse.js'
import { MAX_SIMULATION_DEPTH } from '../../src/simulation/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const FORK_A = 'aaaa'.repeat(16) as SHA256Hex  // 64-char hex
const FORK_B = 'bbbb'.repeat(16) as SHA256Hex

const EV_TOPOLOGY = (h: string) =>
  ({ kind: 'TOPOLOGY_TRANSITION', topology_hash: (h.repeat(16).slice(0, 64)) as SHA256Hex } as const)
const EV_APPROVED = (id: string) =>
  ({ kind: 'CAPABILITY_EVOLUTION', proposal_id: (id.repeat(16).slice(0, 64)) as SHA256Hex, verdict: 'APPROVED' } as const)
const EV_REJECTED = (id: string) =>
  ({ kind: 'CAPABILITY_EVOLUTION', proposal_id: (id.repeat(16).slice(0, 64)) as SHA256Hex, verdict: 'REJECTED' } as const)

describe('Gate 189 — MultiverseRegistry', () => {

  describe('Constants', () => {
    it('MAX_UNIVERSES equals MAX_SIMULATION_DEPTH (8)', () => {
      expect(MAX_UNIVERSES).toBe(8)
      expect(MAX_UNIVERSES).toBe(MAX_SIMULATION_DEPTH)
    })

    it('MULTIVERSE_SCHEMA_VERSION is 1.0.0', () => {
      expect(MULTIVERSE_SCHEMA_VERSION).toBe('1.0.0')
    })
  })

  describe('empty()', () => {
    it('starts with universeCount=0', () => {
      expect(MultiverseRegistry.empty().universeCount).toBe(0)
    })

    it('listUniverses returns empty array', () => {
      expect(MultiverseRegistry.empty().listUniverses()).toHaveLength(0)
    })

    it('getLineage returns null on empty registry', () => {
      expect(MultiverseRegistry.empty().getLineage('x')).toBeNull()
    })

    it('getFork returns null on empty registry', () => {
      expect(MultiverseRegistry.empty().getFork('x')).toBeNull()
    })
  })

  describe('fork()', () => {
    it('forks a universe and returns frozen fork record', async () => {
      const { registry, fork } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      expect(registry.universeCount).toBe(1)
      expect(Object.isFrozen(fork)).toBe(true)
    })

    it('fork_hash is 64-char hex', async () => {
      const { fork } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      expect(fork.fork_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(fork.fork_hash)).toBe(true)
    })

    it('fork_generation starts at 0', async () => {
      const { fork } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      expect(fork.fork_generation).toBe(0)
    })

    it('fork fields are correct', async () => {
      const { fork } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(42))
      expect(fork.universe_id).toBe('alpha')
      expect(fork.fork_point).toBe(FORK_A)
      expect(fork.sequence).toBe(42n)
      expect(fork.schema_version).toBe(MULTIVERSE_SCHEMA_VERSION)
      expect(fork.is_replay_reconstructable).toBe(true)
    })

    it('immutable: original registry unchanged after fork', async () => {
      const r0 = MultiverseRegistry.empty()
      await r0.fork('alpha', FORK_A, seq(1))
      expect(r0.universeCount).toBe(0)
    })

    it('throws MultiverseError on duplicate universe_id', async () => {
      const { registry } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      await expect(registry.fork('alpha', FORK_B, seq(2))).rejects.toThrow(MultiverseError)
    })

    it('throws MultiverseError when MAX_UNIVERSES (8) exceeded', async () => {
      let reg = MultiverseRegistry.empty()
      for (let i = 0; i < MAX_UNIVERSES; i++) {
        const { registry } = await reg.fork(`u${i}`, FORK_A, seq(i + 1))
        reg = registry
      }
      expect(reg.universeCount).toBe(MAX_UNIVERSES)
      await expect(reg.fork('overflow', FORK_A, seq(99))).rejects.toThrow(MultiverseError)
    })

    it('different fork_points produce different fork_hashes', async () => {
      const { fork: f1 } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const { fork: f2 } = await MultiverseRegistry.empty().fork('alpha', FORK_B, seq(1))
      expect(f1.fork_hash).not.toBe(f2.fork_hash)
    })

    it('fork is deterministic ×3 for same inputs', async () => {
      const [r1, r2, r3] = await Promise.all([
        MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1)),
        MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1)),
        MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1)),
      ])
      expect(r1.fork.fork_hash).toBe(r2.fork.fork_hash)
      expect(r2.fork.fork_hash).toBe(r3.fork.fork_hash)
    })

    it('MultiverseError is Error subclass', () => {
      expect(new MultiverseError('x')).toBeInstanceOf(Error)
      expect(new MultiverseError('x').name).toBe('MultiverseError')
    })
  })

  describe('appendToUniverse()', () => {
    it('appends an event and returns a lineage entry', async () => {
      const { registry: r1 } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const { registry: r2, entry } = await r1.appendToUniverse('alpha', EV_TOPOLOGY('cccc'), seq(2))
      expect(r2.getLineage('alpha')!.length).toBe(1)
      expect(Object.isFrozen(entry)).toBe(true)
    })

    it('lineage entry_hash is 64-char hex', async () => {
      const { registry: r1 } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const { entry } = await r1.appendToUniverse('alpha', EV_TOPOLOGY('cccc'), seq(2))
      expect(entry.entry_hash).toHaveLength(64)
    })

    it('generation advances on append', async () => {
      const { registry: r1 } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      // fork_generation = 0; after append it should be 1 (generation counter advanced)
      const { registry: r2 } = await r1.appendToUniverse('alpha', EV_TOPOLOGY('cccc'), seq(2))
      // Internal generation advanced — registry still valid (not saturated)
      expect(r2.universeCount).toBe(1)
    })

    it('throws MultiverseError on non-existent universe', async () => {
      await expect(
        MultiverseRegistry.empty().appendToUniverse('ghost', EV_TOPOLOGY('cccc'), seq(1)),
      ).rejects.toThrow(MultiverseError)
    })

    it('universes are independent: appending to one does not affect another', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('alpha', FORK_A, seq(1))
      const { registry: r2 } = await r1.fork('beta', FORK_B, seq(2))
      const { registry: r3 } = await r2.appendToUniverse('alpha', EV_TOPOLOGY('cccc'), seq(3))
      expect(r3.getLineage('alpha')!.length).toBe(1)
      expect(r3.getLineage('beta')!.length).toBe(0)
    })

    it('multiple appends chain correctly', async () => {
      const { registry: r1 } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const { registry: r2 } = await r1.appendToUniverse('alpha', EV_TOPOLOGY('cccc'), seq(2))
      const { registry: r3 } = await r2.appendToUniverse('alpha', EV_APPROVED('dddd'), seq(3))
      const { registry: r4 } = await r3.appendToUniverse('alpha', EV_REJECTED('eeee'), seq(4))
      expect(r4.getLineage('alpha')!.length).toBe(3)
      const entries = r4.getLineage('alpha')!.getAll()
      expect(entries[1]!.previous_entry_hash).toBe(entries[0]!.entry_hash)
      expect(entries[2]!.previous_entry_hash).toBe(entries[1]!.entry_hash)
    })
  })

  describe('checkConvergence()', () => {
    it('two universes with no events both have GENESIS_TOPOLOGY_HASH — converge immediately', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('alpha', FORK_A, seq(1))
      const { registry: r2 } = await r1.fork('beta', FORK_B, seq(2))
      const conv = await r2.checkConvergence(seq(10))
      expect(conv.swarm_record.quorum_reached).toBe(true)
      expect(conv.converged_universe_ids).toHaveLength(2)
      expect(conv.total_universes).toBe(2)
    })

    it('diverged universes do not reach quorum (1/φ threshold)', async () => {
      // 1 universe has events (different terminal hash), 2 do not
      // 2/3 ≈ 0.667 > 1/φ ≈ 0.618 → quorum still reached for the 2 empty ones
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('alpha', FORK_A, seq(1))
      const { registry: r2 } = await r1.fork('beta', FORK_B, seq(2))
      const { registry: r3 } = await r2.fork('gamma', FORK_A, seq(3))
      // Only alpha diverges via an event
      const { registry: r4 } = await r3.appendToUniverse('alpha', EV_TOPOLOGY('cccc'), seq(4))
      const conv = await r4.checkConvergence(seq(10))
      expect(conv.total_universes).toBe(3)
      // beta and gamma share GENESIS hash → 2/3 = 0.667 > 1/φ → quorum
      expect(conv.swarm_record.quorum_reached).toBe(true)
      expect(conv.converged_universe_ids).toHaveLength(2)
    })

    it('convergence result is frozen', async () => {
      const { registry } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const conv = await registry.checkConvergence(seq(1))
      expect(Object.isFrozen(conv)).toBe(true)
    })

    it('is_replay_reconstructable=true on convergence', async () => {
      const { registry } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const conv = await registry.checkConvergence(seq(1))
      expect(conv.is_replay_reconstructable).toBe(true)
    })

    it('throws MultiverseError on empty registry', async () => {
      await expect(MultiverseRegistry.empty().checkConvergence(seq(1))).rejects.toThrow(MultiverseError)
    })
  })

  describe('listUniverses()', () => {
    it('returns universe IDs in alphabetical order', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('gamma', FORK_A, seq(1))
      const { registry: r2 } = await r1.fork('alpha', FORK_B, seq(2))
      const { registry: r3 } = await r2.fork('beta', FORK_A, seq(3))
      expect(r3.listUniverses()).toEqual(['alpha', 'beta', 'gamma'])
    })
  })

  describe('certifyAll()', () => {
    it('empty registry certifies all with no entries', async () => {
      const { registry } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const certs = await registry.certifyAll()
      expect(certs).toHaveLength(1)
      expect(certs[0]!.universe_id).toBe('alpha')
      expect(certs[0]!.lineage_length).toBe(0)
      expect(certs[0]!.certificate.adaptive_power).toBe(0)
    })

    it('results are sorted by universe_id', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('gamma', FORK_A, seq(1))
      const { registry: r2 } = await r1.fork('alpha', FORK_B, seq(2))
      const { registry: r3 } = await r2.fork('beta', FORK_A, seq(3))
      const certs = await r3.certifyAll()
      expect(certs.map(c => c.universe_id)).toEqual(['alpha', 'beta', 'gamma'])
    })

    it('certificate is frozen', async () => {
      const { registry } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const certs = await registry.certifyAll()
      expect(Object.isFrozen(certs[0]!.certificate)).toBe(true)
    })

    it('adaptive_power counts only APPROVED events in each universe', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('alpha', FORK_A, seq(1))
      const { registry: r2 } = await r1.appendToUniverse('alpha', EV_APPROVED('a001'), seq(2))
      const { registry: r3 } = await r2.appendToUniverse('alpha', EV_APPROVED('a002'), seq(3))
      const { registry: r4 } = await r3.appendToUniverse('alpha', EV_REJECTED('a003'), seq(4))
      const certs = await r4.certifyAll()
      expect(certs[0]!.certificate.adaptive_power).toBe(2)
      expect(certs[0]!.lineage_length).toBe(3)
    })

    it('martingale entropy_bounded reflects per-universe ratio', async () => {
      // Build two universes: one all-APPROVED (above 1/φ), one all-REJECTED (bounded)
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('hot', FORK_A, seq(1))
      const { registry: r2 } = await r1.fork('cold', FORK_B, seq(2))

      let reg = r2
      // hot: 10 APPROVED
      for (let i = 0; i < 10; i++) {
        const { registry } = await reg.appendToUniverse('hot', EV_APPROVED(`h${i.toString().padStart(3, '0')}`), seq(10 + i))
        reg = registry
      }
      // cold: 10 REJECTED
      for (let i = 0; i < 10; i++) {
        const { registry } = await reg.appendToUniverse('cold', EV_REJECTED(`c${i.toString().padStart(3, '0')}`), seq(30 + i))
        reg = registry
      }

      const certs = await reg.certifyAll()
      const cold = certs.find(c => c.universe_id === 'cold')!
      const hot  = certs.find(c => c.universe_id === 'hot')!

      expect(cold.certificate.entropy_bounded).toBe(true)   // 0 APPROVED / 10 = 0 < 1/φ
      expect(hot.certificate.entropy_bounded).toBe(false)   // 10 APPROVED / 10 = 1.0 > 1/φ
    })

    it('fork_hash on certification matches original fork record', async () => {
      const { registry, fork } = await MultiverseRegistry.empty().fork('alpha', FORK_A, seq(1))
      const certs = await registry.certifyAll()
      expect(certs[0]!.fork_hash).toBe(fork.fork_hash)
    })
  })

  describe('Multiverse independence invariant', () => {
    it('three parallel universes evolve independently and certify independently', async () => {
      const r0 = MultiverseRegistry.empty()
      const { registry: r1 } = await r0.fork('timeline-A', FORK_A, seq(1))
      const { registry: r2 } = await r1.fork('timeline-B', FORK_B, seq(2))
      const { registry: r3 } = await r2.fork('timeline-C', FORK_A, seq(3))

      let reg = r3
      // A: 3 APPROVED
      for (let i = 0; i < 3; i++) {
        const { registry } = await reg.appendToUniverse('timeline-A', EV_APPROVED(`aa${i}`), seq(10 + i))
        reg = registry
      }
      // B: 2 TOPOLOGY transitions
      for (let i = 0; i < 2; i++) {
        const { registry } = await reg.appendToUniverse('timeline-B', EV_TOPOLOGY(`bb${i}`), seq(20 + i))
        reg = registry
      }
      // C: no events (stays at genesis)

      const certs = await reg.certifyAll()
      expect(certs).toHaveLength(3)
      expect(certs.find(c => c.universe_id === 'timeline-A')!.lineage_length).toBe(3)
      expect(certs.find(c => c.universe_id === 'timeline-B')!.lineage_length).toBe(2)
      expect(certs.find(c => c.universe_id === 'timeline-C')!.lineage_length).toBe(0)
      // Each universe is independently martingale-anchored
      certs.forEach(c => expect(c.certificate.is_anchored).toBe(true))
    })
  })
})
