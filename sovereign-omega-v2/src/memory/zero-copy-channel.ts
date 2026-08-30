// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH      — message_hash chains every payload transfer event
//   replay_mapping:    PROPAGATE — channel transfers are E5 propagation (no LOCK authority)
//   topology_mapping:  CONSENSUS — channel connects producer_id ↔ consumer_id (two universes)
//
// ZeroCopyChannel — zero-copy inter-fiber message passing via SlabChunkHandle.
//
// Constitutional translation of the Dual-Viewport Zero-Copy IMC spec:
//   "Producer write-only viewport" → send(handle): submits SlabChunkHandle to channel
//   "Consumer read-only viewport"  → receive(message_id): claims handle; payload stays in slab
//   "Host supervisor mediation"    → ZeroCopyChannel enforces handle ownership invariants
//   "Auto-release on crash"        → autoRelease(universe_id): GraceSupervisor hook
//   "Bounds verification"          → duplicate-handle guard + claim-before-release guard
//
// Zero-copy guarantee: only SlabChunkHandle (slab_id + chunk_index + handle_hash — a few
// integers + SHA-256) crosses the channel boundary. The actual payload bytes never move.
//
// Message lifecycle: send → receive (is_claimed=true) → release (removed from pending)
// Auto-release: when a universe is quarantined, all its in-flight messages are cleaned up.

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { SlabChunkHandle } from './slab-allocator.js'

export const CHANNEL_SCHEMA_VERSION = '1.0.0' as const

export interface ChannelMessage {
  readonly message_id:   SHA256Hex   // hashValue({producer_id, consumer_id, handle_hash, sequence})
  readonly producer_id:  string
  readonly consumer_id:  string
  readonly handle:       SlabChunkHandle   // slab chunk carrying the payload — never copied
  readonly message_hash: SHA256Hex         // hashValue({message_id, handle_hash, sequence})
  readonly sequence:     SequenceNumber
  readonly is_claimed:   boolean           // true after consumer calls receive()
  readonly schema_version: typeof CHANNEL_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface ChannelCertificate {
  readonly producer_id:  string
  readonly consumer_id:  string
  readonly pending_count: number
  readonly total_sent:    number
  readonly channel_hash:  SHA256Hex   // hashValue({producer_id, consumer_id, message_hashes, total_sent, sequence})
  readonly sequence:      SequenceNumber
  readonly schema_version: typeof CHANNEL_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class ChannelError extends Error {
  override readonly name = 'ChannelError'
}

export class ZeroCopyChannel {
  readonly #producer_id: string
  readonly #consumer_id: string
  readonly #messages:    ReadonlyMap<SHA256Hex, ChannelMessage>
  readonly #total_sent:  number

  private constructor(
    producer_id: string,
    consumer_id: string,
    messages:    ReadonlyMap<SHA256Hex, ChannelMessage>,
    total_sent:  number,
  ) {
    this.#producer_id = producer_id
    this.#consumer_id = consumer_id
    this.#messages    = messages
    this.#total_sent  = total_sent
  }

  static create(producer_id: string, consumer_id: string): ZeroCopyChannel {
    return new ZeroCopyChannel(producer_id, consumer_id, new Map(), 0)
  }

  get pendingCount(): number { return this.#messages.size }
  get totalSent():    number { return this.#total_sent }

  // Producer submits a slab handle. Throws if same handle already in flight.
  async send(
    handle: SlabChunkHandle,
    sequence: SequenceNumber,
  ): Promise<{ channel: ZeroCopyChannel; message: ChannelMessage }> {
    for (const m of this.#messages.values()) {
      if (m.handle.handle_hash === handle.handle_hash) throw new ChannelError(
        `[CHANNEL_REJECT] handle '${handle.handle_hash}' already in flight`,
      )
    }
    const message_id = await hashValue({
      producer_id: this.#producer_id,
      consumer_id: this.#consumer_id,
      handle_hash: handle.handle_hash,
      sequence:    sequence.toString(),
    }) as SHA256Hex

    const message_hash = await hashValue({
      message_id,
      handle_hash: handle.handle_hash,
      sequence:    sequence.toString(),
    }) as SHA256Hex

    const message = deepFreeze<ChannelMessage>({
      message_id, producer_id: this.#producer_id, consumer_id: this.#consumer_id,
      handle, message_hash, sequence, is_claimed: false,
      schema_version: CHANNEL_SCHEMA_VERSION, is_replay_reconstructable: true,
    })
    const nm = new Map(this.#messages)
    nm.set(message_id, message)
    return { channel: new ZeroCopyChannel(this.#producer_id, this.#consumer_id, nm, this.#total_sent + 1), message }
  }

  // Consumer claims a message. Throws if unknown or already claimed.
  async receive(
    message_id: SHA256Hex,
    _sequence: SequenceNumber,
  ): Promise<{ channel: ZeroCopyChannel; message: ChannelMessage }> {
    const msg = this.#messages.get(message_id)
    if (!msg)       throw new ChannelError(`[CHANNEL_REJECT] message '${message_id}' not found`)
    if (msg.is_claimed) throw new ChannelError(`[CHANNEL_REJECT] message '${message_id}' already claimed`)
    const claimed = deepFreeze<ChannelMessage>({ ...msg, is_claimed: true })
    const nm = new Map(this.#messages)
    nm.set(message_id, claimed)
    return { channel: new ZeroCopyChannel(this.#producer_id, this.#consumer_id, nm, this.#total_sent), message: claimed }
  }

  // Consumer releases a claimed message (removes from pending). Must claim first.
  async release(
    message_id: SHA256Hex,
    _sequence: SequenceNumber,
  ): Promise<{ channel: ZeroCopyChannel }> {
    const msg = this.#messages.get(message_id)
    if (!msg)        throw new ChannelError(`[CHANNEL_REJECT] message '${message_id}' not found`)
    if (!msg.is_claimed) throw new ChannelError(`[CHANNEL_REJECT] message '${message_id}' not claimed — claim before release`)
    const nm = new Map(this.#messages)
    nm.delete(message_id)
    return { channel: new ZeroCopyChannel(this.#producer_id, this.#consumer_id, nm, this.#total_sent) }
  }

  // GraceSupervisor hook: remove all pending messages involving a crashed universe.
  async autoRelease(
    universe_id: string,
    _sequence: SequenceNumber,
  ): Promise<{ channel: ZeroCopyChannel; released_count: number }> {
    const nm = new Map(this.#messages); let count = 0
    for (const [id, msg] of this.#messages) {
      if (msg.producer_id === universe_id || msg.consumer_id === universe_id) {
        nm.delete(id); count++
      }
    }
    return { channel: new ZeroCopyChannel(this.#producer_id, this.#consumer_id, nm, this.#total_sent), released_count: count }
  }

  getMessages(): readonly ChannelMessage[] {
    return Object.freeze([...this.#messages.values()])
  }

  async certify(sequence: SequenceNumber): Promise<ChannelCertificate> {
    const msgs = [...this.#messages.values()].sort((a, b) => a.message_id.localeCompare(b.message_id))
    const channel_hash = await hashValue({
      producer_id: this.#producer_id, consumer_id: this.#consumer_id,
      message_hashes: msgs.map(m => m.message_hash),
      total_sent: this.#total_sent, sequence: sequence.toString(),
    }) as SHA256Hex
    return deepFreeze<ChannelCertificate>({
      producer_id: this.#producer_id, consumer_id: this.#consumer_id,
      pending_count: msgs.length, total_sent: this.#total_sent,
      channel_hash, sequence, schema_version: CHANNEL_SCHEMA_VERSION, is_replay_reconstructable: true,
    })
  }
}
