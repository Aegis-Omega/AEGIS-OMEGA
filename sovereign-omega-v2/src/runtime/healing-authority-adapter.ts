// ============================================================
// SOVEREIGN OMEGA — Agentic Healing Authority Adapter V1
// EPISTEMIC TIER: T0/T1/T2 composition boundary
//
// This adapter does not approve mutation. It only proves that a proposed
// repair is eligible to ENTER the existing authority path:
//
//   sealed operator registry
//   + known mutation operator
//   + component K-bound
//   + anchored/bounded martingale
//
// Final durable mutation approval remains outside this adapter.
// ============================================================

import { hashValue } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import type { AdaptiveLineageEntry } from '../frame/adaptive-lineage.js'
import {
  assertMartingaleAnchored,
  certifyMartingale,
} from '../constitutional/martingale.js'
import {
  capacityRegistry,
  mutationOperatorRegistry,
  type CapacityDeclarationRegistry,
  type MutationOperatorRegistry,
} from '../verifier/registry.js'
import type {
  HealingAuthorityPreflight,
} from './agentic-self-healing.js'

export const HEALING_AUTHORITY_ADAPTER_SCHEMA_VERSION = '1.0.0' as const

export interface HealingAuthorityAdapterOptions {
  readonly lineageEntries: () => readonly AdaptiveLineageEntry[]
  readonly operatorRegistry?: MutationOperatorRegistry
  readonly capacityRegistry?: CapacityDeclarationRegistry
}

export function createHealingAuthorityPreflight(
  options: HealingAuthorityAdapterOptions,
): HealingAuthorityPreflight {
  const operators = options.operatorRegistry ?? mutationOperatorRegistry
  const capacities = options.capacityRegistry ?? capacityRegistry

  return {
    async mutationAuthorityActive(): Promise<boolean> {
      if (!operators.isSealed()) return false

      const cert = await certifyMartingale(options.lineageEntries())
      try {
        assertMartingaleAnchored(cert)
        return true
      } catch {
        return false
      }
    },

    async preflight(input) {
      let eligible = true
      let reason_code = 'SEALED_REGISTRY_K_BOUND_AND_MARTINGALE_OK'

      if (!operators.isSealed()) {
        eligible = false
        reason_code = 'MUTATION_OPERATOR_REGISTRY_UNSEALED'
      }

      if (eligible) {
        try {
          operators.validate([input.operator_id])
        } catch {
          eligible = false
          reason_code = 'UNKNOWN_MUTATION_OPERATOR'
        }
      }

      if (eligible) {
        try {
          if (!capacities.checkKBound(
            input.observation.component_id,
            input.delta_k,
          )) {
            eligible = false
            reason_code = 'K_BOUND_EXCEEDED'
          }
        } catch {
          eligible = false
          reason_code = 'CAPACITY_DECLARATION_MISSING'
        }
      }

      const martingale = await certifyMartingale(options.lineageEntries())
      if (eligible) {
        try {
          assertMartingaleAnchored(martingale)
        } catch {
          eligible = false
          reason_code = 'MARTINGALE_SUSPENDED'
        }
      }

      const evidence_hash = await hashValue({
        schema_version: HEALING_AUTHORITY_ADAPTER_SCHEMA_VERSION,
        operator_registry_sealed: operators.isSealed(),
        operator_id: input.operator_id,
        component_id: input.observation.component_id,
        delta_k: input.delta_k,
        plan_hash: input.plan.plan_hash,
        martingale_certificate_hash: martingale.certificate_hash,
        martingale_is_anchored: martingale.is_anchored,
        martingale_entropy_bounded: martingale.entropy_bounded,
        eligible,
        reason_code,
      }) as SHA256Hex

      return {
        eligible,
        reason_code,
        evidence_hash,
      }
    },
  }
}
