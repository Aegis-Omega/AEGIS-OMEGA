// ============================================================
// Capability Guard — Security Boundary (RULE-02 enforcement)
// ALL environment bindings must pass through this module.
// No direct host mutations permitted outside governed interfaces.
// EPISTEMIC TIER: T0 (mechanically enforced)
// ============================================================

import { deepFreeze } from '../../core/immutable'
import { EpistemicTier } from '../../core/types'
import type {
  HostCapability,
  CapabilityGrant,
  EnvironmentMutation,
} from '../types'
import { CapabilityAdmissionError, MutationRejectedError } from '../types'

// Only T0–T2 capabilities are constitutionally admissible.
const ADMISSIBLE_TIERS = new Set<EpistemicTier>([
  EpistemicTier.T0,
  EpistemicTier.T1,
  EpistemicTier.T2,
])

export class CapabilityGuard {
  private readonly _capabilities: readonly HostCapability[] = []
  private readonly _grants: readonly CapabilityGrant[] = []

  get capabilities(): readonly HostCapability[] { return this._capabilities }
  get grants(): readonly CapabilityGrant[] { return this._grants }

  register(capability: HostCapability): CapabilityGuard {
    if (!ADMISSIBLE_TIERS.has(capability.provenance_tier as EpistemicTier)) {
      throw new CapabilityAdmissionError(
        `Capability ${capability.capability_id} requires T0–T2 provenance; got ${capability.provenance_tier}`
      )
    }
    if (!capability.entropy_impact_bounded) {
      throw new CapabilityAdmissionError(
        `Capability ${capability.capability_id} has unbounded entropy impact — disqualified`
      )
    }
    if (!capability.ontology_term) {
      throw new CapabilityAdmissionError(
        `Capability ${capability.capability_id} lacks ontology registration`
      )
    }
    const next: readonly HostCapability[] = deepFreeze([...this._capabilities, capability])
    return Object.assign(
      Object.create(CapabilityGuard.prototype) as CapabilityGuard,
      { _capabilities: next, _grants: this._grants }
    )
  }

  grant(params: {
    capability_id: string
    granted_to: string
    scope: readonly string[]
    sequence_granted: number
  }): { guard: CapabilityGuard; grant: CapabilityGrant } {
    const cap = this._capabilities.find(c => c.capability_id === params.capability_id)
    if (!cap) {
      throw new CapabilityAdmissionError(
        `Unknown capability: ${params.capability_id}. Must register before granting.`
      )
    }
    const grant: CapabilityGrant = deepFreeze({
      grant_id: `grant_${params.capability_id}_${params.granted_to}_${params.sequence_granted}`,
      capability_id: params.capability_id,
      granted_to: params.granted_to,
      scope: deepFreeze([...params.scope]),
      sequence_granted: params.sequence_granted,
      least_privilege: true,
    })
    const nextGrants: readonly CapabilityGrant[] = deepFreeze([...this._grants, grant])
    const nextGuard = Object.assign(
      Object.create(CapabilityGuard.prototype) as CapabilityGuard,
      { _capabilities: this._capabilities, _grants: nextGrants }
    )
    return { guard: nextGuard, grant }
  }

  revoke(grant_id: string, sequence_revoked: number): CapabilityGuard {
    const nextGrants: readonly CapabilityGrant[] = deepFreeze(
      this._grants.map(g =>
        g.grant_id === grant_id ? deepFreeze({ ...g, sequence_revoked }) : g
      )
    )
    return Object.assign(
      Object.create(CapabilityGuard.prototype) as CapabilityGuard,
      { _capabilities: this._capabilities, _grants: nextGrants }
    )
  }

  isAuthorized(mutation: EnvironmentMutation): boolean {
    return this._grants.some(
      g =>
        g.capability_id === mutation.admitted_by &&
        g.sequence_revoked === undefined &&
        g.sequence_granted <= mutation.sequence
    )
  }

  assertAuthorized(mutation: EnvironmentMutation): void {
    if (!this.isAuthorized(mutation)) {
      throw new MutationRejectedError(
        `Mutation ${mutation.mutation_id} not authorized: no active grant for capability ${mutation.admitted_by}`
      )
    }
  }

  capabilitySurfaceArea(): number {
    return this._capabilities.length
  }
}

export function createCapabilityGuard(): CapabilityGuard {
  return Object.assign(
    Object.create(CapabilityGuard.prototype) as CapabilityGuard,
    { _capabilities: deepFreeze([]), _grants: deepFreeze([]) }
  )
}
