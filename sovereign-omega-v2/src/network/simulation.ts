// ============================================================
// SOVEREIGN OMEGA — Byzantine Network Simulation
// EPISTEMIC TIER: T2 · Gate 24
//
// ByzantineSimulation models a network with f Byzantine peers.
// simulate() is a pure function: same inputs → same outputs.
// No I/O, no Date.now(), no global state.
//
// Safety criterion: is_safe = (equivocations === 0)
// A Byzantine peer may send conflicting messages for the same
// (sender, sequence). Each such conflict is one equivocation.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { DeterministicMessageQueue } from './queue.js'
import type {
  ReplayMessage,
  NetworkConfig,
  SimulationResult,
} from './types.js'
import { NetworkError } from './types.js'

/**
 * Run a Byzantine simulation over a batch of messages.
 *
 * Pure function — deterministic given identical inputs.
 * Messages are delivered in lexicographic message_id order.
 *
 * Anti-equivocation conflicts increment `equivocations` rather
 * than propagating as thrown errors; the simulation records
 * them and marks is_safe=false.
 *
 * @param config   Network topology and BFT parameters
 * @param messages Proposed messages (may include Byzantine traffic)
 * @returns        Frozen SimulationResult
 */
export function simulate(
  config: NetworkConfig,
  messages: readonly ReplayMessage[],
): SimulationResult {
  // Validate BFT quorum invariant: n >= 3f+1
  if (config.peers.length < 3 * config.max_byzantine_peers + 1) {
    throw new NetworkError(
      `BFT quorum violation: peers=${config.peers.length} < 3f+1=${3 * config.max_byzantine_peers + 1}`,
    )
  }

  // Valid recipient set — sorted for deterministic lookup
  const validRecipients = new Set(config.peers)

  const delivered: ReplayMessage[] = []
  const dropped: ReplayMessage[] = []
  let equivocations = 0

  // Process messages through the deterministic queue
  let queue = DeterministicMessageQueue.create()

  for (const msg of messages) {
    // Drop messages addressed to unknown peers
    if (!validRecipients.has(msg.recipient)) {
      dropped.push(msg)
      continue
    }

    try {
      const [nextQueue, result] = queue.enqueue(msg)
      queue = nextQueue

      /* c8 ignore next 3 -- queue only returns DELIVERED or DUPLICATE; DROPPED is structurally unreachable */
      if (result.status === 'DROPPED') {
        dropped.push(msg)
      }
      // DELIVERED and DUPLICATE both stay in queue for drain
    } catch (err) {
      if (err instanceof NetworkError) {
        // Anti-equivocation violation — record and drop the offending message
        equivocations++
        dropped.push(msg)
      } else {
        /* c8 ignore next -- queue.enqueue() only throws NetworkError; non-NetworkError path is structurally unreachable */
        throw err
      }
    }
  }

  // Drain the queue in deterministic order
  const [, orderedMessages] = queue.drain()
  for (const msg of orderedMessages) {
    delivered.push(msg)
  }

  return deepFreeze<SimulationResult>({
    delivered,
    dropped,
    equivocations,
    is_safe: equivocations === 0,
  })
}
