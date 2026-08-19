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
import { compareUtf8 } from '../core/ordering.js'

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
  readonly verifier_trust_root: SHA256Hex
  readonly health: SelfModelHealth
}

export type SelfModelStateComponents = Omit<SelfModelSnapshot, 'state_root'>

export interface KnowledgeGap {
  readonly gap_id: string
  readonly kind: GapKind
  readonly severity: GapSeverity
  readonly evidence_refs: readonly SHA256Hex[]
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
const ZERO_HASH = '0'.repeat(64)
const SAFE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$/
const SAFE_PATH_SEGMENT_PATTERN = /^[A-Za-z0-9._@+~-]+$/
const DRIVE_PATH_PATTERN = /^[A-Za-z]:/
const URI_SCHEME_PATTERN = /^[A-Za-z][A-Za-z0-9+.-]*:/
const WINDOWS_RESERVED_DEVICE_PATTERN = /^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i
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

function assertResolvedHash(field: string, value: unknown): asserts value is SHA256Hex {
  assertHash(field, value)
  if (value === ZERO_HASH) {
    throw new SelfRegulationError(`${field} must resolve to a non-zero root`)
  }
}

function sortedUnique(field: string, values: readonly string[]): readonly string[] {
  if (!Array.isArray(values)) throw new SelfRegulationError(`${field} must be an array`)
  const normalized = values.map((value, index) => {
    assertNonEmpty(`${field}[${index}]`, value)
    return value.trim()
  })
  const unique = [...new Set(normalized)].sort(compareUtf8)
  if (unique.length !== normalized.length) throw new SelfRegulationError(`${field} must be unique`)
  return unique
}

function normalizeOptionalReference(field: string, value: string | undefined): string | undefined {
  if (value === undefined) return undefined
  assertNonEmpty(field, value)
  return value.trim()
}

/**
 * Validate a canonical POSIX repository-relative path without rewriting it.
 *
 * Rejecting non-canonical spellings is intentional: silently normalizing a
 * mutation target would allow the proposal digest to name different bytes
 * from the path ultimately handed to the repository executor.
 */
function canonicalRepositoryPath(field: string, value: unknown): string {
  assertNonEmpty(field, value)
  if (
    value !== value.trim() ||
    value.startsWith('/') ||
    value.startsWith('\\') ||
    value.includes('\\') ||
    DRIVE_PATH_PATTERN.test(value) ||
    URI_SCHEME_PATTERN.test(value) ||
    value.endsWith('/') ||
    value.includes('//')
  ) {
    throw new SelfRegulationError(`${field} must be a canonical POSIX repository-relative path`)
  }

  const segments = value.split('/')
  if (
    segments.length === 0 ||
    segments.some(segment =>
      segment === '' ||
      segment === '.' ||
      segment === '..' ||
      segment.endsWith('.') ||
      segment.endsWith(' ') ||
      WINDOWS_RESERVED_DEVICE_PATTERN.test(segment) ||
      !SAFE_PATH_SEGMENT_PATTERN.test(segment),
    )
  ) {
    throw new SelfRegulationError(`${field} must be a canonical POSIX repository-relative path`)
  }
  return value
}

function validateStateComponents(snapshot: SelfModelStateComponents): void {
  assertResolvedHash('snapshot.identity_root', snapshot.identity_root)
  assertResolvedHash('snapshot.policy_root', snapshot.policy_root)
  assertResolvedHash('snapshot.capability_root', snapshot.capability_root)
  assertResolvedHash('snapshot.memory_root', snapshot.memory_root)
  assertHash('snapshot.metacognition_root', snapshot.metacognition_root)
  assertResolvedHash('snapshot.verifier_trust_root', snapshot.verifier_trust_root)
  if (!Number.isInteger(snapshot.health.corruption_count) || snapshot.health.corruption_count < 0) {
    throw new SelfRegulationError('snapshot.health.corruption_count must be a non-negative integer')
  }
  for (const field of ['t0_verdict', 'membrane_intact', 'entropy_bounded'] as const) {
    if (typeof snapshot.health[field] !== 'boolean') {
      throw new SelfRegulationError(`snapshot.health.${field} must be boolean`)
    }
  }
}

function validateSnapshot(snapshot: SelfModelSnapshot): void {
  assertHash('snapshot.state_root', snapshot.state_root)
  validateStateComponents(snapshot)
}

/**
 * Bind every authority-relevant self-model component into one deterministic
 * state root. Callers may not provide an unrelated label as `state_root`.
 */
export async function hashSelfModelStateRootV1(
  snapshot: SelfModelStateComponents,
): Promise<SHA256Hex> {
  validateStateComponents(snapshot)
  return hashValue({
    domain: 'AEGIS_SELF_MODEL_STATE_V1',
    snapshot,
  })
}

export function normalizeKnowledgeGaps(gaps: readonly KnowledgeGap[]): readonly KnowledgeGap[] {
  if (!Array.isArray(gaps)) throw new SelfRegulationError('gaps must be an array')
  const ids = new Set<string>()
  const normalized = gaps.map((gap, index) => {
    if (!SAFE_ID_PATTERN.test(gap.gap_id)) throw new SelfRegulationError(`gaps[${index}].gap_id is invalid`)
    if (ids.has(gap.gap_id)) throw new SelfRegulationError('gap_id values must be unique')
    ids.add(gap.gap_id)
    if (!VALID_KINDS.has(gap.kind)) throw new SelfRegulationError(`gaps[${index}].kind is invalid`)
    if (!VALID_SEVERITIES.has(gap.severity)) throw new SelfRegulationError(`gaps[${index}].severity is invalid`)
    const evidenceReferences = sortedUnique(`gaps[${index}].evidence_refs`, gap.evidence_refs)
    if (evidenceReferences.length === 0) {
      throw new SelfRegulationError(`gaps[${index}].evidence_refs must contain verified evidence`)
    }
    const evidence_refs = evidenceReferences.map((reference, evidenceIndex) => {
      assertResolvedHash(`gaps[${index}].evidence_refs[${evidenceIndex}]`, reference)
      return reference
    })
    return {
      gap_id: gap.gap_id,
      kind: gap.kind,
      severity: gap.severity,
      evidence_refs,
    }
  })
  return normalized.sort((a, b) => compareUtf8(a.gap_id, b.gap_id))
}

export function normalizeAdaptationProposal(proposal: AdaptationProposal): AdaptationProposal {
  if (!SAFE_ID_PATTERN.test(proposal.proposal_id)) throw new SelfRegulationError('proposal.proposal_id is invalid')
  assertNonEmpty('proposal.objective', proposal.objective)
  if (!VALID_CLASSES.has(proposal.consequence_class)) throw new SelfRegulationError('proposal.consequence_class is invalid')
  assertHash('proposal.expected_parent_state_root', proposal.expected_parent_state_root)

  if (!Array.isArray(proposal.mutations)) throw new SelfRegulationError('proposal.mutations must be an array')
  const mutationOperationsByPath = new Map<string, ProposedMutation['operation']>()
  const mutationPathByCaseFold = new Map<string, string>()
  const mutations = proposal.mutations.map((mutation, index) => {
    const path = canonicalRepositoryPath(`proposal.mutations[${index}].path`, mutation.path)
    if (!VALID_OPERATIONS.has(mutation.operation)) throw new SelfRegulationError(`proposal.mutations[${index}].operation is invalid`)
    const priorOperation = mutationOperationsByPath.get(path)
    if (priorOperation !== undefined) {
      const qualifier = priorOperation === mutation.operation ? 'duplicate' : 'conflicting'
      throw new SelfRegulationError(`proposal.mutations[${index}].path has a ${qualifier} operation`)
    }
    mutationOperationsByPath.set(path, mutation.operation)
    const caseFoldedPath = path.toLowerCase()
    const priorCaseVariant = mutationPathByCaseFold.get(caseFoldedPath)
    if (priorCaseVariant !== undefined && priorCaseVariant !== path) {
      throw new SelfRegulationError(`proposal.mutations[${index}].path collides after Windows case folding`)
    }
    mutationPathByCaseFold.set(caseFoldedPath, path)
    if (mutation.expected_blob !== undefined && !/^[0-9a-f]{40,64}$/.test(mutation.expected_blob)) {
      throw new SelfRegulationError(`proposal.mutations[${index}].expected_blob is invalid`)
    }
    return mutation.expected_blob === undefined
      ? { path, operation: mutation.operation }
      : { path, operation: mutation.operation, expected_blob: mutation.expected_blob }
  })

  if (!Array.isArray(proposal.verification_steps)) {
    throw new SelfRegulationError('proposal.verification_steps must be an array')
  }
  const verification_steps = proposal.verification_steps.map((step, index) => {
    assertNonEmpty(`proposal.verification_steps[${index}]`, step)
    return step.trim()
  })

  const rollback_reference = normalizeOptionalReference(
    'proposal.rollback_reference',
    proposal.rollback_reference,
  )
  const operator_approval_reference = normalizeOptionalReference(
    'proposal.operator_approval_reference',
    proposal.operator_approval_reference,
  )
  const constitutional_change_reference = normalizeOptionalReference(
    'proposal.constitutional_change_reference',
    proposal.constitutional_change_reference,
  )

  return {
    proposal_id: proposal.proposal_id,
    objective: proposal.objective.trim(),
    consequence_class: proposal.consequence_class,
    expected_parent_state_root: proposal.expected_parent_state_root,
    addressed_gap_ids: sortedUnique('proposal.addressed_gap_ids', proposal.addressed_gap_ids),
    requested_capabilities: sortedUnique('proposal.requested_capabilities', proposal.requested_capabilities),
    mutations,
    verification_steps,
    ...(rollback_reference === undefined ? {} : { rollback_reference }),
    ...(operator_approval_reference === undefined ? {} : { operator_approval_reference }),
    ...(constitutional_change_reference === undefined ? {} : { constitutional_change_reference }),
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
  const { state_root: suppliedStateRoot, ...stateComponents } = input.snapshot
  const expectedStateRoot = await hashSelfModelStateRootV1(stateComponents)
  if (suppliedStateRoot !== expectedStateRoot) {
    throw new SelfRegulationError('snapshot.state_root does not bind the self-model components')
  }
  const gaps = normalizeKnowledgeGaps(input.gaps)
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
    const proposal = normalizeAdaptationProposal(input.proposal)
    proposal_digest = await hashValue({ domain: 'AEGIS_ADAPTATION_PROPOSAL_V1', proposal })
    const knownGapIds = new Set(gaps.map(gap => gap.gap_id))

    if (proposal.expected_parent_state_root !== input.snapshot.state_root) reasons.push('STALE_PARENT_STATE')
    if (proposal.addressed_gap_ids.length === 0) reasons.push('NO_ADDRESSED_GAPS')
    if (proposal.addressed_gap_ids.some(id => !knownGapIds.has(id))) reasons.push('UNKNOWN_GAP_REFERENCE')
    if (proposal.mutations.length === 0) reasons.push('NO_PROPOSED_MUTATION')
    if (proposal.consequence_class === 'D0' && proposal.mutations.length > 0) {
      reasons.push('D0_MUTATION_FORBIDDEN')
    }
    if (proposal.verification_steps.length === 0) reasons.push('NO_VERIFICATION_PLAN')
    if (proposal.requested_capabilities.some(forbiddenCapability)) reasons.push('FORBIDDEN_CAPABILITY_REQUEST')

    if (['D1', 'D2', 'D3', 'D4'].includes(proposal.consequence_class) && !proposal.rollback_reference) {
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
