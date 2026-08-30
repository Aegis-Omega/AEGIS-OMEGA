// ============================================================
// Agent Registry — admission and lifecycle management
// EPISTEMIC TIER: T1
// Pattern: identical to ExtensionRegistry (immutable functional update).
// Agents with T3–T5 epistemic tier are constitutionally excluded.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import { EpistemicTier } from '../../core/types'
import type { AgentManifest } from '../types'
import { AgentRegistrationError, AGENT_MANIFEST_SCHEMA_VERSION } from '../types'

const ADMISSIBLE_AGENT_TIERS: readonly EpistemicTier[] = [
  EpistemicTier.T0,
  EpistemicTier.T1,
  EpistemicTier.T2,
]

export class AgentRegistry {
  private readonly _manifests: readonly AgentManifest[]

  private constructor(manifests: readonly AgentManifest[]) {
    this._manifests = manifests
  }

  static empty(): AgentRegistry {
    return new AgentRegistry(deepFreeze([]))
  }

  get manifests(): readonly AgentManifest[] { return this._manifests }

  register(manifest: AgentManifest, sequence: number): AgentRegistry {
    if (manifest.schema_version !== AGENT_MANIFEST_SCHEMA_VERSION) {
      throw new AgentRegistrationError(
        `Agent ${manifest.agent_id} schema version mismatch: expected ${AGENT_MANIFEST_SCHEMA_VERSION}`
      )
    }
    if (!ADMISSIBLE_AGENT_TIERS.includes(manifest.epistemic_tier as EpistemicTier)) {
      throw new AgentRegistrationError(
        `Agent ${manifest.agent_id} epistemic tier ${manifest.epistemic_tier} not admissible (T0–T2 required)`
      )
    }
    if (!manifest.is_replay_safe) {
      throw new AgentRegistrationError(
        `Agent ${manifest.agent_id} is not replay-safe — registration denied`
      )
    }
    if (this._manifests.some(m => m.agent_id === manifest.agent_id)) {
      throw new AgentRegistrationError(
        `Agent ${manifest.agent_id} is already registered`
      )
    }
    const registered: AgentManifest = deepFreeze({
      ...manifest,
      registered_at_sequence: sequence,
      status: 'registered' as const,
    })
    return new AgentRegistry(deepFreeze([...this._manifests, registered]))
  }

  retire(agent_id: string, sequence: number): AgentRegistry {
    void sequence
    const next = this._manifests.map(m =>
      m.agent_id === agent_id ? deepFreeze({ ...m, status: 'retired' as const }) : m
    )
    return new AgentRegistry(deepFreeze(next))
  }

  getActive(): readonly AgentManifest[] {
    return this._manifests.filter(m => m.status === 'registered' || m.status === 'active')
  }

  registeredCount(): number {
    return this._manifests.filter(m => m.status !== 'retired').length
  }
}
