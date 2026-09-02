import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  assertBoundProviderToolSetV1,
  bindProviderToolSetV1,
  type BoundProviderToolSetV1,
} from '../../src/agents/coordination/provider-tool-set.js'

const digest = 'a'.repeat(64) as SHA256Hex

describe('BoundProviderToolSetV1', () => {
  it('binds a frozen provider tool set to an AEGIS policy digest', () => {
    const toolSet = bindProviderToolSetV1(digest, [
      { type: 'function', name: 'read_evidence', parameters: { type: 'object' } },
    ])
    expect(toolSet.policy_digest).toBe(digest)
    expect(Object.isFrozen(toolSet)).toBe(true)
    expect(Object.isFrozen(toolSet.tools)).toBe(true)
    expect(() => assertBoundProviderToolSetV1(toolSet)).not.toThrow()
  })

  it('rejects a structurally forged tool set that did not pass through the binding port', () => {
    const forged = {
      receipt_kind: 'AEGIS_BOUND_PROVIDER_TOOL_SET_V1',
      schema_version: '1.0.0',
      policy_digest: digest,
      tools: Object.freeze([{ type: 'function', name: 'unsafe_write' }]),
    } as unknown as BoundProviderToolSetV1

    expect(() => assertBoundProviderToolSetV1(forged)).toThrow(/not bound/)
  })

  it('rejects malformed policy digests and empty tool sets', () => {
    expect(() => bindProviderToolSetV1('bad' as SHA256Hex, [{ type: 'function' }])).toThrow(/digest/)
    expect(() => bindProviderToolSetV1(digest, [])).toThrow(/at least one/)
  })
})
