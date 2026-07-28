// ============================================================
// SOVEREIGN OMEGA — Adaptation Outcome Comparator
// EPISTEMIC TIER: T2 · deterministic, tested governance primitive
//
// Compares a bounded adaptation proposal with separately rooted,
// verifier-certified authority, terminal-execution, and outcome evidence.
// The verifier trust policy must be authenticated against an operator key
// supplied outside the evidence bundle. This module only recommends a next
// action. It never grants authority, executes a mutation, advances a lease,
// or changes competence.
// ============================================================

import type { SequenceNumber, SHA256Hex } from '../core/types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import { compareUtf8 } from '../core/ordering.js'
import { verifyBytes } from '../consensus/crypto.js'
import type { MetacognitiveEntry } from './loop.js'
import { MetacognitiveLoop } from './loop.js'
import type {
  AdaptationProposal,
  KnowledgeGap,
  SelfModelSnapshot,
} from './self-regulator.js'
import {
  normalizeAdaptationProposal,
  normalizeKnowledgeGaps,
  regulateSelf,
} from './self-regulator.js'

export const OUTCOME_COMPARATOR_SCHEMA_VERSION = '1.0.0' as const

export type AuthorityOutcome = 'ADMITTED' | 'DENIED'
export type TerminalExecutionOutcome = 'SUCCEEDED' | 'DENIED' | 'FAILED' | 'ROLLED_BACK'
export type DurableTerminalStatus = 'COMPLETED' | 'DENIED' | 'FAILED' | 'CANCELLED' | 'ORPHANED'
export type VerificationVerdict = 'PASS' | 'FAIL' | 'INCONCLUSIVE'
export type VerificationMode = 'INDEPENDENT' | 'EXECUTOR_SELF_REPORT'
export type StateDisposition = 'PRESERVE' | 'REVERT' | 'NO_STATE_CHANGE'
export type EvidenceDisposition = 'CONFIRM' | 'DEGRADE' | 'INCONCLUSIVE'
export type OutcomeNextGate = 'OPERATOR_REVIEW' | 'AUTOMATON_3'

export interface AdaptationAuthorityBindingV1 {
  readonly proposal_digest: SHA256Hex
  readonly self_regulation_decision_digest: SHA256Hex
  readonly expected_parent_state_root: SHA256Hex
}

export interface AdaptationAuthorityEvidenceV1 {
  readonly evidence_kind: 'AUTOMATON3_AUTHORITY_DECISION_V1'
  readonly outcome: AuthorityOutcome
  readonly denial_codes: readonly string[]
  readonly execution_identity_root: SHA256Hex
  readonly workspace_binding: SHA256Hex
  readonly policy_root: SHA256Hex
  readonly registry_root: SHA256Hex
  readonly policy_decision_root: SHA256Hex
  readonly authority_receipt_root: SHA256Hex
  readonly executor_principal_root: SHA256Hex
  readonly executor_workload_identity_root: SHA256Hex
  readonly action_binding: AdaptationAuthorityBindingV1
  readonly requested_action_digest: SHA256Hex
}

export interface TerminalExecutionEvidenceV1 {
  readonly evidence_kind: 'AUTOMATON3_TERMINAL_EXECUTION_V1'
  readonly execution_identity_root: SHA256Hex
  readonly workspace_binding: SHA256Hex
  readonly policy_decision_root: SHA256Hex
  readonly authority_receipt_root: SHA256Hex
  readonly requested_action_digest: SHA256Hex
  readonly lease_outcome: AuthorityOutcome
  readonly lease_authorization_receipt_root: SHA256Hex
  readonly durable_execution_root: SHA256Hex
  readonly durable_status: DurableTerminalStatus
  readonly mutation_receipt_root: SHA256Hex
  readonly receipt_chain_status: 'VERIFIED' | 'UNVERIFIED'
  readonly receipt_chain_verification_root: SHA256Hex
  readonly outcome: TerminalExecutionOutcome
  readonly pre_state_root: SHA256Hex
  readonly post_state_root: SHA256Hex
  readonly provider_result_digest: SHA256Hex
  readonly operator_notification_root: SHA256Hex
}

export interface VerificationObservation {
  readonly step_index: number
  readonly verdict: VerificationVerdict
  readonly evidence_digest: SHA256Hex
  readonly verifier_identity_root: SHA256Hex
  readonly verification_mode: VerificationMode
}

export interface OutcomeEvidenceCertificateV1 {
  readonly certificate_kind: 'AEGIS_OUTCOME_EVIDENCE_CERTIFICATE_V1'
  readonly verifier_key_id: string
  readonly verifier_public_key: string
  readonly verifier_identity_root: SHA256Hex
  readonly verifier_principal_root: SHA256Hex
  readonly verifier_workload_identity_root: SHA256Hex
  readonly evidence_bundle_digest: SHA256Hex
  readonly signature: string
}

export interface OutcomeVerifierIdentityV1 {
  readonly verifier_key_id: string
  readonly verifier_public_key: string
  readonly verifier_identity_root: SHA256Hex
  readonly verifier_principal_root: SHA256Hex
  readonly verifier_workload_identity_root: SHA256Hex
}

export interface OutcomeVerifierTrustPolicyV1 {
  readonly schema_version: '1.0.0'
  readonly policy_kind: 'AEGIS_OUTCOME_VERIFIER_TRUST_POLICY_V1'
  readonly governed_policy_root: SHA256Hex
  readonly verifier_trust_root: SHA256Hex
  readonly verifiers: readonly OutcomeVerifierIdentityV1[]
  readonly signer_key_id: string
  readonly signer_public_key: string
  readonly signature: string
}

/**
 * An in-process capability returned only after a trust policy signature has
 * been verified against an operator public key supplied out of band.
 * Serialized evidence cannot manufacture this value.
 */
export interface VerifiedOutcomeVerifierTrustAnchorV1 {
  readonly governed_policy_root: SHA256Hex
  readonly verifier_trust_root: SHA256Hex
  readonly verifiers: readonly OutcomeVerifierIdentityV1[]
  readonly trust_policy_digest: SHA256Hex
}

export interface AdaptationOutcomeInput {
  readonly baseline: {
    readonly snapshot: SelfModelSnapshot
    readonly gaps: readonly KnowledgeGap[]
    readonly proposal: AdaptationProposal
  }
  readonly authority: AdaptationAuthorityEvidenceV1
  readonly terminal_execution?: TerminalExecutionEvidenceV1
  readonly post_snapshot: SelfModelSnapshot
  readonly post_gaps: readonly KnowledgeGap[]
  readonly verification: readonly VerificationObservation[]
  readonly evidence_certificate?: OutcomeEvidenceCertificateV1
}

export interface AdaptationOutcomeAssessment {
  readonly schema_version: typeof OUTCOME_COMPARATOR_SCHEMA_VERSION
  readonly state_disposition: StateDisposition
  readonly evidence_disposition: EvidenceDisposition
  readonly reason_codes: readonly string[]
  readonly required_next_gate: OutcomeNextGate
  readonly grants_authority: false
  readonly executes_mutation: false
  readonly updates_competence: false
  readonly requires_automaton3: boolean
  readonly learning_evidence_eligible: boolean
  readonly source_decision_digest: SHA256Hex
  readonly proposal_digest: SHA256Hex | null
  readonly authority_evidence_digest: SHA256Hex
  readonly authority_decision_root: SHA256Hex
  readonly requested_action_digest: SHA256Hex
  readonly terminal_evidence_digest: SHA256Hex | null
  readonly terminal_receipt_root: SHA256Hex | null
  readonly evidence_bundle_digest: SHA256Hex
  readonly evidence_certificate_digest: SHA256Hex | null
  readonly evidence_certificate_verified: boolean
  readonly verifier_trust_policy_digest: SHA256Hex
  readonly pre_state_root: SHA256Hex
  readonly post_state_root: SHA256Hex
  readonly expected_previous_metacognition_root: SHA256Hex
  readonly resolved_gap_ids: readonly string[]
  readonly remaining_addressed_gap_ids: readonly string[]
  readonly new_gap_ids: readonly string[]
  readonly verification_digest: SHA256Hex
  readonly post_self_model_digest: SHA256Hex
  readonly assessment_digest: SHA256Hex
}

export interface OutcomeEvidenceArtifactV1 {
  readonly schema_version: typeof OUTCOME_COMPARATOR_SCHEMA_VERSION
  readonly artifact_kind: 'AEGIS_OUTCOME_EVIDENCE_ARTIFACT_V1'
  readonly evidence_input: Readonly<Record<string, unknown>>
  readonly verifier_trust_anchor: {
    readonly governed_policy_root: SHA256Hex
    readonly verifier_trust_root: SHA256Hex
    readonly verifiers: readonly OutcomeVerifierIdentityV1[]
    readonly trust_policy_digest: SHA256Hex
  }
  readonly assessment: AdaptationOutcomeAssessment
  readonly artifact_root: SHA256Hex
}

export interface OutcomeEvidencePersistenceReceiptV1 {
  readonly artifact_root: SHA256Hex
  readonly artifact_reference: string
}

/**
 * A caller-supplied persistence boundary. Returning a receipt is a claim that
 * the complete artifact can be resolved by ``artifact_reference``. The
 * comparator verifies the content root before it appends a metacognitive
 * observation; it does not claim storage durability beyond this contract.
 */
export interface OutcomeEvidenceArtifactStore {
  persist(
    artifact: OutcomeEvidenceArtifactV1,
  ): Promise<OutcomeEvidencePersistenceReceiptV1>
}

export class OutcomeComparisonError extends Error {
  override readonly name = 'OutcomeComparisonError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const HASH_PATTERN = /^[0-9a-f]{64}$/
const ZERO_HASH = '0'.repeat(64)
const SIGNATURE_PATTERN = /^[0-9a-f]{128}$/
const SAFE_KEY_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$/
const AUTHORITY_OUTCOMES = new Set<AuthorityOutcome>(['ADMITTED', 'DENIED'])
const TERMINAL_OUTCOMES = new Set<TerminalExecutionOutcome>(['SUCCEEDED', 'DENIED', 'FAILED', 'ROLLED_BACK'])
const DURABLE_STATUSES = new Set<DurableTerminalStatus>(['COMPLETED', 'DENIED', 'FAILED', 'CANCELLED', 'ORPHANED'])
const VERDICTS = new Set<VerificationVerdict>(['PASS', 'FAIL', 'INCONCLUSIVE'])
const VERIFICATION_MODES = new Set<VerificationMode>(['INDEPENDENT', 'EXECUTOR_SELF_REPORT'])
const VERIFIED_TRUST_ANCHORS = new WeakSet<object>()

function assertHash(field: string, value: unknown): asserts value is SHA256Hex {
  if (typeof value !== 'string' || !HASH_PATTERN.test(value)) {
    throw new OutcomeComparisonError(`${field} must be lowercase SHA-256 hex`)
  }
}

function assertResolvedHash(field: string, value: unknown): asserts value is SHA256Hex {
  assertHash(field, value)
  if (value === ZERO_HASH) {
    throw new OutcomeComparisonError(`${field} must resolve to a non-zero identity or evidence root`)
  }
}

function normalizeCodes(field: string, values: readonly string[]): readonly string[] {
  if (!Array.isArray(values)) throw new OutcomeComparisonError(`${field} must be an array`)
  const normalized = values.map((value, index) => {
    if (typeof value !== 'string' || value.trim() === '') {
      throw new OutcomeComparisonError(`${field}[${index}] must be a non-empty string`)
    }
    return value.trim()
  })
  const unique = [...new Set(normalized)].sort(compareUtf8)
  if (unique.length !== normalized.length) throw new OutcomeComparisonError(`${field} must be unique`)
  return unique
}

function validateAuthorityBinding(binding: AdaptationAuthorityBindingV1): void {
  assertHash('authority.action_binding.proposal_digest', binding.proposal_digest)
  assertHash('authority.action_binding.self_regulation_decision_digest', binding.self_regulation_decision_digest)
  assertHash('authority.action_binding.expected_parent_state_root', binding.expected_parent_state_root)
}

function normalizeVerifierPublicKeys(values: readonly string[]): readonly string[] {
  if (!Array.isArray(values) || values.length === 0) {
    throw new OutcomeComparisonError('trusted_verifier_public_keys must be a non-empty array')
  }
  const normalized = values.map((value, index) => {
    if (typeof value !== 'string' || !HASH_PATTERN.test(value)) {
      throw new OutcomeComparisonError(`trusted_verifier_public_keys[${index}] must be 32-byte lowercase hex`)
    }
    if (value === ZERO_HASH) {
      throw new OutcomeComparisonError(`trusted_verifier_public_keys[${index}] must not be unresolved`)
    }
    return value
  })
  const unique = [...new Set(normalized)].sort(compareUtf8)
  if (unique.length !== normalized.length) {
    throw new OutcomeComparisonError('trusted_verifier_public_keys must be unique')
  }
  return unique
}

export async function hashVerifierIdentityV1(publicKey: string): Promise<SHA256Hex> {
  const normalized = normalizeVerifierPublicKeys([publicKey])[0]!
  return hashValue({ domain: 'AEGIS_VERIFIER_IDENTITY_V1', public_key: normalized })
}

async function normalizeVerifierIdentities(
  values: readonly OutcomeVerifierIdentityV1[],
): Promise<readonly OutcomeVerifierIdentityV1[]> {
  if (!Array.isArray(values) || values.length === 0) {
    throw new OutcomeComparisonError('verifiers must be a non-empty array')
  }
  const normalized = await Promise.all(values.map(async (value, index) => {
    if (!SAFE_KEY_ID_PATTERN.test(value.verifier_key_id)) {
      throw new OutcomeComparisonError(`verifiers[${index}].verifier_key_id is invalid`)
    }
    const verifier_public_key = normalizeVerifierPublicKeys([value.verifier_public_key])[0]!
    assertResolvedHash(`verifiers[${index}].verifier_identity_root`, value.verifier_identity_root)
    assertResolvedHash(`verifiers[${index}].verifier_principal_root`, value.verifier_principal_root)
    assertResolvedHash(
      `verifiers[${index}].verifier_workload_identity_root`,
      value.verifier_workload_identity_root,
    )
    const expectedIdentityRoot = await hashVerifierIdentityV1(verifier_public_key)
    if (value.verifier_identity_root !== expectedIdentityRoot) {
      throw new OutcomeComparisonError(`verifiers[${index}].verifier_identity_root is invalid`)
    }
    return {
      verifier_key_id: value.verifier_key_id,
      verifier_public_key,
      verifier_identity_root: value.verifier_identity_root,
      verifier_principal_root: value.verifier_principal_root,
      verifier_workload_identity_root: value.verifier_workload_identity_root,
    }
  }))
  normalized.sort((left, right) => compareUtf8(left.verifier_key_id, right.verifier_key_id))
  const keyIds = normalized.map(value => value.verifier_key_id)
  const publicKeys = normalized.map(value => value.verifier_public_key)
  if (new Set(keyIds).size !== keyIds.length) {
    throw new OutcomeComparisonError('verifier_key_id values must be unique')
  }
  if (new Set(publicKeys).size !== publicKeys.length) {
    throw new OutcomeComparisonError('verifier public keys must be unique')
  }
  return normalized
}

export async function hashVerifierTrustSetV1(
  verifiers: readonly OutcomeVerifierIdentityV1[],
): Promise<SHA256Hex> {
  const normalized = await normalizeVerifierIdentities(verifiers)
  return hashValue({ domain: 'AEGIS_VERIFIER_TRUST_SET_V1', verifiers: normalized })
}

export async function canonicalizeOutcomeVerifierTrustPolicyMessageV1(
  policy: Omit<OutcomeVerifierTrustPolicyV1, 'signature'>,
): Promise<Uint8Array> {
  if (policy.schema_version !== '1.0.0') {
    throw new OutcomeComparisonError('trust policy schema_version is invalid')
  }
  if (policy.policy_kind !== 'AEGIS_OUTCOME_VERIFIER_TRUST_POLICY_V1') {
    throw new OutcomeComparisonError('trust policy kind is invalid')
  }
  assertResolvedHash('trust_policy.governed_policy_root', policy.governed_policy_root)
  assertResolvedHash('trust_policy.verifier_trust_root', policy.verifier_trust_root)
  if (!SAFE_KEY_ID_PATTERN.test(policy.signer_key_id)) {
    throw new OutcomeComparisonError('trust_policy.signer_key_id is invalid')
  }
  const signer_public_key = normalizeVerifierPublicKeys([policy.signer_public_key])[0]!
  const verifiers = await normalizeVerifierIdentities(policy.verifiers)
  return canonicalizeJCS({
    domain: 'AEGIS_OUTCOME_VERIFIER_TRUST_POLICY_V1',
    policy: {
      schema_version: policy.schema_version,
      policy_kind: policy.policy_kind,
      governed_policy_root: policy.governed_policy_root,
      verifier_trust_root: policy.verifier_trust_root,
      verifiers,
      signer_key_id: policy.signer_key_id,
      signer_public_key,
    },
  })
}

export async function verifyOutcomeVerifierTrustPolicyV1(
  policy: OutcomeVerifierTrustPolicyV1,
  expectedGovernedPolicyRoot: SHA256Hex,
  expectedOperatorPublicKey: string,
): Promise<VerifiedOutcomeVerifierTrustAnchorV1> {
  assertHash('expected_governed_policy_root', expectedGovernedPolicyRoot)
  const operatorPublicKey = normalizeVerifierPublicKeys([expectedOperatorPublicKey])[0]!
  if (!SIGNATURE_PATTERN.test(policy.signature)) {
    throw new OutcomeComparisonError('trust_policy.signature must be 64-byte lowercase Ed25519 hex')
  }
  if (policy.governed_policy_root !== expectedGovernedPolicyRoot) {
    throw new OutcomeComparisonError('trust policy is not bound to the expected governed policy root')
  }
  if (policy.signer_public_key !== operatorPublicKey) {
    throw new OutcomeComparisonError('trust policy signer is not the expected operator key')
  }
  const verifiers = await normalizeVerifierIdentities(policy.verifiers)
  const verifierTrustRoot = await hashVerifierTrustSetV1(verifiers)
  if (policy.verifier_trust_root !== verifierTrustRoot) {
    throw new OutcomeComparisonError('trust policy verifier root does not match its verifier set')
  }
  const { signature: _signature, ...unsignedPolicy } = policy
  const message = await canonicalizeOutcomeVerifierTrustPolicyMessageV1(unsignedPolicy)
  if (!await verifyBytes(operatorPublicKey, message, policy.signature)) {
    throw new OutcomeComparisonError('trust policy signature is invalid')
  }
  const trust_policy_digest = await hashValue({
    domain: 'AEGIS_OUTCOME_VERIFIER_TRUST_POLICY_RECORD_V1',
    policy: { ...unsignedPolicy, verifiers, signature: policy.signature },
  })
  const anchor = deepFreeze<VerifiedOutcomeVerifierTrustAnchorV1>({
    governed_policy_root: expectedGovernedPolicyRoot,
    verifier_trust_root: verifierTrustRoot,
    verifiers,
    trust_policy_digest,
  })
  VERIFIED_TRUST_ANCHORS.add(anchor)
  return anchor
}

export function canonicalizeOutcomeEvidenceCertificateMessageV1(
  certificate: Omit<OutcomeEvidenceCertificateV1, 'signature'>,
): Uint8Array {
  validateEvidenceCertificateFields(certificate)
  return canonicalizeJCS({
    domain: 'AEGIS_OUTCOME_EVIDENCE_CERTIFICATE_V1',
    certificate,
  })
}

export async function hashAdaptationAuthorityBinding(
  binding: AdaptationAuthorityBindingV1,
): Promise<SHA256Hex> {
  validateAuthorityBinding(binding)
  return hashValue({ domain: 'AEGIS_ADAPTATION_AUTHORITY_BINDING_V1', binding })
}

function validateAuthorityEvidence(authority: AdaptationAuthorityEvidenceV1): readonly string[] {
  if (authority.evidence_kind !== 'AUTOMATON3_AUTHORITY_DECISION_V1') {
    throw new OutcomeComparisonError('authority.evidence_kind is invalid')
  }
  if (!AUTHORITY_OUTCOMES.has(authority.outcome)) {
    throw new OutcomeComparisonError('authority.outcome is invalid')
  }
  const denialCodes = normalizeCodes('authority.denial_codes', authority.denial_codes)
  if (authority.outcome === 'ADMITTED' && denialCodes.length !== 0) {
    throw new OutcomeComparisonError('admitted authority evidence cannot contain denial codes')
  }
  if (authority.outcome === 'DENIED' && denialCodes.length === 0) {
    throw new OutcomeComparisonError('denied authority evidence requires a denial code')
  }
  for (const field of [
    'execution_identity_root',
    'workspace_binding',
    'policy_root',
    'registry_root',
    'policy_decision_root',
    'authority_receipt_root',
    'executor_principal_root',
    'executor_workload_identity_root',
    'requested_action_digest',
  ] as const) {
    assertResolvedHash(`authority.${field}`, authority[field])
  }
  validateAuthorityBinding(authority.action_binding)
  return denialCodes
}

function validateTerminalEvidence(terminal: TerminalExecutionEvidenceV1): void {
  if (terminal.evidence_kind !== 'AUTOMATON3_TERMINAL_EXECUTION_V1') {
    throw new OutcomeComparisonError('terminal_execution.evidence_kind is invalid')
  }
  if (!AUTHORITY_OUTCOMES.has(terminal.lease_outcome)) {
    throw new OutcomeComparisonError('terminal_execution.lease_outcome is invalid')
  }
  if (!DURABLE_STATUSES.has(terminal.durable_status)) {
    throw new OutcomeComparisonError('terminal_execution.durable_status is invalid')
  }
  if (!TERMINAL_OUTCOMES.has(terminal.outcome)) {
    throw new OutcomeComparisonError('terminal_execution.outcome is invalid')
  }
  if (!['VERIFIED', 'UNVERIFIED'].includes(terminal.receipt_chain_status)) {
    throw new OutcomeComparisonError('terminal_execution.receipt_chain_status is invalid')
  }
  for (const field of [
    'execution_identity_root',
    'workspace_binding',
    'policy_decision_root',
    'authority_receipt_root',
    'requested_action_digest',
    'lease_authorization_receipt_root',
    'durable_execution_root',
    'mutation_receipt_root',
    'receipt_chain_verification_root',
    'pre_state_root',
    'post_state_root',
    'provider_result_digest',
    'operator_notification_root',
  ] as const) {
    assertHash(`terminal_execution.${field}`, terminal[field])
  }
}

function normalizeVerification(
  observations: readonly VerificationObservation[],
  stepCount: number,
): readonly VerificationObservation[] {
  if (!Array.isArray(observations)) throw new OutcomeComparisonError('verification must be an array')
  const indices = new Set<number>()
  const normalized = observations.map((observation, index) => {
    if (!Number.isInteger(observation.step_index) || observation.step_index < 0 || observation.step_index >= stepCount) {
      throw new OutcomeComparisonError(`verification[${index}].step_index is out of range`)
    }
    if (indices.has(observation.step_index)) {
      throw new OutcomeComparisonError('verification step indices must be unique')
    }
    indices.add(observation.step_index)
    if (!VERDICTS.has(observation.verdict)) {
      throw new OutcomeComparisonError(`verification[${index}].verdict is invalid`)
    }
    if (!VERIFICATION_MODES.has(observation.verification_mode)) {
      throw new OutcomeComparisonError(`verification[${index}].verification_mode is invalid`)
    }
    assertHash(`verification[${index}].evidence_digest`, observation.evidence_digest)
    assertHash(`verification[${index}].verifier_identity_root`, observation.verifier_identity_root)
    return { ...observation }
  })
  return normalized.sort((left, right) => left.step_index - right.step_index)
}

export type OutcomeEvidenceInputV1 = Omit<
  AdaptationOutcomeInput,
  'evidence_certificate'
>

export async function hashOutcomeEvidenceBundleV1(
  input: OutcomeEvidenceInputV1,
): Promise<SHA256Hex> {
  const proposal = normalizeAdaptationProposal(input.baseline.proposal)
  const baselineGaps = normalizeKnowledgeGaps(input.baseline.gaps)
  const postGaps = normalizeKnowledgeGaps(input.post_gaps)
  const denialCodes = validateAuthorityEvidence(input.authority)
  if (input.terminal_execution !== undefined) validateTerminalEvidence(input.terminal_execution)
  const verification = normalizeVerification(input.verification, proposal.verification_steps.length)
  return hashValue({
    domain: 'AEGIS_OUTCOME_EVIDENCE_BUNDLE_V1',
    evidence: {
      baseline: {
        snapshot: input.baseline.snapshot,
        gaps: baselineGaps,
        proposal,
      },
      authority: { ...input.authority, denial_codes: denialCodes },
      terminal_execution: input.terminal_execution ?? null,
      post_snapshot: input.post_snapshot,
      post_gaps: postGaps,
      verification,
    },
  })
}

function validateEvidenceCertificateFields(
  certificate: Omit<OutcomeEvidenceCertificateV1, 'signature'>,
): void {
  if (certificate.certificate_kind !== 'AEGIS_OUTCOME_EVIDENCE_CERTIFICATE_V1') {
    throw new OutcomeComparisonError('evidence_certificate.certificate_kind is invalid')
  }
  if (!SAFE_KEY_ID_PATTERN.test(certificate.verifier_key_id)) {
    throw new OutcomeComparisonError('evidence_certificate.verifier_key_id is invalid')
  }
  if (!HASH_PATTERN.test(certificate.verifier_public_key)) {
    throw new OutcomeComparisonError('evidence_certificate.verifier_public_key must be 32-byte lowercase hex')
  }
  assertResolvedHash('evidence_certificate.verifier_identity_root', certificate.verifier_identity_root)
  assertResolvedHash('evidence_certificate.verifier_principal_root', certificate.verifier_principal_root)
  assertResolvedHash(
    'evidence_certificate.verifier_workload_identity_root',
    certificate.verifier_workload_identity_root,
  )
  assertHash('evidence_certificate.evidence_bundle_digest', certificate.evidence_bundle_digest)
}

function validateEvidenceCertificate(certificate: OutcomeEvidenceCertificateV1): void {
  validateEvidenceCertificateFields(certificate)
  if (!SIGNATURE_PATTERN.test(certificate.signature)) {
    throw new OutcomeComparisonError('evidence_certificate.signature must be 64-byte lowercase Ed25519 hex')
  }
}

function expectedDurableStatus(outcome: TerminalExecutionOutcome): DurableTerminalStatus {
  switch (outcome) {
    case 'SUCCEEDED':
    case 'ROLLED_BACK':
      return 'COMPLETED'
    case 'DENIED':
      return 'DENIED'
    case 'FAILED':
      return 'FAILED'
  }
}

function gapIds(gaps: readonly KnowledgeGap[]): readonly string[] {
  return gaps.map(gap => gap.gap_id).sort(compareUtf8)
}

function componentTransitionViolations(
  baseline: SelfModelSnapshot,
  post: SelfModelSnapshot,
  consequenceClass: AdaptationProposal['consequence_class'],
): readonly string[] {
  const reasons: string[] = []
  const changed = (field: keyof Omit<SelfModelSnapshot, 'state_root' | 'health'>): boolean =>
    baseline[field] !== post[field]

  if (changed('verifier_trust_root')) {
    // Rotation needs an operator-signed, dual-key transition contract. Merely
    // labelling a proposal D4 is not rotation evidence.
    reasons.push('VERIFIER_TRUST_ROTATION_EVIDENCE_REQUIRED')
  }
  if (changed('identity_root') && consequenceClass !== 'D4') {
    reasons.push('IDENTITY_TRANSITION_REQUIRES_D4')
  }
  if (changed('policy_root') && consequenceClass !== 'D4') {
    reasons.push('POLICY_TRANSITION_REQUIRES_D4')
  }
  if (changed('capability_root') && !['D2', 'D3', 'D4'].includes(consequenceClass)) {
    reasons.push('CAPABILITY_TRANSITION_REQUIRES_D2')
  }
  if (consequenceClass === 'D0' && (
    changed('memory_root') || changed('metacognition_root')
  )) {
    reasons.push('D0_COMPONENT_TRANSITION_FORBIDDEN')
  }
  return reasons
}

export async function assessAdaptationOutcome(
  input: AdaptationOutcomeInput,
  trustAnchor: VerifiedOutcomeVerifierTrustAnchorV1,
): Promise<AdaptationOutcomeAssessment> {
  if (!VERIFIED_TRUST_ANCHORS.has(trustAnchor)) {
    throw new OutcomeComparisonError(
      'verifier trust anchor was not authenticated by verifyOutcomeVerifierTrustPolicyV1',
    )
  }
  const baselineGaps = normalizeKnowledgeGaps(input.baseline.gaps)
  const postGaps = normalizeKnowledgeGaps(input.post_gaps)
  const proposal = normalizeAdaptationProposal(input.baseline.proposal)
  const sourceDecision = await regulateSelf({
    snapshot: input.baseline.snapshot,
    gaps: baselineGaps,
    proposal,
  })
  const postDecision = await regulateSelf({ snapshot: input.post_snapshot, gaps: postGaps })
  const denialCodes = validateAuthorityEvidence(input.authority)
  const expectedActionDigest = await hashAdaptationAuthorityBinding(input.authority.action_binding)
  const verification = normalizeVerification(
    input.verification,
    proposal.verification_steps.length,
  )
  const verification_digest = await hashValue({
    domain: 'AEGIS_ADAPTATION_VERIFICATION_V1',
    verification,
  })
  const authority_evidence_digest = await hashValue({
    domain: 'AEGIS_ADAPTATION_AUTHORITY_EVIDENCE_V1',
    authority: { ...input.authority, denial_codes: denialCodes },
  })

  const reasons: string[] = []
  const proposalDigest = sourceDecision.proposal_digest
  const authority = input.authority
  const evidence_bundle_digest = await hashOutcomeEvidenceBundleV1(input)
  let evidence_certificate_digest: SHA256Hex | null = null
  let evidence_certificate_verified = false
  const anchorPolicyMatches =
    trustAnchor.governed_policy_root === input.baseline.snapshot.policy_root
  const anchorTrustRootMatches =
    trustAnchor.verifier_trust_root === input.baseline.snapshot.verifier_trust_root
  if (!anchorPolicyMatches) reasons.push('VERIFIER_TRUST_POLICY_ROOT_MISMATCH')
  if (!anchorTrustRootMatches) reasons.push('VERIFIER_TRUST_ROOT_MISMATCH')

  const transitionReasons = componentTransitionViolations(
    input.baseline.snapshot,
    input.post_snapshot,
    proposal.consequence_class,
  )
  reasons.push(...transitionReasons)
  const componentTransitionValid = transitionReasons.length === 0

  const certificate = input.evidence_certificate
  if (certificate === undefined) {
    reasons.push('EVIDENCE_CERTIFICATE_MISSING')
  } else {
    validateEvidenceCertificate(certificate)
    evidence_certificate_digest = await hashValue({
      domain: 'AEGIS_OUTCOME_EVIDENCE_CERTIFICATE_RECORD_V1',
      certificate,
    })
    const expectedVerifierIdentity = await hashVerifierIdentityV1(certificate.verifier_public_key)
    const trustedVerifier = trustAnchor.verifiers.find(
      verifier => verifier.verifier_key_id === certificate.verifier_key_id,
    )
    const verifierIsTrusted = trustedVerifier !== undefined &&
      trustedVerifier.verifier_public_key === certificate.verifier_public_key &&
      trustedVerifier.verifier_identity_root === certificate.verifier_identity_root &&
      trustedVerifier.verifier_principal_root === certificate.verifier_principal_root &&
      trustedVerifier.verifier_workload_identity_root === certificate.verifier_workload_identity_root
    const verifierIdentityMatches = certificate.verifier_identity_root === expectedVerifierIdentity
    const verifierPrincipalIsIndependent =
      certificate.verifier_principal_root !== authority.executor_principal_root
    const verifierWorkloadIsIndependent =
      certificate.verifier_workload_identity_root !== authority.executor_workload_identity_root
    const verifierIsIndependent = verifierPrincipalIsIndependent && verifierWorkloadIsIndependent
    const bundleMatches = certificate.evidence_bundle_digest === evidence_bundle_digest
    const { signature: _certificateSignature, ...unsignedCertificate } = certificate
    const signatureValid = await verifyBytes(
      certificate.verifier_public_key,
      canonicalizeOutcomeEvidenceCertificateMessageV1(unsignedCertificate),
      certificate.signature,
    )
    const observationIdentitiesMatch = verification
      .filter(observation => observation.verification_mode === 'INDEPENDENT')
      .every(observation => observation.verifier_identity_root === certificate.verifier_identity_root)

    if (!verifierIsTrusted) reasons.push('EVIDENCE_VERIFIER_NOT_TRUSTED')
    if (!verifierIdentityMatches) reasons.push('EVIDENCE_VERIFIER_IDENTITY_MISMATCH')
    if (!verifierPrincipalIsIndependent) reasons.push('EVIDENCE_VERIFIER_PRINCIPAL_NOT_INDEPENDENT')
    if (!verifierWorkloadIsIndependent) reasons.push('EVIDENCE_VERIFIER_WORKLOAD_NOT_INDEPENDENT')
    if (!bundleMatches) reasons.push('EVIDENCE_BUNDLE_DIGEST_MISMATCH')
    if (!signatureValid) reasons.push('EVIDENCE_CERTIFICATE_SIGNATURE_INVALID')
    if (!observationIdentitiesMatch) reasons.push('VERIFICATION_IDENTITY_MISMATCH')
    evidence_certificate_verified = anchorPolicyMatches &&
      anchorTrustRootMatches &&
      verifierIsTrusted &&
      verifierIdentityMatches &&
      verifierIsIndependent &&
      bundleMatches &&
      signatureValid &&
      observationIdentitiesMatch &&
      componentTransitionValid
  }

  if (sourceDecision.mode !== 'READY_FOR_AUTHORITY') reasons.push('BASELINE_NOT_READY_FOR_AUTHORITY')
  if (proposalDigest === null || authority.action_binding.proposal_digest !== proposalDigest) {
    reasons.push('AUTHORITY_PROPOSAL_DIGEST_MISMATCH')
  }
  if (authority.action_binding.self_regulation_decision_digest !== sourceDecision.decision_digest) {
    reasons.push('AUTHORITY_REGULATION_DECISION_MISMATCH')
  }
  if (authority.action_binding.expected_parent_state_root !== input.baseline.snapshot.state_root) {
    reasons.push('AUTHORITY_PARENT_STATE_MISMATCH')
  }
  if (authority.requested_action_digest !== expectedActionDigest) reasons.push('AUTHORITY_ACTION_DIGEST_MISMATCH')
  if (authority.execution_identity_root !== input.baseline.snapshot.identity_root) reasons.push('AUTHORITY_IDENTITY_MISMATCH')
  if (authority.policy_root !== input.baseline.snapshot.policy_root) reasons.push('AUTHORITY_POLICY_ROOT_MISMATCH')
  if (authority.registry_root !== input.baseline.snapshot.capability_root) reasons.push('AUTHORITY_REGISTRY_ROOT_MISMATCH')
  if (authority.outcome === 'DENIED') reasons.push('AUTHORITY_DENIED')

  let terminal_evidence_digest: SHA256Hex | null = null
  let terminal_receipt_root: SHA256Hex | null = null
  let terminalBindingValid = false
  const terminal = input.terminal_execution
  if (terminal === undefined) {
    reasons.push('TERMINAL_EXECUTION_EVIDENCE_MISSING')
  } else {
    validateTerminalEvidence(terminal)
    terminal_evidence_digest = await hashValue({
      domain: 'AEGIS_TERMINAL_EXECUTION_EVIDENCE_V1',
      terminal,
    })
    terminal_receipt_root = terminal.mutation_receipt_root
    const terminalReasons: string[] = []
    if (terminal.execution_identity_root !== authority.execution_identity_root) terminalReasons.push('TERMINAL_IDENTITY_MISMATCH')
    if (terminal.workspace_binding !== authority.workspace_binding) terminalReasons.push('TERMINAL_WORKSPACE_MISMATCH')
    if (terminal.policy_decision_root !== authority.policy_decision_root) terminalReasons.push('TERMINAL_POLICY_DECISION_MISMATCH')
    if (terminal.authority_receipt_root !== authority.authority_receipt_root) terminalReasons.push('TERMINAL_AUTHORITY_RECEIPT_MISMATCH')
    if (terminal.requested_action_digest !== authority.requested_action_digest) terminalReasons.push('TERMINAL_ACTION_DIGEST_MISMATCH')
    if (terminal.pre_state_root !== input.baseline.snapshot.state_root) terminalReasons.push('TERMINAL_PRE_STATE_MISMATCH')
    if (terminal.post_state_root !== input.post_snapshot.state_root) terminalReasons.push('TERMINAL_POST_STATE_MISMATCH')
    if (terminal.lease_outcome !== 'ADMITTED') terminalReasons.push('TERMINAL_LEASE_NOT_ADMITTED')
    if (terminal.receipt_chain_status !== 'VERIFIED') terminalReasons.push('TERMINAL_RECEIPT_CHAIN_UNVERIFIED')
    if (terminal.durable_status !== expectedDurableStatus(terminal.outcome)) terminalReasons.push('TERMINAL_DURABLE_STATUS_MISMATCH')
    reasons.push(...terminalReasons)
    terminalBindingValid = terminalReasons.length === 0
  }

  const addressed = [...proposal.addressed_gap_ids]
  const baselineIds = new Set(gapIds(baselineGaps))
  const postIds = new Set(gapIds(postGaps))
  const resolved_gap_ids = addressed.filter(id => !postIds.has(id))
  const remaining_addressed_gap_ids = addressed.filter(id => postIds.has(id))
  const new_gap_ids = [...postIds].filter(id => !baselineIds.has(id)).sort(compareUtf8)
  const unsafePostGap = postGaps.some(gap =>
    gap.severity === 'CRITICAL' || gap.kind === 'INVARIANT_BREACH',
  )

  const stateChanged = input.post_snapshot.state_root !== input.baseline.snapshot.state_root
  const postHealth = input.post_snapshot.health
  const postHealthy = postHealth.t0_verdict &&
    postHealth.corruption_count === 0 &&
    postHealth.membrane_intact &&
    postHealth.entropy_bounded
  if (!postHealthy) reasons.push('POST_STATE_UNHEALTHY')
  if (unsafePostGap) reasons.push('UNSAFE_POST_GAP')
  else if (new_gap_ids.length > 0) reasons.push('NEW_GAPS_OBSERVED')
  if (remaining_addressed_gap_ids.length > 0) reasons.push('ADDRESSED_GAP_UNRESOLVED')

  const verificationCoverageComplete = verification.length === proposal.verification_steps.length
  const verificationFailed = verification.some(item => item.verdict === 'FAIL')
  const verificationInconclusive = verification.some(item => item.verdict === 'INCONCLUSIVE')
  const verificationIndependent = verification.every(item => item.verification_mode === 'INDEPENDENT')
  if (!verificationCoverageComplete) reasons.push('VERIFICATION_COVERAGE_INCOMPLETE')
  if (verificationFailed) reasons.push('VERIFICATION_FAILED')
  if (verificationInconclusive) reasons.push('VERIFICATION_INCONCLUSIVE')
  if (!verificationIndependent) reasons.push('VERIFICATION_NOT_INDEPENDENT')

  const authorityBindingsValid = !reasons.some(reason => reason.startsWith('AUTHORITY_') && reason !== 'AUTHORITY_DENIED') &&
    sourceDecision.mode === 'READY_FOR_AUTHORITY'
  const terminalProofValid = authority.outcome === 'ADMITTED' &&
    authorityBindingsValid &&
    terminalBindingValid &&
    evidence_certificate_verified
  const strongVerification = verificationCoverageComplete &&
    !verificationFailed &&
    !verificationInconclusive &&
    verificationIndependent
  const conclusiveIndependentVerification = verificationCoverageComplete &&
    !verificationInconclusive &&
    verificationIndependent

  let state_disposition: StateDisposition
  let evidence_disposition: EvidenceDisposition
  let learning_evidence_eligible = false

  if (authority.outcome === 'DENIED') {
    state_disposition = stateChanged ? 'REVERT' : 'NO_STATE_CHANGE'
    evidence_disposition = 'INCONCLUSIVE'
  } else if (!terminalProofValid || terminal === undefined) {
    state_disposition = stateChanged ? 'REVERT' : 'NO_STATE_CHANGE'
    evidence_disposition = 'INCONCLUSIVE'
  } else if (terminal.outcome === 'ROLLED_BACK') {
    if (stateChanged) {
      reasons.push('ROLLBACK_POST_STATE_MISMATCH')
      state_disposition = 'REVERT'
      evidence_disposition = 'INCONCLUSIVE'
    } else {
      reasons.push('EXECUTION_ROLLED_BACK')
      state_disposition = 'NO_STATE_CHANGE'
      evidence_disposition = conclusiveIndependentVerification ? 'DEGRADE' : 'INCONCLUSIVE'
      learning_evidence_eligible = conclusiveIndependentVerification
    }
  } else if (terminal.outcome === 'FAILED' || terminal.outcome === 'DENIED') {
    reasons.push(`EXECUTION_${terminal.outcome}`)
    state_disposition = stateChanged ? 'REVERT' : 'NO_STATE_CHANGE'
    evidence_disposition = conclusiveIndependentVerification ? 'DEGRADE' : 'INCONCLUSIVE'
    learning_evidence_eligible = conclusiveIndependentVerification
  } else if (!stateChanged) {
    reasons.push('SUCCESS_WITHOUT_STATE_TRANSITION')
    state_disposition = 'NO_STATE_CHANGE'
    evidence_disposition = strongVerification ? 'DEGRADE' : 'INCONCLUSIVE'
    learning_evidence_eligible = strongVerification
  } else if (!strongVerification) {
    state_disposition = 'REVERT'
    evidence_disposition = verificationFailed && conclusiveIndependentVerification ? 'DEGRADE' : 'INCONCLUSIVE'
    learning_evidence_eligible = evidence_disposition === 'DEGRADE'
  } else if (!postHealthy || unsafePostGap || new_gap_ids.length > 0 || remaining_addressed_gap_ids.length > 0) {
    state_disposition = 'REVERT'
    evidence_disposition = 'DEGRADE'
    learning_evidence_eligible = true
  } else {
    reasons.push('TERMINAL_OUTCOME_INDEPENDENTLY_VERIFIED')
    state_disposition = 'PRESERVE'
    evidence_disposition = 'CONFIRM'
    learning_evidence_eligible = true
  }

  const required_next_gate: OutcomeNextGate =
    state_disposition !== 'NO_STATE_CHANGE' || learning_evidence_eligible
      ? 'AUTOMATON_3'
      : 'OPERATOR_REVIEW'
  const sortedReasons = [...new Set(reasons)].sort(compareUtf8)
  const unsigned = {
    schema_version: OUTCOME_COMPARATOR_SCHEMA_VERSION,
    state_disposition,
    evidence_disposition,
    reason_codes: sortedReasons,
    required_next_gate,
    grants_authority: false as const,
    executes_mutation: false as const,
    updates_competence: false as const,
    requires_automaton3: required_next_gate === 'AUTOMATON_3',
    learning_evidence_eligible,
    source_decision_digest: sourceDecision.decision_digest,
    proposal_digest: proposalDigest,
    authority_evidence_digest,
    authority_decision_root: authority.policy_decision_root,
    requested_action_digest: authority.requested_action_digest,
    terminal_evidence_digest,
    terminal_receipt_root,
    evidence_bundle_digest,
    evidence_certificate_digest,
    evidence_certificate_verified,
    verifier_trust_policy_digest: trustAnchor.trust_policy_digest,
    pre_state_root: input.baseline.snapshot.state_root,
    post_state_root: input.post_snapshot.state_root,
    expected_previous_metacognition_root: input.baseline.snapshot.metacognition_root,
    resolved_gap_ids,
    remaining_addressed_gap_ids,
    new_gap_ids,
    verification_digest,
    post_self_model_digest: postDecision.self_model_digest,
  }
  const assessment_digest = await hashValue({
    domain: 'AEGIS_ADAPTATION_OUTCOME_ASSESSMENT_V1',
    assessment: unsigned,
  })
  return deepFreeze<AdaptationOutcomeAssessment>({ ...unsigned, assessment_digest })
}

export async function recordOutcomeAssessment(
  loop: MetacognitiveLoop,
  input: AdaptationOutcomeInput,
  trustAnchor: VerifiedOutcomeVerifierTrustAnchorV1,
  artifactStore: OutcomeEvidenceArtifactStore,
  sequence: SequenceNumber,
): Promise<{
  assessment: AdaptationOutcomeAssessment
  artifact: OutcomeEvidenceArtifactV1
  persistence: OutcomeEvidencePersistenceReceiptV1
  loop: MetacognitiveLoop
  entry: MetacognitiveEntry
}> {
  // Re-evaluate the authenticated evidence inside the append boundary. A
  // caller cannot submit an edited assessment plus a freshly recomputed public
  // hash and have it accepted as learned evidence.
  const assessment = await assessAdaptationOutcome(input, trustAnchor)
  if (loop.lastHash !== assessment.expected_previous_metacognition_root) {
    throw new OutcomeComparisonError('metacognitive loop head does not match assessment baseline')
  }
  if (artifactStore === null || typeof artifactStore !== 'object' ||
      typeof artifactStore.persist !== 'function') {
    throw new OutcomeComparisonError('outcome evidence artifact store is unavailable')
  }
  const normalizedVerifiers = await normalizeVerifierIdentities(trustAnchor.verifiers)
  const denialCodes = validateAuthorityEvidence(input.authority)
  if (input.terminal_execution !== undefined) validateTerminalEvidence(input.terminal_execution)
  const normalizedInput = deepFreeze<Readonly<Record<string, unknown>>>({
    baseline: {
      snapshot: input.baseline.snapshot,
      gaps: normalizeKnowledgeGaps(input.baseline.gaps),
      proposal: normalizeAdaptationProposal(input.baseline.proposal),
    },
    authority: { ...input.authority, denial_codes: denialCodes },
    terminal_execution: input.terminal_execution ?? null,
    post_snapshot: input.post_snapshot,
    post_gaps: normalizeKnowledgeGaps(input.post_gaps),
    verification: normalizeVerification(
      input.verification,
      input.baseline.proposal.verification_steps.length,
    ),
    evidence_certificate: input.evidence_certificate ?? null,
  })
  const artifactBody = deepFreeze({
    schema_version: OUTCOME_COMPARATOR_SCHEMA_VERSION,
    artifact_kind: 'AEGIS_OUTCOME_EVIDENCE_ARTIFACT_V1' as const,
    evidence_input: normalizedInput,
    verifier_trust_anchor: {
      governed_policy_root: trustAnchor.governed_policy_root,
      verifier_trust_root: trustAnchor.verifier_trust_root,
      verifiers: normalizedVerifiers,
      trust_policy_digest: trustAnchor.trust_policy_digest,
    },
    assessment,
  })
  const artifact_root = await hashValue({
    domain: 'AEGIS_OUTCOME_EVIDENCE_ARTIFACT_V1',
    artifact: artifactBody,
  })
  const artifact = deepFreeze<OutcomeEvidenceArtifactV1>({ ...artifactBody, artifact_root })
  let persistence: OutcomeEvidencePersistenceReceiptV1
  try {
    persistence = await artifactStore.persist(artifact)
  } catch (error) {
    throw new OutcomeComparisonError(
      `outcome evidence persistence failed: ${error instanceof Error ? error.message : String(error)}`,
    )
  }
  assertResolvedHash('outcome_evidence_persistence.artifact_root', persistence.artifact_root)
  if (persistence.artifact_root !== artifact.artifact_root) {
    throw new OutcomeComparisonError('outcome evidence persistence root mismatch')
  }
  if (typeof persistence.artifact_reference !== 'string' ||
      persistence.artifact_reference.length > 1024 ||
      !/^[a-z][a-z0-9+.-]{1,31}:[^\s\u0000-\u001f]+$/.test(persistence.artifact_reference)) {
    throw new OutcomeComparisonError('outcome evidence artifact reference is invalid')
  }
  const persistence_binding = await hashValue({
    domain: 'AEGIS_OUTCOME_EVIDENCE_PERSISTENCE_BINDING_V1',
    artifact_root: persistence.artifact_root,
    artifact_reference: persistence.artifact_reference,
  })
  const observed = await loop.observe({
    layer: 'METACOGNITIVE',
    signal: `OUTCOME_EVIDENCE_ARTIFACT_V1:${artifact.artifact_root}:${persistence_binding}:${assessment.state_disposition}:${assessment.evidence_disposition}`,
    tier: 'T2',
  }, sequence)
  return { assessment, artifact, persistence, ...observed }
}
