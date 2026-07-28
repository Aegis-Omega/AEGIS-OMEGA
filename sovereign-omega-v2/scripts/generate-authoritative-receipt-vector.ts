#!/usr/bin/env tsx
/** Generate the deterministic TypeScript cross-runtime receipt golden vector. */

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { canonicalizeJCS } from '../src/core/canonicalize.js'
import { generateKeypair } from '../src/consensus/crypto.js'
import { hexToUint8Array, sha256Hex } from '../src/core/hashing.js'
import type { SHA256Hex } from '../src/core/types.js'
import {
  CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
  buildCrossRuntimeReceiptEnvelopeV1,
  buildReceiptTrustRegistryV1,
  type CrossRuntimeReceiptBodyV1,
  type CrossRuntimeReceiptDraftV1,
  type CrossRuntimeReceiptEnvelopeV1,
  type CrossRuntimeReceiptKindV1,
  type CrossRuntimeReceiptOutcomeV1,
} from '../src/provenance/cross-runtime-receipts.js'

const OPERATOR_KEY_ID = 'operator-root-v1'
const OPERATOR_PRIVATE =
  '9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60'
const OPERATOR_PUBLIC =
  'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'
const SIGNER_KEY_ID = 'cross-runtime-witness-v1'
const SIGNER_PRIVATE =
  '4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb'
const SIGNER_PUBLIC =
  '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'
const AUTHORITY_DOMAIN = 'repository:mutation'
const H = (character: string): SHA256Hex => character.repeat(64) as SHA256Hex
const ZERO = H('0')
const ALL_RECEIPT_KINDS = [
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
].sort() as CrossRuntimeReceiptKindV1[]

interface BodyInput {
  readonly kind: CrossRuntimeReceiptKindV1
  readonly outcome: CrossRuntimeReceiptOutcomeV1
  readonly leaseId: SHA256Hex
  readonly leaseGeneration: string
  readonly fencingToken: SHA256Hex
  readonly authorityReceiptHash: SHA256Hex
  readonly leaseAuthorizationReceiptHash: SHA256Hex
  readonly observedStateRoot: SHA256Hex
  readonly expectedStateRoot: SHA256Hex
  readonly actionDigest: SHA256Hex
  readonly afterStateRoot?: SHA256Hex
  readonly resultDigest?: SHA256Hex
  readonly timestampMs: string
  readonly expiresAtMs: string
  readonly nonce: string
  readonly denialCodes?: readonly string[]
}

async function domainHash(domain: string, value: unknown): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeJCS({ domain, value }))
}

async function receiptResultDigest(
  kind: CrossRuntimeReceiptKindV1,
  outcome: CrossRuntimeReceiptOutcomeV1,
  denialCodes: readonly string[],
  nonce: string,
): Promise<SHA256Hex> {
  return domainHash('AEGIS_AUTHORITATIVE_RECEIPT_RESULT_V1', {
    receipt_kind: kind,
    outcome,
    denial_codes: denialCodes,
    nonce,
  })
}

export async function buildTypeScriptCrossRuntimeVectorV1(): Promise<unknown> {
  const operator = await generateKeypair(hexToUint8Array(OPERATOR_PRIVATE))
  const signer = await generateKeypair(hexToUint8Array(SIGNER_PRIVATE))
  if (operator.publicKey !== OPERATOR_PUBLIC || signer.publicKey !== SIGNER_PUBLIC) {
    throw new Error('RFC 8032 fixture key derivation mismatch')
  }
  const registry = await buildReceiptTrustRegistryV1({
    registry_version: '1',
    previous_registry_root: ZERO,
    issued_at_ms: '90',
    valid_from_ms: '100',
    expires_at_ms: '10000',
    operator_key_id: OPERATOR_KEY_ID,
    keys: [{
      key_id: SIGNER_KEY_ID,
      public_key: signer.publicKey,
      verifier_identity_root: H('7'),
      valid_from_ms: '100',
      expires_at_ms: '9000',
      status: 'ACTIVE',
      authority_domains: [AUTHORITY_DOMAIN],
      receipt_kinds: ALL_RECEIPT_KINDS,
    }],
  }, operator.privateKey)
  const proof: CrossRuntimeReceiptDraftV1['proof'] = {
    algorithm: 'Ed25519',
    signer_key_id: SIGNER_KEY_ID,
    verifier_identity_root: H('7'),
    trust_registry_version: '1',
    trust_registry_root: registry.registry_root,
  }
  const receipts: CrossRuntimeReceiptEnvelopeV1[] = []

  async function append(input: BodyInput): Promise<CrossRuntimeReceiptEnvelopeV1> {
    const denialCodes = [...(input.denialCodes ?? [])].sort()
    const body: CrossRuntimeReceiptBodyV1 = {
      receipt_sequence: String(receipts.length),
      actor_identity_root: H('1'),
      session_identity_root: H('2'),
      workspace_identity_root: H('3'),
      holon_identity_root: H('4'),
      authority_domain: AUTHORITY_DOMAIN,
      authority_level: 'D2',
      authority_receipt_hash: input.authorityReceiptHash,
      lease_id: input.leaseId,
      lease_generation: input.leaseGeneration,
      fencing_token: input.fencingToken,
      lease_authorization_receipt_hash: input.leaseAuthorizationReceiptHash,
      parent_receipt_hash: receipts.at(-1)?.receipt_id ?? ZERO,
      observed_state_root: input.observedStateRoot,
      expected_state_root: input.expectedStateRoot,
      action_digest: input.actionDigest,
      before_state_root: input.observedStateRoot,
      after_state_root: input.afterStateRoot ?? input.observedStateRoot,
      result_digest: input.resultDigest ?? await receiptResultDigest(
        input.kind,
        input.outcome,
        denialCodes,
        input.nonce,
      ),
      timestamp_ms: input.timestampMs,
      expires_at_ms: input.expiresAtMs,
      nonce: input.nonce,
      outcome: input.outcome,
      denial_codes: denialCodes,
    }
    const receipt = await buildCrossRuntimeReceiptEnvelopeV1({
      schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
      receipt_kind: input.kind,
      receipt_body: body,
      proof,
    }, signer.privateKey)
    receipts.push(receipt)
    return receipt
  }

  await append({
    kind: 'LEASE_ISSUANCE_DENIED',
    outcome: 'DENIED',
    leaseId: H('4'),
    leaseGeneration: '1',
    fencingToken: ZERO,
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('f'),
    expectedStateRoot: H('f'),
    actionDigest: H('1'),
    timestampMs: '1000',
    expiresAtMs: '900',
    nonce: 'vector-lease-denied-01',
    denialCodes: ['LEASE_EXPIRY_INVALID'],
  })

  const leaseOneFence = await domainHash('AEGIS_AUTHORITATIVE_FENCE_V1', {
    authority_domain: AUTHORITY_DOMAIN,
    lease_id: H('5'),
    lease_generation: '1',
    parent_receipt_hash: receipts.at(-1)!.receipt_id,
    nonce: 'vector-lease-issued-01',
  })
  await append({
    kind: 'LEASE_ISSUED',
    outcome: 'ADMITTED',
    leaseId: H('5'),
    leaseGeneration: '1',
    fencingToken: leaseOneFence,
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('a'),
    expectedStateRoot: H('a'),
    actionDigest: H('b'),
    timestampMs: '1100',
    expiresAtMs: '3000',
    nonce: 'vector-lease-issued-01',
  })
  await append({
    kind: 'LEASE_RENEWAL_DENIED',
    outcome: 'DENIED',
    leaseId: H('5'),
    leaseGeneration: '0',
    fencingToken: H('9'),
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('a'),
    expectedStateRoot: H('a'),
    actionDigest: H('b'),
    timestampMs: '1200',
    expiresAtMs: '4000',
    nonce: 'vector-renew-denied-01',
    denialCodes: ['STALE_FENCING_TOKEN', 'STALE_LEASE_GENERATION'],
  })

  const leaseTwoFence = await domainHash('AEGIS_AUTHORITATIVE_FENCE_V1', {
    authority_domain: AUTHORITY_DOMAIN,
    lease_id: H('5'),
    lease_generation: '2',
    parent_receipt_hash: receipts.at(-1)!.receipt_id,
    nonce: 'vector-lease-renewed-1',
  })
  const renewed = await append({
    kind: 'LEASE_RENEWED',
    outcome: 'ADMITTED',
    leaseId: H('5'),
    leaseGeneration: '2',
    fencingToken: leaseTwoFence,
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('a'),
    expectedStateRoot: H('a'),
    actionDigest: H('b'),
    timestampMs: '1300',
    expiresAtMs: '4000',
    nonce: 'vector-lease-renewed-1',
  })
  await append({
    kind: 'MUTATION_DENIED',
    outcome: 'DENIED',
    leaseId: H('5'),
    leaseGeneration: '2',
    fencingToken: leaseTwoFence,
    authorityReceiptHash: H('c'),
    leaseAuthorizationReceiptHash: renewed.receipt_id,
    observedStateRoot: H('a'),
    expectedStateRoot: H('a'),
    actionDigest: H('d'),
    resultDigest: H('4'),
    timestampMs: '1400',
    expiresAtMs: '4000',
    nonce: 'vector-mutation-deny-01',
    denialCodes: ['POLICY_DENIED'],
  })
  await append({
    kind: 'MUTATION_ADMITTED',
    outcome: 'ADMITTED',
    leaseId: H('5'),
    leaseGeneration: '2',
    fencingToken: leaseTwoFence,
    authorityReceiptHash: H('c'),
    leaseAuthorizationReceiptHash: renewed.receipt_id,
    observedStateRoot: H('a'),
    expectedStateRoot: H('a'),
    actionDigest: H('b'),
    timestampMs: '1500',
    expiresAtMs: '4000',
    nonce: 'vector-mutation-admit-1',
  })
  await append({
    kind: 'MUTATION_COMPLETED',
    outcome: 'COMPLETED',
    leaseId: H('5'),
    leaseGeneration: '2',
    fencingToken: leaseTwoFence,
    authorityReceiptHash: H('c'),
    leaseAuthorizationReceiptHash: renewed.receipt_id,
    observedStateRoot: H('a'),
    expectedStateRoot: H('a'),
    actionDigest: H('b'),
    afterStateRoot: H('e'),
    resultDigest: H('f'),
    timestampMs: '1600',
    expiresAtMs: '4000',
    nonce: 'vector-mutation-done-01',
  })

  const cancelFence = await domainHash('AEGIS_AUTHORITATIVE_FENCE_V1', {
    authority_domain: AUTHORITY_DOMAIN,
    lease_id: H('6'),
    lease_generation: '3',
    parent_receipt_hash: receipts.at(-1)!.receipt_id,
    nonce: 'vector-cancel-lease-001',
  })
  const cancelLease = await append({
    kind: 'LEASE_ISSUED',
    outcome: 'ADMITTED',
    leaseId: H('6'),
    leaseGeneration: '3',
    fencingToken: cancelFence,
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('7'),
    timestampMs: '1700',
    expiresAtMs: '2000',
    nonce: 'vector-cancel-lease-001',
  })
  await append({
    kind: 'MUTATION_ADMITTED',
    outcome: 'ADMITTED',
    leaseId: H('6'),
    leaseGeneration: '3',
    fencingToken: cancelFence,
    authorityReceiptHash: H('c'),
    leaseAuthorizationReceiptHash: cancelLease.receipt_id,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('7'),
    timestampMs: '1800',
    expiresAtMs: '2000',
    nonce: 'vector-cancel-admit-01',
  })
  await append({
    kind: 'LEASE_EXPIRED',
    outcome: 'EXPIRED',
    leaseId: H('6'),
    leaseGeneration: '3',
    fencingToken: cancelFence,
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('7'),
    timestampMs: '2000',
    expiresAtMs: '2000',
    nonce: 'vector-lease-expired-1',
    denialCodes: ['LEASE_EXPIRED'],
  })
  await append({
    kind: 'MUTATION_CANCELLED',
    outcome: 'CANCELLED',
    leaseId: H('6'),
    leaseGeneration: '3',
    fencingToken: cancelFence,
    authorityReceiptHash: H('c'),
    leaseAuthorizationReceiptHash: cancelLease.receipt_id,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('7'),
    resultDigest: H('8'),
    timestampMs: '2100',
    expiresAtMs: '2000',
    nonce: 'vector-mutation-cancel1',
    denialCodes: ['CANCELLED_AFTER_EXPIRY'],
  })

  const failureFence = await domainHash('AEGIS_AUTHORITATIVE_FENCE_V1', {
    authority_domain: AUTHORITY_DOMAIN,
    lease_id: H('9'),
    lease_generation: '4',
    parent_receipt_hash: receipts.at(-1)!.receipt_id,
    nonce: 'vector-failure-lease-1',
  })
  const failureLease = await append({
    kind: 'LEASE_ISSUED',
    outcome: 'ADMITTED',
    leaseId: H('9'),
    leaseGeneration: '4',
    fencingToken: failureFence,
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('a'),
    timestampMs: '2200',
    expiresAtMs: '4000',
    nonce: 'vector-failure-lease-1',
  })
  await append({
    kind: 'MUTATION_ADMITTED',
    outcome: 'ADMITTED',
    leaseId: H('9'),
    leaseGeneration: '4',
    fencingToken: failureFence,
    authorityReceiptHash: H('c'),
    leaseAuthorizationReceiptHash: failureLease.receipt_id,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('a'),
    timestampMs: '2300',
    expiresAtMs: '4000',
    nonce: 'vector-failure-admit-1',
  })
  await append({
    kind: 'LEASE_REVOKED',
    outcome: 'REVOKED',
    leaseId: H('9'),
    leaseGeneration: '4',
    fencingToken: failureFence,
    authorityReceiptHash: ZERO,
    leaseAuthorizationReceiptHash: ZERO,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('a'),
    timestampMs: '2400',
    expiresAtMs: '4000',
    nonce: 'vector-lease-revoked-1',
    denialCodes: ['OPERATOR_REVOKED'],
  })
  const terminal = await append({
    kind: 'MUTATION_FAILED',
    outcome: 'FAILED',
    leaseId: H('9'),
    leaseGeneration: '4',
    fencingToken: failureFence,
    authorityReceiptHash: H('c'),
    leaseAuthorizationReceiptHash: failureLease.receipt_id,
    observedStateRoot: H('e'),
    expectedStateRoot: H('e'),
    actionDigest: H('a'),
    resultDigest: H('b'),
    timestampMs: '2500',
    expiresAtMs: '4000',
    nonce: 'vector-mutation-fail-01',
    denialCodes: ['FAILED_AFTER_REVOCATION'],
  })

  const vector = {
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    operator_public_key: OPERATOR_PUBLIC,
    registry,
    receipts,
    terminal_receipt_id: terminal.receipt_id,
    context: {
      operator_key_id: OPERATOR_KEY_ID,
      accepted_registry_roots: [registry.registry_root],
      observed_at_ms: '3000',
      max_clock_skew_ms: '0',
      expected_actor_identity_root: H('1'),
      expected_session_identity_root: H('2'),
      expected_workspace_identity_root: H('3'),
      expected_holon_identity_root: H('4'),
      expected_authority_domain: AUTHORITY_DOMAIN,
      expected_authority_level: 'D2',
      expected_observed_state_root: H('e'),
      expected_action_digest: H('a'),
    },
  }
  return vector
}

async function main(): Promise<void> {
  const outputFlag = process.argv.indexOf('--output')
  if (outputFlag < 0 || process.argv[outputFlag + 1] === undefined) {
    throw new Error('usage: generate-authoritative-receipt-vector.ts --output <path>')
  }
  const output = resolve(process.argv[outputFlag + 1]!)
  const vector = await buildTypeScriptCrossRuntimeVectorV1()
  mkdirSync(dirname(output), { recursive: true })
  writeFileSync(output, Buffer.from(canonicalizeJCS(vector)))
  writeFileSync(output, '\n', { flag: 'a' })
}

if (
  process.argv[1] !== undefined
  && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  await main()
}
