// ============================================================
// AEGIS Provider-Native Conductor V1
// EPISTEMIC TIER: T1 — deterministic code orchestration
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import type { ProviderCapabilityV1, ProviderMeshSnapshotV1 } from './provider-mesh.js'
import {
  selectProviderNativeAgentV1,
  type ProviderNativeAgentRegistryV1,
} from './provider-native-agents.js'

export const PROVIDER_NATIVE_CONDUCTOR_SCHEMA_VERSION = '1.0.0' as const

export interface ProviderConductorAdapterResultV1 {
  readonly output: string
  readonly native_receipt_root: SHA256Hex
}

export interface ProviderConductorAdapterV1 {
  readonly provider_id: string
  execute(task: string): Promise<ProviderConductorAdapterResultV1>
}

export interface ProviderNativeConductorReceiptV1 {
  readonly schema_version: typeof PROVIDER_NATIVE_CONDUCTOR_SCHEMA_VERSION
  readonly outcome: 'EXECUTED' | 'DENIED'
  readonly provider_id: string | null
  readonly agent_id: string | null
  readonly provider_selection_receipt_root: SHA256Hex
  readonly native_receipt_root: SHA256Hex | null
  readonly task_hash: SHA256Hex
  readonly output_hash: SHA256Hex | null
  readonly authority_effect: 'NONE'
  readonly receipt_root: SHA256Hex
}

export function createProviderNativeConductorV1(options: {
  readonly adapters: readonly ProviderConductorAdapterV1[]
}): {
  execute(input: {
    readonly snapshot: ProviderMeshSnapshotV1
    readonly registry: ProviderNativeAgentRegistryV1
    readonly task: string
    readonly required_capabilities: readonly ProviderCapabilityV1[]
    readonly preferred_provider_order?: readonly string[]
    readonly current_generation: string
    readonly max_observation_age_generations: string
  }): Promise<{ readonly output: string | null; readonly receipt: ProviderNativeConductorReceiptV1 }>
} {
  const adapterMap = new Map(options.adapters.map(adapter => [adapter.provider_id, adapter]))
  if (adapterMap.size !== options.adapters.length) throw new TypeError('duplicate conductor provider adapter')

  return {
    async execute(input) {
      if (!input.task.trim()) throw new TypeError('task must be non-empty')
      const task_hash = await sha256Hex(canonicalizeJCS({
        domain: 'AEGIS_PROVIDER_NATIVE_CONDUCTOR_TASK_V1',
        task: input.task,
      })) as SHA256Hex

      const selection = await selectProviderNativeAgentV1(input.snapshot, input.registry, {
        required_capabilities: input.required_capabilities,
        allowed_providers: [...adapterMap.keys()],
        preferred_provider_order: input.preferred_provider_order,
        current_generation: input.current_generation,
        max_observation_age_generations: input.max_observation_age_generations,
      })

      if (selection.outcome !== 'SELECTED' || selection.provider_id === null) {
        const body = {
          schema_version: PROVIDER_NATIVE_CONDUCTOR_SCHEMA_VERSION,
          outcome: 'DENIED' as const,
          provider_id: null,
          agent_id: null,
          provider_selection_receipt_root: selection.receipt_root,
          native_receipt_root: null,
          task_hash,
          output_hash: null,
          authority_effect: 'NONE' as const,
        }
        const receipt_root = await sha256Hex(canonicalizeJCS({
          domain: 'AEGIS_PROVIDER_NATIVE_CONDUCTOR_RECEIPT_V1', receipt: body,
        })) as SHA256Hex
        return { output: null, receipt: { ...body, receipt_root } }
      }

      const adapter = adapterMap.get(selection.provider_id)
      if (!adapter) throw new TypeError('selected provider has no conductor adapter')
      const native = await adapter.execute(input.task)
      if (!/^[0-9a-f]{64}$/.test(native.native_receipt_root)) {
        throw new TypeError('native_receipt_root must be lowercase SHA-256 hex')
      }
      const output_hash = await sha256Hex(canonicalizeJCS({
        domain: 'AEGIS_PROVIDER_NATIVE_CONDUCTOR_OUTPUT_V1',
        provider_id: selection.provider_id,
        output: native.output,
      })) as SHA256Hex

      const body = {
        schema_version: PROVIDER_NATIVE_CONDUCTOR_SCHEMA_VERSION,
        outcome: 'EXECUTED' as const,
        provider_id: selection.provider_id,
        agent_id: selection.agent_id,
        provider_selection_receipt_root: selection.receipt_root,
        native_receipt_root: native.native_receipt_root,
        task_hash,
        output_hash,
        authority_effect: 'NONE' as const,
      }
      const receipt_root = await sha256Hex(canonicalizeJCS({
        domain: 'AEGIS_PROVIDER_NATIVE_CONDUCTOR_RECEIPT_V1', receipt: body,
      })) as SHA256Hex
      return { output: native.output, receipt: { ...body, receipt_root } }
    },
  }
}
