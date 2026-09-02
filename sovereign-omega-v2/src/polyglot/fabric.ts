// ============================================================
// SOVEREIGN OMEGA — Polyglot Metacognitive Capability Fabric
// EPISTEMIC TIER: T2 · authority-neutral routing substrate
//
// This module does not execute external tools and does not admit knowledge.
// It deterministically maps verified capability evidence to heterogeneous
// computational paradigms and emits replay-safe routing receipts.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { MetacognitiveObservation } from '../metacognition/loop.js'

export const POLYGLOT_CAPABILITY_EVIDENCE_SCHEMA =
  'AEGIS-POLYGLOT-CAPABILITY-EVIDENCE-V1' as const
export const POLYGLOT_ROUTE_SCHEMA = 'AEGIS-POLYGLOT-ROUTE-V1' as const

export type PolyglotParadigm =
  | 'CONTENT_ADDRESSED'
  | 'EQUALITY_SATURATION'
  | 'SYMBOLIC_LOGIC'
  | 'PROBABILISTIC'
  | 'FORMAL_PROOF'
  | 'VERIFIED_SYSTEMS'
  | 'ACCELERATOR'
  | 'META_COMPILER'
  | 'QUANTUM'
  | 'NEUROMORPHIC'
  | 'SCIENTIFIC_DYNAMICS'
  | 'DIFFERENTIABLE'

export type PolyglotAuthorityClass = 'NONE'
export type PolyglotAuthorityEffect = 'NONE'
export type ToolchainCapabilityState =
  | 'CATALOGUED_NOT_VERIFIED'
  | 'VERIFIED_AVAILABLE'
  | 'EXECUTION_ADMITTED'

export interface PolyglotFrontierEntry {
  readonly toolchain_id: string
  readonly paradigm: PolyglotParadigm
  readonly runtime_family: string
  readonly authority_class: PolyglotAuthorityClass
  readonly authority_effect: PolyglotAuthorityEffect
  readonly default_state: 'CATALOGUED_NOT_VERIFIED'
}

export const POLYGLOT_FRONTIER_CATALOG: readonly PolyglotFrontierEntry[] = deepFreeze([
  {
    toolchain_id: 'unison',
    paradigm: 'CONTENT_ADDRESSED',
    runtime_family: 'content-addressed-language',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'egg',
    paradigm: 'EQUALITY_SATURATION',
    runtime_family: 'egraph-rewrite-engine',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'cvc5',
    paradigm: 'SYMBOLIC_LOGIC',
    runtime_family: 'smt-solver',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'turing-jl',
    paradigm: 'PROBABILISTIC',
    runtime_family: 'probabilistic-programming',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'lean4',
    paradigm: 'FORMAL_PROOF',
    runtime_family: 'theorem-prover',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'rocq',
    paradigm: 'FORMAL_PROOF',
    runtime_family: 'theorem-prover',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'verus',
    paradigm: 'VERIFIED_SYSTEMS',
    runtime_family: 'verified-rust',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'triton',
    paradigm: 'ACCELERATOR',
    runtime_family: 'gpu-kernel-dsl',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'mlir',
    paradigm: 'META_COMPILER',
    runtime_family: 'compiler-ir',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'cudaq',
    paradigm: 'QUANTUM',
    runtime_family: 'hybrid-quantum-runtime',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'lava',
    paradigm: 'NEUROMORPHIC',
    runtime_family: 'event-driven-neuromorphic',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'sciml',
    paradigm: 'SCIENTIFIC_DYNAMICS',
    runtime_family: 'scientific-dynamics',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
  {
    toolchain_id: 'enzyme',
    paradigm: 'DIFFERENTIABLE',
    runtime_family: 'compiler-autodiff',
    authority_class: 'NONE',
    authority_effect: 'NONE',
    default_state: 'CATALOGUED_NOT_VERIFIED',
  },
])

const CATALOG_BY_ID = new Map(
  POLYGLOT_FRONTIER_CATALOG.map(entry => [entry.toolchain_id, entry] as const),
)
const VALID_PARADIGMS = new Set<PolyglotParadigm>(
  POLYGLOT_FRONTIER_CATALOG.map(entry => entry.paradigm),
)
const SHA256_RE = /^[0-9a-f]{64}$/

export interface ToolchainCapabilityEvidence {
  readonly schema_version: typeof POLYGLOT_CAPABILITY_EVIDENCE_SCHEMA
  readonly toolchain_id: string
  readonly status: ToolchainCapabilityState
  readonly toolchain_version: string
  readonly executable_digest_sha256: string
  readonly source_receipt_digest: string
  readonly authority_class: PolyglotAuthorityClass
  readonly authority_effect: PolyglotAuthorityEffect
}

export interface RoutedToolchain {
  readonly toolchain_id: string
  readonly paradigm: PolyglotParadigm
  readonly toolchain_version: string
  readonly executable_digest_sha256: string
  readonly source_receipt_digest: string
  readonly authority_class: PolyglotAuthorityClass
  readonly authority_effect: PolyglotAuthorityEffect
}

export interface PolyglotRouteRequest {
  readonly task_id: string
  readonly required_paradigms: readonly PolyglotParadigm[]
  readonly max_backends: number
  readonly evidence: readonly ToolchainCapabilityEvidence[]
}

export interface PolyglotRouteReceipt {
  readonly schema_version: typeof POLYGLOT_ROUTE_SCHEMA
  readonly task_id: string
  readonly decision: 'ROUTE' | 'DEFER'
  readonly required_paradigms: readonly PolyglotParadigm[]
  readonly selected_toolchains: readonly RoutedToolchain[]
  readonly unresolved_paradigms: readonly PolyglotParadigm[]
  readonly max_backends: number
  readonly authority_class: PolyglotAuthorityClass
  readonly authority_effect: PolyglotAuthorityEffect
  readonly route_digest: string
  readonly is_replay_reconstructable: true
}

export class PolyglotCapabilityError extends Error {
  override readonly name = 'PolyglotCapabilityError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

function assertCapabilityEvidence(
  item: ToolchainCapabilityEvidence,
  seenIds: Set<string>,
): void {
  if (item.schema_version !== POLYGLOT_CAPABILITY_EVIDENCE_SCHEMA) {
    throw new PolyglotCapabilityError(
      `SCHEMA_MISMATCH:${item.toolchain_id}`,
    )
  }
  if (seenIds.has(item.toolchain_id)) {
    throw new PolyglotCapabilityError(`DUPLICATE_TOOLCHAIN_EVIDENCE:${item.toolchain_id}`)
  }
  seenIds.add(item.toolchain_id)

  if (!CATALOG_BY_ID.has(item.toolchain_id)) {
    throw new PolyglotCapabilityError(`UNKNOWN_TOOLCHAIN:${item.toolchain_id}`)
  }
  if (item.authority_class !== 'NONE' || item.authority_effect !== 'NONE') {
    throw new PolyglotCapabilityError(`AUTHORITY_SPLICE_REJECTED:${item.toolchain_id}`)
  }
  if (item.status !== 'VERIFIED_AVAILABLE' && item.status !== 'EXECUTION_ADMITTED') {
    throw new PolyglotCapabilityError(`UNVERIFIED_CAPABILITY_EVIDENCE:${item.toolchain_id}`)
  }
  if (item.toolchain_version.trim().length === 0) {
    throw new PolyglotCapabilityError(`MISSING_TOOLCHAIN_VERSION:${item.toolchain_id}`)
  }
  if (!SHA256_RE.test(item.executable_digest_sha256)) {
    throw new PolyglotCapabilityError(`INVALID_EXECUTABLE_DIGEST:${item.toolchain_id}`)
  }
  if (!SHA256_RE.test(item.source_receipt_digest)) {
    throw new PolyglotCapabilityError(`INVALID_SOURCE_RECEIPT_DIGEST:${item.toolchain_id}`)
  }
}

function assertRouteRequest(request: PolyglotRouteRequest): void {
  if (request.task_id.trim().length === 0) {
    throw new PolyglotCapabilityError('EMPTY_TASK_ID')
  }
  if (!Number.isInteger(request.max_backends) || request.max_backends < 0) {
    throw new PolyglotCapabilityError('INVALID_BACKEND_BUDGET')
  }

  const seenParadigms = new Set<PolyglotParadigm>()
  for (const paradigm of request.required_paradigms) {
    if (!VALID_PARADIGMS.has(paradigm)) {
      throw new PolyglotCapabilityError(`UNKNOWN_PARADIGM:${String(paradigm)}`)
    }
    if (seenParadigms.has(paradigm)) {
      throw new PolyglotCapabilityError(`DUPLICATE_REQUIRED_PARADIGM:${paradigm}`)
    }
    seenParadigms.add(paradigm)
  }
}

export async function routePolyglotTask(
  request: PolyglotRouteRequest,
): Promise<PolyglotRouteReceipt> {
  assertRouteRequest(request)

  const evidenceById = new Map<string, ToolchainCapabilityEvidence>()
  const seenEvidenceIds = new Set<string>()
  for (const item of request.evidence) {
    assertCapabilityEvidence(item, seenEvidenceIds)
    evidenceById.set(item.toolchain_id, item)
  }

  const selected: RoutedToolchain[] = []
  const unresolved: PolyglotParadigm[] = []

  for (const paradigm of request.required_paradigms) {
    if (selected.length >= request.max_backends) {
      unresolved.push(paradigm)
      continue
    }

    const catalogueEntry = POLYGLOT_FRONTIER_CATALOG.find(entry => {
      if (entry.paradigm !== paradigm) return false
      return evidenceById.has(entry.toolchain_id)
    })

    if (!catalogueEntry) {
      unresolved.push(paradigm)
      continue
    }

    const capability = evidenceById.get(catalogueEntry.toolchain_id)
    if (!capability) {
      throw new PolyglotCapabilityError(
        `INTERNAL_CAPABILITY_LOOKUP_FAILURE:${catalogueEntry.toolchain_id}`,
      )
    }

    selected.push(deepFreeze<RoutedToolchain>({
      toolchain_id: capability.toolchain_id,
      paradigm,
      toolchain_version: capability.toolchain_version,
      executable_digest_sha256: capability.executable_digest_sha256,
      source_receipt_digest: capability.source_receipt_digest,
      authority_class: 'NONE',
      authority_effect: 'NONE',
    }))
  }

  const decision: PolyglotRouteReceipt['decision'] =
    unresolved.length === 0 ? 'ROUTE' : 'DEFER'

  const digestPayload = {
    schema_version: POLYGLOT_ROUTE_SCHEMA,
    task_id: request.task_id,
    decision,
    required_paradigms: [...request.required_paradigms],
    selected_toolchains: selected,
    unresolved_paradigms: unresolved,
    max_backends: request.max_backends,
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }
  const route_digest = await hashValue(digestPayload)

  return deepFreeze<PolyglotRouteReceipt>({
    ...digestPayload,
    route_digest,
  })
}

export function buildPolyglotMetacognitiveObservation(
  receipt: PolyglotRouteReceipt,
): MetacognitiveObservation {
  const selected = receipt.selected_toolchains.map(x => x.toolchain_id).join(',') || 'none'
  const unresolved = receipt.unresolved_paradigms.join(',') || 'none'

  return deepFreeze<MetacognitiveObservation>({
    layer: 'METACOGNITIVE',
    tier: 'T2',
    signal: [
      'POLYGLOT_ROUTE',
      `task=${receipt.task_id}`,
      `decision=${receipt.decision}`,
      `route_digest=${receipt.route_digest}`,
      `selected=${selected}`,
      `unresolved=${unresolved}`,
      'authority=NONE',
    ].join(' '),
  })
}
