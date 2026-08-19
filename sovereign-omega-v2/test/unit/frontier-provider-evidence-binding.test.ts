import { describe, expect, it } from 'vitest'
import {
  createProviderExecutionEvidenceBinding,
  providerExecutionEvidenceBindingRoot,
  verifyProviderExecutionEvidenceBinding,
} from '../../src/api/frontier-provider-evidence-binding.js'

const H = (c: string) => c.repeat(64)

function fixture() {
  const request = {
    provider: 'openai' as const,
    requestId: 'request-pr5a-0001',
    expectedParentStateRoot: H('1'),
  }
  const result = {
    providerOperationId: 'op-pr5a-0001',
    responseDigest: H('2'),
    grantsAuthority: false as const,
  }
  const usage = {
    provider: 'openai' as const,
    requestId: 'request-pr5a-0001',
    status: 'succeeded' as const,
    workOrderDigest: H('3'),
    authorityReceiptRoot: H('4'),
    providerOperationId: 'op-pr5a-0001',
    responseDigest: H('2'),
    grantsAuthority: false as const,
  }
  const transitionId = H('5')
  const executionInstanceId = 'exec-pr5a-0001'
  return { request, result, usage, transitionId, executionInstanceId }
}

describe('PR5A ProviderExecutionEvidenceBindingV1', () => {
  it('creates one exact non-authoritative binding', async () => {
    const f = fixture()
    const binding = createProviderExecutionEvidenceBinding(f)
    expect(binding.binding_kind).toBe('PROVIDER_EXECUTION_EVIDENCE_BINDING_V1')
    expect(binding.provider).toBe('openai')
    expect(binding.request_id).toBe(f.request.requestId)
    expect(binding.provider_operation_id).toBe(f.result.providerOperationId)
    expect(binding.response_digest).toBe(f.result.responseDigest)
    expect(binding.work_order_digest).toBe(f.usage.workOrderDigest)
    expect(binding.authority_receipt_root).toBe(f.usage.authorityReceiptRoot)
    expect(binding.transition_id).toBe(f.transitionId)
    expect(binding.execution_instance_id).toBe(f.executionInstanceId)
    expect(binding.expected_parent_state_root).toBe(f.request.expectedParentStateRoot)
    expect(binding.grants_authority).toBe(false)
    expect(await providerExecutionEvidenceBindingRoot(binding)).toMatch(/^[0-9a-f]{64}$/)
    expect(verifyProviderExecutionEvidenceBinding(binding, binding)).toBe(true)
  })

  it.each([
    ['provider', () => ({ usage: { ...fixture().usage, provider: 'anthropic' as const } })],
    ['request', () => ({ usage: { ...fixture().usage, requestId: 'request-splice' } })],
    ['operation', () => ({ usage: { ...fixture().usage, providerOperationId: 'op-splice' } })],
    ['response', () => ({ usage: { ...fixture().usage, responseDigest: H('6') } })],
  ])('rejects cross-context %s splicing', (_name, mutate) => {
    const f = fixture()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, ...mutate() })).toThrow()
  })

  it('rejects provider result authority escalation', () => {
    const f = fixture()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, result: { ...f.result, grantsAuthority: true as boolean } })).toThrow(/authority/i)
  })

  it('rejects usage authority escalation', () => {
    const f = fixture()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, usage: { ...f.usage, grantsAuthority: true as boolean } })).toThrow(/authority/i)
  })

  it('rejects missing authority receipt root', () => {
    const f = fixture()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, usage: { ...f.usage, authorityReceiptRoot: '' } })).toThrow()
  })

  it.each([
    ['work-order', 'workOrderDigest'],
    ['authority-root', 'authorityReceiptRoot'],
  ] as const)('rejects malformed %s digest', (_name, key) => {
    const f = fixture()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, usage: { ...f.usage, [key]: 'not-a-hash' } })).toThrow()
  })

  it('rejects malformed transition and parent-state hashes', () => {
    const f = fixture()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, transitionId: 'bad' })).toThrow()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, request: { ...f.request, expectedParentStateRoot: 'bad' } })).toThrow()
  })

  it('rejects non-succeeded usage as provider execution evidence', () => {
    const f = fixture()
    expect(() => createProviderExecutionEvidenceBinding({ ...f, usage: { ...f.usage, status: 'failed' as const } })).toThrow()
  })

  it('fails verification on every bound field mismatch', () => {
    const f = fixture()
    const binding = createProviderExecutionEvidenceBinding(f)
    const variants = [
      { ...binding, provider: 'anthropic' },
      { ...binding, request_id: 'request-other' },
      { ...binding, provider_operation_id: 'op-other' },
      { ...binding, response_digest: H('6') },
      { ...binding, work_order_digest: H('7') },
      { ...binding, authority_receipt_root: H('8') },
      { ...binding, transition_id: H('9') },
      { ...binding, execution_instance_id: 'exec-other' },
      { ...binding, expected_parent_state_root: H('a') },
      { ...binding, grants_authority: true },
    ]
    for (const variant of variants) expect(verifyProviderExecutionEvidenceBinding(variant, binding)).toBe(false)
  })

  it('produces a deterministic domain-separated root', async () => {
    const f = fixture()
    const binding = createProviderExecutionEvidenceBinding(f)
    expect(await providerExecutionEvidenceBindingRoot(binding)).toBe(await providerExecutionEvidenceBindingRoot({ ...binding }))
  })
})
