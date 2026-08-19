import { sha256Hex } from '../core/hashing.js'
import type { FrontierStreamContext, StreamLeaseVerifier } from './frontier-inference-gateway.js'

export interface FrontierStreamEventReceipt extends FrontierStreamContext {
  readonly sequence: number
  readonly dataDigest: string
}

export class StreamFenceError extends Error {
  constructor(
    readonly code:
      | 'INVALID_LEASE'
      | 'STALE_GENERATION'
      | 'STALE_OR_FORGED_LEASE'
      | 'NON_MONOTONE_SEQUENCE',
    message: string,
  ) {
    super(message)
    this.name = 'StreamFenceError'
  }
}

export class InMemoryFrontierStreamLeaseRegistry implements StreamLeaseVerifier {
  private readonly leases = new Map<string, FrontierStreamContext>()

  async open(executionId: string, ownerIdentity: string, generation: number): Promise<FrontierStreamContext> {
    if (!executionId || !ownerIdentity || !Number.isInteger(generation) || generation < 0) {
      throw new StreamFenceError('INVALID_LEASE', 'execution, owner, and non-negative integer generation are required')
    }
    const previous = this.leases.get(executionId)
    if (previous !== undefined && generation <= previous.generation) {
      throw new StreamFenceError('STALE_GENERATION', 'stream lease generation must advance monotonically')
    }
    const fencingToken = await sha256Hex(new TextEncoder().encode(`${executionId}\u0000${ownerIdentity}\u0000${generation}`))
    const lease: FrontierStreamContext = Object.freeze({
      executionId,
      ownerIdentity,
      generation,
      fencingToken,
      lastSequence: -1,
    })
    this.leases.set(executionId, lease)
    return lease
  }

  async current(executionId: string): Promise<FrontierStreamContext | undefined> {
    return this.leases.get(executionId)
  }

  async verify(context: FrontierStreamContext): Promise<boolean> {
    const current = this.leases.get(context.executionId)
    return current !== undefined
      && current.ownerIdentity === context.ownerIdentity
      && current.generation === context.generation
      && current.fencingToken === context.fencingToken
      && current.lastSequence === context.lastSequence
  }

  async acceptEvent(context: FrontierStreamContext, sequence: number, data: string): Promise<FrontierStreamEventReceipt> {
    if (!await this.verify(context)) {
      throw new StreamFenceError('STALE_OR_FORGED_LEASE', 'stream event does not carry the current owner/generation/fence')
    }
    if (!Number.isInteger(sequence) || sequence !== context.lastSequence + 1) {
      throw new StreamFenceError('NON_MONOTONE_SEQUENCE', 'stream event sequence must advance exactly once')
    }
    const dataDigest = await sha256Hex(new TextEncoder().encode(data))
    const advanced: FrontierStreamContext = Object.freeze({
      executionId: context.executionId,
      ownerIdentity: context.ownerIdentity,
      generation: context.generation,
      fencingToken: context.fencingToken,
      lastSequence: sequence,
    })
    this.leases.set(context.executionId, advanced)
    return Object.freeze({ ...advanced, sequence, dataDigest })
  }

  revoke(executionId: string): void {
    this.leases.delete(executionId)
  }
}
