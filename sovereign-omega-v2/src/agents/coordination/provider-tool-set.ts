import type { SHA256Hex } from '../../core/types.js'
import { deepFreeze } from '../../core/immutable.js'

export interface BoundProviderToolSetV1 {
  readonly receipt_kind: 'AEGIS_BOUND_PROVIDER_TOOL_SET_V1'
  readonly schema_version: '1.0.0'
  readonly policy_digest: SHA256Hex
  readonly tools: readonly Readonly<Record<string, unknown>>[]
}

const BOUND_TOOL_SETS = new WeakSet<object>()
const SHA256_HEX = /^[0-9a-f]{64}$/

export function bindProviderToolSetV1(
  policyDigest: SHA256Hex,
  tools: readonly Readonly<Record<string, unknown>>[],
): BoundProviderToolSetV1 {
  if (!SHA256_HEX.test(policyDigest)) {
    throw new TypeError('provider tool policy digest must be lowercase SHA-256 hex')
  }
  if (tools.length === 0) {
    throw new TypeError('provider tool set must contain at least one tool')
  }

  const toolSet = deepFreeze({
    receipt_kind: 'AEGIS_BOUND_PROVIDER_TOOL_SET_V1' as const,
    schema_version: '1.0.0' as const,
    policy_digest: policyDigest,
    tools: tools.map(tool => ({ ...tool })),
  }) as BoundProviderToolSetV1

  BOUND_TOOL_SETS.add(toolSet)
  return toolSet
}

export function assertBoundProviderToolSetV1(
  value: BoundProviderToolSetV1,
): asserts value is BoundProviderToolSetV1 {
  if (!BOUND_TOOL_SETS.has(value)) {
    throw new TypeError('provider tool set is not bound by the AEGIS tool-policy port')
  }
}
