/**
 * AEGIS Universal Work Plane v1: pure contract compiler (issue #749).
 * Does not execute tools, grant permissions, or infer independent evidence.
 * Extends the existing E5 event architecture; adapters/dispatch stay external.
 */
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { CapabilityClass, EventType } from '../core/types.js'
import type { SHA256Hex } from '../core/types.js'
import type { SubagentDelegatedPayload } from './workflow.js'

export type WorkAuthority = 'read_only' | 'branch_only' | 'operator_approved'
export type WorkRisk = 'low' | 'moderate' | 'high' | 'critical'
export type EvidenceMethod = 'deterministic' | 'independent' | 'operator'
export type FailurePolicy = 'halt' | 'manual_recovery'

export interface AcceptanceRequirement {
  readonly id: string
  readonly criterion: string
  readonly method: EvidenceMethod
  readonly evidence_kind: string
}

export type EvidenceCoveragePolicy = 'all_acceptance' | 'declared_subset'

/**
 * Resource/standard prerequisites (issue #749 extension, 2026-10-11).
 * Metadata only: declaring that discovery is required is NOT evidence that
 * discovery happened. Runtime (#753/#756) emits the actual receipts.
 */
export interface WorkResources {
  readonly resource_discovery_required: boolean
  readonly authorized_source_scopes: readonly string[]
  readonly asset_reuse_decision_ids: readonly string[]
  readonly applicable_standard_ids: readonly string[]
  readonly baseline_and_falsifier_ids: readonly string[]
  readonly evidence_coverage_policy: EvidenceCoveragePolicy
}

export interface WorkStep {
  readonly id: string
  readonly objective: string
  readonly kind: string
  readonly depends_on: readonly string[]
  readonly authority: WorkAuthority
  readonly risk: WorkRisk
  readonly scope: readonly string[]
  readonly effects: readonly string[]
  readonly acceptance: readonly AcceptanceRequirement[]
  readonly resources?: WorkResources
}

export interface WorkContract {
  readonly schema: 'aegis.work.v1'
  readonly work_id: string
  readonly objective: string
  readonly authority_ceiling: WorkAuthority
  readonly max_cost_cents: number
  readonly failure_policy: FailurePolicy
  readonly forbidden_effects: readonly string[]
  readonly steps: readonly WorkStep[]
}

export interface CompiledWorkPlan {
  readonly schema: 'aegis.work-plan.v1'
  readonly contract_sha256: string
  readonly work_id: string
  readonly ordered_steps: readonly WorkStep[]
  readonly policy: Readonly<Pick<WorkContract, 'authority_ceiling' | 'max_cost_cents' | 'failure_policy' | 'forbidden_effects'>>
  readonly authorization: 'NOT_GRANTED'
  readonly execution: 'NOT_EXECUTED'
}

export class WorkContractError extends Error {
  constructor(readonly reason: string) {
    super('AEGIS_WORK_CONTRACT_' + reason)
    this.name = 'WorkContractError'
  }
}

const ID = /^[a-zA-Z][a-zA-Z0-9._-]{0,63}$/
const TOKEN = /^[a-z][a-z0-9._-]{0,63}$/
const CEILINGS: Record<WorkAuthority, number> = { read_only: 0, branch_only: 1, operator_approved: 2 }
const RISKS: Record<WorkRisk, number> = { low: 0, moderate: 1, high: 2, critical: 3 }
const METHODS = new Set<EvidenceMethod>(['deterministic', 'independent', 'operator'])
const RESOURCE_KEYS = ['resource_discovery_required', 'authorized_source_scopes', 'asset_reuse_decision_ids',
  'applicable_standard_ids', 'baseline_and_falsifier_ids', 'evidence_coverage_policy'] as const

function object(v: unknown, keys: readonly string[], required: readonly string[]): Record<string, unknown> {
  if (v === null || typeof v !== 'object' || Array.isArray(v) || Object.getPrototypeOf(v) !== Object.prototype) {
    throw new WorkContractError('INVALID_OBJECT')
  }
  // Parse only JSON-like, enumerable data properties. Accessor getters are not pure:
  // reading one could invoke arbitrary caller code during planning.
  const descriptors = Object.getOwnPropertyDescriptors(v)
  if (Reflect.ownKeys(v).some(k => typeof k !== 'string') ||
      Object.values(descriptors).some(d => !d.enumerable || !Object.hasOwn(d, 'value'))) {
    throw new WorkContractError('NON_JSON_PROPERTY')
  }
  const data = v as Record<string, unknown>
  if (Object.keys(data).some(k => !keys.includes(k)) || required.some(k => !Object.hasOwn(data, k))) {
    throw new WorkContractError('UNKNOWN_OR_MISSING_FIELD')
  }
  return data
}

function string(v: unknown, reason: string, pattern?: RegExp): string {
  if (typeof v !== 'string' || v.trim() !== v || v.length === 0 || v.length > 2000 || (pattern && !pattern.test(v))) {
    throw new WorkContractError(reason)
  }
  return v
}

function uniqueStrings(v: unknown, reason: string, pattern: RegExp, max = 200): string[] {
  if (!Array.isArray(v) || v.length > max || !isPlainArray(v)) throw new WorkContractError(reason)
  const strings = v.map((x: unknown) => string(x, reason, pattern))
  if (new Set(strings).size !== strings.length) throw new WorkContractError(reason)
  return strings.sort()
}

function isPlainArray(v: unknown): v is unknown[] {
  if (!Array.isArray(v) || Object.getPrototypeOf(v) !== Array.prototype) return false
  const keys = Reflect.ownKeys(v)
  if (keys.length !== v.length + 1 || keys.some(k => typeof k !== 'string' ||
      (k !== 'length' && !/^(0|[1-9][0-9]*)$/.test(k)))) return false
  for (let i = 0; i < v.length; i++) {
    const desc = Object.getOwnPropertyDescriptor(v, String(i))
    if (!desc || !desc.enumerable || !Object.hasOwn(desc, 'value')) return false
  }
  return true
}

function scopeEntry(v: string): boolean {
  // A scope is a bounded, explicit resource, not a wildcard or traversal.
  return /^[a-z][a-z0-9_-]*:[A-Za-z0-9._/-]+$/.test(v) &&
    !v.includes('*') && !v.split(':')[1]!.split('/').includes('..')
}

function authority(v: unknown): WorkAuthority {
  if (typeof v !== 'string' || !Object.hasOwn(CEILINGS, v)) throw new WorkContractError('INVALID_AUTHORITY')
  return v as WorkAuthority
}

function risk(v: unknown): WorkRisk {
  if (typeof v !== 'string' || !Object.hasOwn(RISKS, v)) throw new WorkContractError('INVALID_RISK')
  return v as WorkRisk
}

function acceptance(v: unknown): AcceptanceRequirement[] {
  if (!Array.isArray(v) || !isPlainArray(v) || v.length < 1 || v.length > 50) throw new WorkContractError('NO_ACCEPTANCE')
  const out = v.map((a: unknown) => {
    const o = object(a, ['id', 'criterion', 'method', 'evidence_kind'], ['id', 'criterion', 'method', 'evidence_kind'])
    if (typeof o.method !== 'string' || !METHODS.has(o.method as EvidenceMethod)) throw new WorkContractError('INVALID_VERIFIER')
    return {
      id: string(o.id, 'INVALID_ACCEPTANCE_ID', ID),
      criterion: string(o.criterion, 'INVALID_ACCEPTANCE_CRITERION'),
      method: o.method as EvidenceMethod,
      evidence_kind: string(o.evidence_kind, 'INVALID_EVIDENCE_KIND', TOKEN),
    }
  })
  if (new Set(out.map(a => a.id)).size !== out.length) throw new WorkContractError('DUPLICATE_ACCEPTANCE')
  return out.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
}

function resources(v: unknown): WorkResources {
  // An offline compile cannot observe an inventory; a self-declared one is rejected, not ignored.
  if (v !== null && typeof v === 'object' && Object.hasOwn(v, 'inventory_verified')) {
    throw new WorkContractError('UNOBSERVED_INVENTORY_CLAIM')
  }
  const o = object(v, RESOURCE_KEYS, RESOURCE_KEYS)
  if (typeof o.resource_discovery_required !== 'boolean') throw new WorkContractError('INVALID_RESOURCES')
  if (o.evidence_coverage_policy !== 'all_acceptance' && o.evidence_coverage_policy !== 'declared_subset') {
    throw new WorkContractError('INVALID_RESOURCES')
  }
  const sources = uniqueStrings(o.authorized_source_scopes, 'INVALID_SOURCE_SCOPE', /^[^\x00-\x1F\x7F]{1,300}$/)
  if (sources.some(x => !scopeEntry(x))) throw new WorkContractError('INVALID_SOURCE_SCOPE')
  if (o.resource_discovery_required && sources.length === 0) throw new WorkContractError('DISCOVERY_REQUIRES_SOURCE_SCOPE')
  return {
    resource_discovery_required: o.resource_discovery_required,
    authorized_source_scopes: sources,
    asset_reuse_decision_ids: uniqueStrings(o.asset_reuse_decision_ids, 'INVALID_RESOURCE_ID', ID),
    applicable_standard_ids: uniqueStrings(o.applicable_standard_ids, 'INVALID_RESOURCE_ID', ID),
    baseline_and_falsifier_ids: uniqueStrings(o.baseline_and_falsifier_ids, 'INVALID_RESOURCE_ID', ID),
    evidence_coverage_policy: o.evidence_coverage_policy,
  }
}

function validate(raw: unknown): WorkContract {
  const o = object(raw, ['schema', 'work_id', 'objective', 'authority_ceiling', 'max_cost_cents', 'failure_policy', 'forbidden_effects', 'steps'],
    ['schema', 'work_id', 'objective', 'authority_ceiling', 'max_cost_cents', 'failure_policy', 'forbidden_effects', 'steps'])
  if (o.schema !== 'aegis.work.v1') throw new WorkContractError('SCHEMA_MISMATCH')
  const ceiling = authority(o.authority_ceiling)
  if (!Number.isSafeInteger(o.max_cost_cents) || (o.max_cost_cents as number) < 0) throw new WorkContractError('INVALID_BUDGET')
  if (o.failure_policy !== 'halt' && o.failure_policy !== 'manual_recovery') {
    throw new WorkContractError('INVALID_FAILURE_POLICY')
  }
  const forbidden = uniqueStrings(o.forbidden_effects, 'INVALID_FORBIDDEN_EFFECTS', /^[a-z][a-z0-9._-]{0,63}$/)
  if (forbidden.length === 0) throw new WorkContractError('MISSING_FORBIDDEN_EFFECTS')
  if (!Array.isArray(o.steps) || !isPlainArray(o.steps) || o.steps.length < 1 || o.steps.length > 200) throw new WorkContractError('INVALID_STEPS')
  const steps: WorkStep[] = o.steps.map((step: unknown) => {
    const s = object(step, ['id', 'objective', 'kind', 'depends_on', 'authority', 'risk', 'scope', 'effects', 'acceptance', 'resources'],
      ['id', 'objective', 'kind', 'depends_on', 'authority', 'risk', 'scope', 'effects', 'acceptance'])
    const permitted = authority(s.authority)
    const r = risk(s.risk)
    if (CEILINGS[permitted] > CEILINGS[ceiling]) throw new WorkContractError('AUTHORITY_EXCEEDS_CEILING')
    if (RISKS[r] >= RISKS.high && permitted !== 'operator_approved') throw new WorkContractError('HIGH_RISK_REQUIRES_OPERATOR')
    const effects = uniqueStrings(s.effects, 'INVALID_EFFECTS', /^[a-z][a-z0-9._-]{0,63}$/)
    const scope = uniqueStrings(s.scope, 'INVALID_SCOPE', /^[^\x00-\x1F\x7F]{1,300}$/)
    if (permitted !== 'read_only' && scope.length === 0) throw new WorkContractError('MUTATION_REQUIRES_SCOPE')
    if (scope.some(s => !scopeEntry(s))) throw new WorkContractError('INVALID_SCOPE')
    if (permitted === 'read_only' && effects.length > 0) throw new WorkContractError('READ_ONLY_EFFECT')
    if (permitted !== 'read_only' && effects.length === 0) throw new WorkContractError('MUTATION_REQUIRES_EFFECT')
    if (effects.some(effect => forbidden.includes(effect))) throw new WorkContractError('FORBIDDEN_EFFECT')
    const parsed: WorkStep = {
      id: string(s.id, 'INVALID_STEP_ID', ID),
      objective: string(s.objective, 'INVALID_STEP_OBJECTIVE'),
      kind: string(s.kind, 'INVALID_STEP_KIND', TOKEN),
      depends_on: uniqueStrings(s.depends_on, 'INVALID_DEPENDENCIES', ID),
      authority: permitted,
      risk: r,
      scope,
      effects,
      acceptance: acceptance(s.acceptance),
    }
    // Optional key: absent stays absent so pre-extension specs keep their digest.
    return Object.hasOwn(s, 'resources') ? { ...parsed, resources: resources(s.resources) } : parsed
  })
  if (new Set(steps.map(s => s.id)).size !== steps.length) throw new WorkContractError('DUPLICATE_STEP')
  if (new Set(steps.flatMap(s => s.acceptance.map(a => a.id))).size !== steps.reduce((n, s) => n + s.acceptance.length, 0)) {
    throw new WorkContractError('DUPLICATE_ACCEPTANCE')
  }
  return {
    schema: 'aegis.work.v1',
    work_id: string(o.work_id, 'INVALID_WORK_ID', ID),
    objective: string(o.objective, 'INVALID_OBJECTIVE'),
    authority_ceiling: ceiling,
    max_cost_cents: o.max_cost_cents as number,
    failure_policy: o.failure_policy,
    forbidden_effects: forbidden,
    steps: steps.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  }
}

function topo(steps: readonly WorkStep[]): WorkStep[] {
  const byId = new Map(steps.map(s => [s.id, s]))
  const indegree = new Map(steps.map(s => [s.id, s.depends_on.length]))
  const outbound = new Map(steps.map(s => [s.id, [] as string[]]))
  for (const step of steps) {
    for (const dependency of step.depends_on) {
      if (!byId.has(dependency)) throw new WorkContractError('UNKNOWN_DEPENDENCY')
      if (dependency === step.id) throw new WorkContractError('SELF_DEPENDENCY')
      outbound.get(dependency)!.push(step.id)
    }
  }
  const queue = steps.filter(s => indegree.get(s.id) === 0).map(s => s.id).sort()
  const out: WorkStep[] = []
  while (queue.length) {
    const id = queue.shift()!
    out.push(byId.get(id)!)
    for (const child of outbound.get(id)!) {
      indegree.set(child, indegree.get(child)! - 1)
      if (indegree.get(child) === 0) {
        queue.push(child)
        queue.sort()
      }
    }
  }
  if (out.length !== steps.length) throw new WorkContractError('CYCLE_DETECTED')
  return out
}

/** Pure validation + deterministic planning; hashing relies on existing JCS implementation. */
export async function compileWorkContract(raw: unknown): Promise<CompiledWorkPlan> {
  const contract = validate(raw)
  const orderedSteps = topo(contract.steps)
  // RFC 8785 JCS -> SHA-256 via the repo's only permitted hash path.
  const contractSha256 = await hashValue(contract)
  return deepFreeze({
    schema: 'aegis.work-plan.v1' as const,
    contract_sha256: contractSha256,
    work_id: contract.work_id,
    ordered_steps: orderedSteps,
    policy: {
      authority_ceiling: contract.authority_ceiling,
      max_cost_cents: contract.max_cost_cents,
      failure_policy: contract.failure_policy,
      forbidden_effects: contract.forbidden_effects,
    },
    authorization: 'NOT_GRANTED' as const,
    execution: 'NOT_EXECUTED' as const,
  })
}


export interface E5WorkUnitEvent {
  readonly step_id: string
  readonly event_type: EventType.SUBAGENT_DELEGATED
  readonly payload: SubagentDelegatedPayload
}

const AUTHORITY_CLASS: Record<WorkAuthority, CapabilityClass> = {
  read_only: CapabilityClass.INFERENCE,
  branch_only: CapabilityClass.SELF_MODIFYING,
  operator_approved: CapabilityClass.SELF_MODIFYING,
}

/**
 * Map each compiled work unit to an E5 SUBAGENT_DELEGATED observation, in plan order.
 * Pure: returns payloads only. Recording (recordWorkflowEvent) and dispatch stay with the
 * caller; a mapped event is a description of delegation, not evidence it occurred.
 */
export async function mapPlanToE5Events(
  plan: CompiledWorkPlan,
  delegating_agent_id: string,
): Promise<readonly E5WorkUnitEvent[]> {
  const agent = string(delegating_agent_id, 'INVALID_AGENT_ID', ID)
  if (plan.authorization !== 'NOT_GRANTED' || plan.execution !== 'NOT_EXECUTED') {
    throw new WorkContractError('INVALID_PLAN_STATE')
  }
  const out: E5WorkUnitEvent[] = []
  for (const step of plan.ordered_steps) {
    if (!Object.hasOwn(AUTHORITY_CLASS, step.authority)) {
      throw new WorkContractError('INVALID_AUTHORITY')
    }
    const task_hash: SHA256Hex = await hashValue({ contract_sha256: plan.contract_sha256, step })
    out.push({
      step_id: step.id,
      event_type: EventType.SUBAGENT_DELEGATED,
      payload: {
        delegating_agent_id: agent,
        subagent_id: plan.work_id + '/' + step.id,
        subagent_type: step.kind,
        semantic_scope: step.scope,
        authority_class: AUTHORITY_CLASS[step.authority],
        required_work_authority: step.authority,
        plan_authorization: plan.authorization,
        plan_execution: plan.execution,
        task_hash,
      },
    })
  }
  return deepFreeze(out)
}
