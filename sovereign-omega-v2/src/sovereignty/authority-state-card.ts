import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'

export type AuthorityCardDecision = 'APPROVE' | 'DENY' | 'REVIEW'
export type VerificationStatus = 'PASS' | 'FAIL' | 'NOT_RUN' | 'SKIPPED' | 'UNRESOLVED'

interface VerificationEntry {
  readonly mandatory: true
  readonly status: VerificationStatus
  readonly command_or_verifier: string
  readonly execution_reference: string | null
  readonly artifact_digest: SHA256Hex | null
}

interface BoundClaim {
  readonly value: unknown
  readonly origin_class: 'COMPUTED' | 'THIRD_PARTY_ATTESTED' | 'DECLARED'
  readonly source: {
    readonly kind: string
    readonly locator: string
    readonly digest_or_id: string | null
  }
  readonly verifier: {
    readonly identity: string | null
    readonly execution_reference: string | null
    readonly result: 'PASS' | 'FAIL' | 'NOT_RUN' | 'UNRESOLVED'
  }
  readonly blocking: boolean
}

interface SourceEntailmentEntry {
  readonly claim_id: string
  readonly source_locator: string
  readonly source_digest: SHA256Hex
  readonly verifier: string
  readonly status: 'PASS' | 'FAIL' | 'NOT_RUN' | 'UNRESOLVED'
}

export interface AuthorityStateCardV2 {
  readonly schema_version: '2.0.0'
  readonly claims: Readonly<Record<string, BoundClaim>>
  readonly verification_matrix: Readonly<Record<string, VerificationEntry>>
  readonly source_entailment: readonly SourceEntailmentEntry[]
  readonly replay_verifiability: {
    readonly status: 'PASS' | 'FAIL' | 'NOT_RUN' | 'EXPIRED' | 'UNRESOLVED'
    readonly verified_at: string | null
    readonly valid_until: string | null
    readonly custody_manifest: {
      readonly path: string | null
      readonly digest: SHA256Hex | null
      readonly custodian: string | null
      readonly availability_status: 'AVAILABLE' | 'MISSING' | 'NOT_CHECKED'
    }
    readonly replay_package_digest: SHA256Hex | null
  }
  readonly audit_ledger: {
    readonly root: SHA256Hex
    readonly synchronization: {
      readonly status: VerificationStatus
      readonly verifier: string | null
      readonly execution_reference: string | null
      readonly compared_roots: readonly SHA256Hex[]
    }
  }
  readonly attestation: {
    readonly canonicalization: 'RFC8785_JCS'
    readonly preimage_rule: string
    readonly canonical_hash: SHA256Hex | null
    readonly signer: string | null
    readonly signature: string | null
  }
  readonly external_anchor: {
    readonly status: 'PRESENT' | 'ABSENT' | 'NOT_CHECKED'
    readonly provider: string | null
    readonly locator: string | null
    readonly anchored_hash: SHA256Hex | null
    readonly anchored_at: string | null
  }
  readonly deployment_decision: {
    readonly value: AuthorityCardDecision
    readonly computed_by: string
    readonly execution_reference: string | null
    readonly rule: string
  }
  readonly [key: string]: unknown
}

export interface AuthorityCardValidationResult {
  readonly valid: boolean
  readonly decision: AuthorityCardDecision
  readonly failures: readonly string[]
  readonly computedCanonicalHash: SHA256Hex
}

const REQUIRED_PREIMAGE_RULE =
  'canonicalize the complete card after replacing /attestation/canonical_hash and /attestation/signature with null'

function isNonEmpty(value: string | null): value is string {
  return typeof value === 'string' && value.length > 0
}

function parseTimestamp(field: string, value: string | null, failures: string[]): number | null {
  if (!isNonEmpty(value)) {
    failures.push(`${field}:MISSING`)
    return null
  }
  const parsed = Date.parse(value)
  if (!Number.isFinite(parsed)) {
    failures.push(`${field}:INVALID`)
    return null
  }
  return parsed
}

export function authorityCardHashPreimage(card: AuthorityStateCardV2): unknown {
  return {
    ...card,
    attestation: {
      ...card.attestation,
      canonical_hash: null,
      signature: null,
    },
  }
}

export async function computeAuthorityCardCanonicalHash(card: AuthorityStateCardV2): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeJCS(authorityCardHashPreimage(card)))
}

export async function validateAuthorityStateCardV2(
  card: AuthorityStateCardV2,
  evaluationTime: string,
): Promise<AuthorityCardValidationResult> {
  const failures: string[] = []

  if (card.schema_version !== '2.0.0') failures.push('SCHEMA_VERSION_UNSUPPORTED')

  for (const [claimId, claim] of Object.entries(card.claims)) {
    if (claim.blocking && claim.origin_class === 'DECLARED') {
      failures.push(`BLOCKING_CLAIM_DECLARED:${claimId}`)
    }
    if (claim.blocking && claim.verifier.result !== 'PASS') {
      failures.push(`BLOCKING_CLAIM_UNVERIFIED:${claimId}`)
    }
    if (claim.blocking && !isNonEmpty(claim.verifier.identity)) {
      failures.push(`BLOCKING_CLAIM_VERIFIER_MISSING:${claimId}`)
    }
    if (claim.blocking && !isNonEmpty(claim.verifier.execution_reference)) {
      failures.push(`BLOCKING_CLAIM_EXECUTION_REFERENCE_MISSING:${claimId}`)
    }
  }

  for (const [checkId, check] of Object.entries(card.verification_matrix)) {
    if (check.mandatory && check.status !== 'PASS') {
      failures.push(`MANDATORY_CHECK_${check.status}:${checkId}`)
    }
    if (check.mandatory && !isNonEmpty(check.execution_reference)) {
      failures.push(`MANDATORY_CHECK_EXECUTION_REFERENCE_MISSING:${checkId}`)
    }
    if (check.mandatory && check.artifact_digest === null) {
      failures.push(`MANDATORY_CHECK_ARTIFACT_DIGEST_MISSING:${checkId}`)
    }
  }

  for (const entailment of card.source_entailment) {
    if (entailment.status !== 'PASS') {
      failures.push(`SOURCE_ENTAILMENT_${entailment.status}:${entailment.claim_id}`)
    }
    if (!isNonEmpty(entailment.verifier)) {
      failures.push(`SOURCE_ENTAILMENT_VERIFIER_MISSING:${entailment.claim_id}`)
    }
  }

  if (card.replay_verifiability.status !== 'PASS') {
    failures.push(`REPLAY_${card.replay_verifiability.status}`)
  }

  const evaluationAt = parseTimestamp('evaluation_time', evaluationTime, failures)
  const verifiedAt = parseTimestamp('replay.verified_at', card.replay_verifiability.verified_at, failures)
  const validUntil = parseTimestamp('replay.valid_until', card.replay_verifiability.valid_until, failures)

  if (evaluationAt !== null && verifiedAt !== null && evaluationAt < verifiedAt) {
    failures.push('REPLAY_EVALUATED_BEFORE_VERIFICATION')
  }
  if (evaluationAt !== null && validUntil !== null && evaluationAt > validUntil) {
    failures.push('REPLAY_EXPIRED')
  }
  if (verifiedAt !== null && validUntil !== null && validUntil <= verifiedAt) {
    failures.push('REPLAY_VALIDITY_INTERVAL_INVALID')
  }

  const custody = card.replay_verifiability.custody_manifest
  if (custody.availability_status !== 'AVAILABLE') failures.push('CUSTODY_NOT_AVAILABLE')
  if (!isNonEmpty(custody.path)) failures.push('CUSTODY_PATH_MISSING')
  if (!isNonEmpty(custody.custodian)) failures.push('CUSTODIAN_MISSING')
  if (custody.digest === null) failures.push('CUSTODY_DIGEST_MISSING')
  if (card.replay_verifiability.replay_package_digest === null) failures.push('REPLAY_PACKAGE_DIGEST_MISSING')

  const synchronization = card.audit_ledger.synchronization
  if (synchronization.status !== 'PASS') failures.push(`LEDGER_SYNCHRONIZATION_${synchronization.status}`)
  if (!isNonEmpty(synchronization.verifier)) failures.push('LEDGER_SYNCHRONIZATION_VERIFIER_MISSING')
  if (!isNonEmpty(synchronization.execution_reference)) {
    failures.push('LEDGER_SYNCHRONIZATION_EXECUTION_REFERENCE_MISSING')
  }
  if (synchronization.compared_roots.length < 2) failures.push('LEDGER_COMPARISON_INCOMPLETE')
  if (synchronization.compared_roots.some((root) => root !== card.audit_ledger.root)) {
    failures.push('LEDGER_ROOT_MISMATCH')
  }

  if (card.attestation.canonicalization !== 'RFC8785_JCS') failures.push('ATTESTATION_CANONICALIZATION_UNSUPPORTED')
  if (card.attestation.preimage_rule !== REQUIRED_PREIMAGE_RULE) failures.push('ATTESTATION_PREIMAGE_RULE_MISMATCH')

  const computedCanonicalHash = await computeAuthorityCardCanonicalHash(card)
  if (card.attestation.canonical_hash !== computedCanonicalHash) failures.push('ATTESTATION_CANONICAL_HASH_MISMATCH')
  if (!isNonEmpty(card.attestation.signer)) failures.push('ATTESTATION_SIGNER_MISSING')
  if (!isNonEmpty(card.attestation.signature)) failures.push('ATTESTATION_SIGNATURE_MISSING')

  if (card.external_anchor.status !== 'PRESENT') failures.push(`EXTERNAL_ANCHOR_${card.external_anchor.status}`)
  if (!isNonEmpty(card.external_anchor.provider)) failures.push('EXTERNAL_ANCHOR_PROVIDER_MISSING')
  if (!isNonEmpty(card.external_anchor.locator)) failures.push('EXTERNAL_ANCHOR_LOCATOR_MISSING')
  if (card.external_anchor.anchored_hash !== computedCanonicalHash) failures.push('EXTERNAL_ANCHOR_HASH_MISMATCH')
  parseTimestamp('external_anchor.anchored_at', card.external_anchor.anchored_at, failures)

  if (!isNonEmpty(card.deployment_decision.computed_by)) failures.push('DECISION_VERIFIER_MISSING')
  if (!isNonEmpty(card.deployment_decision.execution_reference)) failures.push('DECISION_EXECUTION_REFERENCE_MISSING')

  const shouldApprove = failures.length === 0
  if (card.deployment_decision.value === 'APPROVE' && !shouldApprove) {
    failures.push('APPROVE_WITH_UNSATISFIED_GATES')
  }
  if (card.deployment_decision.value !== 'APPROVE' && shouldApprove) {
    failures.push('NON_APPROVE_DESPITE_SATISFIED_GATES')
  }

  return {
    valid: failures.length === 0,
    decision: shouldApprove ? 'APPROVE' : card.deployment_decision.value === 'APPROVE' ? 'DENY' : card.deployment_decision.value,
    failures: Object.freeze(failures),
    computedCanonicalHash,
  }
}
