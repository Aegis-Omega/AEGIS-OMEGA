// ============================================================
// SOVEREIGN OMEGA — Metacognitive Self-Regulator
// EPISTEMIC TIER: T1 · deterministic governance primitive
//
// Converts a verified self-model and observed gaps into a bounded
// adaptation disposition. This module never executes mutations and
// never grants authority; READY_FOR_AUTHORITY means Automaton-3 may
// evaluate the proposal next.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const SELF_REGULATOR_SCHEMA_VERSION = '1.0.0' as const

export type ConsequenceClass = 'D0' | 'D1' | 'D2' | 'D3' | 'D4'
export type GapSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type GapKind =
  | 'INVARIANT_BREACH'
  | 'CAPABILITY_DEFICIT'
  | 'EVIDENCE_DEFICIT'
  | 'PERFORMANCE_REGRESSION'
  | 'UNKNOWN'

export type SelfRegulationMode =
  | 'HALT'
  | 'OBSERVE_ONLY'
  | 'NO_CHANGE'
  | 'PROPOSAL_REQUIRED'
  | 'REJECTED'
  | 'READY_FOR_AUTHORITY'

export type RequiredNextGate = 'NONE' | 'REANCHOR' | 'OPERATOR_REVIEW' | 'AUTOMATON_3'

export interface SelfModelHealth {
  readonly t0_verdict: boolean
  readonly corruption_count: number
  readonly membrane_intact: boolean
  readonly entropy_bounded: boolean
}

export interface SelfModelSnapshot {
  readonly state_root: SHA256Hex
  readonly identity_root: SHA256Hex
  readonly policy_root: SHA256Hex
  readonly capability_root: SHA256Hex
  readonly memory_root: SHA256Hex
  readonly metacognition_root: SHA256Hex
  readonly health: SelfModelHealth
}

export interface KnowledgeGap {
  readonly gap_id: string
  readonly kind: GapKind
  readonly severity: GapSeverity
  readonly evidence_refs: readonly string[]
}

export interface ProposedMutation {
  readonly path: string
  readonly operation: 'CREATE' | 'UPDATE' | 'DELETE'
  readonly expected_blob?: string
}

export interface AdaptationProposal {
  readonly proposal_id: string
  readonly objective: string
  readonly consequence_class: ConsequenceClass
  readonly expected_parent_state_root: SHA256Hex
  readonly addressed_gap_ids: readonly string[]
  readonly requested_capabilities: readonly string[]
  readonly mutations: readonly ProposedMutation[]
  readonly verification_steps: readonly string[]
  readonly rollback_reference?: string
  readonly operator_approval_reference?: string
  readonly constitutional_change_reference?: string
}

export interface SelfRegulationInput {
  readonly snapshot: SelfModelSnapshot
  readonly gaps: readonly KnowledgeGap[]
  readonly proposal?: AdaptationProposal
}

export interface SelfRegulationDecision {
  readonly schema_version: typeof SELF_REGULATOR_SCHEMA_VERSION
  readonly mode: SelfRegulationMode
  readonly reasons: readonly string[]
  readonly required_next_gate: RequiredNextGate
  readonly grants_authority: false
  readonly requires_automaton3: boolean
  readonly self_model_digest: SHA256Hex
  readonly proposal_digest: SHA256Hex | null
  readonly decision_digest: SHA256Hex
}

export class SelfRegulationError extends Error {
  override readonly name = 'SelfRegulationError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const HASH_PATTERN = /^[0-9a-f]{64}$/
const SAFE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$/
const SAFE_PATH_PATTERN = /^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9._@/+:-]+$/
const VALID_KINDS = new Set<GapKind>([
  'INVARIANT_BREACH',
  'CAPABILITY_DEFICIT',
  'EVIDENCE_DEFICIT',
  'PERFORMANCE_REGRESSION',
  'UNKNOWN',
])
const VALID_SEVERITIES = new Set<GapSeverity>(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
const VALID_CLASSES = new Set<ConsequenceClass>(['D0', 'D1', 'D2', 'D3', 'D4'])
const VALID_OPERATIONS = new Set<ProposedMutation['operation']>(['CREATE', 'UPDATE', 'DELETE'])

function assertNonEmpty(field: string, value: unknown): asserts value is string {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new SelfRegulationError(`${field} must be a non-empty string`)
  }
}

function assertHash(field: string, value: unknown): asserts value is SHA256Hex {
  if (typeof value !== 'string' || !HASH_PATTERN.test(value)) {
    throw new SelfRegulationError(`${field} must be lowercase SHA-256 hex`)
  }
}

function sortedUnique(field: string, values: readonly string[]): readonly string[] {
  if (!Array.isArray(values)) throw new SelfRegulationError(`${field} must be an array`)
  const normalized = values.map((value, index) => {
    assertNonEmpty(`${field}[${index}]`, value)
    return value.trim()
  })
  const unique = [...new Set(normalized)].sort()
  if (unique.length !== normalized.length) throw new SelfRegulationError(`${field} must be unique`)
  return unique
}

function validateSnapshot(snapshot: SelfModelSnapshot): void {
  assertHash('snapshot.state_root', snapshot.state_root)
  assertHash('snapshot.identity_root', snapshot.identity_root)
  assertHash('snapshot.policy_root', snapshot.policy_root)
  assertHash('snapshot.capability_root', snapshot.capability_root)
  assertHash('snapshot.memory_root', snapshot.memory_root)
  assertHash('snapshot.metacognition_root', snapshot.metacognition_root)
  if (!Number.isInteger(snapshot.health.corruption_count) || snapshot.health.corruption_count < 0) {
    throw new SelfRegulationError('snapshot.health.corruption_count must be a non-negative integer')
  }
  for (const field of ['t0_verdict', 'membrane_intact', 'entropy_bounded'] as const) {
    if (typeof snapshot.health[field] !== 'boolean') {
      throw new SelfRegulationError(`snapshot.health.${field} must be boolean`)
    }
  }
}

function normalizeGaps(gaps: readonly KnowledgeGap[]): readonly KnowledgeGap[] {
  if (!Array.isArray(gaps)) throw new SelfRegulationError('gaps must be an array')
  const ids = new Set<string>()
  const normalized = gaps.map((gap, index) => {
    if (!SAFE_ID_PATTERN.test(gap.gap_id)) throw new SelfRegulationError(`gaps[${index}].gap_id is invalid`)
    if (ids.has(gap.gap_id)) throw new SelfRegulationError('gap_id values must be unique')
    ids.add(gap.gap_id)
    if (!VALID_KINDS.has(gap.kind)) throw new SelfRegulationError(`gaps[${index}].kind is invalid`)
    if (!VALID_SEVERITIES.has(gap.severity)) throw new SelfRegulationError(`gaps[${index}].severity is invalid`)
    return {
      gap_id: gap.gap_id,
      kind: gap.kind,
      severity: gap.severity,
      evidence_refs: sortedUnique(`gaps[${index}].evidence_refs`, gap.evidence_refs),
    }
  })
  return normalized.sort((a, b) => a.gap_id.localeCompare(b.gap_id))
}

function normalizeProposal(proposal: AdaptationProposal): AdaptationProposal {
  if (!SAFE_ID_PATTERN.test(proposal.proposal_id)) throw new SelfRegulationError('proposal.proposal_id is invalid')
  assertNonEmpty('proposal.objective', proposal.objective)
  if (!VALID_CLASSES.has(proposal.consequence_class)) throw new SelfRegulationError('proposal.consequence_class is invalid')
  assertHash('proposal.expected_parent_state_root', proposal.expected_parent_state_root)

  if (!Array.isArray(proposal.mutations)) throw new SelfRegulationError('proposal.mutations must be an array')
  const mutations = proposal.mutations.map((mutation, index) => {
    if (!SAFE_PATH_PATTERN.test(mutation.path)) throw new SelfRegulationError(`proposal.mutations[${index}].path is invalid`)
    if (!VALID_OPERATIONS.has(mutation.operation)) throw new SelfRegulationError(`proposal.mutations[${index}].operation is invalid`)
    if (mutation.expected_blob !== undefined && !/^[0-9a-f]{40,64}$/.test(mutation.expected_blob)) {
      throw new SelfRegulationError(`proposal.mutations[${index}].expected_blob is invalid`)
    }
    return mutation.expected_blob === undefined
      ? { path: mutation.path, operation: mutation.operation }
      : { path: mutation.path, operation: mutation.operation, expected_blob: mutation.expected_blob }
  })

  const verification_steps = proposal.verification_steps.map((step, index) => {
    assertNonEmpty(`proposal.verification_steps[${index}]`, step)
    return step.trim()
  })

  return {
    proposal_id: proposal.proposal_id,
    objective: proposal.objective.trim(),
    consequence_class: proposal.consequence_class,
    expected_parent_state_root: proposal.expected_parent_state_root,
    addressed_gap_ids: sortedUnique('proposal.addressed_gap_ids', proposal.addressed_gap_ids),
    requested_capabilities: sortedUnique('proposal.requested_capabilities', proposal.requested_capabilities),
    mutations,
    verification_steps,
    ...(proposal.rollback_reference === undefined ? {} : { rollback_reference: proposal.rollback_reference }),
    ...(proposal.operator_approval_reference === undefined ? {} : { operator_approval_reference: proposal.operator_approval_reference }),
    ...(proposal.constitutional_change_reference === undefined ? {} : { constitutional_change_reference: proposal.constitutional_change_reference }),
  }
}

function forbiddenCapability(capability: string): boolean {
  return capability.startsWith('authority.') ||
    capability === 'policy.override' ||
    capability === 'receipt.forge' ||
    capability === 'secret.readback'
}

export async function regulateSelf(input: SelfRegulationInput): Promise<SelfRegulationDecision> {
  validateSnapshot(input.snapshot)
  const gaps = normalizeGaps(input.gaps)
  const self_model_digest = await hashValue({
    domain: 'AEGIS_SELF_MODEL_V1',
    snapshot: input.snapshot,
    gaps,
  })

  let proposal_digest: SHA256Hex | null = null
  let mode: SelfRegulationMode
  let required_next_gate: RequiredNextGate
  const reasons: string[] = []

  const health = input.snapshot.health
  if (!health.t0_verdict) reasons.push('T0_VERDICT_FALSE')
  if (health.corruption_count > 0) reasons.push('CORRUPTION_DETECTED')
  if (!health.membrane_intact) reasons.push('MEMBRANE_BREACH')

  if (reasons.length > 0) {
    mode = 'HALT'
    required_next_gate = 'REANCHOR'
  } else if (!health.entropy_bounded) {
    mode = 'OBSERVE_ONLY'
    required_next_gate = 'REANCHOR'
    reasons.push('ADAPTATION_EXCEEDS_REPLAY_CAPACITY')
  } else if (gaps.length === 0) {
    mode = 'NO_CHANGE'
    required_next_gate = 'NONE'
    reasons.push('NO_VERIFIED_GAP')
  } else if (input.proposal === undefined) {
    mode = 'PROPOSAL_REQUIRED'
    required_next_gate = 'OPERATOR_REVIEW'
    reasons.push('VERIFIED_GAP_WITHOUT_ADAPTATION_PROPOSAL')
  } else {
    const proposal = normalizeProposal(input.proposal)
    proposal_digest = await hashValue({ domain: 'AEGIS_ADAPTATION_PROPOSAL_V1', proposal })
    const knownGapIds = new Set(gaps.map(gap => gap.gap_id))

    if (proposal.expected_parent_state_root !== input.snapshot.state_root) reasons.push('STALE_PARENT_STATE')
    if (proposal.addressed_gap_ids.length === 0) reasons.push('NO_ADDRESSED_GAPS')
    if (proposal.addressed_gap_ids.some(id => !knownGapIds.has(id))) reasons.push('UNKNOWN_GAP_REFERENCE')
    if (proposal.mutations.length === 0) reasons.push('NO_PROPOSED_MUTATION')
    if (proposal.verification_steps.length === 0) reasons.push('NO_VERIFICATION_PLAN')
    if (proposal.requested_capabilities.some(forbiddenCapability)) reasons.push('FORBIDDEN_CAPABILITY_REQUEST')

    if (['D2', 'D3', 'D4'].includes(proposal.consequence_class) && !proposal.rollback_reference) {
      reasons.push('ROLLBACK_REFERENCE_REQUIRED')
    }
    if (['D3', 'D4'].includes(proposal.consequence_class) && !proposal.operator_approval_reference) {
      reasons.push('OPERATOR_APPROVAL_REQUIRED')
    }
    if (proposal.consequence_class === 'D4' && !proposal.constitutional_change_reference) {
      reasons.push('CONSTITUTIONAL_CHANGE_REFERENCE_REQUIRED')
    }

    if (reasons.length > 0) {
      mode = 'REJECTED'
      required_next_gate = reasons.includes('OPERATOR_APPROVAL_REQUIRED')
        ? 'OPERATOR_REVIEW'
        : 'NONE'
    } else {
      mode = 'READY_FOR_AUTHORITY'
      required_next_gate = 'AUTOMATON_3'
      reasons.push('PROPOSAL_IS_REPLAYABLE_AND_BOUNDED')
    }
  }

  const unsigned = {
    schema_version: SELF_REGULATOR_SCHEMA_VERSION,
    mode,
    reasons: Object.freeze([...reasons]),
    required_next_gate,
    grants_authority: false as const,
    requires_automaton3: mode === 'READY_FOR_AUTHORITY',
    self_model_digest,
    proposal_digest,
  }
  const decision_digest = await hashValue({ domain: 'AEGIS_SELF_REGULATION_DECISION_V1', decision: unsigned })

  return deepFreeze<SelfRegulationDecision>({ ...unsigned, decision_digest })
}
