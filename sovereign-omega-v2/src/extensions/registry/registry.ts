// ============================================================
// Plugin Registry — admission and lifecycle management
// EPISTEMIC TIER: T1
// Plugins are admitted only when all constitutional checks pass.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import { EpistemicTier } from '../../core/types'
import type { PluginManifest, CapabilityContract, ExtensionTelemetry } from '../types'
import { PluginAdmissionError, PLUGIN_MANIFEST_SCHEMA_VERSION } from '../types'

// Plugins with T3–T5 epistemic tier are constitutionally excluded from admission.
const ADMISSIBLE_PLUGIN_TIERS = [
  EpistemicTier.T0,
  EpistemicTier.T1,
  EpistemicTier.T2,
]

export class ExtensionRegistry {
  private readonly _manifests: readonly PluginManifest[]
  private readonly _contracts: readonly CapabilityContract[]

  private constructor(
    manifests: readonly PluginManifest[],
    contracts: readonly CapabilityContract[]
  ) {
    this._manifests = manifests
    this._contracts = contracts
  }

  static empty(): ExtensionRegistry {
    return new ExtensionRegistry(deepFreeze([]), deepFreeze([]))
  }

  get manifests(): readonly PluginManifest[] { return this._manifests }
  get contracts(): readonly CapabilityContract[] { return this._contracts }

  admit(manifest: PluginManifest, sequence: number): ExtensionRegistry {
    if (manifest.schema_version !== PLUGIN_MANIFEST_SCHEMA_VERSION) {
      throw new PluginAdmissionError(
        `Plugin ${manifest.plugin_id} schema version mismatch: expected ${PLUGIN_MANIFEST_SCHEMA_VERSION}`
      )
    }
    if (!ADMISSIBLE_PLUGIN_TIERS.includes(manifest.epistemic_tier as EpistemicTier)) {
      throw new PluginAdmissionError(
        `Plugin ${manifest.plugin_id} epistemic tier ${manifest.epistemic_tier} is not admissible (T0–T2 required)`
      )
    }
    if (!manifest.is_replay_safe) {
      throw new PluginAdmissionError(
        `Plugin ${manifest.plugin_id} is not replay-safe — admission denied`
      )
    }
    if (this._manifests.some(m => m.plugin_id === manifest.plugin_id)) {
      throw new PluginAdmissionError(
        `Plugin ${manifest.plugin_id} is already registered`
      )
    }
    const admitted: PluginManifest = deepFreeze({
      ...manifest,
      admitted_at_sequence: sequence,
      status: 'admitted' as const,
    })
    return new ExtensionRegistry(
      deepFreeze([...this._manifests, admitted]),
      this._contracts
    )
  }

  evict(plugin_id: string, sequence: number): ExtensionRegistry {
    const nextManifests = this._manifests.map(m =>
      m.plugin_id === plugin_id
        ? deepFreeze({ ...m, status: 'evicted' as const })
        : m
    )
    // Expire all contracts for this plugin
    const nextContracts = this._contracts.map(c =>
      c.plugin_id === plugin_id && c.sequence_expires === undefined
        ? deepFreeze({ ...c, sequence_expires: sequence })
        : c
    )
    return new ExtensionRegistry(
      deepFreeze(nextManifests),
      deepFreeze(nextContracts)
    )
  }

  addContract(contract: CapabilityContract): ExtensionRegistry {
    const manifest = this._manifests.find(m => m.plugin_id === contract.plugin_id)
    if (!manifest) {
      throw new PluginAdmissionError(
        `Cannot grant contract to unregistered plugin: ${contract.plugin_id}`
      )
    }
    if (manifest.status !== 'admitted') {
      throw new PluginAdmissionError(
        `Cannot grant contract to plugin with status: ${manifest.status}`
      )
    }
    return new ExtensionRegistry(
      this._manifests,
      deepFreeze([...this._contracts, deepFreeze(contract)])
    )
  }

  getActiveContracts(plugin_id: string): readonly CapabilityContract[] {
    return this._contracts.filter(
      c => c.plugin_id === plugin_id && c.sequence_expires === undefined
    )
  }

  telemetryFor(plugin_id: string, mutationReceipts: readonly {
    plugin_id: string
    entropy_contribution_fixed: number
    is_replay_reconstructable: boolean
  }[]): ExtensionTelemetry {
    const receipts = mutationReceipts.filter(r => r.plugin_id === plugin_id)
    const replaySafe = receipts.filter(r => r.is_replay_reconstructable).length
    const entropyUsed = receipts.reduce((acc, r) => acc + r.entropy_contribution_fixed, 0)
    const activeContracts = this.getActiveContracts(plugin_id).length
    const manifest = this._manifests.find(m => m.plugin_id === plugin_id)

    return Object.freeze({
      plugin_id,
      mutation_count: receipts.length,
      entropy_used_fixed: entropyUsed,
      replay_safe_ratio: receipts.length === 0 ? 1 : replaySafe / receipts.length,
      capability_grants_active: activeContracts,
      sandbox_isolation_intact: manifest?.status === 'admitted',
    })
  }

  admittedCount(): number {
    return this._manifests.filter(m => m.status === 'admitted').length
  }
}
