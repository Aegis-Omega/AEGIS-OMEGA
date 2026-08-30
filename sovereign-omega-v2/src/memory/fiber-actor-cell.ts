// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: SEQUENCE   — message ordering through the fiber inbox
//   replay_mapping:    PROPAGATE  — fiber processes E5 propagation (no LOCK authority)
//   topology_mapping:  DFA        — fiber state: ACTIVE → TERMINATED (irreversible seal)
//
// FiberActorCell — isolated fiber execution unit with Grace Loop integration.
//
// Constitutional translation of the Fiber Actor Cell with Grace Loop spec:
//   "Producer write-only viewport"   → deposit(handle): producer sends to fiber inbox
//   "Consumer read-only viewport"    → consume(message_id, tier): fiber claims + allocates work chunk
//   "Grace Loop auto-release"        → terminate(): autoReleases all inbox messages
//   "Slab-allocated execution frame" → SlabAllocator tracks fiber's own work chunks
//   "Fiber identity isolation"       → actor_id is the canonical consumer_id boundary
//
// Zero-copy guarantee: only SlabChunkHandles cross fiber boundaries.
// Fiber work chunks (allocated via consume) never escape as raw bytes.
//
// Fiber lifecycle: ACTIVE → (terminate) → TERMINATED (irreversible)

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { ZeroCopyChannel } from './zero-copy-channel.js'
import { SlabAllocator, type SlabTier, type SlabChunkHandle } from './slab-allocator.js'

export const FIBER_SCHEMA_VERSION = '1.0.0' as const

export interface FiberCertificate {
  readonly actor_id:           string
  readonly channel_pending:    number
  readonly channel_total_sent: number
  readonly slab_allocated:     number
  readonly channel_hash:       SHA256Hex
  readonly allocator_hash:     SHA256Hex
  readonly fiber_hash:         SHA256Hex  // hashValue({actor_id, channel_hash, allocator_hash, is_terminated, sequence})
  readonly is_terminated:      boolean
  readonly sequence:           SequenceNumber
  readonly schema_version:     typeof FIBER_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class FiberError extends Error {
  override readonly name = 'FiberError'
}

type FiberState = 'ACTIVE' | 'TERMINATED'

export class FiberActorCell {
  readonly #actor_id:    string
  readonly #producer_id: string
  readonly #channel:     ZeroCopyChannel
  readonly #allocator:   SlabAllocator
  readonly #state:       FiberState

  private constructor(
    actor_id:    string,
    producer_id: string,
    channel:     ZeroCopyChannel,
    allocator:   SlabAllocator,
    state:       FiberState,
  ) {
    this.#actor_id    = actor_id
    this.#producer_id = producer_id
    this.#channel     = channel
    this.#allocator   = allocator
    this.#state       = state
  }

  static create(actor_id: string, producer_id: string): FiberActorCell {
    return new FiberActorCell(
      actor_id, producer_id,
      ZeroCopyChannel.create(producer_id, actor_id),
      SlabAllocator.empty(),
      'ACTIVE',
    )
  }

  get actorId():         string  { return this.#actor_id }
  get pendingMessages(): number  { return this.#channel.pendingCount }
  get allocatedChunks(): number  { return this.#allocator.totalAllocated }
  get isTerminated():    boolean { return this.#state === 'TERMINATED' }

  // Producer deposits a handle into this fiber's inbox channel.
  async deposit(
    handle:   SlabChunkHandle,
    sequence: SequenceNumber,
  ): Promise<{ cell: FiberActorCell; message_id: SHA256Hex }> {
    if (this.#state === 'TERMINATED') throw new FiberError(
      `[FIBER_REJECT] actor '${this.#actor_id}' is terminated`,
    )
    const { channel, message } = await this.#channel.send(handle, sequence)
    return {
      cell: new FiberActorCell(this.#actor_id, this.#producer_id, channel, this.#allocator, 'ACTIVE'),
      message_id: message.message_id,
    }
  }

  // Fiber consumes a message: claims inbox handle, allocates own work chunk, releases message.
  // Zero-copy: producer's payload stays in its slab. Fiber allocates a separate work chunk.
  async consume(
    message_id: SHA256Hex,
    tier:       SlabTier,
    sequence:   SequenceNumber,
  ): Promise<{ cell: FiberActorCell; work_handle: SlabChunkHandle }> {
    if (this.#state === 'TERMINATED') throw new FiberError(
      `[FIBER_REJECT] actor '${this.#actor_id}' is terminated`,
    )
    const { channel: ch1 }          = await this.#channel.receive(message_id, sequence)
    const { allocator, handle: wh } = await this.#allocator.allocate(tier, sequence)
    const { channel: ch2 }          = await ch1.release(message_id, sequence)
    return {
      cell:        new FiberActorCell(this.#actor_id, this.#producer_id, ch2, allocator, 'ACTIVE'),
      work_handle: wh,
    }
  }

  // Grace Loop: terminate this fiber — autoRelease all inbox messages, seal state.
  // Idempotent: second call returns released_count=0.
  async terminate(sequence: SequenceNumber): Promise<{ cell: FiberActorCell; released_count: number }> {
    if (this.#state === 'TERMINATED') return { cell: this, released_count: 0 }
    const { channel, released_count } = await this.#channel.autoRelease(this.#actor_id, sequence)
    return {
      cell: new FiberActorCell(this.#actor_id, this.#producer_id, channel, this.#allocator, 'TERMINATED'),
      released_count,
    }
  }

  async certify(sequence: SequenceNumber): Promise<FiberCertificate> {
    const chCert   = await this.#channel.certify(sequence)
    const slabCert = await this.#allocator.certify(sequence)
    const is_terminated = this.#state === 'TERMINATED'
    const fiber_hash = await hashValue({
      actor_id:      this.#actor_id,
      channel_hash:  chCert.channel_hash,
      allocator_hash: slabCert.allocator_hash,
      is_terminated,
      sequence:      sequence.toString(),
    }) as SHA256Hex
    return deepFreeze<FiberCertificate>({
      actor_id:           this.#actor_id,
      channel_pending:    chCert.pending_count,
      channel_total_sent: chCert.total_sent,
      slab_allocated:     slabCert.total_allocated,
      channel_hash:       chCert.channel_hash,
      allocator_hash:     slabCert.allocator_hash,
      fiber_hash,
      is_terminated,
      sequence,
      schema_version:     FIBER_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }
}
