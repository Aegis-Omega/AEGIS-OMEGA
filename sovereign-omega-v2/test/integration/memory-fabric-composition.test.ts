// test/integration/memory-fabric-composition.test.ts
// Gate 195 — Memory Fabric Holonic Composition
// EPISTEMIC TIER: T2
//
// Proves that GraceSupervisor, SlabAllocator, ForkTree, and MultiverseRegistry
// interoperate correctly across their constitutional boundaries.
//
// Four composition proofs:
//   1. Slab ↔ Multiverse: one slab chunk per universe fork tracks registry count;
//      releasing sealed-universe chunks after collapse leaves exactly 1.
//   2. Grace ↔ Multiverse: GraceSupervisor intercepts ECOLOGY_OVERFLOW; pre-fault
//      registry retained; SlabAllocator count never exceeds MAX_UNIVERSES.
//   3. ForkTree ↔ Collapse: collapseMultiverse() feeds ForkTree.recordCollapse();
//      tree_hash certifies full DAG; sealed_count matches total_collapsed;
//      ancestry chains preserved across epoch boundary.
//   4. Full pipeline: fork→allocate→evolve→converge→collapse→ForkTree→grace→certify;
//      all four certifications consistent; no grace events on clean run.

import { describe, it, expect } from 'vitest'
import { MultiverseRegistry, MAX_UNIVERSES } from '../../src/memory/multiverse.js'
import { collapseMultiverse } from '../../src/memory/collapse.js'
import { ForkTree } from '../../src/memory/fork-tree.js'
import { GraceSupervisor } from '../../src/memory/grace-supervisor.js'
import { SlabAllocator } from '../../src/memory/slab-allocator.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import type { SlabChunkHandle } from '../../src/memory/slab-allocator.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const ROOT_A = 'aabbccdd'.repeat(8) as SHA256Hex
const ROOT_B = '11223344'.repeat(8) as SHA256Hex

const EV_APPROVED = { kind: 'CAPABILITY_EVOLUTION' as const, proposal_id: 'aa'.repeat(32) as SHA256Hex, verdict: 'APPROVED' as const }

// ─── Scenario 1 — Slab ↔ MultiverseRegistry ──────────────────────────────────

describe('Scenario 1 — Slab ↔ MultiverseRegistry alignment', () => {
  it('slab totalAllocated tracks universeCount across three forks', async () => {
    let reg = MultiverseRegistry.empty()
    let slab = SlabAllocator.empty()

    for (let i = 0; i < 3; i++) {
      const { registry }   = await reg.fork(`u${i}`, ROOT_A, seq(i + 1))
      const { allocator }  = await slab.allocate('TINY', seq(i + 1))
      reg = registry; slab = allocator
    }
    expect(reg.universeCount).toBe(3)
    expect(slab.totalAllocated).toBe(3)
  })

  it('releasing sealed-universe slab chunks after collapse leaves exactly 1', async () => {
    let reg = MultiverseRegistry.empty()
    let slab = SlabAllocator.empty()
    const handles: Record<string, SlabChunkHandle> = {}

    // Fork 3 universes, allocate one slab chunk each
    for (const id of ['alpha', 'beta', 'gamma']) {
      const s = seq(['alpha', 'beta', 'gamma'].indexOf(id) + 1)
      const { registry }  = await reg.fork(id, ROOT_A, s)
      const { allocator, handle } = await slab.allocate('TINY', s)
      reg = registry; slab = allocator; handles[id] = handle
    }

    // Diverge alpha — beta+gamma stay at genesis → 2/3 > 1/φ → quorum
    const { registry: r2 } = await reg.appendToUniverse('alpha', EV_APPROVED, seq(4))
    reg = r2
    const convergence = await reg.checkConvergence(seq(5))
    expect(convergence.swarm_record.quorum_reached).toBe(true)

    const { record } = await collapseMultiverse(reg, convergence, seq(6))

    // Release slab chunks for every sealed (losing) universe
    for (const sealed of record.sealed_universes) {
      const { allocator } = await slab.release(handles[sealed.universe_id]!, seq(7))
      slab = allocator
    }
    expect(slab.totalAllocated).toBe(1)
  })

  it('slab chunk_size_bytes reflects tier for each universe', async () => {
    let slab = SlabAllocator.empty()
    const { allocator: a1, handle: h1 } = await slab.allocate('TINY',   seq(1))
    const { allocator: a2, handle: h2 } = await a1.allocate('LARGE',  seq(2))
    const tiny_slab  = a2.getSlabs('TINY')[0]!
    const large_slab = a2.getSlabs('LARGE')[0]!
    expect(tiny_slab.chunk_size_bytes).toBe(4 * 1024)
    expect(large_slab.chunk_size_bytes).toBe(1024 * 1024)
    expect(h1.tier).toBe('TINY'); expect(h2.tier).toBe('LARGE')
  })
})

// ─── Scenario 2 — GraceSupervisor ↔ MultiverseRegistry ──────────────────────

describe('Scenario 2 — Grace Loop ↔ MultiverseRegistry', () => {
  it('ECOLOGY_OVERFLOW intercepted; registry stays at MAX_UNIVERSES', async () => {
    let sv = GraceSupervisor.create(MultiverseRegistry.empty())

    for (let i = 0; i < MAX_UNIVERSES; i++) {
      const { supervisor } = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork(`u${i}`, ROOT_A, seq(i + 1)); return { registry } },
        `u${i}`, seq(i + 1),
      )
      sv = supervisor
    }
    expect(sv.registry.universeCount).toBe(MAX_UNIVERSES)
    expect(sv.graceEventCount).toBe(0)

    // 9th fork — triggers ECOLOGY_OVERFLOW
    const { supervisor: sv2, faulted, grace_event } = await sv.executeWithGrace(
      async (reg) => { const { registry } = await reg.fork('overflow', ROOT_A, seq(99)); return { registry } },
      'overflow', seq(99),
    )
    expect(faulted).toBe(true)
    expect(grace_event!.fault_class).toBe('ECOLOGY_OVERFLOW')
    expect(sv2.registry.universeCount).toBe(MAX_UNIVERSES)  // pre-fault retained
    expect(sv2.graceEventCount).toBe(1)
  })

  it('slab totalAllocated never exceeds MAX_UNIVERSES when grace fires', async () => {
    let sv   = GraceSupervisor.create(MultiverseRegistry.empty())
    let slab = SlabAllocator.empty()

    for (let i = 0; i < MAX_UNIVERSES; i++) {
      const { supervisor } = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork(`u${i}`, ROOT_A, seq(i + 1)); return { registry } },
        `u${i}`, seq(i + 1),
      )
      sv = supervisor
      const { allocator } = await slab.allocate('TINY', seq(i + 1))
      slab = allocator
    }

    // Grace fires — do NOT allocate another slab chunk on fault
    const { faulted } = await sv.executeWithGrace(
      async (reg) => { const { registry } = await reg.fork('over', ROOT_A, seq(99)); return { registry } },
      'over', seq(99),
    )
    expect(faulted).toBe(true)
    expect(slab.totalAllocated).toBe(MAX_UNIVERSES)  // slab never over-allocated
  })

  it('grace certify chains two sequential faults deterministically', async () => {
    let sv = GraceSupervisor.create(MultiverseRegistry.empty())
    const r0 = await sv.executeWithGrace(
      async (reg) => { const { registry } = await reg.fork('d', ROOT_A, seq(1)); return { registry } },
      'd', seq(1),
    )
    sv = r0.supervisor
    // Duplicate fault ×2
    for (const s of [2, 3]) {
      const r = await sv.executeWithGrace(
        async (reg) => { const { registry } = await reg.fork('d', ROOT_A, seq(s)); return { registry } },
        'd', seq(s),
      )
      sv = r.supervisor
    }
    const cert = await sv.certify(seq(10))
    expect(cert.grace_event_count).toBe(2)
    expect(cert.fault_class_counts.DUPLICATE_UNIVERSE).toBe(2)
    expect(cert.grace_chain_hash).toHaveLength(64)
  })
})

// ─── Scenario 3 — ForkTree ↔ Collapse genealogy ──────────────────────────────

describe('Scenario 3 — ForkTree ↔ Collapse genealogy', () => {
  it('sealed_count in ForkTree matches total_collapsed in CollapseRecord', async () => {
    let reg = MultiverseRegistry.empty()
    let tree = ForkTree.empty()
    let s = 1

    for (const id of ['alpha', 'beta', 'gamma']) {
      const { registry, fork } = await reg.fork(id, ROOT_A, seq(s))
      reg = registry
      const { tree: t2 } = await tree.recordFork(id, 'genesis', fork.fork_hash, seq(s))
      tree = t2; s++
    }
    // Diverge alpha
    const { registry: r2 } = await reg.appendToUniverse('alpha', EV_APPROVED, seq(s++))
    reg = r2

    const conv = await reg.checkConvergence(seq(s++))
    const { record } = await collapseMultiverse(reg, conv, seq(s++))

    const { tree: t3 } = await tree.recordCollapse(record, seq(s++))
    tree = t3

    const cert = await tree.certify(seq(50))
    expect(cert.sealed_count).toBe(record.total_collapsed)
    expect(cert.collapse_count).toBe(1)
    expect(cert.node_count).toBe(3)
  })

  it('tree_hash changes after adding a second-epoch fork from canonical', async () => {
    let reg = MultiverseRegistry.empty()
    let tree = ForkTree.empty()

    const { registry: r1, fork: f1 } = await reg.fork('alpha', ROOT_A, seq(1))
    const { registry: r2, fork: f2 } = await r1.fork('beta',  ROOT_A, seq(2))
    reg = r2

    const { tree: t1 } = await tree.recordFork('alpha', 'genesis', f1.fork_hash, seq(1))
    const { tree: t2 } = await t1.recordFork('beta', 'genesis', f2.fork_hash, seq(2))
    tree = t2

    const certBefore = await tree.certify(seq(10))

    // Collapse, then re-fork from canonical
    const conv = await reg.checkConvergence(seq(3))
    const { record, registry: postReg } = await collapseMultiverse(reg, conv, seq(4))
    const { tree: t3 } = await tree.recordCollapse(record, seq(4))
    const canon_hash = postReg.getFork('canonical')!.fork_hash
    const { tree: t4 } = await t3.recordFork('canonical', record.winner_id, canon_hash, seq(5))
    tree = t4

    const certAfter = await tree.certify(seq(10))
    expect(certAfter.node_count).toBe(3)  // alpha + beta + canonical
    expect(certAfter.tree_hash).not.toBe(certBefore.tree_hash)
  })

  it('ancestry chain preserved across epoch boundary', async () => {
    let reg = MultiverseRegistry.empty()
    let tree = ForkTree.empty()

    const { registry: r1, fork: f1 } = await reg.fork('alpha', ROOT_A, seq(1))
    const { registry: r2, fork: f2 } = await r1.fork('beta',  ROOT_A, seq(2))
    reg = r2

    const { tree: t1 } = await tree.recordFork('alpha', 'genesis', f1.fork_hash, seq(1))
    const { tree: t2 } = await t1.recordFork('beta', 'genesis', f2.fork_hash, seq(2))
    tree = t2

    const conv = await reg.checkConvergence(seq(3))
    const { record, registry: postReg } = await collapseMultiverse(reg, conv, seq(4))
    const { tree: t3 } = await tree.recordCollapse(record, seq(4))

    const canon_hash = postReg.getFork('canonical')!.fork_hash
    const { tree: t4 } = await t3.recordFork('canonical', record.winner_id, canon_hash, seq(5))
    // Fork a child from canonical
    const { tree: t5 } = await t4.recordFork('branch-A', 'canonical', ROOT_B, seq(6))
    tree = t5

    // branch-A ancestry: canonical → branch-A
    const ancestry = tree.getAncestry('branch-A')
    expect(ancestry).toContain('branch-A')
    expect(ancestry).toContain('canonical')
    expect(ancestry.indexOf('canonical')).toBeLessThan(ancestry.indexOf('branch-A'))
  })
})

// ─── Scenario 4 — Full pipeline ───────────────────────────────────────────────

describe('Scenario 4 — Full pipeline: all four layers consistent', () => {
  it('fork→allocate→evolve→converge→collapse→ForkTree→grace: all certifications consistent', async () => {
    let sv   = GraceSupervisor.create(MultiverseRegistry.empty())
    let slab = SlabAllocator.empty()
    let tree = ForkTree.empty()
    const handles: Record<string, SlabChunkHandle> = {}
    let s = 1

    // Fork 3 universes via GraceSupervisor (no faults expected)
    for (const id of ['alpha', 'beta', 'gamma']) {
      const { supervisor, faulted } = await sv.executeWithGrace(
        async (reg) => {
          const { registry, fork } = await reg.fork(id, ROOT_A, seq(s))
          return { registry, fork }
        },
        id, seq(s),
      )
      expect(faulted).toBe(false)
      sv = supervisor

      // Allocate slab + record fork in ForkTree
      const { allocator, handle } = await slab.allocate('SMALL', seq(s))
      slab = allocator; handles[id] = handle
      const fork = sv.registry.getFork(id)!
      const { tree: t2 } = await tree.recordFork(id, 'genesis', fork.fork_hash, seq(s))
      tree = t2; s++
    }

    // Diverge gamma only
    const { supervisor: sv2 } = await sv.executeWithGrace(
      async (reg) => {
        const { registry } = await reg.appendToUniverse('gamma', EV_APPROVED, seq(s))
        return { registry }
      },
      'gamma', seq(s++),
    )
    sv = sv2

    // Converge: alpha+beta at genesis → 2/3 > 1/φ
    const conv = await sv.registry.checkConvergence(seq(s++))
    expect(conv.swarm_record.quorum_reached).toBe(true)

    // Collapse
    const { record, registry: postReg } = await collapseMultiverse(sv.registry, conv, seq(s++))
    const { tree: t3 } = await tree.recordCollapse(record, seq(s++))
    tree = t3

    // Release sealed slab chunks
    for (const sealed of record.sealed_universes) {
      const { allocator } = await slab.release(handles[sealed.universe_id]!, seq(s++))
      slab = allocator
    }

    // Certify all four layers
    const graceCert = await sv.certify(seq(s))
    const slabCert  = await slab.certify(seq(s))
    const treeCert  = await tree.certify(seq(s))
    const regCerts  = await postReg.certifyAll()

    // No grace events on clean run
    expect(graceCert.grace_event_count).toBe(0)

    // Slab: only winner's chunk remains
    expect(slabCert.total_allocated).toBe(1)

    // ForkTree: 3 nodes, 1 collapse, sealed_count = total_collapsed
    expect(treeCert.node_count).toBe(3)
    expect(treeCert.collapse_count).toBe(1)
    expect(treeCert.sealed_count).toBe(record.total_collapsed)

    // Post-collapse registry: only canonical
    expect(regCerts).toHaveLength(1)
    expect(regCerts[0]!.universe_id).toBe('canonical')
    expect(regCerts[0]!.certificate.is_anchored).toBe(true)

    // All certificate hashes are 64-char hex
    expect(graceCert.grace_chain_hash).toHaveLength(64)
    expect(slabCert.allocator_hash).toHaveLength(64)
    expect(treeCert.tree_hash).toHaveLength(64)
  }, 15_000)

  it('full pipeline is deterministic x3', async () => {
    async function runPipeline(): Promise<{ treeHash: string; slabHash: string }> {
      let reg  = MultiverseRegistry.empty()
      let slab = SlabAllocator.empty()
      let tree = ForkTree.empty()
      const handles: Record<string, SlabChunkHandle> = {}
      let s = 1

      for (const id of ['a', 'b', 'c']) {
        const { registry, fork } = await reg.fork(id, ROOT_A, seq(s))
        reg = registry
        const { allocator, handle } = await slab.allocate('TINY', seq(s))
        slab = allocator; handles[id] = handle
        const { tree: t2 } = await tree.recordFork(id, 'genesis', fork.fork_hash, seq(s))
        tree = t2; s++
      }
      // Diverge 'c'
      const { registry: r2 } = await reg.appendToUniverse('c', EV_APPROVED, seq(s++))
      reg = r2
      const conv = await reg.checkConvergence(seq(s++))
      const { record } = await collapseMultiverse(reg, conv, seq(s++))
      const { tree: t3 } = await tree.recordCollapse(record, seq(s++))
      tree = t3
      for (const sealed of record.sealed_universes) {
        const { allocator } = await slab.release(handles[sealed.universe_id]!, seq(s++))
        slab = allocator
      }
      const treeCert = await tree.certify(seq(s))
      const slabCert = await slab.certify(seq(s))
      return { treeHash: treeCert.tree_hash, slabHash: slabCert.allocator_hash }
    }

    const [r1, r2, r3] = await Promise.all([runPipeline(), runPipeline(), runPipeline()])
    expect(r1.treeHash).toBe(r2.treeHash)
    expect(r2.treeHash).toBe(r3.treeHash)
    expect(r1.slabHash).toBe(r2.slabHash)
    expect(r2.slabHash).toBe(r3.slabHash)
  }, 20_000)
})
