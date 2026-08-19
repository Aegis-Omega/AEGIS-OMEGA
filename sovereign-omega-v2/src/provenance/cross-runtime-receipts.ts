// ============================================================
// AEGIS Cross-Runtime Authoritative Receipts V1
// PROVENANCE ASSURANCE: T2->T3 implemented; projection admission pending
//
// The JSON schemas in /schemas are the normative wire contract. Every value
// crosses the strict I-JSON boundary before the repository's sole JCS encoder
// is used. No receipt or registry value is inferred from model output.
// ============================================================

import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import { assertIJsonValue } from '../core/i-json.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex } from '../core/types.js'
import { signBytes } from '../consensus/crypto.js'

export const CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION = '1.0.0' as const
export const RECEIPT_SIGNATURE_DOMAIN = 'AEGIS_CROSS_RUNTIME_RECEIPT_SIGNATURE_V1' as const
export const RECEIPT_ID_DOMAIN = 'AEGIS_CROSS_RUNTIME_RECEIPT_ID_V1' as const
export const REGISTRY_SIGNATURE_DOMAIN = 'AEGIS_RECEIPT_TRUST_REGISTRY_SIGNATURE_V1' as const
export const REGISTRY_ROOT_DOMAIN = 'AEGIS_RECEIPT_TRUST_REGISTRY_ROOT_V1' as const

export type CrossRuntimeReceiptKindV1 =
  | 'LEASE_ISSUED'
  | 'LEASE_ISSUANCE_DENIED'
  | 'LEASE_RENEWED'
  | 'LEASE_RENEWAL_DENIED'
  | 'LEASE_EXPIRED'
  | 'LEASE_REVOKED'
  | 'MUTATION_ADMITTED'
  | 'MUTATION_DENIED'
  | 'MUTATION_COMPLETED'
  | 'MUTATION_CANCELLED'
  | 'MUTATION_FAILED'

export type CrossRuntimeReceiptOutcomeV1 =
  | 'ADMITTED'
  | 'DENIED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'FAILED'
  | 'EXPIRED'
  | 'REVOKED'

export type AuthorityLevelV1 = 'D0' | 'D1' | 'D2' | 'D3' | 'D4'
export type DecimalStringV1 = string

export interface CrossRuntimeReceiptBodyV1 {
  readonly receipt_sequence: DecimalStringV1
  readonly actor_identity_root: SHA256Hex
  readonly session_identity_root: SHA256Hex
  readonly workspace_identity_root: SHA256Hex
  readonly holon_identity_root: SHA256Hex
  readonly authority_domain: string
  readonly authority_level: AuthorityLevelV1
  readonly authority_receipt_hash: SHA256Hex
  readonly lease_id: SHA256Hex
  readonly lease_generation: DecimalStringV1
  readonly fencing_token: SHA256Hex
  readonly lease_authorization_receipt_hash: SHA256Hex
  readonly parent_receipt_hash: SHA256Hex
  readonly observed_state_root: SHA256Hex
  readonly expected_state_root: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly before_state_root: SHA256Hex
  readonly after_state_root: SHA256Hex
  readonly result_digest: SHA256Hex
  readonly timestamp_ms: DecimalStringV1
  readonly expires_at_ms: DecimalStringV1
  readonly nonce: string
  readonly outcome: CrossRuntimeReceiptOutcomeV1
  readonly denial_codes: readonly string[]
}

export interface CrossRuntimeReceiptProofV1 {
  readonly algorithm: 'Ed25519'
  readonly signer_key_id: string
  readonly verifier_identity_root: SHA256Hex
  readonly trust_registry_version: DecimalStringV1
  readonly trust_registry_root: SHA256Hex
  readonly signature: string
}

export interface CrossRuntimeReceiptEnvelopeV1 {
  readonly schema_version: typeof CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION
  readonly receipt_kind: CrossRuntimeReceiptKindV1
  readonly receipt_body: CrossRuntimeReceiptBodyV1
  readonly proof: CrossRuntimeReceiptProofV1
  readonly receipt_id: SHA256Hex
}

export interface CrossRuntimeReceiptDraftV1 {
  readonly schema_version: typeof CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION
  readonly receipt_kind: CrossRuntimeReceiptKindV1
  readonly receipt_body: CrossRuntimeReceiptBodyV1
  readonly proof: Omit<CrossRuntimeReceiptProofV1, 'signature'>
}

export type ReceiptTrustKeyStatusV1 = 'ACTIVE' | 'REVOKED'

export interface ReceiptTrustKeyEntryV1 {
  readonly key_id: string
  readonly public_key: string
  readonly verifier_identity_root: SHA256Hex
  readonly valid_from_ms: DecimalStringV1
  readonly expires_at_ms: DecimalStringV1
  readonly status: ReceiptTrustKeyStatusV1
  readonly authority_domains: readonly string[]
  readonly receipt_kinds: readonly CrossRuntimeReceiptKindV1[]
}

export interface ReceiptTrustRegistryBodyV1 {
  readonly registry_version: DecimalStringV1
  readonly previous_registry_root: SHA256Hex
  readonly issued_at_ms: DecimalStringV1
  readonly valid_from_ms: DecimalStringV1
  readonly expires_at_ms: DecimalStringV1
  readonly operator_key_id: string
  readonly keys: readonly ReceiptTrustKeyEntryV1[]
}

export interface ReceiptTrustRegistryV1 {
  readonly schema_version: typeof CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION
  readonly registry_body: ReceiptTrustRegistryBodyV1
  readonly proof: {
    readonly algorithm: 'Ed25519'
    readonly signature: string
  }
  readonly registry_root: SHA256Hex
}

export class CrossRuntimeReceiptValidationError extends Error {
  override readonly name = 'CrossRuntimeReceiptValidationError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const HASH_PATTERN = /^[0-9a-f]{64}$/
const SIGNATURE_PATTERN = /^[0-9a-f]{128}$/
const DECIMAL_PATTERN = /^(0|[1-9][0-9]*)$/
const SAFE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/
const NONCE_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{15,127}$/
const ZERO_HASH = '0'.repeat(64)
const RECEIPT_KINDS = new Set<CrossRuntimeReceiptKindV1>([
  'LEASE_ISSUED',
  'LEASE_ISSUANCE_DENIED',
  'LEASE_RENEWED',
  'LEASE_RENEWAL_DENIED',
  'LEASE_EXPIRED',
  'LEASE_REVOKED',
  'MUTATION_ADMITTED',
  'MUTATION_DENIED',
  'MUTATION_COMPLETED',
  'MUTATION_CANCELLED',
  'MUTATION_FAILED',
])
const OUTCOMES = new Set<CrossRuntimeReceiptOutcomeV1>([
  'ADMITTED', 'DENIED', 'COMPLETED', 'CANCELLED', 'FAILED', 'EXPIRED', 'REVOKED',
])
const AUTHORITY_LEVELS = new Set<AuthorityLevelV1>(['D0', 'D1', 'D2', 'D3', 'D4'])
const KEY_STATUSES = new Set<ReceiptTrustKeyStatusV1>(['ACTIVE', 'REVOKED'])

const RECEIPT_KEYS = [
  'proof', 'receipt_body', 'receipt_id', 'receipt_kind', 'schema_version',
] as const
const RECEIPT_BODY_KEYS = [
  'action_digest',
  'actor_identity_root',
  'after_state_root',
  'authority_domain',
  'authority_level',
  'authority_receipt_hash',
  'before_state_root',
  'denial_codes',
  'expected_state_root',
  'expires_at_ms',
  'fencing_token',
  'holon_identity_root',
  'lease_authorization_receipt_hash',
  'lease_generation',
  'lease_id',
  'nonce',
  'observed_state_root',
  'outcome',
  'parent_receipt_hash',
  'receipt_sequence',
  'result_digest',
  'session_identity_root',
  'timestamp_ms',
  'workspace_identity_root',
] as const
const RECEIPT_PROOF_KEYS = [
  'algorithm', 'signature', 'signer_key_id', 'trust_registry_root',
  'trust_registry_version', 'verifier_identity_root',
] as const
const RECEIPT_UNSIGNED_PROOF_KEYS = [
  'algorithm', 'signer_key_id', 'trust_registry_root', 'trust_registry_version',
  'verifier_identity_root',
] as const
const REGISTRY_KEYS = ['proof', 'registry_body', 'registry_root', 'schema_version'] as const
const REGISTRY_BODY_KEYS = [
  'expires_at_ms', 'issued_at_ms', 'keys', 'operator_key_id',
  'previous_registry_root', 'registry_version', 'valid_from_ms',
] as const
const REGISTRY_KEY_ENTRY_KEYS = [
  'authority_domains', 'expires_at_ms', 'key_id', 'public_key', 'receipt_kinds',
  'status', 'valid_from_ms', 'verifier_identity_root',
] as const

export function normalizeCrossRuntimeReceiptEnvelopeV1(
  value: unknown,
): CrossRuntimeReceiptEnvelopeV1 {
  const snapshot = snapshotIJson(value, 'cross-runtime receipt envelope')
  const envelope = asObject('receipt', snapshot)
  assertExactKeys('receipt', envelope, RECEIPT_KEYS)
  if (envelope.schema_version !== CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION) {
    fail('receipt.schema_version is unsupported')
  }
  const receipt_kind = assertReceiptKind('receipt.receipt_kind', envelope.receipt_kind)
  const receipt_body = normalizeReceiptBody(envelope.receipt_body)
  assertReceiptKindBodySemantics(receipt_kind, receipt_body)
  const proof = normalizeReceiptProof(envelope.proof)
  const receipt_id = assertHash('receipt.receipt_id', envelope.receipt_id)
  return deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    receipt_kind,
    receipt_body,
    proof,
    receipt_id,
  })
}

export function normalizeReceiptTrustRegistryV1(value: unknown): ReceiptTrustRegistryV1 {
  const snapshot = snapshotIJson(value, 'receipt trust registry')
  const registry = asObject('registry', snapshot)
  assertExactKeys('registry', registry, REGISTRY_KEYS)
  if (registry.schema_version !== CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION) {
    fail('registry.schema_version is unsupported')
  }
  const registry_body = normalizeRegistryBody(registry.registry_body)
  const proofObject = asObject('registry.proof', registry.proof)
  assertExactKeys('registry.proof', proofObject, ['algorithm', 'signature'])
  if (proofObject.algorithm !== 'Ed25519') fail('registry.proof.algorithm is unsupported')
  const signature = assertSignature('registry.proof.signature', proofObject.signature)
  const registry_root = assertNonZeroHash('registry.registry_root', registry.registry_root)
  return deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    registry_body,
    proof: { algorithm: 'Ed25519', signature },
    registry_root,
  })
}

export function canonicalizeCrossRuntimeReceiptSignatureMessageV1(
  value: CrossRuntimeReceiptDraftV1,
): Uint8Array {
  const draft = normalizeReceiptDraft(value)
  return canonicalizeJCS({
    domain: RECEIPT_SIGNATURE_DOMAIN,
    schema_version: draft.schema_version,
    receipt_kind: draft.receipt_kind,
    receipt_body: draft.receipt_body,
    proof: draft.proof,
  })
}

export async function deriveCrossRuntimeReceiptIdV1(
  value: Omit<CrossRuntimeReceiptEnvelopeV1, 'receipt_id'>,
): Promise<SHA256Hex> {
  const signed = normalizeSignedReceiptWithoutId(value)
  return sha256Hex(canonicalizeJCS({
    domain: RECEIPT_ID_DOMAIN,
    envelope: signed,
  }))
}

export async function buildCrossRuntimeReceiptEnvelopeV1(
  draft: CrossRuntimeReceiptDraftV1,
  privateKey: Uint8Array,
): Promise<CrossRuntimeReceiptEnvelopeV1> {
  const normalized = normalizeReceiptDraft(draft)
  const signature = await signBytes(
    privateKey,
    canonicalizeCrossRuntimeReceiptSignatureMessageV1(normalized),
  )
  const signed = deepFreeze({
    schema_version: normalized.schema_version,
    receipt_kind: normalized.receipt_kind,
    receipt_body: normalized.receipt_body,
    proof: { ...normalized.proof, signature },
  })
  const receipt_id = await deriveCrossRuntimeReceiptIdV1(signed)
  return normalizeCrossRuntimeReceiptEnvelopeV1({ ...signed, receipt_id })
}

export function canonicalizeReceiptTrustRegistrySignatureMessageV1(
  body: ReceiptTrustRegistryBodyV1,
): Uint8Array {
  const registryBody = normalizeRegistryBody(snapshotIJson(body, 'registry body'))
  return canonicalizeJCS({
    domain: REGISTRY_SIGNATURE_DOMAIN,
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    registry_body: registryBody,
    proof: { algorithm: 'Ed25519' },
  })
}

export async function deriveReceiptTrustRegistryRootV1(
  value: Omit<ReceiptTrustRegistryV1, 'registry_root'>,
): Promise<SHA256Hex> {
  const registry = normalizeRegistryWithoutRoot(value)
  return sha256Hex(canonicalizeJCS({
    domain: REGISTRY_ROOT_DOMAIN,
    registry,
  }))
}

export async function buildReceiptTrustRegistryV1(
  body: ReceiptTrustRegistryBodyV1,
  operatorPrivateKey: Uint8Array,
): Promise<ReceiptTrustRegistryV1> {
  const registry_body = normalizeRegistryBody(snapshotIJson(body, 'registry body'))
  const signature = await signBytes(
    operatorPrivateKey,
    canonicalizeReceiptTrustRegistrySignatureMessageV1(registry_body),
  )
  const unsignedRoot = deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    registry_body,
    proof: { algorithm: 'Ed25519' as const, signature },
  })
  const registry_root = await deriveReceiptTrustRegistryRootV1(unsignedRoot)
  return normalizeReceiptTrustRegistryV1({ ...unsignedRoot, registry_root })
}

export async function assertCrossRuntimeReceiptIdV1(
  envelope: CrossRuntimeReceiptEnvelopeV1,
): Promise<void> {
  const normalized = normalizeCrossRuntimeReceiptEnvelopeV1(envelope)
  const { receipt_id: _receiptId, ...signed } = normalized
  const expected = await deriveCrossRuntimeReceiptIdV1(signed)
  if (normalized.receipt_id !== expected) fail('receipt.receipt_id does not match its signed content')
}

export async function assertReceiptTrustRegistryRootV1(
  registry: ReceiptTrustRegistryV1,
): Promise<void> {
  const normalized = normalizeReceiptTrustRegistryV1(registry)
  const { registry_root: _registryRoot, ...signed } = normalized
  const expected = await deriveReceiptTrustRegistryRootV1(signed)
  if (normalized.registry_root !== expected) fail('registry.registry_root does not match its signed content')
}

function normalizeReceiptDraft(value: unknown): CrossRuntimeReceiptDraftV1 {
  const snapshot = snapshotIJson(value, 'cross-runtime receipt draft')
  const draft = asObject('receipt draft', snapshot)
  assertExactKeys('receipt draft', draft, ['proof', 'receipt_body', 'receipt_kind', 'schema_version'])
  if (draft.schema_version !== CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION) {
    fail('receipt draft.schema_version is unsupported')
  }
  const proofObject = asObject('receipt draft.proof', draft.proof)
  assertExactKeys('receipt draft.proof', proofObject, RECEIPT_UNSIGNED_PROOF_KEYS)
  const receiptKind = assertReceiptKind('receipt draft.receipt_kind', draft.receipt_kind)
  const receiptBody = normalizeReceiptBody(draft.receipt_body)
  assertReceiptKindBodySemantics(receiptKind, receiptBody)
  return deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    receipt_kind: receiptKind,
    receipt_body: receiptBody,
    proof: normalizeUnsignedReceiptProof(proofObject),
  })
}

function normalizeSignedReceiptWithoutId(
  value: unknown,
): Omit<CrossRuntimeReceiptEnvelopeV1, 'receipt_id'> {
  const snapshot = snapshotIJson(value, 'signed receipt')
  const signed = asObject('signed receipt', snapshot)
  assertExactKeys('signed receipt', signed, ['proof', 'receipt_body', 'receipt_kind', 'schema_version'])
  if (signed.schema_version !== CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION) {
    fail('signed receipt.schema_version is unsupported')
  }
  const receiptKind = assertReceiptKind('signed receipt.receipt_kind', signed.receipt_kind)
  const receiptBody = normalizeReceiptBody(signed.receipt_body)
  assertReceiptKindBodySemantics(receiptKind, receiptBody)
  return deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    receipt_kind: receiptKind,
    receipt_body: receiptBody,
    proof: normalizeReceiptProof(signed.proof),
  })
}

function normalizeRegistryWithoutRoot(
  value: unknown,
): Omit<ReceiptTrustRegistryV1, 'registry_root'> {
  const snapshot = snapshotIJson(value, 'signed receipt trust registry')
  const registry = asObject('signed registry', snapshot)
  assertExactKeys('signed registry', registry, ['proof', 'registry_body', 'schema_version'])
  if (registry.schema_version !== CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION) {
    fail('signed registry.schema_version is unsupported')
  }
  const proof = asObject('signed registry.proof', registry.proof)
  assertExactKeys('signed registry.proof', proof, ['algorithm', 'signature'])
  if (proof.algorithm !== 'Ed25519') fail('signed registry.proof.algorithm is unsupported')
  return deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    registry_body: normalizeRegistryBody(registry.registry_body),
    proof: {
      algorithm: 'Ed25519',
      signature: assertSignature('signed registry.proof.signature', proof.signature),
    },
  })
}

function normalizeReceiptBody(value: unknown): CrossRuntimeReceiptBodyV1 {
  const body = asObject('receipt.receipt_body', value)
  assertExactKeys('receipt.receipt_body', body, RECEIPT_BODY_KEYS)
  const denialCodes = asArray('receipt.receipt_body.denial_codes', body.denial_codes)
  if (denialCodes.length > 32) fail('receipt.receipt_body.denial_codes has too many entries')
  const normalizedCodes = denialCodes.map((code, index) =>
    assertSafeId(`receipt.receipt_body.denial_codes[${index}]`, code))
  if (new Set(normalizedCodes).size !== normalizedCodes.length) {
    fail('receipt.receipt_body.denial_codes must be unique')
  }
  assertSortedUtf8('receipt.receipt_body.denial_codes', normalizedCodes)
  const authorityLevel = body.authority_level
  if (typeof authorityLevel !== 'string' || !AUTHORITY_LEVELS.has(authorityLevel as AuthorityLevelV1)) {
    fail('receipt.receipt_body.authority_level is invalid')
  }
  const outcome = body.outcome
  if (typeof outcome !== 'string' || !OUTCOMES.has(outcome as CrossRuntimeReceiptOutcomeV1)) {
    fail('receipt.receipt_body.outcome is invalid')
  }
  return deepFreeze({
    receipt_sequence: assertDecimal('receipt.receipt_body.receipt_sequence', body.receipt_sequence),
    actor_identity_root: assertNonZeroHash('receipt.receipt_body.actor_identity_root', body.actor_identity_root),
    session_identity_root: assertNonZeroHash('receipt.receipt_body.session_identity_root', body.session_identity_root),
    workspace_identity_root: assertNonZeroHash('receipt.receipt_body.workspace_identity_root', body.workspace_identity_root),
    holon_identity_root: assertNonZeroHash('receipt.receipt_body.holon_identity_root', body.holon_identity_root),
    authority_domain: assertSafeId('receipt.receipt_body.authority_domain', body.authority_domain),
    authority_level: authorityLevel as AuthorityLevelV1,
    authority_receipt_hash: assertHash('receipt.receipt_body.authority_receipt_hash', body.authority_receipt_hash),
    lease_id: assertNonZeroHash('receipt.receipt_body.lease_id', body.lease_id),
    lease_generation: assertDecimal('receipt.receipt_body.lease_generation', body.lease_generation),
    fencing_token: assertHash('receipt.receipt_body.fencing_token', body.fencing_token),
    lease_authorization_receipt_hash: assertHash(
      'receipt.receipt_body.lease_authorization_receipt_hash',
      body.lease_authorization_receipt_hash,
    ),
    parent_receipt_hash: assertHash('receipt.receipt_body.parent_receipt_hash', body.parent_receipt_hash),
    observed_state_root: assertNonZeroHash('receipt.receipt_body.observed_state_root', body.observed_state_root),
    expected_state_root: assertNonZeroHash('receipt.receipt_body.expected_state_root', body.expected_state_root),
    action_digest: assertNonZeroHash('receipt.receipt_body.action_digest', body.action_digest),
    before_state_root: assertNonZeroHash('receipt.receipt_body.before_state_root', body.before_state_root),
    after_state_root: assertNonZeroHash('receipt.receipt_body.after_state_root', body.after_state_root),
    result_digest: assertNonZeroHash('receipt.receipt_body.result_digest', body.result_digest),
    timestamp_ms: assertDecimal('receipt.receipt_body.timestamp_ms', body.timestamp_ms),
    expires_at_ms: assertDecimal('receipt.receipt_body.expires_at_ms', body.expires_at_ms),
    nonce: assertNonce('receipt.receipt_body.nonce', body.nonce),
    outcome: outcome as CrossRuntimeReceiptOutcomeV1,
    denial_codes: normalizedCodes,
  })
}

function normalizeReceiptProof(value: unknown): CrossRuntimeReceiptProofV1 {
  const proof = asObject('receipt.proof', value)
  assertExactKeys('receipt.proof', proof, RECEIPT_PROOF_KEYS)
  return deepFreeze({
    ...normalizeUnsignedReceiptProof(proof),
    signature: assertSignature('receipt.proof.signature', proof.signature),
  })
}

function normalizeUnsignedReceiptProof(
  proof: Record<string, unknown>,
): Omit<CrossRuntimeReceiptProofV1, 'signature'> {
  if (proof.algorithm !== 'Ed25519') fail('receipt.proof.algorithm is unsupported')
  return deepFreeze({
    algorithm: 'Ed25519',
    signer_key_id: assertSafeId('receipt.proof.signer_key_id', proof.signer_key_id),
    verifier_identity_root: assertNonZeroHash(
      'receipt.proof.verifier_identity_root',
      proof.verifier_identity_root,
    ),
    trust_registry_version: assertDecimal(
      'receipt.proof.trust_registry_version',
      proof.trust_registry_version,
    ),
    trust_registry_root: assertNonZeroHash(
      'receipt.proof.trust_registry_root',
      proof.trust_registry_root,
    ),
  })
}

function normalizeRegistryBody(value: unknown): ReceiptTrustRegistryBodyV1 {
  const body = asObject('registry.registry_body', value)
  assertExactKeys('registry.registry_body', body, REGISTRY_BODY_KEYS)
  const entries = asArray('registry.registry_body.keys', body.keys)
  if (entries.length < 1 || entries.length > 128) {
    fail('registry.registry_body.keys must contain between 1 and 128 entries')
  }
  const keys = entries.map((entry, index) => normalizeRegistryKeyEntry(entry, index))
  assertSortedUtf8('registry.registry_body.keys', keys.map(entry => entry.key_id))
  if (new Set(keys.map(entry => entry.key_id)).size !== keys.length) {
    fail('registry.registry_body.keys must have unique key_id values')
  }
  if (new Set(keys.map(entry => entry.public_key)).size !== keys.length) {
    fail('registry.registry_body.keys must have unique public_key values')
  }
  const issuedAt = assertDecimal('registry.registry_body.issued_at_ms', body.issued_at_ms)
  const validFrom = assertDecimal('registry.registry_body.valid_from_ms', body.valid_from_ms)
  const expiresAt = assertDecimal('registry.registry_body.expires_at_ms', body.expires_at_ms)
  if (BigInt(issuedAt) > BigInt(validFrom) || BigInt(validFrom) >= BigInt(expiresAt)) {
    fail('registry.registry_body validity interval is invalid or empty')
  }
  for (const [index, key] of keys.entries()) {
    if (BigInt(key.valid_from_ms) < BigInt(validFrom) ||
        BigInt(key.expires_at_ms) > BigInt(expiresAt)) {
      fail(`registry.registry_body.keys[${index}] validity must be contained by the registry window`)
    }
  }
  return deepFreeze({
    registry_version: assertDecimal('registry.registry_body.registry_version', body.registry_version),
    previous_registry_root: assertHash(
      'registry.registry_body.previous_registry_root',
      body.previous_registry_root,
    ),
    issued_at_ms: issuedAt,
    valid_from_ms: validFrom,
    expires_at_ms: expiresAt,
    operator_key_id: assertSafeId('registry.registry_body.operator_key_id', body.operator_key_id),
    keys,
  })
}

function normalizeRegistryKeyEntry(value: unknown, index: number): ReceiptTrustKeyEntryV1 {
  const field = `registry.registry_body.keys[${index}]`
  const entry = asObject(field, value)
  assertExactKeys(field, entry, REGISTRY_KEY_ENTRY_KEYS)
  const authorityDomains = asArray(`${field}.authority_domains`, entry.authority_domains)
  if (authorityDomains.length === 0) fail(`${field}.authority_domains must not be empty`)
  const normalizedDomains = authorityDomains.map((domain, domainIndex) =>
    assertSafeId(`${field}.authority_domains[${domainIndex}]`, domain))
  if (new Set(normalizedDomains).size !== normalizedDomains.length) {
    fail(`${field}.authority_domains must be unique`)
  }
  assertSortedUtf8(`${field}.authority_domains`, normalizedDomains)
  const kinds = asArray(`${field}.receipt_kinds`, entry.receipt_kinds)
  if (kinds.length === 0) fail(`${field}.receipt_kinds must not be empty`)
  const normalizedKinds = kinds.map((kind, kindIndex) =>
    assertReceiptKind(`${field}.receipt_kinds[${kindIndex}]`, kind))
  if (new Set(normalizedKinds).size !== normalizedKinds.length) {
    fail(`${field}.receipt_kinds must be unique`)
  }
  assertSortedUtf8(`${field}.receipt_kinds`, normalizedKinds)
  const status = entry.status
  if (typeof status !== 'string' || !KEY_STATUSES.has(status as ReceiptTrustKeyStatusV1)) {
    fail(`${field}.status is invalid`)
  }
  const validFrom = assertDecimal(`${field}.valid_from_ms`, entry.valid_from_ms)
  const expiresAt = assertDecimal(`${field}.expires_at_ms`, entry.expires_at_ms)
  if (BigInt(validFrom) >= BigInt(expiresAt)) fail(`${field} validity interval is invalid or empty`)
  return deepFreeze({
    key_id: assertSafeId(`${field}.key_id`, entry.key_id),
    public_key: assertHash(`${field}.public_key`, entry.public_key),
    verifier_identity_root: assertNonZeroHash(
      `${field}.verifier_identity_root`,
      entry.verifier_identity_root,
    ),
    valid_from_ms: validFrom,
    expires_at_ms: expiresAt,
    status: status as ReceiptTrustKeyStatusV1,
    authority_domains: normalizedDomains,
    receipt_kinds: normalizedKinds,
  })
}

function snapshotIJson(value: unknown, label: string): unknown {
  try {
    assertIJsonValue(value, label)
    const snapshot = structuredClone(value) as unknown
    assertIJsonValue(snapshot, label)
    return snapshot
  } catch (error) {
    if (error instanceof CrossRuntimeReceiptValidationError) throw error
    fail(`${label} is not a closed I-JSON value: ${error instanceof Error ? error.message : String(error)}`)
  }
}

function asObject(field: string, value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) fail(`${field} must be an object`)
  return value as Record<string, unknown>
}

function asArray(field: string, value: unknown): readonly unknown[] {
  if (!Array.isArray(value)) fail(`${field} must be an array`)
  return value
}

function assertExactKeys(
  field: string,
  value: Record<string, unknown>,
  expectedKeys: readonly string[],
): void {
  const actual = Object.keys(value).sort(compareUtf8)
  const expected = [...expectedKeys].sort(compareUtf8)
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    fail(`${field} has unexpected or missing fields`)
  }
}

function assertReceiptKind(field: string, value: unknown): CrossRuntimeReceiptKindV1 {
  if (typeof value !== 'string' || !RECEIPT_KINDS.has(value as CrossRuntimeReceiptKindV1)) {
    fail(`${field} is invalid`)
  }
  return value as CrossRuntimeReceiptKindV1
}

function assertHash(field: string, value: unknown): SHA256Hex {
  if (typeof value !== 'string' || !HASH_PATTERN.test(value)) fail(`${field} must be lowercase SHA-256 hex`)
  return value as SHA256Hex
}

function assertNonZeroHash(field: string, value: unknown): SHA256Hex {
  const hash = assertHash(field, value)
  if (hash === ZERO_HASH) fail(`${field} must be a non-zero SHA-256 root`)
  return hash
}

function assertSignature(field: string, value: unknown): string {
  if (typeof value !== 'string' || !SIGNATURE_PATTERN.test(value)) {
    fail(`${field} must be 64-byte lowercase Ed25519 hex`)
  }
  return value
}

function assertDecimal(field: string, value: unknown): DecimalStringV1 {
  if (typeof value !== 'string' || value.length > 20 || !DECIMAL_PATTERN.test(value)) {
    fail(`${field} must be a canonical decimal string of at most 20 digits`)
  }
  return value
}

function assertSafeId(field: string, value: unknown): string {
  if (typeof value !== 'string' || !SAFE_ID_PATTERN.test(value)) fail(`${field} is not a canonical safe identifier`)
  return value
}

function assertNonce(field: string, value: unknown): string {
  if (typeof value !== 'string' || !NONCE_PATTERN.test(value)) fail(`${field} is not a canonical nonce`)
  return value
}

function compareUtf8(left: string, right: string): number {
  const leftBytes = new TextEncoder().encode(left)
  const rightBytes = new TextEncoder().encode(right)
  const length = Math.min(leftBytes.length, rightBytes.length)
  for (let index = 0; index < length; index += 1) {
    const difference = leftBytes[index]! - rightBytes[index]!
    if (difference !== 0) return difference
  }
  return leftBytes.length - rightBytes.length
}

function assertSortedUtf8(field: string, values: readonly string[]): void {
  for (let index = 1; index < values.length; index += 1) {
    if (compareUtf8(values[index - 1]!, values[index]!) >= 0) {
      fail(`${field} must be strictly sorted by UTF-8 bytes`)
    }
  }
}

function assertReceiptKindBodySemantics(
  kind: CrossRuntimeReceiptKindV1,
  body: CrossRuntimeReceiptBodyV1,
): void {
  const expectedOutcomes: Readonly<Record<CrossRuntimeReceiptKindV1, CrossRuntimeReceiptOutcomeV1>> = {
    LEASE_ISSUED: 'ADMITTED',
    LEASE_ISSUANCE_DENIED: 'DENIED',
    LEASE_RENEWED: 'ADMITTED',
    LEASE_RENEWAL_DENIED: 'DENIED',
    LEASE_EXPIRED: 'EXPIRED',
    LEASE_REVOKED: 'REVOKED',
    MUTATION_ADMITTED: 'ADMITTED',
    MUTATION_DENIED: 'DENIED',
    MUTATION_COMPLETED: 'COMPLETED',
    MUTATION_CANCELLED: 'CANCELLED',
    MUTATION_FAILED: 'FAILED',
  }
  if (body.outcome !== expectedOutcomes[kind]) {
    fail(`receipt.receipt_body.outcome is invalid for ${kind}`)
  }
  const denialRequired = new Set<CrossRuntimeReceiptKindV1>([
    'LEASE_ISSUANCE_DENIED',
    'LEASE_RENEWAL_DENIED',
    'LEASE_EXPIRED',
    'LEASE_REVOKED',
    'MUTATION_DENIED',
    'MUTATION_CANCELLED',
    'MUTATION_FAILED',
  ]).has(kind)
  if (denialRequired && body.denial_codes.length === 0) {
    fail(`receipt.receipt_body.denial_codes must not be empty for ${kind}`)
  }
  if (!denialRequired && body.denial_codes.length !== 0) {
    fail(`receipt.receipt_body.denial_codes must be empty for ${kind}`)
  }
  if (kind === 'LEASE_ISSUANCE_DENIED') {
    if (body.fencing_token !== ZERO_HASH) {
      fail('receipt.receipt_body.fencing_token must be unresolved for denied lease issuance')
    }
  } else if (body.fencing_token === ZERO_HASH) {
    fail(`receipt.receipt_body.fencing_token must be resolved for ${kind}`)
  }
  if (kind.startsWith('LEASE_')) {
    if (body.authority_receipt_hash !== ZERO_HASH ||
        body.lease_authorization_receipt_hash !== ZERO_HASH) {
      fail(`${kind} must not carry mutation authority receipt roots`)
    }
  } else if (body.authority_receipt_hash === ZERO_HASH ||
             body.lease_authorization_receipt_hash === ZERO_HASH) {
    fail(`${kind} must resolve authority and lease-authorization receipt roots`)
  }
}

function fail(message: string): never {
  throw new CrossRuntimeReceiptValidationError(message)
}
