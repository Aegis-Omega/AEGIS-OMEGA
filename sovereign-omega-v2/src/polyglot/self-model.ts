// ============================================================
// SOVEREIGN OMEGA — Polyglot Metacognitive Self-Model
// EPISTEMIC TIER: T2 · derived operational self-model only
//
// Strategy performance may change future routing preferences, but neither the
// ledger nor this self-model has canonical-knowledge admission authority.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { MetacognitiveObservation } from '../metacognition/loop.js'
import type { PolyglotParadigm, ToolchainCapabilityEvidence } from './fabric.js'
import type { PrismaticJoinReceipt } from './evidence.js'

export const STRATEGY_PERFORMANCE_SCHEMA = 'AEGIS-STRATEGY-PERFORMANCE-V1' as const
export const METACOGNITIVE_SELF_MODEL_SCHEMA = 'AEGIS-POLYGLOT-SELF-MODEL-V1' as const

const SHA256_RE = /^[0-9a-f]{64}$/

export interface StrategyPerformanceInput {
  readonly strategy_id: string
  readonly task_class: string
  readonly tokens_to_verified_effect: number
  readonly actions_to_verified_effect: number
  readonly latency_ms: number
  readonly verified_effect_count: number
  readonly failure_count: number
  readonly evidence_digest: string
}

export interface StrategyPerformanceRecord extends StrategyPerformanceInput {
  readonly schema_version: typeof STRATEGY_PERFORMANCE_SCHEMA
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly record_digest: string
  readonly is_replay_reconstructable: true
}

export interface SelfModelCapabilityState {
  readonly toolchain_id: string
  readonly status: ToolchainCapabilityEvidence['status']
  readonly toolchain_version: string
  readonly executable_digest_sha256: string
  readonly capability_receipt_digest: string
}

export interface MetacognitiveSelfModelInput {
  readonly capabilities: readonly ToolchainCapabilityEvidence[]
  readonly joins: readonly PrismaticJoinReceipt[]
  readonly strategy_ledger: StrategyPerformanceLedger
  readonly unresolved_paradigms: readonly PolyglotParadigm[]
}

export interface MetacognitiveSelfModel {
  readonly schema_version: typeof METACOGNITIVE_SELF_MODEL_SCHEMA
  readonly capability_states: readonly SelfModelCapabilityState[]
  readonly quarantined_claim_count: number
  readonly not_established_claim_count: number
  readonly unresolved_paradigms: readonly PolyglotParadigm[]
  readonly pareto_strategy_ids: readonly string[]
  readonly strategy_record_count: number
  readonly operational_metacognitive_self_model: 'ACTIVE_T2'
  readonly subjective_consciousness: 'NOT_ESTABLISHED'
  readonly knowledge_admission_allowed: false
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly model_digest: string
  readonly is_replay_reconstructable: true
}

export class StrategyPerformanceError extends Error {
  override readonly name: string = 'StrategyPerformanceError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function requireNonNegativeInteger(label: string, value: number): void {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new StrategyPerformanceError(`INVALID_${label}`)
  }
}

export async function createStrategyPerformanceRecord(
  input: StrategyPerformanceInput,
): Promise<StrategyPerformanceRecord> {
  if (input.strategy_id.trim().length === 0) throw new StrategyPerformanceError('EMPTY_STRATEGY_ID')
  if (input.task_class.trim().length === 0) throw new StrategyPerformanceError('EMPTY_TASK_CLASS')
  requireNonNegativeInteger('TOKENS_TO_VERIFIED_EFFECT', input.tokens_to_verified_effect)
  requireNonNegativeInteger('ACTIONS_TO_VERIFIED_EFFECT', input.actions_to_verified_effect)
  requireNonNegativeInteger('LATENCY_MS', input.latency_ms)
  requireNonNegativeInteger('VERIFIED_EFFECT_COUNT', input.verified_effect_count)
  requireNonNegativeInteger('FAILURE_COUNT', input.failure_count)
  if (!SHA256_RE.test(input.evidence_digest)) throw new StrategyPerformanceError('INVALID_EVIDENCE_DIGEST')

  const body = {
    schema_version: STRATEGY_PERFORMANCE_SCHEMA,
    strategy_id: input.strategy_id,
    task_class: input.task_class,
    tokens_to_verified_effect: input.tokens_to_verified_effect,
    actions_to_verified_effect: input.actions_to_verified_effect,
    latency_ms: input.latency_ms,
    verified_effect_count: input.verified_effect_count,
    failure_count: input.failure_count,
    evidence_digest: input.evidence_digest,
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }
  const record_digest = await hashValue(body)

  return deepFreeze<StrategyPerformanceRecord>({
    ...body,
    record_digest,
  })
}

function dominates(a: StrategyPerformanceRecord, b: StrategyPerformanceRecord): boolean {
  const noWorse =
    a.tokens_to_verified_effect <= b.tokens_to_verified_effect &&
    a.actions_to_verified_effect <= b.actions_to_verified_effect &&
    a.latency_ms <= b.latency_ms &&
    a.failure_count <= b.failure_count &&
    a.verified_effect_count >= b.verified_effect_count
  const strictlyBetter =
    a.tokens_to_verified_effect < b.tokens_to_verified_effect ||
    a.actions_to_verified_effect < b.actions_to_verified_effect ||
    a.latency_ms < b.latency_ms ||
    a.failure_count < b.failure_count ||
    a.verified_effect_count > b.verified_effect_count
  return noWorse && strictlyBetter
}

export class StrategyPerformanceLedger {
  private constructor(private readonly _records: readonly StrategyPerformanceRecord[]) {
    Object.freeze(this)
  }

  static empty(): StrategyPerformanceLedger {
    return new StrategyPerformanceLedger(deepFreeze([]))
  }

  get records(): readonly StrategyPerformanceRecord[] { return this._records }
  get length(): number { return this._records.length }

  append(record: StrategyPerformanceRecord): StrategyPerformanceLedger {
    if (this._records.some(existing => existing.record_digest === record.record_digest)) {
      throw new StrategyPerformanceError(`DUPLICATE_STRATEGY_RECORD:${record.record_digest}`)
    }
    if (record.authority_class !== 'NONE' || record.authority_effect !== 'NONE') {
      throw new StrategyPerformanceError('AUTHORITY_SPLICE_REJECTED')
    }
    return new StrategyPerformanceLedger(deepFreeze([...this._records, record]))
  }

  paretoFrontier(taskClass: string): readonly StrategyPerformanceRecord[] {
    const candidates = this._records.filter(record => record.task_class === taskClass)
    const frontier = candidates.filter(candidate =>
      !candidates.some(other => other.record_digest !== candidate.record_digest && dominates(other, candidate)),
    )
    return deepFreeze([...frontier].sort((a, b) =>
      a.strategy_id.localeCompare(b.strategy_id) || a.record_digest.localeCompare(b.record_digest),
    ))
  }
}

function allParetoStrategyIds(ledger: StrategyPerformanceLedger): readonly string[] {
  const taskClasses = [...new Set(ledger.records.map(record => record.task_class))].sort()
  const ids = new Set<string>()
  for (const taskClass of taskClasses) {
    for (const record of ledger.paretoFrontier(taskClass)) ids.add(record.strategy_id)
  }
  return deepFreeze([...ids].sort())
}

export async function buildMetacognitiveSelfModel(
  input: MetacognitiveSelfModelInput,
): Promise<MetacognitiveSelfModel> {
  const seenCapabilities = new Set<string>()
  const capability_states = input.capabilities.map(capability => {
    if (seenCapabilities.has(capability.toolchain_id)) {
      throw new StrategyPerformanceError(`DUPLICATE_CAPABILITY:${capability.toolchain_id}`)
    }
    seenCapabilities.add(capability.toolchain_id)
    if (capability.authority_class !== 'NONE' || capability.authority_effect !== 'NONE') {
      throw new StrategyPerformanceError(`CAPABILITY_AUTHORITY_SPLICE:${capability.toolchain_id}`)
    }
    return deepFreeze<SelfModelCapabilityState>({
      toolchain_id: capability.toolchain_id,
      status: capability.status,
      toolchain_version: capability.toolchain_version,
      executable_digest_sha256: capability.executable_digest_sha256,
      capability_receipt_digest: capability.source_receipt_digest,
    })
  }).sort((a, b) => a.toolchain_id.localeCompare(b.toolchain_id))

  const quarantined_claim_count = input.joins.filter(join => join.status === 'QUARANTINED').length
  const not_established_claim_count = input.joins.filter(join => join.status === 'NOT_ESTABLISHED').length
  for (const join of input.joins) {
    if (join.knowledge_admission_allowed !== false || join.authority_effect !== 'NONE') {
      throw new StrategyPerformanceError(`JOIN_AUTHORITY_SPLICE:${join.join_digest}`)
    }
  }

  const body = {
    schema_version: METACOGNITIVE_SELF_MODEL_SCHEMA,
    capability_states,
    quarantined_claim_count,
    not_established_claim_count,
    unresolved_paradigms: [...input.unresolved_paradigms].sort(),
    pareto_strategy_ids: allParetoStrategyIds(input.strategy_ledger),
    strategy_record_count: input.strategy_ledger.length,
    operational_metacognitive_self_model: 'ACTIVE_T2' as const,
    subjective_consciousness: 'NOT_ESTABLISHED' as const,
    knowledge_admission_allowed: false as const,
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }
  const model_digest = await hashValue(body)

  return deepFreeze<MetacognitiveSelfModel>({
    ...body,
    model_digest,
  })
}

export function buildSelfModelObservation(
  model: MetacognitiveSelfModel,
): MetacognitiveObservation {
  return deepFreeze<MetacognitiveObservation>({
    layer: 'SELF_MODEL',
    tier: 'T2',
    signal: [
      'POLYGLOT_SELF_MODEL',
      `digest=${model.model_digest}`,
      `capabilities=${model.capability_states.length}`,
      `quarantined=${model.quarantined_claim_count}`,
      `not_established=${model.not_established_claim_count}`,
      `strategies=${model.strategy_record_count}`,
      'knowledge_admission=false',
      'subjective_consciousness=NOT_ESTABLISHED',
      'authority=NONE',
    ].join(' '),
  })
}
