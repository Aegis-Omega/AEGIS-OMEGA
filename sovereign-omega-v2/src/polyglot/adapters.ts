// ============================================================
// SOVEREIGN OMEGA — First-Wave Polyglot Adapter Contracts
// EPISTEMIC TIER: T2 · planning only · authority NONE
//
// Adapters bind already-verified capability evidence to deterministic planning
// receipts. They never execute an external tool and never promote evidence to
// canonical knowledge.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import {
  routePolyglotTask,
  type PolyglotParadigm,
  type ToolchainCapabilityEvidence,
} from './fabric.js'
import {
  ROLE_CONTEXT_POLICIES,
  type CognitiveRole,
  type ContextInheritancePolicy,
} from './dispatch.js'
import type { EvidenceReceiptKind } from './evidence.js'

export const POLYGLOT_ADAPTER_SCHEMA = 'AEGIS-POLYGLOT-ADAPTER-V1' as const
export const POLYGLOT_ADAPTER_PLAN_SCHEMA = 'AEGIS-POLYGLOT-ADAPTER-PLAN-V1' as const

const SHA256_RE = /^[0-9a-f]{64}$/
const CONTEXT_POLICIES: readonly ContextInheritancePolicy[] = deepFreeze([
  'PRESERVE',
  'RAW_EVIDENCE_ONLY',
  'CLEAN_ROOM',
])

export interface CudaQSelfWitnessBinding {
  readonly binding_mode: 'REFERENCE_ONLY_EXACT_HEAD'
  readonly source_pr: 373
  readonly source_head: '6965e93bf892df556e86a07e12fddb540639125a'
  readonly contract_id: 'SELF-WITNESS-0'
  readonly protocol_version: 'QUANTUM_SELF_DIGEST_RECEIPT_V1'
  readonly kernel_spec_version: 'SELF_WITNESS_4Q_RY_CZ_RING_RZ_V1'
  readonly epistemic_layer: 'L6_QUANTUM_DIAGNOSTICS'
  readonly physical_advantage: 'NOT_ESTABLISHED'
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface PolyglotAdapterDescriptor {
  readonly schema_version: typeof POLYGLOT_ADAPTER_SCHEMA
  readonly adapter_id: string
  readonly toolchain_id: 'egg' | 'cvc5' | 'lean4' | 'rocq' | 'cudaq'
  readonly paradigm: PolyglotParadigm
  readonly required_capability_state: 'VERIFIED_AVAILABLE'
  readonly compatible_context_policies: readonly ContextInheritancePolicy[]
  readonly output_receipt_kind: EvidenceReceiptKind
  readonly invocation_mode: 'PLAN_ONLY'
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly external_binding?: CudaQSelfWitnessBinding
}

export interface AdapterInvocationRequest {
  readonly task_id: string
  readonly claim_id: string
  readonly toolchain_id: string
  readonly role: CognitiveRole
  readonly source_evidence_digest: string
  readonly capability: ToolchainCapabilityEvidence
}

export interface AdapterInvocationPlan {
  readonly schema_version: typeof POLYGLOT_ADAPTER_PLAN_SCHEMA
  readonly task_id: string
  readonly claim_id: string
  readonly adapter_id: string
  readonly toolchain_id: string
  readonly paradigm: PolyglotParadigm
  readonly role: CognitiveRole
  readonly context_policy: ContextInheritancePolicy
  readonly source_evidence_digest: string
  readonly output_receipt_kind: EvidenceReceiptKind
  readonly toolchain_version: string
  readonly executable_digest_sha256: string
  readonly capability_receipt_digest: string
  readonly invocation_mode: 'PLAN_ONLY'
  readonly external_binding?: CudaQSelfWitnessBinding
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly plan_digest: string
  readonly is_replay_reconstructable: true
}

export class PolyglotAdapterError extends Error {
  override readonly name: string = 'PolyglotAdapterError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const CUDAQ_SELF_WITNESS_BINDING: CudaQSelfWitnessBinding = deepFreeze({
  binding_mode: 'REFERENCE_ONLY_EXACT_HEAD',
  source_pr: 373,
  source_head: '6965e93bf892df556e86a07e12fddb540639125a',
  contract_id: 'SELF-WITNESS-0',
  protocol_version: 'QUANTUM_SELF_DIGEST_RECEIPT_V1',
  kernel_spec_version: 'SELF_WITNESS_4Q_RY_CZ_RING_RZ_V1',
  epistemic_layer: 'L6_QUANTUM_DIAGNOSTICS',
  physical_advantage: 'NOT_ESTABLISHED',
  authority_class: 'NONE',
  authority_effect: 'NONE',
})

export const FIRST_WAVE_ADAPTERS: readonly PolyglotAdapterDescriptor[] = deepFreeze([
  {
    schema_version: POLYGLOT_ADAPTER_SCHEMA,
    adapter_id: 'egg-equality-saturation-v1',
    toolchain_id: 'egg',
    paradigm: 'EQUALITY_SATURATION',
    required_capability_state: 'VERIFIED_AVAILABLE',
    compatible_context_policies: CONTEXT_POLICIES,
    output_receipt_kind: 'CLAIM',
    invocation_mode: 'PLAN_ONLY',
    authority_class: 'NONE',
    authority_effect: 'NONE',
  },
  {
    schema_version: POLYGLOT_ADAPTER_SCHEMA,
    adapter_id: 'cvc5-symbolic-logic-v1',
    toolchain_id: 'cvc5',
    paradigm: 'SYMBOLIC_LOGIC',
    required_capability_state: 'VERIFIED_AVAILABLE',
    compatible_context_policies: CONTEXT_POLICIES,
    output_receipt_kind: 'COUNTEREXAMPLE',
    invocation_mode: 'PLAN_ONLY',
    authority_class: 'NONE',
    authority_effect: 'NONE',
  },
  {
    schema_version: POLYGLOT_ADAPTER_SCHEMA,
    adapter_id: 'lean4-formal-proof-v1',
    toolchain_id: 'lean4',
    paradigm: 'FORMAL_PROOF',
    required_capability_state: 'VERIFIED_AVAILABLE',
    compatible_context_policies: CONTEXT_POLICIES,
    output_receipt_kind: 'PROOF',
    invocation_mode: 'PLAN_ONLY',
    authority_class: 'NONE',
    authority_effect: 'NONE',
  },
  {
    schema_version: POLYGLOT_ADAPTER_SCHEMA,
    adapter_id: 'rocq-formal-proof-v1',
    toolchain_id: 'rocq',
    paradigm: 'FORMAL_PROOF',
    required_capability_state: 'VERIFIED_AVAILABLE',
    compatible_context_policies: CONTEXT_POLICIES,
    output_receipt_kind: 'PROOF',
    invocation_mode: 'PLAN_ONLY',
    authority_class: 'NONE',
    authority_effect: 'NONE',
  },
  {
    schema_version: POLYGLOT_ADAPTER_SCHEMA,
    adapter_id: 'cudaq-self-witness-0-v1',
    toolchain_id: 'cudaq',
    paradigm: 'QUANTUM',
    required_capability_state: 'VERIFIED_AVAILABLE',
    compatible_context_policies: CONTEXT_POLICIES,
    output_receipt_kind: 'QUANTUM',
    invocation_mode: 'PLAN_ONLY',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    external_binding: CUDAQ_SELF_WITNESS_BINDING,
  },
])

const ADAPTER_BY_TOOLCHAIN: ReadonlyMap<string, PolyglotAdapterDescriptor> = new Map(
  FIRST_WAVE_ADAPTERS.map(adapter => [adapter.toolchain_id, adapter] as const),
)

function requireIdentifier(label: string, value: string): void {
  if (value.trim().length === 0) {
    throw new PolyglotAdapterError(`EMPTY_${label}`)
  }
}

function requireDigest(label: string, value: string): void {
  if (!SHA256_RE.test(value)) {
    throw new PolyglotAdapterError(`INVALID_${label}`)
  }
}

function requireAuthorityNeutral(capability: ToolchainCapabilityEvidence): void {
  if (capability.authority_class !== 'NONE' || capability.authority_effect !== 'NONE') {
    throw new PolyglotAdapterError(`AUTHORITY_SPLICE_REJECTED:${capability.toolchain_id}`)
  }
}

export async function buildAdapterInvocationPlan(
  request: AdapterInvocationRequest,
): Promise<AdapterInvocationPlan> {
  requireIdentifier('TASK_ID', request.task_id)
  requireIdentifier('CLAIM_ID', request.claim_id)
  requireDigest('SOURCE_EVIDENCE_DIGEST', request.source_evidence_digest)

  const descriptor = ADAPTER_BY_TOOLCHAIN.get(request.toolchain_id)
  if (!descriptor) {
    throw new PolyglotAdapterError(`UNKNOWN_ADAPTER_TOOLCHAIN:${request.toolchain_id}`)
  }
  if (request.capability.toolchain_id !== request.toolchain_id) {
    throw new PolyglotAdapterError(
      `CAPABILITY_TOOLCHAIN_SPLICE:${request.toolchain_id}:${request.capability.toolchain_id}`,
    )
  }
  if (
    request.capability.status !== 'VERIFIED_AVAILABLE'
    && request.capability.status !== 'EXECUTION_ADMITTED'
  ) {
    throw new PolyglotAdapterError(`TOOLCHAIN_UNAVAILABLE:${request.toolchain_id}`)
  }
  requireAuthorityNeutral(request.capability)

  let route
  try {
    route = await routePolyglotTask({
      task_id: request.task_id,
      required_paradigms: [descriptor.paradigm],
      max_backends: 1,
      evidence: [request.capability],
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    throw new PolyglotAdapterError(message)
  }

  const selected = route.selected_toolchains[0]
  if (route.decision !== 'ROUTE' || !selected) {
    throw new PolyglotAdapterError(`TOOLCHAIN_UNAVAILABLE:${request.toolchain_id}`)
  }
  if (selected.toolchain_id !== request.toolchain_id) {
    throw new PolyglotAdapterError(
      `CAPABILITY_TOOLCHAIN_SPLICE:${request.toolchain_id}:${selected.toolchain_id}`,
    )
  }

  const contextPolicy = ROLE_CONTEXT_POLICIES[request.role]
  if (!descriptor.compatible_context_policies.includes(contextPolicy)) {
    throw new PolyglotAdapterError(
      `CONTEXT_POLICY_UNSUPPORTED:${request.toolchain_id}:${contextPolicy}`,
    )
  }

  const body = {
    schema_version: POLYGLOT_ADAPTER_PLAN_SCHEMA,
    task_id: request.task_id,
    claim_id: request.claim_id,
    adapter_id: descriptor.adapter_id,
    toolchain_id: descriptor.toolchain_id,
    paradigm: descriptor.paradigm,
    role: request.role,
    context_policy: contextPolicy,
    source_evidence_digest: request.source_evidence_digest,
    output_receipt_kind: descriptor.output_receipt_kind,
    toolchain_version: selected.toolchain_version,
    executable_digest_sha256: selected.executable_digest_sha256,
    capability_receipt_digest: selected.source_receipt_digest,
    invocation_mode: 'PLAN_ONLY' as const,
    ...(descriptor.external_binding
      ? { external_binding: descriptor.external_binding }
      : {}),
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }
  const plan_digest = await hashValue(body)

  return deepFreeze<AdapterInvocationPlan>({
    ...body,
    plan_digest,
  })
}
