import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'

export type AuthorityCardDecision = 'APPROVE' | 'DENY' | 'REVIEW'
type Status = 'PASS' | 'FAIL' | 'NOT_RUN' | 'SKIPPED' | 'UNRESOLVED'

type VerificationEntry = {
  readonly mandatory: true
  readonly status: Status
  readonly command_or_verifier: string
  readonly execution_reference: string | null
  readonly artifact_digest: SHA256Hex | null
}

type BoundClaim = {
  readonly value: unknown
  readonly origin_class: 'COMPUTED' | 'THIRD_PARTY_ATTESTED' | 'DECLARED'
  readonly source: { readonly kind: string; readonly locator: string; readonly digest_or_id: string | null }
  readonly verifier: {
    readonly identity: string | null
    readonly execution_reference: string | null
    readonly result: 'PASS' | 'FAIL' | 'NOT_RUN' | 'UNRESOLVED'
  }
  readonly blocking: boolean
}

export interface AuthorityStateCardV2 {
  readonly schema_version: '2.0.0'
  readonly claims: Readonly<Record<string, BoundClaim>>
  readonly verification_matrix: Readonly<Record<string, VerificationEntry>>
  readonly source_entailment: readonly {
    readonly claim_id: string
    readonly source_locator: string
    readonly source_digest: SHA256Hex
    readonly verifier: string
    readonly status: 'PASS' | 'FAIL' | 'NOT_RUN' | 'UNRESOLVED'
  }[]
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
      readonly status: Status
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

export const AUTHORITY_CARD_PREIMAGE_RULE =
  'canonicalize the complete card after replacing /attestation/canonical_hash, /attestation/signature, and /external_anchor/anchored_hash with null'

const present = (value: string | null): value is string => typeof value === 'string' && value.length > 0

function time(field: string, value: string | null, failures: string[]): number | null {
  if (!present(value)) {
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
    attestation: { ...card.attestation, canonical_hash: null, signature: null },
    external_anchor: { ...card.external_anchor, anchored_hash: null },
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

  for (const [id, claim] of Object.entries(card.claims)) {
    if (claim.blocking && claim.origin_class === 'DECLARED') failures.push(`BLOCKING_CLAIM_DECLARED:${id}`)
    if (claim.blocking && claim.verifier.result !== 'PASS') failures.push(`BLOCKING_CLAIM_UNVERIFIED:${id}`)
    if (claim.blocking && !present(claim.verifier.identity)) failures.push(`BLOCKING_CLAIM_VERIFIER_MISSING:${id}`)
    if (claim.blocking && !present(claim.verifier.execution_reference)) {
      failures.push(`BLOCKING_CLAIM_EXECUTION_REFERENCE_MISSING:${id}`)
    }
  }

  for (const [id, check] of Object.entries(card.verification_matrix)) {
    if (check.mandatory && check.status !== 'PASS') failures.push(`MANDATORY_CHECK_${check.status}:${id}`)
    if (check.mandatory && !present(check.execution_reference)) failures.push(`MANDATORY_CHECK_EXECUTION_REFERENCE_MISSING:${id}`)
    if (check.mandatory && check.artifact_digest === null) failures.push(`MANDATORY_CHECK_ARTIFACT_DIGEST_MISSING:${id}`)
  }

  for (const edge of card.source_entailment) {
    if (edge.status !== 'PASS') failures.push(`SOURCE_ENTAILMENT_${edge.status}:${edge.claim_id}`)
    if (!present(edge.verifier)) failures.push(`SOURCE_ENTAILMENT_VERIFIER_MISSING:${edge.claim_id}`)
  }

  if (card.replay_verifiability.status !== 'PASS') failures.push(`REPLAY_${card.replay_verifiability.status}`)
  const evaluatedAt = time('evaluation_time', evaluationTime, failures)
  const verifiedAt = time('replay.verified_at', card.replay_verifiability.verified_at, failures)
  const validUntil = time('replay.valid_until', card.replay_verifiability.valid_until, failures)
  if (evaluatedAt !== null && verifiedAt !== null && evaluatedAt < verifiedAt) failures.push('REPLAY_EVALUATED_BEFORE_VERIFICATION')
  if (evaluatedAt !== null && validUntil !== null && evaluatedAt > validUntil) failures.push('REPLAY_EXPIRED')
  if (verifiedAt !== null && validUntil !== null && validUntil <= verifiedAt) failures.push('REPLAY_VALIDITY_INTERVAL_INVALID')

  const custody = card.replay_verifiability.custody_manifest
  if (custody.availability_status !== 'AVAILABLE') failures.push('CUSTODY_NOT_AVAILABLE')
  if (!present(custody.path)) failures.push('CUSTODY_PATH_MISSING')
  if (!present(custody.custodian)) failures.push('CUSTODIAN_MISSING')
  if (custody.digest === null) failures.push('CUSTODY_DIGEST_MISSING')
  if (card.replay_verifiability.replay_package_digest === null) failures.push('REPLAY_PACKAGE_DIGEST_MISSING')

  const sync = card.audit_ledger.synchronization
  if (sync.status !== 'PASS') failures.push(`LEDGER_SYNCHRONIZATION_${sync.status}`)
  if (!present(sync.verifier)) failures.push('LEDGER_SYNCHRONIZATION_VERIFIER_MISSING')
  if (!present(sync.execution_reference)) failures.push('LEDGER_SYNCHRONIZATION_EXECUTION_REFERENCE_MISSING')
  if (sync.compared_roots.length < 2) failures.push('LEDGER_COMPARISON_INCOMPLETE')
  if (sync.compared_roots.some((root) => root !== card.audit_ledger.root)) failures.push('LEDGER_ROOT_MISMATCH')

  if (card.attestation.preimage_rule !== AUTHORITY_CARD_PREIMAGE_RULE) failures.push('ATTESTATION_PREIMAGE_RULE_MISMATCH')
  const computedCanonicalHash = await computeAuthorityCardCanonicalHash(card)
  if (card.attestation.canonical_hash !== computedCanonicalHash) failures.push('ATTESTATION_CANONICAL_HASH_MISMATCH')
  if (!present(card.attestation.signer)) failures.push('ATTESTATION_SIGNER_MISSING')
  if (!present(card.attestation.signature)) failures.push('ATTESTATION_SIGNATURE_MISSING')

  if (card.external_anchor.status !== 'PRESENT') failures.push(`EXTERNAL_ANCHOR_${card.external_anchor.status}`)
  if (!present(card.external_anchor.provider)) failures.push('EXTERNAL_ANCHOR_PROVIDER_MISSING')
  if (!present(card.external_anchor.locator)) failures.push('EXTERNAL_ANCHOR_LOCATOR_MISSING')
  if (card.external_anchor.anchored_hash !== computedCanonicalHash) failures.push('EXTERNAL_ANCHOR_HASH_MISMATCH')
  time('external_anchor.anchored_at', card.external_anchor.anchored_at, failures)

  if (!present(card.deployment_decision.computed_by)) failures.push('DECISION_VERIFIER_MISSING')
  if (!present(card.deployment_decision.execution_reference)) failures.push('DECISION_EXECUTION_REFERENCE_MISSING')

  const gatesPass = failures.length === 0
  if (card.deployment_decision.value === 'APPROVE' && !gatesPass) failures.push('APPROVE_WITH_UNSATISFIED_GATES')
  if (card.deployment_decision.value !== 'APPROVE' && gatesPass) failures.push('NON_APPROVE_DESPITE_SATISFIED_GATES')

  return {
    valid: failures.length === 0,
    decision: gatesPass ? 'APPROVE' : card.deployment_decision.value === 'APPROVE' ? 'DENY' : card.deployment_decision.value,
    failures: Object.freeze(failures),
    computedCanonicalHash,
  }
}
