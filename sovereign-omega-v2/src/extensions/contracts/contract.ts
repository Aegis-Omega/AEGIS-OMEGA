// ============================================================
// Capability Contracts — least-privilege access grants for plugins
// EPISTEMIC TIER: T1
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { CapabilityContract } from '../types'
import { PluginAdmissionError } from '../types'

export function createContract(params: {
  plugin_id: string
  capability_id: string
  granted_scope: readonly string[]
  sequence_granted: number
  admissibility_reason: string
}): CapabilityContract {
  if (!params.admissibility_reason) {
    throw new PluginAdmissionError(
      `Contract for plugin ${params.plugin_id} must have an admissibility reason`
    )
  }
  const contract_id = `contract_${params.plugin_id}_${params.capability_id}_${params.sequence_granted}`
  return deepFreeze({
    contract_id,
    plugin_id: params.plugin_id,
    capability_id: params.capability_id,
    granted_scope: deepFreeze([...params.granted_scope]),
    sequence_granted: params.sequence_granted,
    is_least_privilege: true,
    admissibility_reason: params.admissibility_reason,
  })
}

export function expireContract(
  contract: CapabilityContract,
  sequence_expires: number
): CapabilityContract {
  if (contract.sequence_expires !== undefined) {
    throw new PluginAdmissionError(
      `Contract ${contract.contract_id} is already expired at sequence ${contract.sequence_expires}`
    )
  }
  return deepFreeze({ ...contract, sequence_expires })
}

export function isContractActive(
  contract: CapabilityContract,
  atSequence: number
): boolean {
  return (
    contract.sequence_granted <= atSequence &&
    (contract.sequence_expires === undefined || contract.sequence_expires > atSequence)
  )
}
