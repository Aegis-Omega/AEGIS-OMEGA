// test/unit/grace-supervisor.test.ts
// Gate 193 — GraceSupervisor (fault-tolerant execution wrapper)
// EPISTEMIC TIER: T2
//
// Constitutional translation of the Self-Healing Runtime Grace Loop spec.
// Validates: trap interception, state reversion (immutable pattern), grace audit chain,
// fault classification, GraceCertificate determinism.

import { describe, it, expect } from 'vitest'
import {
  GraceSupervisor,
  GraceError,
  GRACE_SCHEMA_VERSION,
  type FaultClass,
} from '../../src/memory/grace-supervisor.js'
import { MultiverseRegistry, MAX_UNIVERSES } from '../../src/memory/multiverse.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const ROOT = 'a0b1c2d3'.repeat(8) as SHA256Hex

describe('Gate 193 — GraceSupervisor', () => {

  describe('Constants', () => {
    it('GRACE_SCHEMA_VERSION is 1.0.0', () => {
      expect(GRACE_SCHEMA_VERSION).toBe('1.0.0')
    })

    it('GraceError is Error subclass with correct name', () => {
      const err = new GraceError('x')
      expect(err).toBeInstanceOf(Error)
      expect(err.name).toBe('GraceError')
    })
  })

  describe('GraceSupervisor.create()', () => {
    it('starts with graceEventCount=0 and empty registry', () => {
      const sv = GraceSupervisor.create(MultiverseRegistry.empty())
      expect(sv.graceEventCount).toBe(0)
      expect(sv.registry.universeCount).toBe(0)
    })

    it('getGraceEvents returns empty array initially', () => {
      const sv = GraceSupervisor.create(MultiverseRegistry.empty())
      expect(sv.getGraceEvents()).toHaveLength(0)
    })
  })

  describe('executeWithGrace — success path', () => {
    it('forwards registry update on success', async () => {
      const sv = GraceSupervisor.create(MultiverseRegistry.empty())
      const { supervisor, faulted, grace_event } = await sv.executeWithGrace(
        async (reg) => {
          const { registry } = await reg.fork('u0', ROOT, seq(1))
          return { registry }
        },
        'u0',
        seq(1),
      )
      expect(faulted).toBe(false)
      expect(grace_event).toBeNull()
      expect(supervisor.registry.universeCount).toBe(1)
      expect(supervisor.graceEventCount).toBe(0)
    })

    it('original supervisor is unchanged after success (immutable pattern)', async () => {
      const sv = GraceSupervisor.create(MultiverseRegistry.empty())
      await sv.executeWithGrace(
        async (reg) => {
          const { registry } = await reg.fork('u0', ROOT, seq(1))
          return { registry }
        },
        'u0',
        seq(1),
      )
      expect(sv.registry.universeCount).toBe(0)
      expect(sv.graceEventCount).toBe(0)
    })

    it('chaining multiple success steps advances registry', async () => {
      let sv = GraceSupervisor.create(MultiverseRegistry.empty())
      for (let i = 0; i < 3; i++) {
        const result = await sv.executeWithGrace(
          async (reg) => {
            const { registry } = await reg.fork(`u${i}`, ROOT, seq(i + 1))
            return { registry }
          },
          `u${i}`,
          seq(i + 1),
        )
        sv = result.supervisor
      }
      expect(sv.registry.universeCount).toBe(3)
      expect(sv.graceEventCount).toBe(0)
    })
  })

  describe('executeWithGrace — fault path (ECOLOGY_OVERFLOW)', () => {
    async function buildFullRegistry(): Promise<GraceSupervisor> {
      let sv = GraceSupervisor.create(MultiverseRegistry.empty())
      for (let i = 0; i < MAX_UNIVERSES; i++) {
        const { supervisor } = await sv.executeWithGrace(
          async (reg) => {
            const { registry } = await reg.fork(`u${i}`, ROOT, seq(i + 1))
            return { registry }
          },
          `u${i}`,
          seq(i + 1),
        )
        sv = supervisor
      }
      return sv
    }

    it('faulted=true on ecology overflow', async () => {
      const sv = await buildFullRegistry()
      const { faulted } = await sv.executeWithGrace(
        async (reg) => {
          const { registry } = await reg.fork('overflow', ROOT, seq(99))
          return { registry }
        },
        'overflow',
        seq(99),
      )
      expect(faulted).toBe(true)
    })

    it('grace_event is not null on fault', async () => {
      const sv = await buildFullRegistry()
      const { grace_event } = await sv.executeWithGrace(
        async (reg) => {
          const { registry } = await reg.fork('overflow', ROOT, seq(99))
          return { registry }
        },
        'overflow',
        seq(99),
      )
      expect(grace_event).not.toBeNull()
    })

    it('fault_class=ECOLOGY_OVERFLOW on ecology fault', async () => {
      const sv = await buildFullRegistry()
      const { grace_event } = await sv.executeWithGrace(
        async (reg) => {
          const { registry } = await reg.fork('overflow', ROOT, seq(99))
          return { registry }
        },
        'overflow',
        seq(99),
      )
      expect(grace_event!.fault_class).toBe('ECOLOGY_OVERFLOW' satisfies FaultClass)
    })

    it('pre-fault registry retained on fault', async () => {
      const sv = await buildFullRegistry()
      const preCount = sv.registry.universeCount
      const { supervisor } = await sv.executeWithGrace(
        async (reg) => {
          const { registry } = await reg.fork('overflow', ROOT, seq(99))
          return { registry }
        },
        'overflow',
        seq(99),
      )
      expect(supervisor.registry.universeCount).toBe(preCount)
    })

    it('graceEventCount increments per fault', async () => {
      let sv = await buildFullRegistry()
      expect(sv.graceEventCount).toBe(0)
      const r1 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('ov1', ROOT, seq(99)); return { registry } },
        'ov1', seq(99),
      )
      sv = r1.supervisor
      const r2 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('ov2', ROOT, seq(100)); return { registry } },
        'ov2', seq(100),
      )
      sv = r2.supervisor
      expect(sv.graceEventCount).toBe(2)
    })
  })

  describe('executeWithGrace — fault path (DUPLICATE_UNIVERSE)', () => {
    it('fault_class=DUPLICATE_UNIVERSE on duplicate fork', async () => {
      let sv = GraceSupervisor.create(MultiverseRegistry.empty())
      const r1 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('alpha', ROOT, seq(1)); return { registry } },
        'alpha', seq(1),
      )
      sv = r1.supervisor

      const r2 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('alpha', ROOT, seq(2)); return { registry } },
        'alpha', seq(2),
      )
      expect(r2.faulted).toBe(true)
      expect(r2.grace_event!.fault_class).toBe('DUPLICATE_UNIVERSE' satisfies FaultClass)
    })
  })

  describe('GraceEvent integrity', () => {
    it('grace_event is frozen', async () => {
      let sv = GraceSupervisor.create(MultiverseRegistry.empty())
      const r1 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('a', ROOT, seq(1)); return { registry } },
        'a', seq(1),
      )
      sv = r1.supervisor
      const r2 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('a', ROOT, seq(2)); return { registry } },
        'a', seq(2),
      )
      expect(Object.isFrozen(r2.grace_event)).toBe(true)
    })

    it('grace_hash is 64-char hex', async () => {
      let sv = GraceSupervisor.create(MultiverseRegistry.empty())
      const r1 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('x', ROOT, seq(1)); return { registry } },
        'x', seq(1),
      )
      sv = r1.supervisor
      const r2 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('x', ROOT, seq(2)); return { registry } },
        'x', seq(2),
      )
      expect(r2.grace_event!.grace_hash).toHaveLength(64)
      expect(/^[0-9a-f]{64}$/.test(r2.grace_event!.grace_hash)).toBe(true)
    })

    it('grace_hash is deterministic x3 for same fault inputs', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        let sv = GraceSupervisor.create(MultiverseRegistry.empty())
        const r1 = await sv.executeWithGrace(
          async (reg) => { const { registry } = await reg.fork('dup', ROOT, seq(1)); return { registry } },
          'dup', seq(1),
        )
        sv = r1.supervisor
        const r2 = await sv.executeWithGrace(
          async (reg) => { const { registry } = await reg.fork('dup', ROOT, seq(2)); return { registry } },
          'dup', seq(2),
        )
        return r2.grace_event!.grace_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })

    it('is_replay_reconstructable=true and schema_version correct', async () => {
      let sv = GraceSupervisor.create(MultiverseRegistry.empty())
      const r1 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('z', ROOT, seq(1)); return { registry } },
        'z', seq(1),
      )
      sv = r1.supervisor
      const r2 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('z', ROOT, seq(2)); return { registry } },
        'z', seq(2),
      )
      expect(r2.grace_event!.is_replay_reconstructable).toBe(true)
      expect(r2.grace_event!.schema_version).toBe(GRACE_SCHEMA_VERSION)
    })

    it('different sequences produce different grace_hashes', async () => {
      async function getFaultHash(s: number): Promise<string> {
        let sv = GraceSupervisor.create(MultiverseRegistry.empty())
        const r1 = await sv.executeWithGrace(
          async (reg) => { const { registry } = await reg.fork('d', ROOT, seq(1)); return { registry } },
          'd', seq(1),
        )
        sv = r1.supervisor
        const r2 = await sv.executeWithGrace(
          async (reg) => { const { registry } = await reg.fork('d', ROOT, seq(s)); return { registry } },
          'd', seq(s),
        )
        return r2.grace_event!.grace_hash
      }
      const h1 = await getFaultHash(2)
      const h2 = await getFaultHash(3)
      expect(h1).not.toBe(h2)
    })
  })

  describe('certify()', () => {
    it('certifies empty history with grace_chain_hash', async () => {
      const sv = GraceSupervisor.create(MultiverseRegistry.empty())
      const cert = await sv.certify(seq(10))
      expect(Object.isFrozen(cert)).toBe(true)
      expect(cert.grace_event_count).toBe(0)
      expect(cert.grace_chain_hash).toHaveLength(64)
      expect(cert.schema_version).toBe(GRACE_SCHEMA_VERSION)
      expect(cert.is_replay_reconstructable).toBe(true)
    })

    it('fault_class_counts accumulate correctly', async () => {
      let sv = GraceSupervisor.create(MultiverseRegistry.empty())
      // Two DUPLICATE faults
      const r1 = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('m', ROOT, seq(1)); return { registry } },
        'm', seq(1),
      )
      sv = r1.supervisor
      for (let i = 2; i <= 3; i++) {
        const r = await sv.executeWithGrace(
          async (reg) => { const { registry } = await reg.fork('m', ROOT, seq(i)); return { registry } },
          'm', seq(i),
        )
        sv = r.supervisor
      }
      const cert = await sv.certify(seq(50))
      expect(cert.grace_event_count).toBe(2)
      expect(cert.fault_class_counts.DUPLICATE_UNIVERSE).toBe(2)
      expect(cert.fault_class_counts.ECOLOGY_OVERFLOW).toBe(0)
    })

    it('grace_chain_hash is deterministic x3', async () => {
      const hashes = await Promise.all([1, 2, 3].map(async () => {
        let sv = GraceSupervisor.create(MultiverseRegistry.empty())
        const r1 = await sv.executeWithGrace(
          async (reg) => { const { registry } = await reg.fork('q', ROOT, seq(1)); return { registry } },
          'q', seq(1),
        )
        sv = r1.supervisor
        const r2 = await sv.executeWithGrace(
          async (reg) => { const { registry } = await reg.fork('q', ROOT, seq(2)); return { registry } },
          'q', seq(2),
        )
        sv = r2.supervisor
        const cert = await sv.certify(seq(10))
        return cert.grace_chain_hash
      }))
      expect(hashes[0]).toBe(hashes[1])
      expect(hashes[1]).toBe(hashes[2])
    })
  })

  describe('Unrecoverable errors propagate', () => {
    it('non-MultiverseError / non-AdaptiveLineageError rethrows', async () => {
      const sv = GraceSupervisor.create(MultiverseRegistry.empty())
      await expect(
        sv.executeWithGrace(
          async (_reg) => { throw new TypeError('totally unrelated') },
          'x',
          seq(1),
        ),
      ).rejects.toThrow(TypeError)
    })
  })
})
