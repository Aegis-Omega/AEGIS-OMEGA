// ============================================================
// SOVEREIGN OMEGA — Network Kernel
// EPISTEMIC TIER: T2 · Gate 24
//
// Pure functions for constructing and routing messages in the
// Byzantine transport simulation layer. No network I/O, no
// timers, no global state.
//
// Invariants:
//   - No Date.now() — timestamps are injected parameters
//   - computeMessageId uses FNV-1a (deterministic, no crypto)
//   - broadcastVote produces exactly one ReplayMessage per peer
//   - All outputs are deeply frozen
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { PeerId, MessageId, ReplayMessage, NetworkConfig } from './types.js'

// ─── FNV-1a Constants (32-bit) ─────────────────────────────

const FNV_OFFSET_BASIS = 0x811c9dc5 >>> 0
const FNV_PRIME = 0x01000193 >>> 0

/**
 * FNV-1a 32-bit hash over a UTF-8 string.
 * Deterministic, no crypto API, no I/O.
 */
function fnv1a32(input: string): number {
  let hash = FNV_OFFSET_BASIS
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i)
    // Unsigned 32-bit multiply (avoid signed overflow via >>> 0)
    hash = Math.imul(hash, FNV_PRIME) >>> 0
  }
  return hash >>> 0
}

/**
 * Compute a deterministic MessageId from the four components that uniquely
 * identify a message in the network layer.
 *
 * Uses FNV-1a to avoid any dependency on the crypto subsystem.
 * Output format: "fnv1a:<hex8>:<sender>:<recipient>:<seq>"
 * This keeps the id human-readable and globally unique in test scenarios.
 */
export function computeMessageId(
  sender: PeerId,
  recipient: PeerId,
  payloadHash: SHA256Hex,
  sequence: SequenceNumber,
): MessageId {
  const raw = `${sender}|${recipient}|${payloadHash}|${String(sequence)}`
  const hash = fnv1a32(raw)
  const hex = hash.toString(16).padStart(8, '0')
  return `fnv1a:${hex}:${sender}:${recipient}:${String(sequence)}` as MessageId
}

/**
 * Broadcast a vote to all peers listed in the config (excluding the sender).
 *
 * Returns one frozen ReplayMessage per recipient. The messages are returned
 * in lexicographic peer-id order to guarantee deterministic output.
 *
 * @param sender      The peer originating the vote
 * @param payloadHash SHA-256 of the vote content being gossiped
 * @param sequence    Sequence number for this broadcast round
 * @param timestampMs Injected timestamp — never Date.now()
 * @param config      Network topology
 * @returns           Sorted, frozen array of ReplayMessage
 */
export function broadcastVote(
  sender: PeerId,
  payloadHash: SHA256Hex,
  sequence: SequenceNumber,
  timestampMs: number,
  config: NetworkConfig,
): readonly ReplayMessage[] {
  // Collect recipients (all peers except sender), sorted deterministically
  const recipients = config.peers
    .filter(p => p !== sender)
    .slice()
    .sort()

  const messages: ReplayMessage[] = recipients.map(recipient => {
    const message_id = computeMessageId(sender, recipient, payloadHash, sequence)
    return deepFreeze<ReplayMessage>({
      message_id,
      sender,
      recipient,
      payload_hash: payloadHash,
      sequence,
      timestamp_ms: timestampMs,
    })
  })

  return Object.freeze(messages)
}
