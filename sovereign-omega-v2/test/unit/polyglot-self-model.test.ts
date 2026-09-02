import { describe, expect, it } from 'vitest'
import type { SequenceNumber } from '../../src/core/types'
import { MetacognitiveLoop, certifyMetacognitiveLoop } from '../../src/metacognition/loop'
import type { ToolchainCapabilityEvidence } from '../../src/polyglot/fabric'
import { createEvidenceReceipt, joinPolyglotEvidence } from '../../src/polyglot/evidence'
import {
  StrategyPerformanceLedger,
  buildMetacognitiveSelfModel,
  buildSelfModelObservation,
  createStrategyPerformanceRecord,
} from '../../src/polyglot/self-model'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)
const SHA_C = 'c'.repeat(64)

function capability(toolchain_id: string): ToolchainCapabilityEvidence {
  return {
    schema_version: 'AEGIS-POLYGLOT-CAPABILITY-EVIDENCE-V1',
    toolchain_id,
    status: 'VERIFIED_AVAILABLE',
    toolchain_version: 'test-1.0.0',
    executable_digest_sha256: SHA_A,
    source_receipt_digest: SHA_B,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

async function nonEstablishedJoin() {
  const claim = await createEvidenceReceipt({
    receipt_kind: 'CLAIM',
    task_id: 'task-self',
    claim_id: 'claim-self',
    toolchain_id: 'egg',
    paradigm: 'EQUALITY_SATURATION',
    role: 'BUILDER',
    context_policy: 'PRESERVE',
    source_digests: [SHA_A],
    payload: { assertion: 'candidate', support: 'SUPPORT' },
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })
  return joinPolyglotEvidence([claim])
}

describe('MetacognitiveSelfModel and StrategyPerformanceLedger', () => {
  it('creates digest-bound immutable strategy performance records', async () => {
    const record = await createStrategyPerformanceRecord({
      strategy_id: 'egg+cvc5',
      task_class: 'symbolic-equivalence',
      tokens_to_verified_effect: 800,
      actions_to_verified_effect: 4,
      latency_ms: 120,
      verified_effect_count: 2,
      failure_count: 0,
      evidence_digest: SHA_C,
    })
    expect(record.record_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(record.authority_effect).toBe('NONE')
    expect(Object.isFrozen(record)).toBe(true)
  })

  it('keeps the strategy ledger immutable and append-only', async () => {
    const a = await createStrategyPerformanceRecord({
      strategy_id: 'a', task_class: 'formal', tokens_to_verified_effect: 100,
      actions_to_verified_effect: 2, latency_ms: 50, verified_effect_count: 1,
      failure_count: 0, evidence_digest: SHA_A,
    })
    const empty = StrategyPerformanceLedger.empty()
    const one = empty.append(a)

    expect(empty.length).toBe(0)
    expect(one.length).toBe(1)
    expect(one.records[0]).toEqual(a)
    expect(Object.isFrozen(one.records)).toBe(true)
  })

  it('computes a deterministic Pareto frontier without scalar confidence collapse', async () => {
    const better = await createStrategyPerformanceRecord({
      strategy_id: 'better', task_class: 'symbolic', tokens_to_verified_effect: 100,
      actions_to_verified_effect: 2, latency_ms: 50, verified_effect_count: 3,
      failure_count: 0, evidence_digest: SHA_A,
    })
    const dominated = await createStrategyPerformanceRecord({
      strategy_id: 'dominated', task_class: 'symbolic', tokens_to_verified_effect: 150,
      actions_to_verified_effect: 3, latency_ms: 60, verified_effect_count: 2,
      failure_count: 1, evidence_digest: SHA_B,
    })
    const tradeoff = await createStrategyPerformanceRecord({
      strategy_id: 'tradeoff', task_class: 'symbolic', tokens_to_verified_effect: 70,
      actions_to_verified_effect: 4, latency_ms: 80, verified_effect_count: 4,
      failure_count: 0, evidence_digest: SHA_C,
    })

    const ledger = StrategyPerformanceLedger.empty().append(dominated).append(tradeoff).append(better)
    expect(ledger.paretoFrontier('symbolic').map(x => x.strategy_id)).toEqual(['better', 'tradeoff'])
    expect(ledger.paretoFrontier('symbolic')).toEqual(ledger.paretoFrontier('symbolic'))
  })

  it('builds a capability-aware self-model that cannot admit knowledge', async () => {
    const record = await createStrategyPerformanceRecord({
      strategy_id: 'formal-clean-room', task_class: 'formal', tokens_to_verified_effect: 200,
      actions_to_verified_effect: 3, latency_ms: 90, verified_effect_count: 1,
      failure_count: 0, evidence_digest: SHA_C,
    })
    const ledger = StrategyPerformanceLedger.empty().append(record)
    const joined = await nonEstablishedJoin()

    const model = await buildMetacognitiveSelfModel({
      capabilities: [capability('lean4'), capability('cvc5')],
      joins: [joined],
      strategy_ledger: ledger,
      unresolved_paradigms: ['QUANTUM'],
    })

    expect(model.capability_states.map(x => x.toolchain_id)).toEqual(['cvc5', 'lean4'])
    expect(model.not_established_claim_count).toBe(1)
    expect(model.quarantined_claim_count).toBe(0)
    expect(model.unresolved_paradigms).toEqual(['QUANTUM'])
    expect(model.knowledge_admission_allowed).toBe(false)
    expect(model.authority_class).toBe('NONE')
    expect(model.authority_effect).toBe('NONE')
    expect(model.subjective_consciousness).toBe('NOT_ESTABLISHED')
    expect(model.model_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(Object.isFrozen(model)).toBe(true)
  })

  it('is deterministic across three self-model reconstructions', async () => {
    const joined = await nonEstablishedJoin()
    const input = {
      capabilities: [capability('cvc5')],
      joins: [joined],
      strategy_ledger: StrategyPerformanceLedger.empty(),
      unresolved_paradigms: ['FORMAL_PROOF'] as const,
    }
    const a = await buildMetacognitiveSelfModel(input)
    const b = await buildMetacognitiveSelfModel(input)
    const c = await buildMetacognitiveSelfModel(input)
    expect(a).toEqual(b)
    expect(b).toEqual(c)
  })

  it('emits a real T2 SELF_MODEL observation accepted by the existing MetacognitiveLoop', async () => {
    const joined = await nonEstablishedJoin()
    const model = await buildMetacognitiveSelfModel({
      capabilities: [capability('cvc5')],
      joins: [joined],
      strategy_ledger: StrategyPerformanceLedger.empty(),
      unresolved_paradigms: [],
    })
    const observation = buildSelfModelObservation(model)
    expect(observation.layer).toBe('SELF_MODEL')
    expect(observation.tier).toBe('T2')
    expect(observation.signal).toContain(model.model_digest)

    const start = MetacognitiveLoop.empty()
    const { loop, entry } = await start.observe(observation, 1n as SequenceNumber)
    expect(entry.observation).toEqual(observation)
    const certificate = await certifyMetacognitiveLoop(loop.getAll())
    expect(certificate.is_valid).toBe(true)
    expect(certificate.entry_count).toBe(1)
  })
})
