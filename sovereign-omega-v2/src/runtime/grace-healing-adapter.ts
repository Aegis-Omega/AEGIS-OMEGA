// ============================================================
// SOVEREIGN OMEGA — Grace → Agentic Healing Adapter V1
// EPISTEMIC TIER: T2
//
// GraceSupervisor already performs the safe recovery primitive:
// a faulted operation never commits and the pre-fault immutable registry remains.
//
// This adapter:
//   1. content-addresses the retained registry;
//   2. maps GraceEvent → HealingObservation;
//   3. exposes a VolatileRecoveryAdapter that confirms, but does not mutate,
//      the retained pre-fault state.
// ============================================================

import { hashValue } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import {
  GraceSupervisor,
  type GraceEvent,
} from '../memory/grace-supervisor.js'
import type { MultiverseRegistry } from '../memory/multiverse.js'
import type {
  HealingObservation,
  VolatileRecoveryAdapter,
} from './agentic-self-healing.js'

export const GRACE_HEALING_ADAPTER_SCHEMA_VERSION = '1.0.0' as const

export async function hashMultiverseRegistry(
  registry: MultiverseRegistry,
): Promise<SHA256Hex> {
  const certifications = await registry.certifyAll()

  return await hashValue({
    schema_version: GRACE_HEALING_ADAPTER_SCHEMA_VERSION,
    universe_count: registry.universeCount,
    universes: certifications.map(item => ({
      universe_id: item.universe_id,
      fork_hash: item.fork_hash,
      lineage_length: item.lineage_length,
      martingale_certificate_hash: item.certificate.certificate_hash,
      terminal_hash: item.certificate.terminal_hash,
      is_anchored: item.certificate.is_anchored,
      entropy_bounded: item.certificate.entropy_bounded,
    })),
  }) as SHA256Hex
}

export async function healingObservationFromGrace(
  supervisor: GraceSupervisor,
  event: GraceEvent,
  component_id: string,
): Promise<HealingObservation> {
  if (!component_id) throw new Error('component_id required')

  const retained_state_hash = await hashMultiverseRegistry(supervisor.registry)

  return {
    incident_id: `grace:${event.grace_hash}`,
    component_id,
    fault_code: event.fault_class,
    severity: 'FAULT',
    sequence: event.sequence,
    state_hash: retained_state_hash,
    pre_fault_state_hash: retained_state_hash,
    evidence_hash: event.grace_hash,
    replay_diverged: false,
    is_replay_reconstructable: true,
  }
}

export function createGraceRetentionRecoveryAdapter(
  supervisor: GraceSupervisor,
): VolatileRecoveryAdapter {
  return {
    async revertToPreFault({ observation }) {
      const retained_state_hash = await hashMultiverseRegistry(supervisor.registry)
      return {
        applied: observation.pre_fault_state_hash === retained_state_hash,
        state_hash: retained_state_hash,
      }
    },
  }
}
