import 'fake-indexeddb/auto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { canonicalizeJCS } from '../../src/core/canonicalize.js'
import type { SHA256Hex } from '../../src/core/types.js'
import { generateKeypair } from '../../src/consensus/crypto.js'
import {
  CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
  buildCrossRuntimeReceiptEnvelopeV1,
  buildReceiptTrustRegistryV1,
  deriveCrossRuntimeReceiptIdV1,
  normalizeCrossRuntimeReceiptEnvelopeV1,
  type CrossRuntimeReceiptBodyV1,
  type CrossRuntimeReceiptDraftV1,
  type CrossRuntimeReceiptEnvelopeV1,
  type CrossRuntimeReceiptKindV1,
  type ReceiptTrustRegistryV1,
} from '../../src/provenance/cross-runtime-receipts.js'
import {
  resolveAndVerifyCrossRuntimeReceiptChainV1,
  verifyCrossRuntimeReceiptVerificationDecisionDigestV1,
  type CrossRuntimeReceiptSourceV1,
  type TrustedReceiptResolutionContextV1,
} from '../../src/provenance/receipt-resolver.js'
import { IndexedDBCrossRuntimeReceiptSourceV1 } from '../../src/provenance/indexeddb-receipt-source.js'
import { buildTypeScriptCrossRuntimeVectorV1 } from '../../scripts/generate-authoritative-receipt-vector.js'

const H = (digit: string): SHA256Hex => digit.repeat(64) as SHA256Hex
const ZERO = H('0')
const ALL_KINDS: readonly CrossRuntimeReceiptKindV1[] = [
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

interface Fixture {
  readonly operatorPrivateKey: Uint8Array
  readonly receiptPrivateKey: Uint8Array
  readonly registry: ReceiptTrustRegistryV1
  readonly receipts: readonly [
    CrossRuntimeReceiptEnvelopeV1,
    CrossRuntimeReceiptEnvelopeV1,
    CrossRuntimeReceiptEnvelopeV1,
  ]
  readonly context: TrustedReceiptResolutionContextV1
}

class MemorySource implements CrossRuntimeReceiptSourceV1 {
  readonly receipts = new Map<string, unknown>()
  readonly registries = new Map<string, unknown>()

  resolveReceipt(receiptId: SHA256Hex): Promise<unknown | null> {
    return Promise.resolve(this.receipts.get(receiptId) ?? null)
  }

  resolveTrustRegistry(registryRoot: SHA256Hex): Promise<unknown | null> {
    return Promise.resolve(this.registries.get(registryRoot) ?? null)
  }
}

async function fixture(): Promise<Fixture> {
  const operator = await generateKeypair(new Uint8Array(32).fill(1))
  const receiptSigner = await generateKeypair(new Uint8Array(32).fill(2))
  const verifierIdentity = H('e')
  const registry = await buildReceiptTrustRegistryV1({
    registry_version: '1',
    previous_registry_root: ZERO,
    issued_at_ms: '500',
    valid_from_ms: '1000',
    expires_at_ms: '100000',
    operator_key_id: 'operator-key-1',
    keys: [{
      key_id: 'receipt-key-1',
      public_key: receiptSigner.publicKey,
      verifier_identity_root: verifierIdentity,
      valid_from_ms: '1000',
      expires_at_ms: '100000',
      status: 'ACTIVE',
      authority_domains: ['repo/main'],
      receipt_kinds: ALL_KINDS,
    }],
  }, operator.privateKey)
  const proof: CrossRuntimeReceiptDraftV1['proof'] = {
    algorithm: 'Ed25519',
    signer_key_id: 'receipt-key-1',
    verifier_identity_root: verifierIdentity,
    trust_registry_version: '1',
    trust_registry_root: registry.registry_root,
  }
  const issuedBody = body({
    receipt_sequence: '0',
    parent_receipt_hash: ZERO,
    timestamp_ms: '2000',
    expires_at_ms: '4500',
    nonce: 'nonce-receipt-0001',
    authority_receipt_hash: ZERO,
    lease_authorization_receipt_hash: ZERO,
  })
  const issued = await buildCrossRuntimeReceiptEnvelopeV1({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    receipt_kind: 'LEASE_ISSUED',
    receipt_body: issuedBody,
    proof,
  }, receiptSigner.privateKey)
  const admittedBody = body({
    receipt_sequence: '1',
    parent_receipt_hash: issued.receipt_id,
    timestamp_ms: '3000',
    expires_at_ms: '4500',
    nonce: 'nonce-receipt-0002',
    authority_receipt_hash: H('a'),
    lease_authorization_receipt_hash: issued.receipt_id,
  })
  const admitted = await buildCrossRuntimeReceiptEnvelopeV1({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    receipt_kind: 'MUTATION_ADMITTED',
    receipt_body: admittedBody,
    proof,
  }, receiptSigner.privateKey)
  const completedBody = body({
    receipt_sequence: '2',
    parent_receipt_hash: admitted.receipt_id,
    timestamp_ms: '4000',
    expires_at_ms: '4500',
    nonce: 'nonce-receipt-0003',
    authority_receipt_hash: H('a'),
    lease_authorization_receipt_hash: issued.receipt_id,
    after_state_root: H('c'),
    result_digest: H('d'),
    outcome: 'COMPLETED',
  })
  const completed = await buildCrossRuntimeReceiptEnvelopeV1({
    schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
    receipt_kind: 'MUTATION_COMPLETED',
    receipt_body: completedBody,
    proof,
  }, receiptSigner.privateKey)
  return {
    operatorPrivateKey: operator.privateKey,
    receiptPrivateKey: receiptSigner.privateKey,
    registry,
    receipts: [issued, admitted, completed],
    context: {
      operator_key_id: 'operator-key-1',
      operator_public_key: operator.publicKey,
      accepted_registry_roots: [registry.registry_root],
      observed_at_ms: '5000',
      max_clock_skew_ms: '100',
      expected_actor_identity_root: H('1'),
      expected_session_identity_root: H('2'),
      expected_workspace_identity_root: H('3'),
      expected_holon_identity_root: H('4'),
      expected_authority_domain: 'repo/main',
      expected_authority_level: 'D2',
      expected_observed_state_root: H('7'),
      expected_action_digest: H('8'),
    },
  }
}

function body(overrides: Partial<CrossRuntimeReceiptBodyV1> = {}): CrossRuntimeReceiptBodyV1 {
  return {
    receipt_sequence: '0',
    actor_identity_root: H('1'),
    session_identity_root: H('2'),
    workspace_identity_root: H('3'),
    holon_identity_root: H('4'),
    authority_domain: 'repo/main',
    authority_level: 'D2',
    authority_receipt_hash: ZERO,
    lease_id: H('5'),
    lease_generation: '1',
    fencing_token: H('6'),
    lease_authorization_receipt_hash: ZERO,
    parent_receipt_hash: ZERO,
    observed_state_root: H('7'),
    expected_state_root: H('7'),
    action_digest: H('8'),
    before_state_root: H('7'),
    after_state_root: H('7'),
    result_digest: H('9'),
    timestamp_ms: '2000',
    expires_at_ms: '9000',
    nonce: 'nonce-receipt-0001',
    outcome: 'ADMITTED',
    denial_codes: [],
    ...overrides,
  }
}

function memorySource(value: Fixture): MemorySource {
  const source = new MemorySource()
  source.registries.set(value.registry.registry_root, value.registry)
  for (const receipt of value.receipts) source.receipts.set(receipt.receipt_id, receipt)
  return source
}

async function rebuild(
  original: CrossRuntimeReceiptEnvelopeV1,
  privateKey: Uint8Array,
  updates: {
    readonly kind?: CrossRuntimeReceiptKindV1
    readonly body?: Partial<CrossRuntimeReceiptBodyV1>
  },
): Promise<CrossRuntimeReceiptEnvelopeV1> {
  const { signature: _signature, ...proof } = original.proof
  return buildCrossRuntimeReceiptEnvelopeV1({
    schema_version: original.schema_version,
    receipt_kind: updates.kind ?? original.receipt_kind,
    receipt_body: { ...original.receipt_body, ...updates.body },
    proof,
  }, privateKey)
}

async function rebuildUnderRegistry(
  original: CrossRuntimeReceiptEnvelopeV1,
  registry: ReceiptTrustRegistryV1,
  privateKey: Uint8Array,
  updates: {
    readonly kind?: CrossRuntimeReceiptKindV1
    readonly body?: Partial<CrossRuntimeReceiptBodyV1>
  } = {},
): Promise<CrossRuntimeReceiptEnvelopeV1> {
  const { signature: _signature, ...proof } = original.proof
  return buildCrossRuntimeReceiptEnvelopeV1({
    schema_version: original.schema_version,
    receipt_kind: updates.kind ?? original.receipt_kind,
    receipt_body: { ...original.receipt_body, ...updates.body },
    proof: {
      ...proof,
      trust_registry_version: registry.registry_body.registry_version,
      trust_registry_root: registry.registry_root,
    },
  }, privateKey)
}

describe('cross-runtime authoritative receipt provenance', () => {
  it('builds, independently verifies, and round-trips a deterministic success decision', async () => {
    const value = await fixture()
    const source = memorySource(value)
    const decision = await resolveAndVerifyCrossRuntimeReceiptChainV1(
      source, value.receipts[2].receipt_id, value.context,
    )
    expect(decision.decision).toBe('VERIFIED')
    expect(decision.receipt_count).toBe('3')
    expect(decision.authority_receipt_hash).toBe(H('a'))
    expect(decision.lease_authorization_receipt_hash).toBe(value.receipts[0].receipt_id)
    expect(decision.before_state_root).toBe(H('7'))
    expect(decision.after_state_root).toBe(H('c'))
    expect(decision.result_digest).toBe(H('d'))
    expect(decision.grants_authority).toBe(false)
    expect(decision.executes_mutation).toBe(false)
    await expect(verifyCrossRuntimeReceiptVerificationDecisionDigestV1(
      JSON.parse(JSON.stringify(decision)),
    )).resolves.toEqual(decision)
    await expect(verifyCrossRuntimeReceiptVerificationDecisionDigestV1({
      ...decision,
      result_digest: H('f'),
    })).rejects.toThrow('decision digest is invalid')
  })

  it('rejects non-I-JSON values, schema drift, and noncanonical signed arrays', async () => {
    const value = await fixture()
    expect(() => normalizeCrossRuntimeReceiptEnvelopeV1({
      ...value.receipts[0],
      unsigned_extension: true,
    })).toThrow('unexpected or missing fields')
    expect(() => normalizeCrossRuntimeReceiptEnvelopeV1({
      ...value.receipts[0],
      receipt_body: { ...value.receipts[0].receipt_body, denial_codes: undefined },
    })).toThrow('closed I-JSON')
    const denied = {
      ...value.receipts[0],
      receipt_kind: 'LEASE_ISSUANCE_DENIED',
      receipt_body: {
        ...value.receipts[0].receipt_body,
        outcome: 'DENIED',
        denial_codes: ['Z_REASON', 'A_REASON'],
      },
    }
    expect(() => normalizeCrossRuntimeReceiptEnvelopeV1(denied)).toThrow('strictly sorted')
    await expect(rebuild(value.receipts[1], value.receiptPrivateKey, {
      body: { fencing_token: ZERO },
    })).rejects.toThrow('fencing_token must be resolved')
    await expect(rebuild(value.receipts[0], value.receiptPrivateKey, {
      body: { authority_receipt_hash: H('a') },
    })).rejects.toThrow('must not carry mutation authority')
  })

  it('rejects signature tampering even when the attacker recomputes the content id', async () => {
    const value = await fixture()
    const terminal = value.receipts[2]
    const { receipt_id: _receiptId, ...signed } = terminal
    const signature = terminal.proof.signature
    const tamperedSigned = {
      ...signed,
      proof: {
        ...signed.proof,
        signature: `${signature[0] === '0' ? '1' : '0'}${signature.slice(1)}`,
      },
    }
    const tampered = normalizeCrossRuntimeReceiptEnvelopeV1({
      ...tamperedSigned,
      receipt_id: await deriveCrossRuntimeReceiptIdV1(tamperedSigned),
    })
    const source = memorySource(value)
    source.receipts.set(tampered.receipt_id, tampered)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      source, tampered.receipt_id, value.context,
    )).rejects.toThrow('signature is invalid')
  })

  it.each([
    ['stale fence', { fencing_token: H('f') }, 'stale lease or fencing token'],
    ['expired lease', { timestamp_ms: '4500' }, 'expired lease cannot admit'],
    ['stale expected state', { expected_state_root: H('f') }, 'expected state is stale'],
  ] as const)('rejects a signed %s mutation admission', async (_label, updates, message) => {
    const value = await fixture()
    const admitted = await rebuild(value.receipts[1], value.receiptPrivateKey, { body: updates })
    const source = new MemorySource()
    source.registries.set(value.registry.registry_root, value.registry)
    source.receipts.set(value.receipts[0].receipt_id, value.receipts[0])
    source.receipts.set(admitted.receipt_id, admitted)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      source, admitted.receipt_id, value.context,
    )).rejects.toThrow(message)
  })

  it('rejects broken parents, unknown trust roots, and future receipts', async () => {
    const value = await fixture()
    const broken = await rebuild(value.receipts[2], value.receiptPrivateKey, {
      body: { parent_receipt_hash: H('f') },
    })
    const brokenSource = memorySource(value)
    brokenSource.receipts.set(broken.receipt_id, broken)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      brokenSource, broken.receipt_id, value.context,
    )).rejects.toThrow('cannot be resolved')

    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      memorySource(value),
      value.receipts[2].receipt_id,
      { ...value.context, accepted_registry_roots: [H('f')] },
    )).rejects.toThrow('not explicitly accepted')

    const future = await rebuild(value.receipts[2], value.receiptPrivateKey, {
      body: { timestamp_ms: '5200' },
    })
    const futureSource = memorySource(value)
    futureSource.receipts.set(future.receipt_id, future)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      futureSource, future.receipt_id, value.context,
    )).rejects.toThrow('clock skew')
  })

  it('verifies a terminal denial and proves the canonical state root is unchanged', async () => {
    const value = await fixture()
    const denied = await rebuild(value.receipts[1], value.receiptPrivateKey, {
      kind: 'MUTATION_DENIED',
      body: {
        outcome: 'DENIED',
        denial_codes: ['STALE_EXPECTED_STATE'],
        expected_state_root: H('f'),
        after_state_root: H('7'),
      },
    })
    const source = new MemorySource()
    source.registries.set(value.registry.registry_root, value.registry)
    source.receipts.set(value.receipts[0].receipt_id, value.receipts[0])
    source.receipts.set(denied.receipt_id, denied)
    const decision = await resolveAndVerifyCrossRuntimeReceiptChainV1(
      source, denied.receipt_id, value.context,
    )
    expect(decision.terminal_outcome).toBe('DENIED')
    expect(decision.before_state_root).toBe(H('7'))
    expect(decision.after_state_root).toBe(H('7'))
  })

  it('verifies and restart-resolves a signed replay denial without admitting a second mutation', async () => {
    const value = await fixture()
    const replayDenied = await rebuild(value.receipts[2], value.receiptPrivateKey, {
      kind: 'MUTATION_DENIED',
      body: {
        receipt_sequence: '3',
        parent_receipt_hash: value.receipts[2].receipt_id,
        observed_state_root: H('c'),
        expected_state_root: H('c'),
        before_state_root: H('c'),
        after_state_root: H('c'),
        timestamp_ms: '4100',
        nonce: 'nonce-replay-denied1',
        outcome: 'DENIED',
        denial_codes: ['MUTATION_REPLAY'],
      },
    })
    const context = {
      ...value.context,
      expected_observed_state_root: H('c'),
    }
    const source = memorySource(value)
    source.receipts.set(replayDenied.receipt_id, replayDenied)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      source,
      replayDenied.receipt_id,
      context,
    )).resolves.toMatchObject({
      terminal_receipt_kind: 'MUTATION_DENIED',
      before_state_root: H('c'),
      after_state_root: H('c'),
    })

    const databaseName = `receipt-replay-${crypto.randomUUID()}`
    const store = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await store.open()
    await store.persistBatch([value.registry], [...value.receipts, replayDenied])
    store.close()
    const reopened = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await reopened.open()
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      reopened,
      replayDenied.receipt_id,
      context,
    )).resolves.toMatchObject({ terminal_receipt_kind: 'MUTATION_DENIED' })
    reopened.close()
  })

  it('rejects reuse of a previously issued lease id after the original lease closes', async () => {
    const value = await fixture()
    const reused = await rebuild(value.receipts[2], value.receiptPrivateKey, {
      kind: 'LEASE_ISSUED',
      body: {
        receipt_sequence: '3',
        parent_receipt_hash: value.receipts[2].receipt_id,
        observed_state_root: H('c'),
        expected_state_root: H('c'),
        before_state_root: H('c'),
        after_state_root: H('c'),
        action_digest: H('f'),
        lease_generation: '2',
        fencing_token: H('f'),
        authority_receipt_hash: ZERO,
        lease_authorization_receipt_hash: ZERO,
        timestamp_ms: '4100',
        expires_at_ms: '6000',
        nonce: 'nonce-lease-reuse-01',
        outcome: 'ADMITTED',
        denial_codes: [],
      },
    })
    const revoked = await rebuild(reused, value.receiptPrivateKey, {
      kind: 'LEASE_REVOKED',
      body: {
        receipt_sequence: '4',
        parent_receipt_hash: reused.receipt_id,
        timestamp_ms: '4200',
        nonce: 'nonce-lease-reuse-r1',
        outcome: 'REVOKED',
        denial_codes: ['LEASE_REVOKED'],
      },
    })
    const source = memorySource(value)
    source.receipts.set(reused.receipt_id, reused)
    source.receipts.set(revoked.receipt_id, revoked)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      source,
      revoked.receipt_id,
      {
        ...value.context,
        expected_observed_state_root: H('c'),
        expected_action_digest: H('f'),
      },
    )).rejects.toThrow('lease id is replayed')
  })

  it('rejects cancellation that presents a stale fence after lease renewal', async () => {
    const value = await fixture()
    const renewed = await rebuild(value.receipts[1], value.receiptPrivateKey, {
      kind: 'LEASE_RENEWED',
      body: {
        receipt_sequence: '2',
        parent_receipt_hash: value.receipts[1].receipt_id,
        lease_generation: '2',
        fencing_token: H('f'),
        authority_receipt_hash: ZERO,
        lease_authorization_receipt_hash: ZERO,
        timestamp_ms: '3500',
        expires_at_ms: '5500',
        nonce: 'nonce-renew-before-c1',
      },
    })
    const cancelled = await rebuild(value.receipts[1], value.receiptPrivateKey, {
      kind: 'MUTATION_CANCELLED',
      body: {
        receipt_sequence: '3',
        parent_receipt_hash: renewed.receipt_id,
        timestamp_ms: '3600',
        nonce: 'nonce-stale-cancel-1',
        outcome: 'CANCELLED',
        denial_codes: ['MUTATION_CANCELLED'],
      },
    })
    const source = memorySource(value)
    source.receipts.set(renewed.receipt_id, renewed)
    source.receipts.set(cancelled.receipt_id, cancelled)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      source,
      cancelled.receipt_id,
      value.context,
    )).rejects.toThrow('stale lease or fencing token')
  })

  it('does not let a denied genesis lease attempt initialize canonical state', async () => {
    const value = await fixture()
    const { signature: _signature, ...proof } = value.receipts[0].proof
    const denied = await buildCrossRuntimeReceiptEnvelopeV1({
      schema_version: CROSS_RUNTIME_RECEIPT_SCHEMA_VERSION,
      receipt_kind: 'LEASE_ISSUANCE_DENIED',
      receipt_body: body({
        receipt_sequence: '0',
        parent_receipt_hash: ZERO,
        observed_state_root: H('f'),
        expected_state_root: H('f'),
        before_state_root: H('f'),
        after_state_root: H('f'),
        fencing_token: ZERO,
        expires_at_ms: '1999',
        nonce: 'nonce-denied-genesis',
        outcome: 'DENIED',
        denial_codes: ['LEASE_EXPIRY_INVALID'],
      }),
      proof,
    }, value.receiptPrivateKey)
    const issued = await rebuild(value.receipts[0], value.receiptPrivateKey, {
      body: {
        receipt_sequence: '1',
        parent_receipt_hash: denied.receipt_id,
        nonce: 'nonce-issued-after-denial',
      },
    })
    const revoked = await rebuild(issued, value.receiptPrivateKey, {
      kind: 'LEASE_REVOKED',
      body: {
        receipt_sequence: '2',
        parent_receipt_hash: issued.receipt_id,
        timestamp_ms: '3000',
        nonce: 'nonce-revoke-after-denial',
        outcome: 'REVOKED',
        denial_codes: ['OPERATOR_REVOKED'],
      },
    })
    const source = new MemorySource()
    source.registries.set(value.registry.registry_root, value.registry)
    for (const receipt of [denied, issued, revoked]) {
      source.receipts.set(receipt.receipt_id, receipt)
    }

    const decision = await resolveAndVerifyCrossRuntimeReceiptChainV1(
      source,
      revoked.receipt_id,
      value.context,
    )
    expect(decision.before_state_root).toBe(H('7'))
    expect(decision.after_state_root).toBe(H('7'))
  })

  it.each([
    ['expiry', 'LEASE_EXPIRED', 'EXPIRED', 'MUTATION_CANCELLED', 'CANCELLED'],
    ['revocation', 'LEASE_REVOKED', 'REVOKED', 'MUTATION_FAILED', 'FAILED'],
  ] as const)(
    'allows a %s receipt to be followed by a resolvable mutation terminal receipt',
    async (_label, leaseKind, leaseOutcome, terminalKind, terminalOutcome) => {
      const value = await fixture()
      const leaseTerminal = await rebuild(value.receipts[2], value.receiptPrivateKey, {
        kind: leaseKind,
        body: {
          parent_receipt_hash: value.receipts[1].receipt_id,
          timestamp_ms: leaseKind === 'LEASE_EXPIRED' ? '4500' : '3500',
          authority_receipt_hash: ZERO,
          lease_authorization_receipt_hash: ZERO,
          after_state_root: H('7'),
          outcome: leaseOutcome,
          denial_codes: [leaseKind === 'LEASE_EXPIRED' ? 'LEASE_WINDOW_ELAPSED' : 'LEASE_REVOKED_BY_POLICY'],
          nonce: 'nonce-receipt-0003',
        },
      })
      const mutationTerminal = await rebuild(value.receipts[2], value.receiptPrivateKey, {
        kind: terminalKind,
        body: {
          receipt_sequence: '3',
          parent_receipt_hash: leaseTerminal.receipt_id,
          timestamp_ms: leaseKind === 'LEASE_EXPIRED' ? '4600' : '3600',
          after_state_root: H('7'),
          outcome: terminalOutcome,
          denial_codes: [terminalKind === 'MUTATION_CANCELLED' ? 'CANCELLED_AFTER_EXPIRY' : 'FAILED_AFTER_REVOCATION'],
          nonce: 'nonce-receipt-0004',
        },
      })
      const source = new MemorySource()
      source.registries.set(value.registry.registry_root, value.registry)
      for (const receipt of [value.receipts[0], value.receipts[1], leaseTerminal, mutationTerminal]) {
        source.receipts.set(receipt.receipt_id, receipt)
      }
      await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
        source, mutationTerminal.receipt_id, value.context,
      )).resolves.toMatchObject({
        terminal_receipt_kind: terminalKind,
        terminal_outcome: terminalOutcome,
        before_state_root: H('7'),
        after_state_root: H('7'),
      })
    },
  )

  it('accepts an ancestral registry rotation and rejects a divergent signed registry branch', async () => {
    const value = await fixture()
    const rotated = await buildReceiptTrustRegistryV1({
      ...value.registry.registry_body,
      registry_version: '2',
      previous_registry_root: value.registry.registry_root,
      issued_at_ms: '600',
    }, value.operatorPrivateKey)
    const rotatedAdmitted = await rebuildUnderRegistry(
      value.receipts[1], rotated, value.receiptPrivateKey,
    )
    const rotatedCompleted = await rebuildUnderRegistry(
      value.receipts[2], rotated, value.receiptPrivateKey,
      { body: { parent_receipt_hash: rotatedAdmitted.receipt_id } },
    )
    const acceptedRoots = [value.registry.registry_root, rotated.registry_root].sort() as SHA256Hex[]
    const validSource = new MemorySource()
    for (const registry of [value.registry, rotated]) {
      validSource.registries.set(registry.registry_root, registry)
    }
    for (const receipt of [value.receipts[0], rotatedAdmitted, rotatedCompleted]) {
      validSource.receipts.set(receipt.receipt_id, receipt)
    }
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      validSource,
      rotatedCompleted.receipt_id,
      { ...value.context, accepted_registry_roots: acceptedRoots },
    )).resolves.toMatchObject({ terminal_outcome: 'COMPLETED', receipt_count: '3' })

    const alternateGenesis = await buildReceiptTrustRegistryV1({
      ...value.registry.registry_body,
      issued_at_ms: '501',
    }, value.operatorPrivateKey)
    const divergent = await buildReceiptTrustRegistryV1({
      ...rotated.registry_body,
      previous_registry_root: alternateGenesis.registry_root,
    }, value.operatorPrivateKey)
    const divergentAdmitted = await rebuildUnderRegistry(
      value.receipts[1], divergent, value.receiptPrivateKey,
    )
    const divergentCompleted = await rebuildUnderRegistry(
      value.receipts[2], divergent, value.receiptPrivateKey,
      { body: { parent_receipt_hash: divergentAdmitted.receipt_id } },
    )
    const divergentSource = new MemorySource()
    for (const registry of [value.registry, alternateGenesis, divergent]) {
      divergentSource.registries.set(registry.registry_root, registry)
    }
    for (const receipt of [value.receipts[0], divergentAdmitted, divergentCompleted]) {
      divergentSource.receipts.set(receipt.receipt_id, receipt)
    }
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      divergentSource,
      divergentCompleted.receipt_id,
      {
        ...value.context,
        accepted_registry_roots: [value.registry.registry_root, divergent.registry_root]
          .sort() as SHA256Hex[],
      },
    )).rejects.toThrow('does not descend from the prior registry root')
  })

  it('persists an atomic batch, reopens, reads back, and resolves the chain', async () => {
    const value = await fixture()
    const databaseName = `receipt-source-${crypto.randomUUID()}`
    const store = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await store.open()
    await store.persistBatch([value.registry], value.receipts)
    store.close()

    const reopened = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await reopened.open()
    await expect(reopened.resolveReceipt(value.receipts[2].receipt_id)).resolves.toEqual(value.receipts[2])
    await expect(reopened.resolveTrustRegistry(value.registry.registry_root)).resolves.toEqual(value.registry)
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      reopened, value.receipts[2].receipt_id, value.context,
    )).resolves.toMatchObject({ decision: 'VERIFIED', receipt_count: '3' })
    reopened.close()
  })

  it('aborts a conflicting batch without partially persisting its registry or receipts', async () => {
    const value = await fixture()
    const deniedOne = await rebuild(value.receipts[1], value.receiptPrivateKey, {
      kind: 'MUTATION_DENIED',
      body: { outcome: 'DENIED', denial_codes: ['DENIED_ONE'] },
    })
    const deniedTwo = await rebuild(value.receipts[1], value.receiptPrivateKey, {
      kind: 'MUTATION_DENIED',
      body: { outcome: 'DENIED', denial_codes: ['DENIED_TWO'], nonce: 'nonce-receipt-0002' },
    })
    const store = new IndexedDBCrossRuntimeReceiptSourceV1(`receipt-source-${crypto.randomUUID()}`)
    await store.open()
    await expect(store.persistBatch(
      [value.registry], [value.receipts[0], deniedOne, deniedTwo],
    )).rejects.toThrow('duplicate')
    await expect(store.resolveTrustRegistry(value.registry.registry_root)).resolves.toBeNull()
    await expect(store.resolveReceipt(value.receipts[0].receipt_id)).resolves.toBeNull()
    store.close()
  })

  it('rolls back earlier writes when a later IndexedDB uniqueness constraint aborts the transaction', async () => {
    const value = await fixture()
    const databaseName = `receipt-transaction-${crypto.randomUUID()}`
    const store = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await store.open()
    await store.persistBatch([value.registry], [value.receipts[0]])
    const colliding = await rebuild(value.receipts[0], value.receiptPrivateKey, {
      body: { action_digest: H('f') },
    })

    await expect(store.persistBatch([], [value.receipts[1], colliding])).rejects.toThrow()
    await expect(store.resolveReceipt(value.receipts[0].receipt_id)).resolves.toEqual(value.receipts[0])
    await expect(store.resolveReceipt(value.receipts[1].receipt_id)).resolves.toBeNull()
    await expect(store.resolveReceipt(colliding.receipt_id)).resolves.toBeNull()
    store.close()

    const reopened = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await reopened.open()
    await expect(reopened.resolveReceipt(value.receipts[0].receipt_id)).resolves.toEqual(value.receipts[0])
    await expect(reopened.resolveReceipt(value.receipts[1].receipt_id)).resolves.toBeNull()
    reopened.close()
  })
})

interface PythonGoldenFixture {
  readonly operator_public_key: string
  readonly registry: ReceiptTrustRegistryV1
  readonly receipts: readonly CrossRuntimeReceiptEnvelopeV1[]
  readonly terminal_receipt_id: SHA256Hex
  readonly context: Omit<TrustedReceiptResolutionContextV1, 'operator_public_key'>
  readonly expected_decision_digest?: SHA256Hex
}

const pythonFixturePath = resolve('test/vectors/python-cross-runtime-receipt-v1.json')
const typescriptFixturePath = resolve('test/vectors/typescript-cross-runtime-receipt-v1.json')

describe('Python cross-runtime golden fixture', () => {
  it(
    'verifies Python-generated registry, receipts, signatures, ids, and decision digest',
    async () => {
      const golden = JSON.parse(readFileSync(pythonFixturePath, 'utf8')) as PythonGoldenFixture
      const source = new MemorySource()
      source.registries.set(golden.registry.registry_root, golden.registry)
      for (const receipt of golden.receipts) source.receipts.set(receipt.receipt_id, receipt)
      const decision = await resolveAndVerifyCrossRuntimeReceiptChainV1(
        source,
        golden.terminal_receipt_id,
        { ...golden.context, operator_public_key: golden.operator_public_key },
      )
      expect(decision.decision).toBe('VERIFIED')
      if (golden.expected_decision_digest !== undefined) {
        expect(decision.decision_digest).toBe(golden.expected_decision_digest)
      }
    },
  )

  it('persists, reopens, and verifies every Python-generated receipt kind', async () => {
    const golden = JSON.parse(readFileSync(pythonFixturePath, 'utf8')) as PythonGoldenFixture
    const databaseName = `receipt-all-kinds-${crypto.randomUUID()}`
    const store = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await store.open()
    await store.persistBatch([golden.registry], golden.receipts)
    store.close()

    const reopened = new IndexedDBCrossRuntimeReceiptSourceV1(databaseName)
    await reopened.open()
    for (const receipt of golden.receipts) {
      await expect(reopened.resolveReceipt(receipt.receipt_id)).resolves.toEqual(receipt)
    }
    await expect(resolveAndVerifyCrossRuntimeReceiptChainV1(
      reopened,
      golden.terminal_receipt_id,
      { ...golden.context, operator_public_key: golden.operator_public_key },
    )).resolves.toMatchObject({
      decision: 'VERIFIED',
      receipt_count: String(golden.receipts.length),
    })
    reopened.close()
  })

  it('independently regenerates byte-identical Python and TypeScript all-kind vectors', async () => {
    const pythonBytes = readFileSync(pythonFixturePath)
    const typescriptBytes = readFileSync(typescriptFixturePath)
    const regenerated = Buffer.concat([
      Buffer.from(canonicalizeJCS(await buildTypeScriptCrossRuntimeVectorV1())),
      Buffer.from('\n'),
    ])
    expect(typescriptBytes.equals(regenerated)).toBe(true)
    expect(pythonBytes.equals(regenerated)).toBe(true)
  })
})
