import { describe, expect, it, vi } from 'vitest'
import {
  Automaton3WorkOrderVerifier,
  type Automaton3EnvelopeFactory,
  type Automaton3Runner,
} from '../../src/api/frontier-automaton3-verifier.js'
import type { ProofCarryingWorkOrder } from '../../src/api/frontier-inference-gateway.js'

const hex = (digit: string): string => digit.repeat(64)

const workOrder = (overrides: Partial<ProofCarryingWorkOrder> = {}): ProofCarryingWorkOrder => ({
  schemaVersion: '1.0.0',
  workOrderId: 'wo-openai-1',
  requestId: 'req-openai-1',
  provider: 'openai',
  capability: 'inference.run',
  target: 'openai-prod',
  consequenceClass: 'D3',
  argumentsDigest: hex('1'),
  expectedParentStateRoot: hex('2'),
  idempotencyKey: 'idem-openai-0001',
  maxCostMicroUsd: 500_000,
  maxInputTokens: 1_000,
  maxOutputTokens: 500,
  evidenceReferences: ['receipt://evidence/1'],
  operatorApprovalReference: 'approval://operator/1',
  issuedSequence: 9,
  ...overrides,
})

const factory: Automaton3EnvelopeFactory = {
  create: vi.fn(async order => ({
    identity: { source_commit: 'exact-head', action_digest: 'bound-by-factory' },
    workspace: { actual_cwd: '/repo' },
    action: {
      provider: order.provider,
      capability: order.capability,
      target: order.target,
      request_id: order.requestId,
    },
    request: {
      action_class: order.consequenceClass,
      authority_domain: `frontier-provider:${order.provider}`,
      requested_capability: order.capability,
      tool: order.provider,
      target: order.target,
      workspace_mode: 'REPOSITORY',
      idempotency_key: order.idempotencyKey,
    },
  })),
}

describe('Automaton3WorkOrderVerifier', () => {
  it('accepts only an ADMITTED decision carrying a receipt root', async () => {
    const runner: Automaton3Runner = {
      evaluate: vi.fn(async () => ({ outcome: 'ADMITTED', authority_receipt_root: hex('a') })),
    }
    const verifier = new Automaton3WorkOrderVerifier(factory, runner)

    const verified = await verifier.verify(workOrder())

    expect(verified.valid).toBe(true)
    expect(verified.digest).toMatch(/^[a-f0-9]{64}$/)
    expect(verifier.authorityReceiptRoot('wo-openai-1')).toBe(hex('a'))
    expect(runner.evaluate).toHaveBeenCalledOnce()
  })

  it('fails closed on a DENIED authority decision', async () => {
    const runner: Automaton3Runner = {
      evaluate: vi.fn(async () => ({ outcome: 'DENIED', denial_codes: ['CAPABILITY_DENIED'] })),
    }
    const verifier = new Automaton3WorkOrderVerifier(factory, runner)

    await expect(verifier.verify(workOrder())).resolves.toMatchObject({ valid: false })
    expect(verifier.authorityReceiptRoot('wo-openai-1')).toBeUndefined()
  })

  it('fails closed when an admitted decision lacks a valid authority receipt root', async () => {
    const runner: Automaton3Runner = {
      evaluate: vi.fn(async () => ({ outcome: 'ADMITTED', authority_receipt_root: 'not-a-root' })),
    }
    const verifier = new Automaton3WorkOrderVerifier(factory, runner)

    await expect(verifier.verify(workOrder())).resolves.toMatchObject({ valid: false })
  })

  it('work-order digest changes when the target deployment changes', async () => {
    const runner: Automaton3Runner = { evaluate: async () => ({ outcome: 'ADMITTED', authority_receipt_root: hex('a') }) }
    const verifier = new Automaton3WorkOrderVerifier(factory, runner)

    const first = await verifier.verify(workOrder())
    const second = await verifier.verify(workOrder({ target: 'openai-other' }))

    expect(first.digest).not.toBe(second.digest)
  })
})
