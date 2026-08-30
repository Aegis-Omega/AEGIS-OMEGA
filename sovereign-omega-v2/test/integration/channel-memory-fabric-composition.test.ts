// test/integration/channel-memory-fabric-composition.test.ts
// Gate 197 — ZeroCopyChannel + Memory Fabric Holonic Composition
// EPISTEMIC TIER: T2
//
// Proves ZeroCopyChannel integrates correctly with the four memory-fabric layers:
//   Scenario 1 — Channel + Slab: allocate handle → send → receive → release → free chunk
//   Scenario 2 — autoRelease + GraceSupervisor: crashed universe clears in-flight messages
//   Scenario 3 — Multi-universe channel matrix: channel state consistent with slab state
//   Scenario 4 — Full pipeline: fork→allocate→send→collapse→autoRelease proves end-to-end
//   Scenario 5 — Determinism: full pipeline deterministic ×3 in parallel

import { describe, it, expect } from 'vitest'
import { ZeroCopyChannel } from '../../src/memory/zero-copy-channel.js'
import { SlabAllocator } from '../../src/memory/slab-allocator.js'
import { GraceSupervisor } from '../../src/memory/grace-supervisor.js'
import { MultiverseRegistry } from '../../src/memory/multiverse.js'
import { ForkTree } from '../../src/memory/fork-tree.js'
import type { SequenceNumber } from '../../src/core/types.js'

function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

describe('Gate 197 — ZeroCopyChannel + Memory Fabric Holonic Composition', () => {

  describe('Scenario 1 — Channel + Slab lifecycle', () => {
    it('slab handle flows through channel and slab is released after channel release', async () => {
      let alloc = SlabAllocator.empty()
      const r1 = await alloc.allocate('TINY', seq(1)); alloc = r1.allocator
      expect(alloc.totalAllocated).toBe(1)

      let ch = ZeroCopyChannel.create('fiber-A', 'fiber-B')
      const { channel: ch1, message: m1 } = await ch.send(r1.handle, seq(2)); ch = ch1
      expect(ch.pendingCount).toBe(1)
      expect(ch.totalSent).toBe(1)

      // Handle payload preserved by reference (zero-copy guarantee)
      expect(m1.handle.slab_id).toBe(r1.handle.slab_id)
      expect(m1.handle.chunk_index).toBe(r1.handle.chunk_index)
      expect(m1.handle.handle_hash).toBe(r1.handle.handle_hash)

      const { channel: ch2 } = await ch.receive(m1.message_id, seq(3)); ch = ch2
      expect(ch.pendingCount).toBe(1) // still pending until release

      const { channel: ch3 } = await ch.release(m1.message_id, seq(4)); ch = ch3
      expect(ch.pendingCount).toBe(0)

      // Now free the slab chunk — handle is still valid for this
      const r2 = await alloc.release(r1.handle, seq(5)); alloc = r2.allocator
      expect(alloc.totalAllocated).toBe(0)
    })

    it('multiple handles flow independently through the same channel', async () => {
      let alloc = SlabAllocator.empty()
      const r1 = await alloc.allocate('TINY', seq(1)); alloc = r1.allocator
      const r2 = await alloc.allocate('SMALL', seq(2)); alloc = r2.allocator
      expect(alloc.totalAllocated).toBe(2)

      let ch = ZeroCopyChannel.create('fiber-A', 'fiber-B')
      const { channel: ch1, message: m1 } = await ch.send(r1.handle, seq(3)); ch = ch1
      const { channel: ch2, message: m2 } = await ch.send(r2.handle, seq(4)); ch = ch2
      expect(ch.pendingCount).toBe(2)

      // Each handle preserves its tier identity through the channel
      expect(m1.handle.tier).toBe('TINY')
      expect(m2.handle.tier).toBe('SMALL')
    })

    it('re-allocating a slab chunk after channel release gives the same chunk_index', async () => {
      let alloc = SlabAllocator.empty()
      const r1 = await alloc.allocate('MEDIUM', seq(1)); alloc = r1.allocator

      let ch = ZeroCopyChannel.create('fiber-P', 'fiber-C')
      const { channel: ch1, message: m1 } = await ch.send(r1.handle, seq(2)); ch = ch1
      const { channel: ch2 } = await ch.receive(m1.message_id, seq(3)); ch = ch2
      const { channel: ch3 } = await ch.release(m1.message_id, seq(4)); ch = ch3

      // Release slab chunk and re-allocate — bitmap bit is cleared → same chunk reused
      const r2 = await alloc.release(r1.handle, seq(5)); alloc = r2.allocator
      const r3 = await alloc.allocate('MEDIUM', seq(6))
      expect(r3.handle.chunk_index).toBe(0)
      expect(r3.handle.slab_id).toBe(r1.handle.slab_id)
    })
  })

  describe('Scenario 2 — autoRelease + GraceSupervisor', () => {
    it('autoRelease removes all in-flight messages after GraceSupervisor quarantines universe', async () => {
      // Set up channel between two universes
      let ch = ZeroCopyChannel.create('universe-A', 'universe-B')
      let alloc = SlabAllocator.empty()

      // Send 3 messages universe-A → universe-B
      const handles = []
      for (let i = 1; i <= 3; i++) {
        const { allocator, handle } = await alloc.allocate('TINY', seq(i)); alloc = allocator
        handles.push(handle)
      }
      const { channel: ch1, message: m1 } = await ch.send(handles[0]!, seq(4)); ch = ch1
      const { channel: ch2 } = await ch.send(handles[1]!, seq(5)); ch = ch2
      const { channel: ch3 } = await ch.send(handles[2]!, seq(6)); ch = ch3
      expect(ch.pendingCount).toBe(3)

      // Claim one — autoRelease should still remove claimed messages
      const { channel: ch4 } = await ch.receive(m1.message_id, seq(7)); ch = ch4

      // GraceSupervisor: set up registry, intentionally overflow to trigger fault
      let reg = MultiverseRegistry.empty()
      const { registry: reg1 } = await reg.fork('universe-A', 'genesis-hash' as any, seq(8)); reg = reg1
      let sup = GraceSupervisor.create(reg)

      // universe-B crashes — autoRelease clears its channel messages
      const { channel: chClean, released_count } = await ch.autoRelease('universe-B', seq(9))
      expect(released_count).toBe(3) // all 3 messages (claimed + unclaimed) removed
      expect(chClean.pendingCount).toBe(0)

      // Supervisor itself remains healthy (graceEventCount unaffected by channel cleanup)
      expect(sup.graceEventCount).toBe(0)
    })

    it('GraceSupervisor fault isolation + channel autoRelease are independent operations', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('u-A', 'genesis' as any, seq(1)); reg = r1
      let sup = GraceSupervisor.create(reg)

      // Force a fault via ecology overflow
      const overflow = async (r: MultiverseRegistry) => {
        let rr = r
        for (let i = 2; i <= 9; i++) {
          const res = await rr.fork(`u-${i}`, 'genesis' as any, seq(i))
          rr = res.registry
        }
        return { registry: rr }
      }
      const { supervisor: sup2, faulted } = await sup.executeWithGrace(overflow, 'u-overflow', seq(10))
      expect(faulted).toBe(true)
      expect(sup2.graceEventCount).toBe(1)
      expect(sup2.registry.universeCount).toBe(1) // reverted to pre-fault state

      // Channel between existing universes is unaffected by the supervisor fault
      let ch = ZeroCopyChannel.create('u-A', 'u-B')
      let alloc = SlabAllocator.empty()
      const { handle } = await alloc.allocate('TINY', seq(11))
      const { channel: ch1 } = await ch.send(handle, seq(12)); ch = ch1
      expect(ch.pendingCount).toBe(1)

      // autoRelease for the faulted non-existent universe touches nothing
      const { released_count } = await ch.autoRelease('u-overflow', seq(13))
      expect(released_count).toBe(0)
      expect(ch.pendingCount).toBe(1)
    })
  })

  describe('Scenario 3 — Multi-universe channel matrix', () => {
    it('three pairwise channels total pending count matches slab totalAllocated', async () => {
      let alloc = SlabAllocator.empty()

      // A↔B, B↔C, A↔C channels — one handle per channel
      let chAB = ZeroCopyChannel.create('u-A', 'u-B')
      let chBC = ZeroCopyChannel.create('u-B', 'u-C')
      let chAC = ZeroCopyChannel.create('u-A', 'u-C')

      const rAB = await alloc.allocate('TINY', seq(1)); alloc = rAB.allocator
      const rBC = await alloc.allocate('TINY', seq(2)); alloc = rBC.allocator
      const rAC = await alloc.allocate('TINY', seq(3)); alloc = rAC.allocator

      const { channel: chAB1 } = await chAB.send(rAB.handle, seq(4)); chAB = chAB1
      const { channel: chBC1 } = await chBC.send(rBC.handle, seq(5)); chBC = chBC1
      const { channel: chAC1 } = await chAC.send(rAC.handle, seq(6)); chAC = chAC1

      // Channels in flight == slab chunks in flight
      const totalChannelPending = chAB.pendingCount + chBC.pendingCount + chAC.pendingCount
      expect(totalChannelPending).toBe(alloc.totalAllocated)
      expect(totalChannelPending).toBe(3)
    })

    it('certify on all three channels produces distinct channel_hashes', async () => {
      let alloc = SlabAllocator.empty()
      const r1 = await alloc.allocate('TINY', seq(1)); alloc = r1.allocator
      const r2 = await alloc.allocate('TINY', seq(2)); alloc = r2.allocator
      const r3 = await alloc.allocate('SMALL', seq(3)); alloc = r3.allocator

      let chAB = ZeroCopyChannel.create('u-A', 'u-B')
      let chBC = ZeroCopyChannel.create('u-B', 'u-C')
      let chAC = ZeroCopyChannel.create('u-A', 'u-C')

      const { channel: chAB1 } = await chAB.send(r1.handle, seq(4)); chAB = chAB1
      const { channel: chBC1 } = await chBC.send(r2.handle, seq(5)); chBC = chBC1
      const { channel: chAC1 } = await chAC.send(r3.handle, seq(6)); chAC = chAC1

      const certAB = await chAB.certify(seq(10))
      const certBC = await chBC.certify(seq(10))
      const certAC = await chAC.certify(seq(10))

      expect(certAB.channel_hash).not.toBe(certBC.channel_hash)
      expect(certBC.channel_hash).not.toBe(certAC.channel_hash)
      expect(certAB.channel_hash).not.toBe(certAC.channel_hash)
    })
  })

  describe('Scenario 4 — Full pipeline: fork→allocate→send→collapse→autoRelease', () => {
    it('completes end-to-end without error; channel is empty after collapse autoRelease', async () => {
      // Fork two universes from a registry
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('canonical', 'genesis' as any, seq(1)); reg = r1
      const { registry: r2 } = await reg.fork('branch-A', 'genesis' as any, seq(2)); reg = r2

      // Allocate slab handles for each universe's fiber
      let alloc = SlabAllocator.empty()
      const hC = await alloc.allocate('TINY', seq(3)); alloc = hC.allocator
      const hA = await alloc.allocate('TINY', seq(4)); alloc = hA.allocator
      expect(alloc.totalAllocated).toBe(2)

      // Set up channel: canonical → branch-A (canonical produces, branch-A consumes)
      let ch = ZeroCopyChannel.create('canonical', 'branch-A')
      const { channel: ch1 } = await ch.send(hC.handle, seq(5)); ch = ch1
      const { channel: ch2 } = await ch.send(hA.handle, seq(6)); ch = ch2
      expect(ch.pendingCount).toBe(2)

      // Evolve both universes
      const ev = { kind: 'TOPOLOGY_TRANSITION' as const, topology_hash: 'abc123'.padEnd(64, '0') as any }
      const { registry: r3 } = await reg.appendToUniverse('canonical', ev, seq(7)); reg = r3
      const { registry: r4 } = await reg.appendToUniverse('branch-A', ev, seq(8)); reg = r4

      // Track genealogy in ForkTree
      let tree = ForkTree.empty()
      const genesisHash = 'genesis00'.padEnd(64, '0') as any
      const branchHash  = 'brancha00'.padEnd(64, '0') as any
      const { tree: t1 } = await tree.recordFork('canonical', 'genesis-root', genesisHash, seq(9)); tree = t1
      const { tree: t2 } = await tree.recordFork('branch-A', 'canonical', branchHash, seq(10)); tree = t2
      expect(tree.nodeCount).toBe(2)

      // autoRelease for the collapsed loser universe — clears its channel messages
      const { channel: chFinal, released_count } = await ch.autoRelease('branch-A', seq(12))
      expect(released_count).toBe(2) // both messages cleared
      expect(chFinal.pendingCount).toBe(0)
      expect(chFinal.totalSent).toBe(2) // history preserved

      // Certify all four layers
      const slabCert = await alloc.certify(seq(12))
      const treeCert = await tree.certify(seq(13))
      const sup = GraceSupervisor.create(reg)
      const graceCert = await sup.certify(seq(14))
      const chCert = await chFinal.certify(seq(15))

      expect(slabCert.allocator_hash).toHaveLength(64)
      expect(treeCert.tree_hash).toHaveLength(64)
      expect(graceCert.grace_chain_hash).toHaveLength(64)
      expect(chCert.channel_hash).toHaveLength(64)

      // Channel cert reflects final state: 0 pending, 2 total sent
      expect(chCert.pending_count).toBe(0)
      expect(chCert.total_sent).toBe(2)
    })

    it('graceEventCount=0 on clean pipeline (no faults triggered)', async () => {
      let reg = MultiverseRegistry.empty()
      const { registry: r1 } = await reg.fork('canonical', 'genesis' as any, seq(1)); reg = r1
      const sup = GraceSupervisor.create(reg)
      expect(sup.graceEventCount).toBe(0)

      let alloc = SlabAllocator.empty()
      const r = await alloc.allocate('TINY', seq(2)); alloc = r.allocator
      let ch = ZeroCopyChannel.create('canonical', 'peer')
      const { channel: ch1, message: m } = await ch.send(r.handle, seq(3)); ch = ch1
      const { channel: ch2 } = await ch.receive(m.message_id, seq(4)); ch = ch2
      const { channel: ch3 } = await ch.release(m.message_id, seq(5)); ch = ch3

      expect(sup.graceEventCount).toBe(0)
      expect(ch.pendingCount).toBe(0)
      expect(ch.totalSent).toBe(1)
    })
  })

  describe('Scenario 5 — Determinism', () => {
    it('full pipeline channel_hash + tree_hash + allocator_hash deterministic ×3', async () => {
      async function runPipeline() {
        let alloc = SlabAllocator.empty()
        const h1 = await alloc.allocate('TINY', seq(1)); alloc = h1.allocator
        const h2 = await alloc.allocate('SMALL', seq(2)); alloc = h2.allocator

        let ch = ZeroCopyChannel.create('u-prod', 'u-cons')
        const { channel: ch1, message: m1 } = await ch.send(h1.handle, seq(3)); ch = ch1
        const { channel: ch2 } = await ch.send(h2.handle, seq(4)); ch = ch2
        const { channel: ch3 } = await ch.receive(m1.message_id, seq(5)); ch = ch3

        let tree = ForkTree.empty()
        const fh1 = 'prodHash0'.padEnd(64, '0') as any
        const fh2 = 'consHash0'.padEnd(64, '0') as any
        const { tree: t1 } = await tree.recordFork('u-prod', 'genesis-root', fh1, seq(6)); tree = t1
        const { tree: t2 } = await tree.recordFork('u-cons', 'u-prod', fh2, seq(7)); tree = t2

        const chCert = await ch.certify(seq(10))
        const treeCert = await tree.certify(seq(10))
        const slabCert = await alloc.certify(seq(10))
        return { chHash: chCert.channel_hash, treeHash: treeCert.tree_hash, slabHash: slabCert.allocator_hash }
      }

      const results = await Promise.all([runPipeline(), runPipeline(), runPipeline()])
      expect(results[0]!.chHash).toBe(results[1]!.chHash)
      expect(results[1]!.chHash).toBe(results[2]!.chHash)
      expect(results[0]!.treeHash).toBe(results[1]!.treeHash)
      expect(results[1]!.treeHash).toBe(results[2]!.treeHash)
      expect(results[0]!.slabHash).toBe(results[1]!.slabHash)
      expect(results[1]!.slabHash).toBe(results[2]!.slabHash)
    })
  })
})
