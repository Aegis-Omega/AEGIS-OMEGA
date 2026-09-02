// ============================================================
// SOVEREIGN OMEGA — Polyglot Paradigm Decomposer / Dispatcher
// EPISTEMIC TIER: T2 · planning only · authority NONE
//
// This module creates deterministic work units and dispatch bindings. It does
// not invoke external processes. Context inheritance is part of the hashed
// work-unit contract so Builder/Falsifier/Reviewer perspectives cannot be
// silently collapsed into one shared reasoning context.
// ============================================================

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type {
  PolyglotParadigm,
  PolyglotRouteReceipt,
  RoutedToolchain,
} from './fabric.js'

export const POLYGLOT_WORK_UNIT_SCHEMA = 'AEGIS-POLYGLOT-WORK-UNIT-V1' as const
export const POLYGLOT_DISPATCH_SCHEMA = 'AEGIS-POLYGLOT-DISPATCH-V1' as const

export type CognitiveRole = 'BUILDER' | 'FALSIFIER' | 'REVIEWER'
export type ContextInheritancePolicy = 'PRESERVE' | 'RAW_EVIDENCE_ONLY' | 'CLEAN_ROOM'
export type PolyglotOracleClass = 'SYMBOLIC' | 'FORMAL' | 'PROBABILISTIC' | 'HARDWARE'

export const ROLE_CONTEXT_POLICIES: Readonly<Record<CognitiveRole, ContextInheritancePolicy>> =
  deepFreeze({
    BUILDER: 'PRESERVE',
    FALSIFIER: 'RAW_EVIDENCE_ONLY',
    REVIEWER: 'CLEAN_ROOM',
  })

const ROLE_ORDER: readonly CognitiveRole[] = deepFreeze([
  'BUILDER',
  'FALSIFIER',
  'REVIEWER',
])
const SHA256_RE = /^[0-9a-f]{64}$/

export interface PolyglotDecompositionRequest {
  readonly task_id: string
  readonly claim_id: string
  readonly required_paradigms: readonly PolyglotParadigm[]
  readonly source_evidence_digest: string
}

export interface ParadigmWorkUnit {
  readonly schema_version: typeof POLYGLOT_WORK_UNIT_SCHEMA
  readonly work_unit_id: string
  readonly task_id: string
  readonly claim_id: string
  readonly paradigm: PolyglotParadigm
  readonly oracle_class: PolyglotOracleClass
  readonly role: CognitiveRole
  readonly context_policy: ContextInheritancePolicy
  readonly source_evidence_digest: string
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
}

export interface DispatchBinding {
  readonly work_unit_id: string
  readonly task_id: string
  readonly claim_id: string
  readonly paradigm: PolyglotParadigm
  readonly oracle_class: PolyglotOracleClass
  readonly role: CognitiveRole
  readonly context_policy: ContextInheritancePolicy
  readonly source_evidence_digest: string
  readonly toolchain_id: string
  readonly toolchain_version: string
  readonly executable_digest_sha256: string
  readonly capability_receipt_digest: string
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
}

export interface PolyglotDispatchPlan {
  readonly schema_version: typeof POLYGLOT_DISPATCH_SCHEMA
  readonly task_id: string
  readonly decision: 'DISPATCH' | 'DEFER'
  readonly dispatches: readonly DispatchBinding[]
  readonly unresolved_paradigms: readonly PolyglotParadigm[]
  readonly authority_class: 'NONE'
  readonly authority_effect: 'NONE'
  readonly dispatch_digest: string
  readonly is_replay_reconstructable: true
}

export class PolyglotDispatchError extends Error {
  override readonly name: string = 'PolyglotDispatchError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export function classifyParadigmOracle(paradigm: PolyglotParadigm): PolyglotOracleClass {
  switch (paradigm) {
    case 'CONTENT_ADDRESSED':
    case 'EQUALITY_SATURATION':
    case 'SYMBOLIC_LOGIC':
    case 'META_COMPILER':
      return 'SYMBOLIC'
    case 'FORMAL_PROOF':
    case 'VERIFIED_SYSTEMS':
      return 'FORMAL'
    case 'PROBABILISTIC':
    case 'SCIENTIFIC_DYNAMICS':
    case 'DIFFERENTIABLE':
      return 'PROBABILISTIC'
    case 'ACCELERATOR':
    case 'QUANTUM':
    case 'NEUROMORPHIC':
      return 'HARDWARE'
  }
}

function validateDecompositionRequest(request: PolyglotDecompositionRequest): void {
  if (request.task_id.trim().length === 0) {
    throw new PolyglotDispatchError('EMPTY_TASK_ID')
  }
  if (request.claim_id.trim().length === 0) {
    throw new PolyglotDispatchError('EMPTY_CLAIM_ID')
  }
  if (!SHA256_RE.test(request.source_evidence_digest)) {
    throw new PolyglotDispatchError('INVALID_EVIDENCE_DIGEST')
  }
  const seen = new Set<PolyglotParadigm>()
  for (const paradigm of request.required_paradigms) {
    if (seen.has(paradigm)) {
      throw new PolyglotDispatchError(`DUPLICATE_PARADIGM:${paradigm}`)
    }
    seen.add(paradigm)
  }
}

export async function decomposePolyglotTask(
  request: PolyglotDecompositionRequest,
): Promise<readonly ParadigmWorkUnit[]> {
  validateDecompositionRequest(request)
  const units: ParadigmWorkUnit[] = []

  for (const paradigm of request.required_paradigms) {
    for (const role of ROLE_ORDER) {
      const body = {
        schema_version: POLYGLOT_WORK_UNIT_SCHEMA,
        task_id: request.task_id,
        claim_id: request.claim_id,
        paradigm,
        oracle_class: classifyParadigmOracle(paradigm),
        role,
        context_policy: ROLE_CONTEXT_POLICIES[role],
        source_evidence_digest: request.source_evidence_digest,
        authority_class: 'NONE' as const,
        authority_effect: 'NONE' as const,
        is_replay_reconstructable: true as const,
      }
      const work_unit_id = await hashValue(body)
      units.push(deepFreeze<ParadigmWorkUnit>({
        ...body,
        work_unit_id,
      }))
    }
  }

  return deepFreeze(units)
}

function assertWorkUnitIntegrity(
  route: PolyglotRouteReceipt,
  unit: ParadigmWorkUnit,
): void {
  if (unit.task_id !== route.task_id) {
    throw new PolyglotDispatchError(
      `TASK_SPLICE:${route.task_id}:${unit.task_id}`,
    )
  }
  if (unit.context_policy !== ROLE_CONTEXT_POLICIES[unit.role]) {
    throw new PolyglotDispatchError(`CONTEXT_POLICY_SPLICE:${unit.work_unit_id}`)
  }
  if (!SHA256_RE.test(unit.work_unit_id) || !SHA256_RE.test(unit.source_evidence_digest)) {
    throw new PolyglotDispatchError(`INVALID_WORK_UNIT_DIGEST:${unit.work_unit_id}`)
  }
  if (unit.authority_class !== 'NONE' || unit.authority_effect !== 'NONE') {
    throw new PolyglotDispatchError(`AUTHORITY_SPLICE:${unit.work_unit_id}`)
  }
}

function bindWorkUnit(unit: ParadigmWorkUnit, toolchain: RoutedToolchain): DispatchBinding {
  if (unit.paradigm !== toolchain.paradigm) {
    throw new PolyglotDispatchError(
      `PARADIGM_SPLICE:${unit.paradigm}:${toolchain.paradigm}`,
    )
  }

  return deepFreeze<DispatchBinding>({
    work_unit_id: unit.work_unit_id,
    task_id: unit.task_id,
    claim_id: unit.claim_id,
    paradigm: unit.paradigm,
    oracle_class: unit.oracle_class,
    role: unit.role,
    context_policy: unit.context_policy,
    source_evidence_digest: unit.source_evidence_digest,
    toolchain_id: toolchain.toolchain_id,
    toolchain_version: toolchain.toolchain_version,
    executable_digest_sha256: toolchain.executable_digest_sha256,
    capability_receipt_digest: toolchain.source_receipt_digest,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  })
}

export async function buildDispatchPlan(
  route: PolyglotRouteReceipt,
  workUnits: readonly ParadigmWorkUnit[],
): Promise<PolyglotDispatchPlan> {
  for (const unit of workUnits) {
    assertWorkUnitIntegrity(route, unit)
  }

  const selectedByParadigm = new Map<PolyglotParadigm, RoutedToolchain>(
    route.selected_toolchains.map(toolchain => [toolchain.paradigm, toolchain]),
  )
  const dispatches: DispatchBinding[] = []

  for (const unit of workUnits) {
    const selected = selectedByParadigm.get(unit.paradigm)
    if (!selected) continue
    dispatches.push(bindWorkUnit(unit, selected))
  }

  const decision: PolyglotDispatchPlan['decision'] =
    route.unresolved_paradigms.length === 0 ? 'DISPATCH' : 'DEFER'
  const body = {
    schema_version: POLYGLOT_DISPATCH_SCHEMA,
    task_id: route.task_id,
    decision,
    dispatches,
    unresolved_paradigms: [...route.unresolved_paradigms],
    authority_class: 'NONE' as const,
    authority_effect: 'NONE' as const,
    is_replay_reconstructable: true as const,
  }
  const dispatch_digest = await hashValue(body)

  return deepFreeze<PolyglotDispatchPlan>({
    ...body,
    dispatch_digest,
  })
}
