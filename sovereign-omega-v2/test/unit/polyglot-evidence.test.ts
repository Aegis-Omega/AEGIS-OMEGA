import { describe, expect, it } from 'vitest'
import {
  canonicalReceiptJSON,
  createEvidenceReceipt,
  joinPolyglotEvidence,
  verifyEvidenceReceipt,
  type ClaimReceipt,
  type CounterexampleReceipt,
  type ProofReceipt,
  type QuantumReceipt,
} from '../../src/polyglot/evidence'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)
const SHA_C = 'c'.repeat(64)

const base = {
  task_id: 'task-evidence',
  claim_id: 'claim-evidence',
  toolchain_id: 'cvc5',
  paradigm: 'SYMBOLIC_LOGIC' as const,
  role: 'FALSIFIER' as const,
  context_policy: 'RAW_EVIDENCE_ONLY' as const,
  source_digests: [SHA_A, SHA_B],
  authority_class: 'NONE' as const,
  authority_effect: 'NONE' as const,
}

describe('Evidence normalization and Prismatic metacognitive join', () => {
  it('produces typed, deeply frozen RFC8785-digest-bound receipts', async () => {
    const receipt: ClaimReceipt = await createEvidenceReceipt({
      ...base,
      receipt_kind: 'CLAIM',
      payload: { assertion: 'x = x', support: 'SUPPORT' },
    })

    expect(receipt.schema_version).toBe('AEGIS-POLYGLOT-EVIDENCE-V1')
    expect(receipt.receipt_kind).toBe('CLAIM')
    expect(receipt.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
    expect(receipt.is_replay_reconstructable).toBe(true)
    expect(Object.isFrozen(receipt)).toBe(true)
    expect(Object.isFrozen(receipt.payload)).toBe(true)
    expect(await verifyEvidenceReceipt(receipt)).toBe(true)
  })

  it('canonicalizes semantically identical payload key orders to byte-identical JSON and digest', async () => {
    const a = await createEvidenceReceipt({
      ...base,
      receipt_kind: 'CLAIM',
      payload: { assertion: 'same', support: 'SUPPORT' },
    })
    const b = await createEvidenceReceipt({
      ...base,
      receipt_kind: 'CLAIM',
      payload: { support: 'SUPPORT', assertion: 'same' },
    })

    expect(a.receipt_digest).toBe(b.receipt_digest)
    expect(canonicalReceiptJSON(a)).toBe(canonicalReceiptJSON(b))
    expect(canonicalReceiptJSON(a)).toContain('"authority_effect":"NONE"')
  })

  it('detects receipt tampering by recomputing the RFC8785 SHA-256 digest', async () => {
    const receipt = await createEvidenceReceipt({
      ...base,
      receipt_kind: 'CLAIM',
      payload: { assertion: 'original', support: 'SUPPORT' },
    })
    const tampered = {
      ...receipt,
      payload: { assertion: 'tampered', support: 'SUPPORT' as const },
    }
    expect(await verifyEvidenceReceipt(tampered)).toBe(false)
  })

  it('rejects authority splicing and malformed source digests before receipt emission', async () => {
    await expect(createEvidenceReceipt({
      ...base,
      receipt_kind: 'CLAIM',
      authority_effect: 'KNOWLEDGE_ADMISSION' as never,
      payload: { assertion: 'forged authority', support: 'SUPPORT' },
    })).rejects.toThrow(/AUTHORITY/)

    await expect(createEvidenceReceipt({
      ...base,
      receipt_kind: 'CLAIM',
      source_digests: ['abc'],
      payload: { assertion: 'bad digest', support: 'SUPPORT' },
    })).rejects.toThrow(/SOURCE_DIGEST/)
  })

  it('does not let majority support overrule one concrete counterexample', async () => {
    const support: ClaimReceipt[] = []
    for (let i = 0; i < 5; i++) {
      support.push(await createEvidenceReceipt({
        ...base,
        toolchain_id: `support-${i}`,
        receipt_kind: 'CLAIM',
        payload: { assertion: 'universal statement', support: 'SUPPORT' },
      }))
    }
    const counterexample: CounterexampleReceipt = await createEvidenceReceipt({
      ...base,
      receipt_kind: 'COUNTEREXAMPLE',
      payload: { counterexample_status: 'FOUND', witness_digest: SHA_C },
    })

    const joined = await joinPolyglotEvidence([...support, counterexample])
    expect(joined.status).toBe('NOT_ESTABLISHED')
    expect(joined.veto_receipt_digests).toContain(counterexample.receipt_digest)
    expect(joined.reason_codes).toContain('COUNTEREXAMPLE_PRESENT')
    expect(joined.status).not.toBe('ESTABLISHED')
  })

  it('quarantines a claim when a proof receipt and a concrete counterexample conflict', async () => {
    const proof: ProofReceipt = await createEvidenceReceipt({
      ...base,
      toolchain_id: 'lean4',
      paradigm: 'FORMAL_PROOF',
      role: 'REVIEWER',
      context_policy: 'CLEAN_ROOM',
      receipt_kind: 'PROOF',
      payload: { proof_status: 'PROVED', theorem: 'T', assumptions_declared: 0 },
    })
    const counterexample: CounterexampleReceipt = await createEvidenceReceipt({
      ...base,
      receipt_kind: 'COUNTEREXAMPLE',
      payload: { counterexample_status: 'FOUND', witness_digest: SHA_C },
    })

    const joined = await joinPolyglotEvidence([proof, counterexample])
    expect(joined.status).toBe('QUARANTINED')
    expect(joined.reason_codes).toContain('PROOF_COUNTEREXAMPLE_CONFLICT')
    expect(joined.conflict_receipt_digests).toEqual(
      expect.arrayContaining([proof.receipt_digest, counterexample.receipt_digest]),
    )
    expect(joined.authority_effect).toBe('NONE')
  })

  it('keeps probabilistic and quantum diagnostics below knowledge-admission authority', async () => {
    const posterior = await createEvidenceReceipt({
      ...base,
      toolchain_id: 'turing-jl',
      paradigm: 'PROBABILISTIC',
      role: 'BUILDER',
      context_policy: 'PRESERVE',
      receipt_kind: 'POSTERIOR',
      payload: { posterior_ppm: 990000, model_digest: SHA_C },
    })
    const quantum: QuantumReceipt = await createEvidenceReceipt({
      ...base,
      toolchain_id: 'cudaq',
      paradigm: 'QUANTUM',
      receipt_kind: 'QUANTUM',
      payload: {
        diagnostic_status: 'OBSERVED',
        contract_id: 'SELF-WITNESS-0-V1',
        physical_advantage: 'NOT_ESTABLISHED',
      },
    })

    const joined = await joinPolyglotEvidence([posterior, quantum])
    expect(joined.status).toBe('NOT_ESTABLISHED')
    expect(joined.authority_class).toBe('NONE')
    expect(joined.authority_effect).toBe('NONE')
    expect(joined.knowledge_admission_allowed).toBe(false)
  })

  it('fails closed on cross-task or cross-claim receipt splicing', async () => {
    const a = await createEvidenceReceipt({
      ...base,
      receipt_kind: 'CLAIM',
      payload: { assertion: 'A', support: 'SUPPORT' },
    })
    const b = await createEvidenceReceipt({
      ...base,
      task_id: 'other-task',
      receipt_kind: 'CLAIM',
      payload: { assertion: 'B', support: 'SUPPORT' },
    })
    await expect(joinPolyglotEvidence([a, b])).rejects.toThrow(/TASK_SPLICE/)

    const c = await createEvidenceReceipt({
      ...base,
      claim_id: 'other-claim',
      receipt_kind: 'CLAIM',
      payload: { assertion: 'C', support: 'SUPPORT' },
    })
    await expect(joinPolyglotEvidence([a, c])).rejects.toThrow(/CLAIM_SPLICE/)
  })
})
