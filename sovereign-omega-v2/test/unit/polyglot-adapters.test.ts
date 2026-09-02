import { describe, expect, it } from 'vitest'
import {
  FIRST_WAVE_ADAPTERS,
  PolyglotAdapterError,
  buildAdapterInvocationPlan,
} from '../../src/polyglot/adapters'
import {
  POLYGLOT_CAPABILITY_EVIDENCE_SCHEMA,
  type ToolchainCapabilityEvidence,
} from '../../src/polyglot/fabric'

const SHA_EXEC = 'a'.repeat(64)
const SHA_RECEIPT = 'b'.repeat(64)
const SHA_SOURCE = 'c'.repeat(64)
const CUDAQ_SELF_WITNESS_HEAD = '6965e93bf892df556e86a07e12fddb540639125a'

function capability(
  toolchain_id: string,
  overrides: Partial<ToolchainCapabilityEvidence> = {},
): ToolchainCapabilityEvidence {
  return {
    schema_version: POLYGLOT_CAPABILITY_EVIDENCE_SCHEMA,
    toolchain_id,
    status: 'VERIFIED_AVAILABLE',
    toolchain_version: 'v-test-1.0.0',
    executable_digest_sha256: SHA_EXEC,
    source_receipt_digest: SHA_RECEIPT,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

describe('Polyglot first-wave adapter contracts', () => {
  it('registers exactly egg, cvc5, Lean 4, Rocq and CUDA-Q with exact paradigms and receipt kinds', () => {
    const descriptors = Object.fromEntries(
      FIRST_WAVE_ADAPTERS.map(adapter => [adapter.toolchain_id, adapter]),
    )

    expect(Object.keys(descriptors).sort()).toEqual(['cudaq', 'cvc5', 'egg', 'lean4', 'rocq'])
    expect(descriptors.egg?.paradigm).toBe('EQUALITY_SATURATION')
    expect(descriptors.egg?.output_receipt_kind).toBe('CLAIM')
    expect(descriptors.cvc5?.paradigm).toBe('SYMBOLIC_LOGIC')
    expect(descriptors.cvc5?.output_receipt_kind).toBe('COUNTEREXAMPLE')
    expect(descriptors.lean4?.paradigm).toBe('FORMAL_PROOF')
    expect(descriptors.lean4?.output_receipt_kind).toBe('PROOF')
    expect(descriptors.rocq?.paradigm).toBe('FORMAL_PROOF')
    expect(descriptors.rocq?.output_receipt_kind).toBe('PROOF')
    expect(descriptors.cudaq?.paradigm).toBe('QUANTUM')
    expect(descriptors.cudaq?.output_receipt_kind).toBe('QUANTUM')
  })

  it('keeps every adapter plan-only, authority-neutral and compatible with all isolated context policies', () => {
    for (const adapter of FIRST_WAVE_ADAPTERS) {
      expect(adapter.required_capability_state).toBe('VERIFIED_AVAILABLE')
      expect(adapter.invocation_mode).toBe('PLAN_ONLY')
      expect(adapter.compatible_context_policies).toEqual([
        'PRESERVE',
        'RAW_EVIDENCE_ONLY',
        'CLEAN_ROOM',
      ])
      expect(adapter.authority_class).toBe('NONE')
      expect(adapter.authority_effect).toBe('NONE')
      expect(Object.isFrozen(adapter)).toBe(true)
    }
    expect(Object.isFrozen(FIRST_WAVE_ADAPTERS)).toBe(true)
  })

  it('binds CUDA-Q by reference to the exact Self-Witness-0 diagnostic contract without upgrading quantum authority', () => {
    const cudaq = FIRST_WAVE_ADAPTERS.find(adapter => adapter.toolchain_id === 'cudaq')
    expect(cudaq?.external_binding).toEqual({
      binding_mode: 'REFERENCE_ONLY_EXACT_HEAD',
      source_pr: 373,
      source_head: CUDAQ_SELF_WITNESS_HEAD,
      contract_id: 'SELF-WITNESS-0',
      protocol_version: 'QUANTUM_SELF_DIGEST_RECEIPT_V1',
      kernel_spec_version: 'SELF_WITNESS_4Q_RY_CZ_RING_RZ_V1',
      epistemic_layer: 'L6_QUANTUM_DIAGNOSTICS',
      physical_advantage: 'NOT_ESTABLISHED',
      authority_class: 'NONE',
      authority_effect: 'NONE',
    })
  })

  it('builds a deterministic plan from exact verified capability evidence and role-bound context policy', async () => {
    const request = {
      task_id: 'task-adapter-1',
      claim_id: 'claim-adapter-1',
      toolchain_id: 'cvc5',
      role: 'FALSIFIER' as const,
      source_evidence_digest: SHA_SOURCE,
      capability: capability('cvc5'),
    }

    const first = await buildAdapterInvocationPlan(request)
    const second = await buildAdapterInvocationPlan(request)

    expect(first).toEqual(second)
    expect(first.toolchain_id).toBe('cvc5')
    expect(first.paradigm).toBe('SYMBOLIC_LOGIC')
    expect(first.role).toBe('FALSIFIER')
    expect(first.context_policy).toBe('RAW_EVIDENCE_ONLY')
    expect(first.output_receipt_kind).toBe('COUNTEREXAMPLE')
    expect(first.capability_receipt_digest).toBe(SHA_RECEIPT)
    expect(first.executable_digest_sha256).toBe(SHA_EXEC)
    expect(first.invocation_mode).toBe('PLAN_ONLY')
    expect(first.authority_class).toBe('NONE')
    expect(first.authority_effect).toBe('NONE')
    expect(first.plan_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(first.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(first)).toBe(true)
  })

  it('fails closed when capability evidence is not verified instead of fabricating an adapter fallback', async () => {
    await expect(buildAdapterInvocationPlan({
      task_id: 'task-unavailable',
      claim_id: 'claim-unavailable',
      toolchain_id: 'egg',
      role: 'BUILDER',
      source_evidence_digest: SHA_SOURCE,
      capability: capability('egg', { status: 'CATALOGUED_NOT_VERIFIED' }),
    })).rejects.toThrow(/TOOLCHAIN_UNAVAILABLE:egg/)
  })

  it('rejects toolchain splicing and malformed capability evidence', async () => {
    await expect(buildAdapterInvocationPlan({
      task_id: 'task-splice',
      claim_id: 'claim-splice',
      toolchain_id: 'cvc5',
      role: 'REVIEWER',
      source_evidence_digest: SHA_SOURCE,
      capability: capability('egg'),
    })).rejects.toThrow(/CAPABILITY_TOOLCHAIN_SPLICE:cvc5:egg/)

    await expect(buildAdapterInvocationPlan({
      task_id: 'task-digest',
      claim_id: 'claim-digest',
      toolchain_id: 'lean4',
      role: 'REVIEWER',
      source_evidence_digest: SHA_SOURCE,
      capability: capability('lean4', { executable_digest_sha256: 'not-a-digest' }),
    })).rejects.toThrow(PolyglotAdapterError)
  })

  it('rejects authority-bearing capability evidence and invalid source evidence digests', async () => {
    await expect(buildAdapterInvocationPlan({
      task_id: 'task-authority',
      claim_id: 'claim-authority',
      toolchain_id: 'rocq',
      role: 'BUILDER',
      source_evidence_digest: SHA_SOURCE,
      capability: capability('rocq', { authority_effect: 'KNOWLEDGE_ADMISSION' as never }),
    })).rejects.toThrow(/AUTHORITY/)

    await expect(buildAdapterInvocationPlan({
      task_id: 'task-source',
      claim_id: 'claim-source',
      toolchain_id: 'rocq',
      role: 'BUILDER',
      source_evidence_digest: 'bad',
      capability: capability('rocq'),
    })).rejects.toThrow(/INVALID_SOURCE_EVIDENCE_DIGEST/)
  })

  it('exposes no executor, runner, command or mock seam in the public planning function', () => {
    const source = buildAdapterInvocationPlan.toString()
    expect(source).not.toMatch(/executor/i)
    expect(source).not.toMatch(/commandRunner/i)
    expect(source).not.toMatch(/spawn/i)
    expect(source).not.toMatch(/mock/i)
  })
})
