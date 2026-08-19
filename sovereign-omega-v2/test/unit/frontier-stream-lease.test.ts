import { describe, expect, it } from 'vitest'
import { InMemoryFrontierStreamLeaseRegistry, StreamFenceError } from '../../src/api/frontier-stream-lease.js'


describe('InMemoryFrontierStreamLeaseRegistry', () => {
  it('opens a deterministic current lease and satisfies the gateway verifier contract', async () => {
    const registry = new InMemoryFrontierStreamLeaseRegistry()
    const lease = await registry.open('exec-1', 'operator:tarik', 1)

    expect(await registry.verify(lease)).toBe(true)
    expect(lease.lastSequence).toBe(-1)
    expect(lease.fencingToken).toMatch(/^[a-f0-9]{64}$/)
  })

  it('advances exactly one SSE event at a time and emits a digest-bound receipt', async () => {
    const registry = new InMemoryFrontierStreamLeaseRegistry()
    const lease = await registry.open('exec-1', 'operator:tarik', 1)

    const receipt = await registry.acceptEvent(lease, 0, 'data: hello')

    expect(receipt.sequence).toBe(0)
    expect(receipt.dataDigest).toMatch(/^[a-f0-9]{64}$/)
    expect((await registry.current('exec-1'))?.lastSequence).toBe(0)
  })

  it('rejects stale generation after a newer owner lease is opened', async () => {
    const registry = new InMemoryFrontierStreamLeaseRegistry()
    const oldLease = await registry.open('exec-1', 'operator:tarik', 1)
    const newLease = await registry.open('exec-1', 'agent:worker-2', 2)

    expect(await registry.verify(oldLease)).toBe(false)
    expect(await registry.verify(newLease)).toBe(true)
    await expect(registry.acceptEvent(oldLease, 0, 'stale')).rejects.toBeInstanceOf(StreamFenceError)
  })

  it('rejects owner/fence forgery even when execution and generation match', async () => {
    const registry = new InMemoryFrontierStreamLeaseRegistry()
    const lease = await registry.open('exec-1', 'operator:tarik', 4)

    expect(await registry.verify({ ...lease, ownerIdentity: 'agent:forged' })).toBe(false)
    expect(await registry.verify({ ...lease, fencingToken: '0'.repeat(64) })).toBe(false)
  })

  it('rejects duplicate or skipped SSE sequence numbers', async () => {
    const registry = new InMemoryFrontierStreamLeaseRegistry()
    const lease = await registry.open('exec-1', 'operator:tarik', 1)
    await registry.acceptEvent(lease, 0, 'first')
    const current = await registry.current('exec-1')
    expect(current).toBeDefined()

    await expect(registry.acceptEvent(current!, 0, 'duplicate')).rejects.toMatchObject({ code: 'NON_MONOTONE_SEQUENCE' })
    await expect(registry.acceptEvent(current!, 2, 'skipped')).rejects.toMatchObject({ code: 'NON_MONOTONE_SEQUENCE' })
  })

  it('rejects non-increasing lease generations', async () => {
    const registry = new InMemoryFrontierStreamLeaseRegistry()
    await registry.open('exec-1', 'operator:tarik', 3)

    await expect(registry.open('exec-1', 'operator:tarik', 3)).rejects.toMatchObject({ code: 'STALE_GENERATION' })
    await expect(registry.open('exec-1', 'operator:tarik', 2)).rejects.toMatchObject({ code: 'STALE_GENERATION' })
  })
})
