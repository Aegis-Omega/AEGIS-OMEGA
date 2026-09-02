// ============================================================
// SOVEREIGN OMEGA — Polyglot Evidence Normalization / Prismatic Join
// EPISTEMIC TIER: T2 · authority-neutral evidence algebra
//
// Heterogeneous backends emit typed receipts normalized with the repository's
// RFC 8785 canonicalizer and SHA-256 hashValue primitive. This module can detect
// conflicts and veto conditions, but it cannot establish canonical knowledge.
// ============================================================

import { canonicalizeJCSString } from '../core/canonicalize.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { PolyglotParadigm } from './fabric.js'
import {
  ROLE_CONTEXT_POLICIES,
  type CognitiveRole,
  type ContextInheritancePolicy,
} from './dispatch.js'

export const POLYGLOT_EVIDENCE_SCHEMA = 'AEGIS-POLYGLOT-EVIDENCE-V1' as const
export const POLYGLOT_JOIN_SCHEMA = 'AEGIS-PRISMATIC-JOIN-V1' as const

export type EvidenceReceiptKind =
  | 'CLAIM'
  | 'COUNTEREXAMPLE'
  | 'PROOF'
  | 'POSTERIOR'
  | 'SIMULATION'
  | 'QUANTUM'
  | 'PERFORMANCE'

export interface ClaimEvidencePayload {
  readonly assertion: string
  readonly support: 'SUPPORT' | 'NEUTRAL' | 'OPPOSE'
}

export interface CounterexampleEvidencePayload {
  readonly counterexample_status: 'FOUND' | 'NOT_FOUND'
  readonly witness_digest: string
}

export interface ProofEvidencePayload {
  readonly proof_status: 'PROVED' | 'FAILED' | 'INCOMPLETE'
  readonly theorem: string
  readonly assumptions_declared: number
}

export interface PosteriorEvidencePayload {
  readonly posterior_ppm: number
  readonly model_digest: string
}

export interface SimulationEvidencePayload {
  readonly simulation_status: 'CONSISTENT' | 'CONTRADICTS' | 'INCONCLUSIVE'
  readonly trace_digest: string
}

export interface QuantumEvidencePayload {
  readonly diagnostic_status: 'OBSERVED' | 'NOT_RUN' | 'INCONCLUSIVE'
  readonly contract_id: string
  readonly physical_advantage: 'NOT_ESTABLISHED'
}

export interface PerformanceEvidencePayload {
  readonly metric_set_digest: string
  readonly verified_effect_count: number
}

export interface EvidencePayloadMap {
  readonly CLAIM: ClaimEvidencePayload
  readonly COUNTEREXAMPLE: CounterexampleEvidencePayload
  readonly PROOF: ProofEvidencePayload
  readonly POSTERIOR: PosteriorEvidencePayload
  readonly SIMULATION: SimulationEvidencePayload
  readonly QUANTUM: QuantumEvidencePayload
  readonly PERFORMANCE: PerformanceEvidencePayload
}

export interface EvidenceReceiptInput<K extends EvidenceReceiptKind> {
  readonly receipt_kind: K
  readonly task_id: string
  readonly claim_id: string
  readonly toolchain_id: string
  readonly paradigm: PolyglotParadigm
  readonly role: CognitiveRole
  readonly context_policy: ContextInheritancePolicy
  readonly source_digests: readonly string[]
  readonly payload: EvidencePayloadMap[K]
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface PolyglotEvidenceReceipt<K extends EvidenceReceiptKind = EvidenceReceiptKind> {
  readonly schema_version: typeof POLYGLOT_EVIDENCE_SCHEMA
  readonly receipt_kind: K
  readonly task_id: string
  readonly claim_id: string
  readonly toolchain_id: string
  readonly paradigm: PolyglotParadigm
  readonly role: CognitiveRole
  readonly context_policy: ContextInheritancePolicy
  readonly source_digests: readonly string[]
  readonly payload: EvidencePayloadMap[K]
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly receipt_digest: string
  readonly is_replay_reconstructable: true
}

export type ClaimReceipt = PolyglotEvidenceReceipt<'CLAIM'>
export type CounterexampleReceipt = PolyglotEvidenceReceipt<'COUNTEREXAMPLE'>
export type ProofReceipt = PolyglotEvidenceReceipt<'PROOF'>
export type PosteriorReceipt = PolyglotEvidenceReceipt<'POSTERIOR'>
export type SimulationReceipt = PolyglotEvidenceReceipt<'SIMULATION'>
export type QuantumReceipt = PolyglotEvidenceReceipt<'QUANTUM'>
export type PerformanceReceipt = PolyglotEvidenceReceipt<'PERFORMANCE'>

export type AnyEvidenceReceipt = {
  readonly [K in EvidenceReceiptKind]: PolyglotEvidenceReceipt<K>
}[EvidenceReceiptKind]

export type PrismaticClaimStatus = 'NOT_ESTABLISHED' | 'QUARANTINED'

export interface PrismaticJoinReceipt {
  readonly schema_version: typeof POLYGLOT_JOIN_SCHEMA
  readonly task_id: string
  readonly claim_id: string
  readonly status: PrismaticClaimStatus
  readonly reason_codes: readonly string[]
  readonly input_receipt_digests: readonly string[]
  readonly veto_receipt_digests: readonly string[]
  readonly conflict_receipt_digests: readonly string[]
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly knowledge_admission_allowed: false
  readonly join_digest: string
  readonly is_replay_reconstructable: true
}

export class PolyglotEvidenceError extends Error {
  override readonly name: string = 'PolyglotEvidenceError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const SHA256_RE = /^[0-9a-f]{64}$/

function requireDigest(label: string, value: string): void {
  if (!SHA256_RE.test(value)) {
    throw new PolyglotEvidenceError(`INVALID_${label}`)
  }
}

function validatePayload(kind: EvidenceReceiptKind, payload: EvidencePayloadMap[EvidenceReceiptKind]): void {
  switch (kind) {
    case 'CLAIM': {
      const claim = payload as ClaimEvidencePayload
      if (claim.assertion.trim().length === 0) throw new PolyglotEvidenceError('EMPTY_CLAIM_ASSERTION')
      return
    }
    case 'COUNTEREXAMPLE': {
      const counterexample = payload as CounterexampleEvidencePayload
      requireDigest('COUNTEREXAMPLE_WITNESS_DIGEST', counterexample.witness_digest)
      return
    }
    case 'PROOF': {
      const proof = payload as ProofEvidencePayload
      if (proof.theorem.trim().length === 0) throw new PolyglotEvidenceError('EMPTY_THEOREM')
      if (!Number.isInteger(proof.assumptions_declared) || proof.assumptions_declared < 0) {
        throw new PolyglotEvidenceError('INVALID_ASSUMPTION_COUNT')
      }
      return
    }
    case 'POSTERIOR': {
      const posterior = payload as PosteriorEvidencePayload
      if (!Number.isInteger(posterior.posterior_ppm) || posterior.posterior_ppm < 0 || posterior.posterior_ppm > 1_000_000) {
        throw new PolyglotEvidenceError('INVALID_POSTERIOR_PPM')
      }
      requireDigest('POSTERIOR_MODEL_DIGEST', posterior.model_digest)
      return
    }
    case 'SIMULATION': {
      const simulation = payload as SimulationEvidencePayload
      requireDigest('SIMULATION_TRACE_DIGEST', simulation.trace_digest)
      return
    }
    case 'QUANTUM': {
      const quantum = payload as QuantumEvidencePayload
      if (quantum.contract_id.trim().length === 0) throw new PolyglotEvidenceError('EMPTY_QUANTUM_CONTRACT')
      if (quantum.physical_advantage !== 'NOT_ESTABLISHED') {
        throw new PolyglotEvidenceError('QUANTUM_ADVANTAGE_AUTHORITY_VIOLATION')
      }
      return
    }
    case 'PERFORMANCE': {
      const performance = payload as PerformanceEvidencePayload
      requireDigest('PERFORMANCE_METRIC_SET_DIGEST', performance.metric_set_digest)
      if (!Number.isInteger(performance.verified_effect_count) || performance.verified_effect_count < 0) {
        throw new PolyglotEvidenceError('INVALID_VERIFIED_EFFECT_COUNT')
      }
      return
    }
  }
}

export async function createEvidenceReceipt<K extends EvidenceReceiptKind>(
  input: EvidenceReceiptInput<K>,
): Promise<PolyglotEvidenceReceipt<K>> {
  if (input.task_id.trim().length === 0) throw new PolyglotEvidenceError('EMPTY_TASK_ID')
  if (input.claim_id.trim().length === 0) throw new PolyglotEvidenceError('EMPTY_CLAIM_ID')
  if (input.toolchain_id.trim().length === 0) throw new PolyglotEvidenceError('EMPTY_TOOLCHAIN_ID')
  if (input.authority_class !== 'NONE' || input.authority_effect !== 'NONE') {
    throw new PolyglotEvidenceError('AUTHORITY_SPLICE_REJECTED')
  }
  if (input.context_policy !== ROLE_CONTEXT_POLICIES[input.role]) {
    throw new PolyglotEvidenceError('CONTEXT_POLICY_SPLICE_REJECTED')
  }
  if (input.source_digests.length === 0) {
    throw new PolyglotEvidenceError('SOURCE_DIGEST_REQUIRED')
  }
  for (const digest of input.source_digests) requireDigest('SOURCE_DIGEST', digest)
  validatePayload(input.receipt_kind, input.payload)

  const body = {
    schema_version: POLYGLOT_EVIDENCE_SCHEMA,
    receipt_kind: input.receipt_kind,
    task_id: input.task_id,
    claim_id: input.claim_id,
    toolchain_id: input.toolchain_id,
    paradigm: input.paradigm,
    role: input.role,
    context_policy: input.context_policy,
    source_digests: [...input.source_digests],
    payload: input.payload,
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }
  const receipt_digest = await hashValue(body)

  return deepFreeze<PolyglotEvidenceReceipt<K>>({
    ...body,
    receipt_digest,
  })
}

export function canonicalReceiptJSON(receipt: unknown): string {
  return canonicalizeJCSString(receipt)
}

export async function verifyEvidenceReceipt(receipt: unknown): Promise<boolean> {
  try {
    if (receipt === null || typeof receipt !== 'object') return false
    const candidate = receipt as Record<string, unknown>
    if (candidate.schema_version !== POLYGLOT_EVIDENCE_SCHEMA) return false
    if (candidate.authority_class !== 'NONE' || candidate.authority_effect !== 'NONE') return false
    if (candidate.is_replay_reconstructable !== true) return false
    if (typeof candidate.receipt_digest !== 'string' || !SHA256_RE.test(candidate.receipt_digest)) return false

    const { receipt_digest, ...body } = candidate
    const recomputed = await hashValue(body)
    return recomputed === receipt_digest
  } catch {
    return false
  }
}

function isProofReceipt(receipt: AnyEvidenceReceipt): receipt is ProofReceipt {
  return receipt.receipt_kind === 'PROOF'
}

function isCounterexampleReceipt(receipt: AnyEvidenceReceipt): receipt is CounterexampleReceipt {
  return receipt.receipt_kind === 'COUNTEREXAMPLE'
}

export async function joinPolyglotEvidence(
  receipts: readonly AnyEvidenceReceipt[],
): Promise<PrismaticJoinReceipt> {
  if (receipts.length === 0) {
    throw new PolyglotEvidenceError('EMPTY_EVIDENCE_SET')
  }

  const task_id = receipts[0]!.task_id
  const claim_id = receipts[0]!.claim_id
  for (const receipt of receipts) {
    if (receipt.task_id !== task_id) throw new PolyglotEvidenceError('TASK_SPLICE_REJECTED')
    if (receipt.claim_id !== claim_id) throw new PolyglotEvidenceError('CLAIM_SPLICE_REJECTED')
    if (receipt.authority_class !== 'NONE' || receipt.authority_effect !== 'NONE') {
      throw new PolyglotEvidenceError('AUTHORITY_SPLICE_REJECTED')
    }
    if (!(await verifyEvidenceReceipt(receipt))) {
      throw new PolyglotEvidenceError(`INVALID_RECEIPT:${receipt.receipt_digest}`)
    }
  }

  const proved = receipts.filter(isProofReceipt).filter(r => r.payload.proof_status === 'PROVED')
  const counterexamples = receipts
    .filter(isCounterexampleReceipt)
    .filter(r => r.payload.counterexample_status === 'FOUND')

  const reason_codes: string[] = []
  const veto_receipt_digests = counterexamples.map(r => r.receipt_digest)
  const conflict_receipt_digests: string[] = []
  let status: PrismaticClaimStatus = 'NOT_ESTABLISHED'

  if (proved.length > 0 && counterexamples.length > 0) {
    status = 'QUARANTINED'
    reason_codes.push('PROOF_COUNTEREXAMPLE_CONFLICT')
    conflict_receipt_digests.push(
      ...proved.map(r => r.receipt_digest),
      ...counterexamples.map(r => r.receipt_digest),
    )
  } else if (counterexamples.length > 0) {
    reason_codes.push('COUNTEREXAMPLE_PRESENT')
  } else if (proved.length > 0) {
    reason_codes.push('PROOF_ARTIFACT_REQUIRES_EXTERNAL_ADMISSION')
  } else {
    reason_codes.push('NON_AUTHORITATIVE_EVIDENCE_ONLY')
  }

  const body = {
    schema_version: POLYGLOT_JOIN_SCHEMA,
    task_id,
    claim_id,
    status,
    reason_codes,
    input_receipt_digests: receipts.map(r => r.receipt_digest),
    veto_receipt_digests,
    conflict_receipt_digests,
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    knowledge_admission_allowed: false as const,
    is_replay_reconstructable: true as const,
  }
  const join_digest = await hashValue(body)

  return deepFreeze<PrismaticJoinReceipt>({
    ...body,
    join_digest,
  })
}
