// ============================================================
// AEGIS Cross-Runtime Receipt Resolver V1
// PROVENANCE ASSURANCE: T2->T3 implemented; projection admission pending
//
// Resolution is read-only. It verifies an operator-pinned registry and every
// signed receipt from genesis through the requested terminal receipt, then
// replays lease, fencing, state, and mutation invariants. It never grants
// authority, executes a mutation, or projects an authoritative UI status.
// ============================================================

import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import { assertIJsonValue } from '../core/i-json.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex } from '../core/types.js'
import { verifyBytes } from '../consensus/crypto.js'
import {
  CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
  assertCrossRuntimeReceiptIdV1,
  assertReceiptTrustRegistryRootV1,
  canonicalizeCrossRuntimeReceiptSignatureMessageV1,
  canonicalizeReceiptTrustRegistrySignatureMessageV1,
  normalizeCrossRuntimeReceiptEnvelopeV1,
  normalizeReceiptTrustRegistryV1,
} from './cross-runtime-receipts.js'
import type {
  AuthorityLevelV1,
  CrossRuntimeReceiptBodyV1,
  CrossRuntimeReceiptEnvelopeV1,
  CrossRuntimeReceiptKindV1,
  CrossRuntimeReceiptOutcomeV1,
  DecimalStringV1,
  ReceiptTrustKeyEntryV1,
  ReceiptTrustRegistryV1,
} from './cross-runtime-receipts.js'

const ZERO_HASH = '0'.repeat(64) as SHA256Hex
const HASH_PATTERN = /^[0-9a-f]{64}$/
const DECIMAL_PATTERN = /^(0|[1-9][0-9]*)$/
const SAFE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/
const MAX_CHAIN_LENGTH = 4096
const MAX_CLOCK_SKEW_MS = 300_000n
const VERIFICATION_DECISION_DOMAIN = 'AEGIS_CROSS_RUNTIME_RECEIPT_VERIFICATION_DECISION_V1'
const VERIFIED_CHAIN_DOMAIN = 'AEGIS_CROSS_RUNTIME_VERIFIED_RECEIPT_CHAIN_V1'

export interface CrossRuntimeReceiptSourceV1 {
  resolveReceipt(receiptId: SHA256Hex): Promise<unknown | null>
  resolveTrustRegistry(registryRoot: SHA256Hex): Promise<unknown | null>
}

export interface TrustedReceiptResolutionContextV1 {
  readonly operator_key_id: string
  readonly operator_public_key: string
  readonly accepted_registry_roots: readonly SHA256Hex[]
  readonly observed_at_ms: DecimalStringV1
  readonly max_clock_skew_ms: DecimalStringV1
  readonly expected_actor_identity_root: SHA256Hex
  readonly expected_session_identity_root: SHA256Hex
  readonly expected_workspace_identity_root: SHA256Hex
  readonly expected_holon_identity_root: SHA256Hex
  readonly expected_authority_domain: string
  readonly expected_authority_level: AuthorityLevelV1
  readonly expected_observed_state_root: SHA256Hex
  readonly expected_action_digest: SHA256Hex
}

export interface VerifiedReceiptTrustRegistryV1 {
  readonly registry: ReceiptTrustRegistryV1
  readonly operator_key_id: string
  readonly operator_public_key: string
}

export interface CrossRuntimeReceiptVerificationDecisionV1 {
  readonly schema_version: typeof CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION
  readonly decision_kind: 'AEGIS_CROSS_RUNTIME_RECEIPT_VERIFICATION_DECISION_V1'
  readonly decision: 'VERIFIED'
  readonly terminal_receipt_id: SHA256Hex
  readonly terminal_receipt_kind: CrossRuntimeReceiptKindV1
  readonly terminal_outcome: CrossRuntimeReceiptOutcomeV1
  readonly chain_digest: SHA256Hex
  readonly receipt_count: DecimalStringV1
  readonly registry_roots: readonly SHA256Hex[]
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
  readonly action_digest: SHA256Hex
  readonly before_state_root: SHA256Hex
  readonly after_state_root: SHA256Hex
  readonly result_digest: SHA256Hex
  readonly observed_at_ms: DecimalStringV1
  readonly max_clock_skew_ms: DecimalStringV1
  readonly grants_authority: false
  readonly executes_mutation: false
  readonly decision_digest: SHA256Hex
}

export class CrossRuntimeReceiptResolutionError extends Error {
  override readonly name = 'CrossRuntimeReceiptResolutionError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

interface NormalizedResolutionContext extends TrustedReceiptResolutionContextV1 {
  readonly observedAt: bigint
  readonly maxClockSkew: bigint
}

interface ActiveLease {
  readonly body: CrossRuntimeReceiptBodyV1
  readonly receiptId: SHA256Hex
  readonly expiresAt: bigint
}

interface MutationState {
  readonly admission: CrossRuntimeReceiptEnvelopeV1
  terminal: CrossRuntimeReceiptEnvelopeV1 | null
}

interface VerifiedRegistryCacheEntry {
  readonly verified: VerifiedReceiptTrustRegistryV1
  readonly ancestryRoots: ReadonlySet<SHA256Hex>
}

export async function verifyReceiptTrustRegistryV1(
  value: unknown,
  context: TrustedReceiptResolutionContextV1,
): Promise<VerifiedReceiptTrustRegistryV1> {
  const trusted = normalizeResolutionContext(context)
  return verifyReceiptTrustRegistryWithNormalizedContextV1(value, trusted)
}

async function verifyReceiptTrustRegistryWithNormalizedContextV1(
  value: unknown,
  trusted: NormalizedResolutionContext,
): Promise<VerifiedReceiptTrustRegistryV1> {
  const registry = normalizeReceiptTrustRegistryV1(value)
  await assertReceiptTrustRegistryRootV1(registry)
  if (!trusted.accepted_registry_roots.includes(registry.registry_root)) {
    fail('receipt trust registry root is not explicitly accepted')
  }
  if (registry.registry_body.operator_key_id !== trusted.operator_key_id) {
    fail('receipt trust registry operator key id does not match the pinned key')
  }
  const version = BigInt(registry.registry_body.registry_version)
  if (version < 1n) fail('receipt trust registry version must be positive')
  if (version === 1n && registry.registry_body.previous_registry_root !== ZERO_HASH) {
    fail('receipt trust registry version 1 must have the genesis previous root')
  }
  if (version > 1n && registry.registry_body.previous_registry_root === ZERO_HASH) {
    fail('rotated receipt trust registry must resolve its previous root')
  }
  const issuedAt = BigInt(registry.registry_body.issued_at_ms)
  if (issuedAt > trusted.observedAt + trusted.maxClockSkew) {
    fail('receipt trust registry was issued beyond the allowed clock skew')
  }
  const valid = await verifyBytes(
    trusted.operator_public_key,
    canonicalizeReceiptTrustRegistrySignatureMessageV1(registry.registry_body),
    registry.proof.signature,
  )
  if (!valid) fail('receipt trust registry operator signature is invalid')
  return deepFreeze({
    registry,
    operator_key_id: trusted.operator_key_id,
    operator_public_key: trusted.operator_public_key,
  })
}

export async function resolveAndVerifyCrossRuntimeReceiptChainV1(
  source: CrossRuntimeReceiptSourceV1,
  terminalReceiptId: SHA256Hex,
  context: TrustedReceiptResolutionContextV1,
): Promise<CrossRuntimeReceiptVerificationDecisionV1> {
  assertSource(source)
  const trusted = normalizeResolutionContext(context)
  const requestedTerminal = assertNonZeroHash('terminal receipt id', terminalReceiptId)
  const reverseChain: CrossRuntimeReceiptEnvelopeV1[] = []
  const seenIds = new Set<string>()
  let cursor: SHA256Hex = requestedTerminal
  while (cursor !== ZERO_HASH) {
    if (reverseChain.length >= MAX_CHAIN_LENGTH) fail('receipt chain exceeds the replay bound')
    if (seenIds.has(cursor)) fail('receipt parent chain contains a cycle')
    seenIds.add(cursor)
    const raw = await source.resolveReceipt(cursor)
    if (raw === null) fail(`receipt ${cursor} cannot be resolved`)
    const receipt = normalizeCrossRuntimeReceiptEnvelopeV1(raw)
    await assertCrossRuntimeReceiptIdV1(receipt)
    if (receipt.receipt_id !== cursor) fail('resolved receipt does not match its requested content hash')
    reverseChain.push(receipt)
    cursor = receipt.receipt_body.parent_receipt_hash
  }
  const chain = reverseChain.reverse()
  if (chain.length === 0) fail('receipt chain must not be empty')

  const registryCache = new Map<SHA256Hex, VerifiedRegistryCacheEntry>()
  let previousRegistryRoot: SHA256Hex | null = null
  let previousRegistryVersion = -1n
  for (const receipt of chain) {
    const verifiedRegistry = await verifyReceiptAgainstRegistry(receipt, source, trusted, registryCache)
    const registryVersion = BigInt(verifiedRegistry.verified.registry.registry_body.registry_version)
    if (registryVersion < previousRegistryVersion) {
      fail('receipt chain rolls back its trust registry version')
    }
    if (registryVersion === previousRegistryVersion && previousRegistryRoot !== null &&
        receipt.proof.trust_registry_root !== previousRegistryRoot) {
      fail('receipt chain changes registry roots without advancing the registry version')
    }
    if (registryVersion > previousRegistryVersion && previousRegistryRoot !== null &&
        !verifiedRegistry.ancestryRoots.has(previousRegistryRoot)) {
      fail('receipt chain trust registry rotation does not descend from the prior registry root')
    }
    previousRegistryRoot = receipt.proof.trust_registry_root
    previousRegistryVersion = registryVersion
  }
  replayReceiptChain(chain)

  const terminal = chain[chain.length - 1]!
  if (!isTerminalKind(terminal.receipt_kind)) {
    fail(`receipt ${terminal.receipt_kind} is not terminal evidence`)
  }
  assertTerminalContextBindings(terminal.receipt_body, trusted)
  const registry_roots = [...new Set(chain.map(receipt => receipt.proof.trust_registry_root))]
    .sort(compareUtf8) as SHA256Hex[]
  const chain_digest = await sha256Hex(canonicalizeJCS({
    domain: VERIFIED_CHAIN_DOMAIN,
    receipt_ids: chain.map(receipt => receipt.receipt_id),
  }))
  const body = terminal.receipt_body
  const unsigned = deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    decision_kind: 'AEGIS_CROSS_RUNTIME_RECEIPT_VERIFICATION_DECISION_V1' as const,
    decision: 'VERIFIED' as const,
    terminal_receipt_id: terminal.receipt_id,
    terminal_receipt_kind: terminal.receipt_kind,
    terminal_outcome: body.outcome,
    chain_digest,
    receipt_count: String(chain.length),
    registry_roots,
    actor_identity_root: body.actor_identity_root,
    session_identity_root: body.session_identity_root,
    workspace_identity_root: body.workspace_identity_root,
    holon_identity_root: body.holon_identity_root,
    authority_domain: body.authority_domain,
    authority_level: body.authority_level,
    authority_receipt_hash: body.authority_receipt_hash,
    lease_id: body.lease_id,
    lease_generation: body.lease_generation,
    fencing_token: body.fencing_token,
    lease_authorization_receipt_hash: body.lease_authorization_receipt_hash,
    action_digest: body.action_digest,
    before_state_root: body.before_state_root,
    after_state_root: body.after_state_root,
    result_digest: body.result_digest,
    observed_at_ms: trusted.observed_at_ms,
    max_clock_skew_ms: trusted.max_clock_skew_ms,
    grants_authority: false as const,
    executes_mutation: false as const,
  })
  assertIJsonValue(unsigned, 'receipt verification decision')
  const decision_digest = await sha256Hex(canonicalizeJCS({
    domain: VERIFICATION_DECISION_DOMAIN,
    decision: unsigned,
  }))
  return deepFreeze({ ...unsigned, decision_digest })
}

export function normalizeCrossRuntimeReceiptVerificationDecisionV1(
  value: unknown,
): CrossRuntimeReceiptVerificationDecisionV1 {
  const snapshot = snapshotIJson(value, 'cross-runtime receipt verification decision')
  const decision = asObject('receipt verification decision', snapshot)
  assertExactKeys('receipt verification decision', decision, [
    'action_digest',
    'actor_identity_root',
    'after_state_root',
    'authority_domain',
    'authority_level',
    'authority_receipt_hash',
    'before_state_root',
    'chain_digest',
    'decision',
    'decision_digest',
    'decision_kind',
    'executes_mutation',
    'fencing_token',
    'grants_authority',
    'holon_identity_root',
    'lease_authorization_receipt_hash',
    'lease_generation',
    'lease_id',
    'max_clock_skew_ms',
    'observed_at_ms',
    'receipt_count',
    'registry_roots',
    'result_digest',
    'schema_version',
    'session_identity_root',
    'terminal_outcome',
    'terminal_receipt_id',
    'terminal_receipt_kind',
    'workspace_identity_root',
  ])
  if (decision.schema_version !== CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION ||
      decision.decision_kind !== 'AEGIS_CROSS_RUNTIME_RECEIPT_VERIFICATION_DECISION_V1' ||
      decision.decision !== 'VERIFIED') {
    fail('receipt verification decision schema or kind is unsupported')
  }
  if (decision.grants_authority !== false || decision.executes_mutation !== false) {
    fail('receipt verification decision must remain non-authoritative')
  }
  const terminalKind = assertDecisionReceiptKind(decision.terminal_receipt_kind)
  if (!isTerminalKind(terminalKind)) fail('receipt verification decision does not reference terminal evidence')
  const terminalOutcome = assertDecisionOutcome(decision.terminal_outcome)
  assertTerminalKindOutcome(terminalKind, terminalOutcome)
  const registryRoots = asArray('receipt verification decision.registry_roots', decision.registry_roots)
    .map((root, index) => assertNonZeroHash(`receipt verification decision.registry_roots[${index}]`, root))
  if (registryRoots.length === 0 || new Set(registryRoots).size !== registryRoots.length) {
    fail('receipt verification decision registry roots must be non-empty and unique')
  }
  assertSortedUtf8('receipt verification decision.registry_roots', registryRoots)
  const authorityLevel = decision.authority_level
  if (!['D0', 'D1', 'D2', 'D3', 'D4'].includes(String(authorityLevel))) {
    fail('receipt verification decision authority level is invalid')
  }
  const receiptCount = assertDecimal('receipt verification decision.receipt_count', decision.receipt_count)
  if (BigInt(receiptCount) < 1n) fail('receipt verification decision receipt count must be positive')
  const maxClockSkew = assertDecimal(
    'receipt verification decision.max_clock_skew_ms', decision.max_clock_skew_ms,
  )
  if (BigInt(maxClockSkew) > MAX_CLOCK_SKEW_MS) {
    fail('receipt verification decision clock skew exceeds the fail-closed bound')
  }
  return deepFreeze({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    decision_kind: 'AEGIS_CROSS_RUNTIME_RECEIPT_VERIFICATION_DECISION_V1',
    decision: 'VERIFIED',
    terminal_receipt_id: assertNonZeroHash(
      'receipt verification decision.terminal_receipt_id', decision.terminal_receipt_id,
    ),
    terminal_receipt_kind: terminalKind,
    terminal_outcome: terminalOutcome,
    chain_digest: assertNonZeroHash('receipt verification decision.chain_digest', decision.chain_digest),
    receipt_count: receiptCount,
    registry_roots: registryRoots,
    actor_identity_root: assertNonZeroHash(
      'receipt verification decision.actor_identity_root', decision.actor_identity_root,
    ),
    session_identity_root: assertNonZeroHash(
      'receipt verification decision.session_identity_root', decision.session_identity_root,
    ),
    workspace_identity_root: assertNonZeroHash(
      'receipt verification decision.workspace_identity_root', decision.workspace_identity_root,
    ),
    holon_identity_root: assertNonZeroHash(
      'receipt verification decision.holon_identity_root', decision.holon_identity_root,
    ),
    authority_domain: assertSafeId(
      'receipt verification decision.authority_domain', decision.authority_domain,
    ),
    authority_level: authorityLevel as AuthorityLevelV1,
    authority_receipt_hash: assertNonZeroHash(
      'receipt verification decision.authority_receipt_hash', decision.authority_receipt_hash,
    ),
    lease_id: assertNonZeroHash('receipt verification decision.lease_id', decision.lease_id),
    lease_generation: assertDecimal(
      'receipt verification decision.lease_generation', decision.lease_generation,
    ),
    fencing_token: assertNonZeroHash(
      'receipt verification decision.fencing_token', decision.fencing_token,
    ),
    lease_authorization_receipt_hash: assertNonZeroHash(
      'receipt verification decision.lease_authorization_receipt_hash',
      decision.lease_authorization_receipt_hash,
    ),
    action_digest: assertNonZeroHash(
      'receipt verification decision.action_digest', decision.action_digest,
    ),
    before_state_root: assertNonZeroHash(
      'receipt verification decision.before_state_root', decision.before_state_root,
    ),
    after_state_root: assertNonZeroHash(
      'receipt verification decision.after_state_root', decision.after_state_root,
    ),
    result_digest: assertNonZeroHash(
      'receipt verification decision.result_digest', decision.result_digest,
    ),
    observed_at_ms: assertDecimal(
      'receipt verification decision.observed_at_ms', decision.observed_at_ms,
    ),
    max_clock_skew_ms: maxClockSkew,
    grants_authority: false,
    executes_mutation: false,
    decision_digest: assertNonZeroHash(
      'receipt verification decision.decision_digest', decision.decision_digest,
    ),
  })
}

export async function verifyCrossRuntimeReceiptVerificationDecisionDigestV1(
  value: unknown,
): Promise<CrossRuntimeReceiptVerificationDecisionV1> {
  const decision = normalizeCrossRuntimeReceiptVerificationDecisionV1(value)
  const { decision_digest: _decisionDigest, ...unsigned } = decision
  const expected = await sha256Hex(canonicalizeJCS({
    domain: VERIFICATION_DECISION_DOMAIN,
    decision: unsigned,
  }))
  if (decision.decision_digest !== expected) fail('receipt verification decision digest is invalid')
  return decision
}

async function verifyReceiptAgainstRegistry(
  receipt: CrossRuntimeReceiptEnvelopeV1,
  source: CrossRuntimeReceiptSourceV1,
  trusted: NormalizedResolutionContext,
  cache: Map<SHA256Hex, VerifiedRegistryCacheEntry>,
): Promise<VerifiedRegistryCacheEntry> {
  let cached = cache.get(receipt.proof.trust_registry_root)
  if (cached === undefined) {
    const raw = await source.resolveTrustRegistry(receipt.proof.trust_registry_root)
    if (raw === null) fail(`receipt trust registry ${receipt.proof.trust_registry_root} cannot be resolved`)
    const verified = await verifyReceiptTrustRegistryWithNormalizedContextV1(raw, trusted)
    const ancestryRoots = await verifyRegistryAncestry(verified.registry, source, trusted)
    cached = { verified, ancestryRoots }
    cache.set(receipt.proof.trust_registry_root, cached)
  }
  const registry = cached.verified.registry
  if (receipt.proof.trust_registry_version !== registry.registry_body.registry_version) {
    fail('receipt trust registry version does not match its content root')
  }
  const key = registry.registry_body.keys.find(entry => entry.key_id === receipt.proof.signer_key_id)
  if (key === undefined) fail('receipt signer key is absent from the trusted registry')
  assertReceiptKeyPermission(receipt, registry, key)
  const { signature: _signature, ...proof } = receipt.proof
  const valid = await verifyBytes(
    key.public_key,
    canonicalizeCrossRuntimeReceiptSignatureMessageV1({
      schema_version: receipt.schema_version,
      receipt_kind: receipt.receipt_kind,
      receipt_body: receipt.receipt_body,
      proof,
    }),
    receipt.proof.signature,
  )
  if (!valid) fail(`receipt ${receipt.receipt_id} signature is invalid`)
  const timestamp = BigInt(receipt.receipt_body.timestamp_ms)
  if (timestamp > trusted.observedAt + trusted.maxClockSkew) {
    fail(`receipt ${receipt.receipt_id} timestamp exceeds the allowed clock skew`)
  }
  return cached
}

async function verifyRegistryAncestry(
  registry: ReceiptTrustRegistryV1,
  source: CrossRuntimeReceiptSourceV1,
  trusted: NormalizedResolutionContext,
): Promise<ReadonlySet<SHA256Hex>> {
  let current = registry
  const seen = new Set<SHA256Hex>([current.registry_root])
  for (let depth = 0; depth < 128; depth += 1) {
    const version = BigInt(current.registry_body.registry_version)
    if (version === 1n) {
      if (current.registry_body.previous_registry_root !== ZERO_HASH) {
        fail('registry lineage genesis root is broken')
      }
      return seen
    }
    const parentRoot = current.registry_body.previous_registry_root
    if (parentRoot === ZERO_HASH || seen.has(parentRoot)) fail('registry lineage is broken or cyclic')
    seen.add(parentRoot)
    const raw = await source.resolveTrustRegistry(parentRoot)
    if (raw === null) fail(`previous receipt trust registry ${parentRoot} cannot be resolved`)
    const accepted = [...new Set([...trusted.accepted_registry_roots, parentRoot])]
      .sort(compareUtf8) as SHA256Hex[]
    const parent = await verifyReceiptTrustRegistryWithNormalizedContextV1(raw, {
      ...trusted,
      accepted_registry_roots: accepted,
    })
    if (BigInt(parent.registry.registry_body.registry_version) !== version - 1n) {
      fail('registry lineage version is not contiguous')
    }
    current = parent.registry
  }
  fail('registry lineage exceeds the replay bound')
}

function assertReceiptKeyPermission(
  receipt: CrossRuntimeReceiptEnvelopeV1,
  registry: ReceiptTrustRegistryV1,
  key: ReceiptTrustKeyEntryV1,
): void {
  if (key.status !== 'ACTIVE') fail('receipt signer key is revoked')
  if (key.verifier_identity_root !== receipt.proof.verifier_identity_root) {
    fail('receipt verifier identity does not match the trusted key')
  }
  if (!key.authority_domains.includes(receipt.receipt_body.authority_domain)) {
    fail('receipt signer key is not permitted for the authority domain')
  }
  if (!key.receipt_kinds.includes(receipt.receipt_kind)) {
    fail('receipt signer key is not permitted for the receipt kind')
  }
  const timestamp = BigInt(receipt.receipt_body.timestamp_ms)
  const registryValidFrom = BigInt(registry.registry_body.valid_from_ms)
  const registryExpiresAt = BigInt(registry.registry_body.expires_at_ms)
  if (timestamp < registryValidFrom || timestamp >= registryExpiresAt) {
    fail('receipt timestamp is outside the trusted registry validity window')
  }
  const keyValidFrom = BigInt(key.valid_from_ms)
  const keyExpiresAt = BigInt(key.expires_at_ms)
  if (timestamp < keyValidFrom || timestamp >= keyExpiresAt) {
    fail('receipt timestamp is outside the signer key validity window')
  }
}

function replayReceiptChain(
  chain: readonly CrossRuntimeReceiptEnvelopeV1[],
): void {
  const activeLeases = new Map<string, ActiveLease>()
  const lastLeaseGeneration = new Map<string, bigint>()
  const usedLeaseIds = new Set<SHA256Hex>()
  const currentState = new Map<string, SHA256Hex>()
  const mutations = new Map<string, MutationState>()
  const actionClaims = new Set<string>()
  const nonces = new Set<string>()
  let previousId = ZERO_HASH
  let previousTimestamp = -1n
  let previousRegistryVersion = -1n
  let previousRegistryRoot: SHA256Hex | null = null

  for (let index = 0; index < chain.length; index += 1) {
    const receipt = chain[index]!
    const body = receipt.receipt_body
    const sequence = BigInt(body.receipt_sequence)
    const timestamp = BigInt(body.timestamp_ms)
    if (sequence !== BigInt(index)) fail('receipt chain sequence is not contiguous from genesis')
    if (body.parent_receipt_hash !== previousId) fail('receipt chain parent hash is broken')
    if (timestamp < previousTimestamp) fail('receipt chain timestamps are not monotonic')
    const registryVersion = BigInt(receipt.proof.trust_registry_version)
    if (registryVersion < previousRegistryVersion) fail('receipt chain rolls back its trust registry version')
    if (registryVersion === previousRegistryVersion && previousRegistryRoot !== null &&
        receipt.proof.trust_registry_root !== previousRegistryRoot) {
      fail('receipt chain changes registry roots without advancing the registry version')
    }
    if (nonces.has(body.nonce)) fail('receipt chain reuses a signed nonce')
    nonces.add(body.nonce)
    previousId = receipt.receipt_id
    previousTimestamp = timestamp
    previousRegistryVersion = registryVersion
    previousRegistryRoot = receipt.proof.trust_registry_root

    const scopeKey = scopeKeyFor(body)
    const knownState = currentState.get(scopeKey)
    if (knownState === undefined &&
        receipt.receipt_kind !== 'LEASE_ISSUED' &&
        receipt.receipt_kind !== 'LEASE_ISSUANCE_DENIED') {
      fail('receipt scope has no initialized canonical state')
    }
    if (knownState !== undefined && body.observed_state_root !== knownState) {
      fail('receipt observed state is stale relative to the replayed workspace state')
    }
    if (body.before_state_root !== body.observed_state_root) {
      fail('receipt before state does not match the observed canonical state')
    }
    if (receipt.receipt_kind !== 'MUTATION_COMPLETED' && body.after_state_root !== body.before_state_root) {
      fail(`${receipt.receipt_kind} must leave the canonical state root unchanged`)
    }
    // A denied first lease attempt attests the presented roots but cannot
    // initialize canonical state. Only successful lease issuance establishes
    // a new replay scope; all later receipts operate on an existing root.
    if (knownState !== undefined || receipt.receipt_kind === 'LEASE_ISSUED') {
      currentState.set(scopeKey, body.after_state_root)
    }

    if (receipt.receipt_kind.startsWith('LEASE_')) {
      if (body.authority_receipt_hash !== ZERO_HASH || body.lease_authorization_receipt_hash !== ZERO_HASH) {
        fail('lease receipt must not manufacture authority or lease-authorization receipt roots')
      }
    } else if (body.authority_receipt_hash === ZERO_HASH ||
               body.lease_authorization_receipt_hash === ZERO_HASH) {
      fail('mutation receipt must resolve authority and lease-authorization receipt roots')
    }

    const active = activeLeases.get(scopeKey)
    switch (receipt.receipt_kind) {
      case 'LEASE_ISSUED': {
        if (active !== undefined) fail('lease issuance conflicts with an active writer')
        if (usedLeaseIds.has(body.lease_id)) fail('lease id is replayed')
        const previousGeneration = lastLeaseGeneration.get(scopeKey) ?? 0n
        if (BigInt(body.lease_generation) !== previousGeneration + 1n) {
          fail('lease generation does not monotonically fence the previous writer')
        }
        if (body.fencing_token === ZERO_HASH) fail('issued lease fencing token is unresolved')
        if (body.observed_state_root !== body.expected_state_root) {
          fail('issued lease expected state is stale')
        }
        const expiresAt = BigInt(body.expires_at_ms)
        if (expiresAt <= timestamp) fail('issued lease is already expired')
        activeLeases.set(scopeKey, { body, receiptId: receipt.receipt_id, expiresAt })
        usedLeaseIds.add(body.lease_id)
        lastLeaseGeneration.set(scopeKey, BigInt(body.lease_generation))
        break
      }
      case 'LEASE_ISSUANCE_DENIED':
        break
      case 'LEASE_RENEWED': {
        if (active === undefined) fail('lease renewal has no active lease')
        assertRenewalBindings(active.body, body)
        if (timestamp >= active.expiresAt) fail('expired lease cannot be renewed')
        const expiresAt = BigInt(body.expires_at_ms)
        if (expiresAt <= active.expiresAt) fail('lease renewal must extend the expiry')
        if (body.observed_state_root !== body.expected_state_root) fail('renewed lease expected state is stale')
        activeLeases.set(scopeKey, { body, receiptId: receipt.receipt_id, expiresAt })
        lastLeaseGeneration.set(scopeKey, BigInt(body.lease_generation))
        break
      }
      case 'LEASE_RENEWAL_DENIED':
        break
      case 'LEASE_EXPIRED': {
        const current = requireActiveLease(active, body, 'lease expiry')
        if (timestamp < current.expiresAt) fail('lease expiry receipt predates the active lease expiry')
        activeLeases.delete(scopeKey)
        break
      }
      case 'LEASE_REVOKED':
        requireActiveLease(active, body, 'lease revocation')
        activeLeases.delete(scopeKey)
        break
      case 'MUTATION_ADMITTED': {
        const current = requireActiveLease(active, body, 'mutation admission')
        if (timestamp >= current.expiresAt) fail('expired lease cannot admit a mutation')
        if (body.observed_state_root !== body.expected_state_root) fail('mutation expected state is stale')
        assertLeaseToMutationBindings(current, body)
        const mutationKey = mutationKeyFor(body)
        const actionKey = actionKeyFor(body)
        if (mutations.has(mutationKey) || actionClaims.has(actionKey)) {
          fail('duplicate or replayed mutation action')
        }
        mutations.set(mutationKey, { admission: receipt, terminal: null })
        actionClaims.add(actionKey)
        break
      }
      case 'MUTATION_DENIED': {
        const mutationKey = mutationKeyFor(body)
        const actionKey = actionKeyFor(body)
        const replayed = mutations.has(mutationKey) || actionClaims.has(actionKey)
        if (replayed && !body.denial_codes.includes('MUTATION_REPLAY')) {
          fail('replayed mutation denial does not attest MUTATION_REPLAY')
        }
        if (!replayed) {
          actionClaims.add(actionKey)
        }
        break
      }
      case 'MUTATION_COMPLETED':
      case 'MUTATION_CANCELLED':
      case 'MUTATION_FAILED': {
        const mutation = mutations.get(mutationKeyFor(body))
        if (mutation === undefined) fail('terminal mutation has no admitted parent action')
        if (mutation.terminal !== null) fail('mutation action has more than one terminal receipt')
        assertMutationAttemptBindings(mutation.admission.receipt_body, body)
        if (receipt.receipt_kind === 'MUTATION_COMPLETED') {
          const current = requireActiveLease(active, body, 'completed mutation')
          if (timestamp >= current.expiresAt) fail('expired lease cannot complete a successful mutation')
          if (body.observed_state_root !== body.expected_state_root) {
            fail('completed mutation expected state is stale')
          }
          activeLeases.delete(scopeKey)
        } else if (active !== undefined) {
          requireActiveLease(active, body, 'terminal mutation')
          activeLeases.delete(scopeKey)
        }
        mutation.terminal = receipt
        break
      }
    }
  }
}

function requireActiveLease(
  active: ActiveLease | undefined,
  body: CrossRuntimeReceiptBodyV1,
  operation: string,
): ActiveLease {
  if (active === undefined) fail(`${operation} has no active lease`)
  const expected = active.body
  if (body.lease_id !== expected.lease_id ||
      body.lease_generation !== expected.lease_generation ||
      body.fencing_token !== expected.fencing_token) {
    fail(`${operation} presents a stale lease or fencing token`)
  }
  assertIdentityAndAuthorityBindings(expected, body, operation)
  return active
}

function assertLeaseToMutationBindings(
  lease: ActiveLease,
  mutation: CrossRuntimeReceiptBodyV1,
): void {
  assertIdentityAndAuthorityBindings(lease.body, mutation, 'lease-to-mutation binding')
  if (lease.body.action_digest !== mutation.action_digest) fail('lease-to-mutation action digest mismatch')
  if (mutation.lease_authorization_receipt_hash !== lease.receiptId) {
    fail('mutation lease authorization does not resolve to the active issued or renewed lease receipt')
  }
}

function assertRenewalBindings(
  current: CrossRuntimeReceiptBodyV1,
  renewal: CrossRuntimeReceiptBodyV1,
): void {
  for (const field of [
    'actor_identity_root',
    'session_identity_root',
    'workspace_identity_root',
    'holon_identity_root',
    'authority_domain',
    'authority_level',
    'lease_id',
    'action_digest',
  ] as const) {
    if (renewal[field] !== current[field]) fail(`lease renewal ${field} mismatch`)
  }
  if (BigInt(renewal.lease_generation) !== BigInt(current.lease_generation) + 1n) {
    fail('lease renewal must advance the lease generation exactly once')
  }
  if (renewal.fencing_token === ZERO_HASH || renewal.fencing_token === current.fencing_token) {
    fail('lease renewal must issue a new non-zero fencing token')
  }
}

function assertMutationAttemptBindings(
  admission: CrossRuntimeReceiptBodyV1,
  terminal: CrossRuntimeReceiptBodyV1,
): void {
  assertIdentityAndAuthorityBindings(admission, terminal, 'mutation terminal binding')
  for (const [actual, expected, label] of [
    [terminal.action_digest, admission.action_digest, 'action digest'],
    [terminal.authority_receipt_hash, admission.authority_receipt_hash, 'authority receipt'],
    [terminal.lease_authorization_receipt_hash, admission.lease_authorization_receipt_hash, 'lease authorization'],
  ] as const) {
    if (actual !== expected) fail(`mutation terminal ${label} mismatch`)
  }
}

function assertIdentityAndAuthorityBindings(
  expected: CrossRuntimeReceiptBodyV1,
  actual: CrossRuntimeReceiptBodyV1,
  label: string,
): void {
  for (const field of [
    'actor_identity_root',
    'session_identity_root',
    'workspace_identity_root',
    'holon_identity_root',
    'authority_domain',
    'authority_level',
    'lease_id',
    'lease_generation',
    'fencing_token',
    'action_digest',
  ] as const) {
    if (actual[field] !== expected[field]) fail(`${label} ${field} mismatch`)
  }
}

function assertTerminalContextBindings(
  body: CrossRuntimeReceiptBodyV1,
  context: NormalizedResolutionContext,
): void {
  const bindings = [
    [body.actor_identity_root, context.expected_actor_identity_root, 'actor identity'],
    [body.session_identity_root, context.expected_session_identity_root, 'session identity'],
    [body.workspace_identity_root, context.expected_workspace_identity_root, 'workspace identity'],
    [body.holon_identity_root, context.expected_holon_identity_root, 'holon identity'],
    [body.authority_domain, context.expected_authority_domain, 'authority domain'],
    [body.authority_level, context.expected_authority_level, 'authority level'],
    [body.observed_state_root, context.expected_observed_state_root, 'observed state'],
    [body.action_digest, context.expected_action_digest, 'action digest'],
  ] as const
  for (const [actual, expected, label] of bindings) {
    if (actual !== expected) fail(`terminal receipt ${label} does not match trusted context`)
  }
}

function mutationKeyFor(body: CrossRuntimeReceiptBodyV1): string {
  return `${actionScopeKeyFor(body)}\u0000${body.lease_id}`
}

function actionKeyFor(body: CrossRuntimeReceiptBodyV1): string {
  return actionScopeKeyFor(body)
}

function scopeKeyFor(body: CrossRuntimeReceiptBodyV1): string {
  return [
    body.workspace_identity_root,
    body.holon_identity_root,
    body.authority_domain,
  ].join('\u0000')
}

function actionScopeKeyFor(body: CrossRuntimeReceiptBodyV1): string {
  return [
    body.actor_identity_root,
    body.session_identity_root,
    body.workspace_identity_root,
    body.holon_identity_root,
    body.authority_domain,
    body.action_digest,
  ].join('\u0000')
}

function isTerminalKind(kind: CrossRuntimeReceiptKindV1): boolean {
  return !['LEASE_ISSUED', 'LEASE_RENEWED', 'MUTATION_ADMITTED'].includes(kind)
}

function assertDecisionReceiptKind(value: unknown): CrossRuntimeReceiptKindV1 {
  const kinds: readonly CrossRuntimeReceiptKindV1[] = [
    'LEASE_ISSUED', 'LEASE_ISSUANCE_DENIED', 'LEASE_RENEWED', 'LEASE_RENEWAL_DENIED',
    'LEASE_EXPIRED', 'LEASE_REVOKED', 'MUTATION_ADMITTED', 'MUTATION_DENIED',
    'MUTATION_COMPLETED', 'MUTATION_CANCELLED', 'MUTATION_FAILED',
  ]
  if (typeof value !== 'string' || !kinds.includes(value as CrossRuntimeReceiptKindV1)) {
    fail('receipt verification decision terminal kind is invalid')
  }
  return value as CrossRuntimeReceiptKindV1
}

function assertDecisionOutcome(value: unknown): CrossRuntimeReceiptOutcomeV1 {
  const outcomes: readonly CrossRuntimeReceiptOutcomeV1[] = [
    'ADMITTED', 'DENIED', 'COMPLETED', 'CANCELLED', 'FAILED', 'EXPIRED', 'REVOKED',
  ]
  if (typeof value !== 'string' || !outcomes.includes(value as CrossRuntimeReceiptOutcomeV1)) {
    fail('receipt verification decision terminal outcome is invalid')
  }
  return value as CrossRuntimeReceiptOutcomeV1
}

function assertTerminalKindOutcome(
  kind: CrossRuntimeReceiptKindV1,
  outcome: CrossRuntimeReceiptOutcomeV1,
): void {
  const expected: Readonly<Record<CrossRuntimeReceiptKindV1, CrossRuntimeReceiptOutcomeV1>> = {
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
  if (outcome !== expected[kind]) fail('receipt verification decision terminal kind/outcome mismatch')
}

function normalizeResolutionContext(value: TrustedReceiptResolutionContextV1): NormalizedResolutionContext {
  const snapshot = snapshotIJson(value, 'trusted receipt resolution context')
  const context = asObject('trusted receipt resolution context', snapshot)
  assertExactKeys('trusted receipt resolution context', context, [
    'accepted_registry_roots',
    'expected_action_digest',
    'expected_actor_identity_root',
    'expected_authority_domain',
    'expected_authority_level',
    'expected_holon_identity_root',
    'expected_observed_state_root',
    'expected_session_identity_root',
    'expected_workspace_identity_root',
    'max_clock_skew_ms',
    'observed_at_ms',
    'operator_key_id',
    'operator_public_key',
  ])
  const roots = asArray('accepted_registry_roots', context.accepted_registry_roots)
    .map((root, index) => assertNonZeroHash(`accepted_registry_roots[${index}]`, root))
  if (roots.length === 0 || new Set(roots).size !== roots.length) {
    fail('accepted_registry_roots must be non-empty and unique')
  }
  assertSortedUtf8('accepted_registry_roots', roots)
  const observed_at_ms = assertDecimal('observed_at_ms', context.observed_at_ms)
  const max_clock_skew_ms = assertDecimal('max_clock_skew_ms', context.max_clock_skew_ms)
  const maxClockSkew = BigInt(max_clock_skew_ms)
  if (maxClockSkew > MAX_CLOCK_SKEW_MS) fail('max_clock_skew_ms exceeds the fail-closed bound')
  const authorityLevel = context.expected_authority_level
  if (!['D0', 'D1', 'D2', 'D3', 'D4'].includes(String(authorityLevel))) {
    fail('expected_authority_level is invalid')
  }
  return deepFreeze({
    operator_key_id: assertSafeId('operator_key_id', context.operator_key_id),
    operator_public_key: assertNonZeroHash('operator_public_key', context.operator_public_key),
    accepted_registry_roots: roots,
    observed_at_ms,
    max_clock_skew_ms,
    expected_actor_identity_root: assertNonZeroHash(
      'expected_actor_identity_root', context.expected_actor_identity_root,
    ),
    expected_session_identity_root: assertNonZeroHash(
      'expected_session_identity_root', context.expected_session_identity_root,
    ),
    expected_workspace_identity_root: assertNonZeroHash(
      'expected_workspace_identity_root', context.expected_workspace_identity_root,
    ),
    expected_holon_identity_root: assertNonZeroHash(
      'expected_holon_identity_root', context.expected_holon_identity_root,
    ),
    expected_authority_domain: assertSafeId(
      'expected_authority_domain', context.expected_authority_domain,
    ),
    expected_authority_level: authorityLevel as AuthorityLevelV1,
    expected_observed_state_root: assertNonZeroHash(
      'expected_observed_state_root', context.expected_observed_state_root,
    ),
    expected_action_digest: assertNonZeroHash(
      'expected_action_digest', context.expected_action_digest,
    ),
    observedAt: BigInt(observed_at_ms),
    maxClockSkew,
  })
}

function assertSource(source: CrossRuntimeReceiptSourceV1): void {
  if (source === null || typeof source !== 'object' ||
      typeof source.resolveReceipt !== 'function' ||
      typeof source.resolveTrustRegistry !== 'function') {
    fail('cross-runtime receipt source is unavailable')
  }
}

function snapshotIJson(value: unknown, label: string): unknown {
  try {
    assertIJsonValue(value, label)
    const snapshot = structuredClone(value) as unknown
    assertIJsonValue(snapshot, label)
    return snapshot
  } catch (error) {
    fail(`${label} is not closed I-JSON: ${error instanceof Error ? error.message : String(error)}`)
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

function assertExactKeys(field: string, value: Record<string, unknown>, expected: readonly string[]): void {
  const actualKeys = Object.keys(value).sort(compareUtf8)
  const expectedKeys = [...expected].sort(compareUtf8)
  if (actualKeys.length !== expectedKeys.length ||
      actualKeys.some((key, index) => key !== expectedKeys[index])) {
    fail(`${field} has unexpected or missing fields`)
  }
}

function assertNonZeroHash(field: string, value: unknown): SHA256Hex {
  if (typeof value !== 'string' || !HASH_PATTERN.test(value) || value === ZERO_HASH) {
    fail(`${field} must be a non-zero lowercase SHA-256 root`)
  }
  return value as SHA256Hex
}

function assertDecimal(field: string, value: unknown): DecimalStringV1 {
  if (typeof value !== 'string' || value.length > 20 || !DECIMAL_PATTERN.test(value)) {
    fail(`${field} must be a canonical decimal string of at most 20 digits`)
  }
  return value
}

function assertSafeId(field: string, value: unknown): string {
  if (typeof value !== 'string' || !SAFE_ID_PATTERN.test(value)) fail(`${field} is invalid`)
  return value
}

function assertSortedUtf8(field: string, values: readonly string[]): void {
  for (let index = 1; index < values.length; index += 1) {
    if (compareUtf8(values[index - 1]!, values[index]!) >= 0) fail(`${field} must be UTF-8 sorted`)
  }
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

function fail(message: string): never {
  throw new CrossRuntimeReceiptResolutionError(message)
}
