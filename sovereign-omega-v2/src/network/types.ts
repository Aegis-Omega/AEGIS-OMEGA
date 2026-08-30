// ============================================================
// SOVEREIGN OMEGA — Byzantine Transport Interface Types
// EPISTEMIC TIER: T2 · Gate 24
//
// Pure types for deterministic Byzantine fault-tolerant message
// passing simulation. No network I/O — all operations are pure
// functions over message queues and sorted arrays.
//
// Invariants:
//   - No Date.now() — timestamps are injected parameters
//   - No Set/Map in queue state — arrays only (RFC 8785 safe)
//   - Anti-equivocation: (sender, sequence) is unique per payload_hash
//   - n >= 3f+1 for Byzantine safety (quorum invariant)
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'

// ─── Branded Primitives ────────────────────────────────────

export type PeerId = string & { readonly __brand: 'PeerId' }
export type MessageId = string & { readonly __brand: 'MessageId' }

// ─── Core Structures ───────────────────────────────────────

/**
 * A gossip message ready for replay-deterministic delivery.
 * timestamp_ms is injected from the event substrate — never Date.now().
 */
export interface ReplayMessage {
  readonly message_id: MessageId
  readonly sender: PeerId
  readonly recipient: PeerId
  readonly payload_hash: SHA256Hex     // hash of the content being gossiped
  readonly sequence: SequenceNumber
  readonly timestamp_ms: number        // injected — never Date.now()
}

/**
 * Network topology and Byzantine fault tolerance configuration.
 * INVARIANT: peers.length >= 3 * max_byzantine_peers + 1
 */
export interface NetworkConfig {
  readonly peers: readonly PeerId[]
  readonly max_byzantine_peers: number   // f — must satisfy peers.length >= 3f+1
  readonly message_ttl_sequence: number  // how many rounds a message lives
}

// ─── Delivery Result ───────────────────────────────────────

export type MessageDeliveryStatus = 'DELIVERED' | 'DROPPED' | 'DUPLICATE'

export interface DeliveryResult {
  readonly message: ReplayMessage
  readonly status: MessageDeliveryStatus
  readonly reason?: string
}

// ─── Simulation Result ─────────────────────────────────────

export interface SimulationResult {
  readonly delivered: readonly ReplayMessage[]
  readonly dropped: readonly ReplayMessage[]
  readonly equivocations: number
  /** True iff no anti-equivocation violations were detected. */
  readonly is_safe: boolean
}

// ─── Error ─────────────────────────────────────────────────

export class NetworkError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NetworkError'
  }
}
