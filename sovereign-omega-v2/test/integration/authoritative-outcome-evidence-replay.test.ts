import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import { generateKeypair } from '../../src/consensus/crypto.js'
import { MetacognitiveLoop } from '../../src/metacognition/loop.js'
import type {
  ReadableOutcomeEvidenceArtifactStore,
} from '../../src/metacognition/outcome-evidence-artifact-store.js'
import {
  AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED,
  replayAuthoritativeOutcomeEvidenceV1,
} from '../../src/metacognition/authoritative-outcome-evidence-replay.js'
import type {
  OutcomeEvidenceArtifactV1,
} from '../../src/metacognition/outcome-comparator.js'
import type {
  OutcomeReplayEvidenceV1,
} from '../../src/metacognition/outcome-evidence-replay.js'
import {
  buildCrossRuntimeReceiptEnvelopeV1,
  buildReceiptTrustRegistryV1,
} from '../../src/provenance/cross-runtime-receipts.js'
import type {
  CrossRuntimeReceiptBodyV1,
  CrossRuntimeReceiptEnvelopeV1,
  CrossRuntimeReceiptKindV1,
  ReceiptTrustRegistryBodyV1,
} from '../../src/provenance/cross-runtime-receipts.js'
import {
  resolveAndVerifyCrossRuntimeReceiptChainV1,
  verifyCrossRuntimeReceiptVerificationDecisionDigestV1,
} from '../../src/provenance/receipt-resolver.js'
import type {
  CrossRuntimeReceiptSourceV1,
  TrustedReceiptResolutionContextV1,
} from '../../src/provenance/receipt-resolver.js'
import {
  H,
  SEQ,
  certifyOutcomeInput,
  createOutcomeClosureFixture,
  outcomeReplayEvidence,
  trustedOutcomeReplayContext,
} from '../helpers/outcome-evidence-fixture.js'
import type {
  OutcomeClosureFixture,
} from '../helpers/outcome-evidence-fixture.js'

const ZERO_HASH = '0'.repeat(64) as SHA256Hex

interface ReceiptChainFixture {
  readonly source: CrossRuntimeReceiptSourceV1
  readonly receipts: Map<SHA256Hex, unknown>
  readonly terminalReceiptId: SHA256Hex
  readonly admissionReceiptId: SHA256Hex
  readonly context: TrustedReceiptResolutionContextV1
}

interface ReceiptChainOptions {
  readonly terminalKind?: 'MUTATION_COMPLETED' | 'MUTATION_CANCELLED'
  readonly terminalTimestamp?: string
  readonly terminalStateRoot?: SHA256Hex
}

function trackingStore() {
  let persistCalls = 0
  const artifacts = new Map<SHA256Hex, OutcomeEvidenceArtifactV1>()
  const store: ReadableOutcomeEvidenceArtifactStore = {
    async persist(artifact) {
      persistCalls += 1
      artifacts.set(artifact.artifact_root, artifact)
      return {
        artifact_root: artifact.artifact_root,
        artifact_reference: `memory:${artifact.artifact_root}`,
      }
    },
    async read(artifactRoot) {
      return artifacts.get(artifactRoot) ?? null
    },
  }
  return { store, persistCalls: () => persistCalls }
}

function receiptBody(
  fixture: OutcomeClosureFixture,
  overrides: Partial<CrossRuntimeReceiptBodyV1>,
): CrossRuntimeReceiptBodyV1 {
  return {
    receipt_sequence: '0',
    actor_identity_root: fixture.input.authority.execution_identity_root,
    session_identity_root: H('1'),
    workspace_identity_root: fixture.input.authority.workspace_binding,
    holon_identity_root: H('6'),
    authority_domain: 'aegis.outcome',
    authority_level: 'D2',
    authority_receipt_hash: ZERO_HASH,
    lease_id: H('5'),
    lease_generation: '1',
    fencing_token: H('6'),
    lease_authorization_receipt_hash: ZERO_HASH,
    parent_receipt_hash: ZERO_HASH,
    observed_state_root: fixture.input.baseline.snapshot.state_root,
    expected_state_root: fixture.input.baseline.snapshot.state_root,
    action_digest: fixture.input.authority.requested_action_digest,
    before_state_root: fixture.input.baseline.snapshot.state_root,
    after_state_root: fixture.input.baseline.snapshot.state_root,
    result_digest: H('1'),
    timestamp_ms: '1100',
    expires_at_ms: '4000',
    nonce: 'nonce-lease-issued-0001',
    outcome: 'ADMITTED',
    denial_codes: [],
    ...overrides,
  }
}

async function createReceiptChain(
  fixture: OutcomeClosureFixture,
  options: ReceiptChainOptions = {},
): Promise<ReceiptChainFixture> {
  const operatorKeypair = await generateKeypair(new Uint8Array(32).fill(41))
  const receiptKeypair = await generateKeypair(new Uint8Array(32).fill(43))
  const verifierIdentityRoot = H('f')
  const receiptKinds: CrossRuntimeReceiptKindV1[] = [
    'LEASE_ISSUED',
    'MUTATION_ADMITTED',
    'MUTATION_CANCELLED',
    'MUTATION_COMPLETED',
  ].sort() as CrossRuntimeReceiptKindV1[]
  const registryBody: ReceiptTrustRegistryBodyV1 = {
    registry_version: '1',
    previous_registry_root: ZERO_HASH,
    issued_at_ms: '900',
    valid_from_ms: '1000',
    expires_at_ms: '5000',
    operator_key_id: 'receipt-operator-key',
    keys: [{
      key_id: 'receipt-signer-key',
      public_key: receiptKeypair.publicKey,
      verifier_identity_root: verifierIdentityRoot,
      valid_from_ms: '1000',
      expires_at_ms: '5000',
      status: 'ACTIVE',
      authority_domains: ['aegis.outcome'],
      receipt_kinds: receiptKinds,
    }],
  }
  const registry = await buildReceiptTrustRegistryV1(registryBody, operatorKeypair.privateKey)
  const proof = {
    algorithm: 'Ed25519' as const,
    signer_key_id: 'receipt-signer-key',
    verifier_identity_root: verifierIdentityRoot,
    trust_registry_version: '1',
    trust_registry_root: registry.registry_root,
  }
  const signReceipt = async (
    receipt_kind: CrossRuntimeReceiptKindV1,
    body: CrossRuntimeReceiptBodyV1,
  ): Promise<CrossRuntimeReceiptEnvelopeV1> => buildCrossRuntimeReceiptEnvelopeV1({
    schema_version: '1.0.0',
    receipt_kind,
    receipt_body: body,
    proof,
  }, receiptKeypair.privateKey)

  const lease = await signReceipt('LEASE_ISSUED', receiptBody(fixture, {}))
  const admission = await signReceipt('MUTATION_ADMITTED', receiptBody(fixture, {
    receipt_sequence: '1',
    authority_receipt_hash: fixture.input.authority.authority_receipt_root,
    lease_authorization_receipt_hash: lease.receipt_id,
    parent_receipt_hash: lease.receipt_id,
    result_digest: H('2'),
    timestamp_ms: '1200',
    nonce: 'nonce-mutation-admit-0002',
  }))
  const terminalKind = options.terminalKind ?? 'MUTATION_COMPLETED'
  const terminalState = options.terminalStateRoot ?? fixture.input.baseline.snapshot.state_root
  const cancelled = terminalKind === 'MUTATION_CANCELLED'
  const terminal = await signReceipt(terminalKind, receiptBody(fixture, {
    receipt_sequence: '2',
    authority_receipt_hash: fixture.input.authority.authority_receipt_root,
    lease_authorization_receipt_hash: lease.receipt_id,
    parent_receipt_hash: admission.receipt_id,
    observed_state_root: terminalState,
    expected_state_root: terminalState,
    before_state_root: terminalState,
    after_state_root: cancelled ? terminalState : fixture.input.post_snapshot.state_root,
    result_digest: fixture.input.terminal_execution?.provider_result_digest ?? H('e'),
    timestamp_ms: options.terminalTimestamp ?? '1300',
    nonce: cancelled ? 'nonce-mutation-cancel-0003' : 'nonce-mutation-complete-003',
    outcome: cancelled ? 'CANCELLED' : 'COMPLETED',
    denial_codes: cancelled ? ['OPERATOR_CANCELLED'] : [],
  }))

  const receipts = new Map<SHA256Hex, unknown>([
    [lease.receipt_id, lease],
    [admission.receipt_id, admission],
    [terminal.receipt_id, terminal],
  ])
  const registries = new Map<SHA256Hex, unknown>([[registry.registry_root, registry]])
  const source: CrossRuntimeReceiptSourceV1 = {
    async resolveReceipt(receiptId) {
      return receipts.get(receiptId) ?? null
    },
    async resolveTrustRegistry(registryRoot) {
      return registries.get(registryRoot) ?? null
    },
  }
  const context: TrustedReceiptResolutionContextV1 = {
    operator_key_id: 'receipt-operator-key',
    operator_public_key: operatorKeypair.publicKey,
    accepted_registry_roots: [registry.registry_root],
    observed_at_ms: '4500',
    max_clock_skew_ms: '0',
    expected_actor_identity_root: fixture.input.authority.execution_identity_root,
    expected_session_identity_root: H('1'),
    expected_workspace_identity_root: fixture.input.authority.workspace_binding,
    expected_holon_identity_root: H('6'),
    expected_authority_domain: 'aegis.outcome',
    expected_authority_level: 'D2',
    expected_observed_state_root: fixture.input.baseline.snapshot.state_root,
    expected_action_digest: fixture.input.authority.requested_action_digest,
  }
  return {
    source,
    receipts,
    terminalReceiptId: terminal.receipt_id,
    admissionReceiptId: admission.receipt_id,
    context,
  }
}

async function createBoundScenario() {
  const fixture = await createOutcomeClosureFixture()
  const receiptChain = await createReceiptChain(fixture)
  const decision = await resolveAndVerifyCrossRuntimeReceiptChainV1(
    receiptChain.source,
    receiptChain.terminalReceiptId,
    receiptChain.context,
  )
  const terminal = fixture.input.terminal_execution
  if (terminal === undefined) throw new Error('outcome fixture terminal evidence is unavailable')
  const { evidence_certificate: _certificate, ...unsigned } = fixture.input
  const input = await certifyOutcomeInput({
    ...unsigned,
    terminal_execution: {
      ...terminal,
      execution_identity_root: decision.actor_identity_root,
      workspace_binding: decision.workspace_identity_root,
      authority_receipt_root: decision.authority_receipt_hash,
      requested_action_digest: decision.action_digest,
      lease_authorization_receipt_root: decision.lease_authorization_receipt_hash,
      mutation_receipt_root: decision.terminal_receipt_id,
      receipt_chain_status: 'VERIFIED',
      receipt_chain_verification_root: decision.chain_digest,
      durable_status: 'COMPLETED',
      outcome: 'SUCCEEDED',
      pre_state_root: decision.before_state_root,
      post_state_root: decision.after_state_root,
      provider_result_digest: decision.result_digest,
    },
  }, fixture.verifier, fixture.verifierKeypair)
  return { fixture, receiptChain, decision, evidence: outcomeReplayEvidence(fixture, input) }
}

async function expectRejectedWithoutPersistence(
  fixture: OutcomeClosureFixture,
  chain: ReceiptChainFixture,
  terminalReceiptId: SHA256Hex = chain.terminalReceiptId,
  context: TrustedReceiptResolutionContextV1 = chain.context,
): Promise<void> {
  const tracked = trackingStore()
  const loop = MetacognitiveLoop.empty()
  await expect(replayAuthoritativeOutcomeEvidenceV1(
    loop,
    tracked.store,
    SEQ(1),
    trustedOutcomeReplayContext(fixture),
    outcomeReplayEvidence(fixture),
    chain.source,
    terminalReceiptId,
    context,
  )).rejects.toThrow()
  expect(tracked.persistCalls()).toBe(0)
  expect(loop.length).toBe(0)
}

describe('authoritative outcome evidence replay', () => {
  it('resolves completion provenance before persisting and remains non-authoritative', async () => {
    const scenario = await createBoundScenario()
    const tracked = trackingStore()
    const observed = await replayAuthoritativeOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(scenario.fixture),
      scenario.evidence,
      scenario.receiptChain.source,
      scenario.receiptChain.terminalReceiptId,
      scenario.receiptChain.context,
    )

    expect(observed.provenance_status).toBe(AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED)
    expect(observed.provenance_decision).toEqual(scenario.decision)
    expect(observed.provenance_decision.grants_authority).toBe(false)
    expect(observed.provenance_decision.executes_mutation).toBe(false)
    expect(observed.assessment.grants_authority).toBe(false)
    expect(observed.assessment.executes_mutation).toBe(false)
    expect(observed.assessment.updates_competence).toBe(false)
    expect(tracked.persistCalls()).toBe(1)
    expect(observed.loop.length).toBe(1)
  })

  it('returns a verification decision that survives JSON round-trip and digest verification', async () => {
    const scenario = await createBoundScenario()
    const tracked = trackingStore()
    const observed = await replayAuthoritativeOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(scenario.fixture),
      scenario.evidence,
      scenario.receiptChain.source,
      scenario.receiptChain.terminalReceiptId,
      scenario.receiptChain.context,
    )
    const roundTripped: unknown = JSON.parse(JSON.stringify(observed.provenance_decision))
    await expect(verifyCrossRuntimeReceiptVerificationDecisionDigestV1(roundTripped))
      .resolves.toEqual(observed.provenance_decision)
  })

  it('rejects a tampered terminal receipt before artifact persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const chain = await createReceiptChain(fixture)
    const stored = chain.receipts.get(chain.terminalReceiptId) as CrossRuntimeReceiptEnvelopeV1
    chain.receipts.set(chain.terminalReceiptId, {
      ...stored,
      receipt_body: { ...stored.receipt_body, result_digest: H('4') },
    })
    await expectRejectedWithoutPersistence(fixture, chain)
  })

  it('rejects an untrusted registry before artifact persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const chain = await createReceiptChain(fixture)
    await expectRejectedWithoutPersistence(fixture, chain, chain.terminalReceiptId, {
      ...chain.context,
      accepted_registry_roots: [H('4')],
    })
  })

  it('rejects completion under an expired lease before artifact persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const chain = await createReceiptChain(fixture, { terminalTimestamp: '4000' })
    await expectRejectedWithoutPersistence(fixture, chain)
  })

  it('rejects a stale terminal state before artifact persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const chain = await createReceiptChain(fixture, { terminalStateRoot: H('4') })
    await expectRejectedWithoutPersistence(fixture, chain)
  })

  it('rejects a broken parent chain before artifact persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const chain = await createReceiptChain(fixture)
    chain.receipts.delete(chain.admissionReceiptId)
    await expectRejectedWithoutPersistence(fixture, chain)
  })

  it('rejects outcome evidence not exactly bound to the verified receipt decision', async () => {
    const fixture = await createOutcomeClosureFixture()
    const chain = await createReceiptChain(fixture)
    const tracked = trackingStore()
    const loop = MetacognitiveLoop.empty()
    await expect(replayAuthoritativeOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture),
      chain.source,
      chain.terminalReceiptId,
      chain.context,
    )).rejects.toThrow('authoritative and legacy lease authorization receipt binding mismatch')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
  })

  it('rejects non-admitted legacy authority or lease outcomes with zero writes', async () => {
    const scenario = await createBoundScenario()
    const deniedAuthority: OutcomeReplayEvidenceV1 = {
      ...scenario.evidence,
      input: {
        ...scenario.evidence.input,
        authority: {
          ...scenario.evidence.input.authority,
          outcome: 'DENIED',
          denial_codes: ['APPROVAL_MISSING'],
        },
      },
    }
    const deniedLease: OutcomeReplayEvidenceV1 = {
      ...scenario.evidence,
      input: {
        ...scenario.evidence.input,
        terminal_execution: {
          ...scenario.evidence.input.terminal_execution!,
          lease_outcome: 'DENIED',
        },
      },
    }

    for (const [evidence, message] of [
      [deniedAuthority, 'legacy authority admission outcome binding mismatch'],
      [deniedLease, 'legacy lease admission outcome binding mismatch'],
    ] as const) {
      const tracked = trackingStore()
      const loop = MetacognitiveLoop.empty()
      await expect(replayAuthoritativeOutcomeEvidenceV1(
        loop,
        tracked.store,
        SEQ(1),
        trustedOutcomeReplayContext(scenario.fixture),
        evidence,
        scenario.receiptChain.source,
        scenario.receiptChain.terminalReceiptId,
        scenario.receiptChain.context,
      )).rejects.toThrow(message)
      expect(tracked.persistCalls()).toBe(0)
      expect(loop.length).toBe(0)
    }
  })

  it('rejects cancelled and incomplete chains before artifact persistence', async () => {
    const cancelledFixture = await createOutcomeClosureFixture()
    const cancelled = await createReceiptChain(cancelledFixture, {
      terminalKind: 'MUTATION_CANCELLED',
    })
    await expectRejectedWithoutPersistence(cancelledFixture, cancelled)

    const incompleteFixture = await createOutcomeClosureFixture()
    const incomplete = await createReceiptChain(incompleteFixture)
    await expectRejectedWithoutPersistence(
      incompleteFixture,
      incomplete,
      incomplete.admissionReceiptId,
    )
  })

  it('rejects replay against an advanced loop with zero new artifact writes', async () => {
    const scenario = await createBoundScenario()
    const initialStore = trackingStore()
    const first = await replayAuthoritativeOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      initialStore.store,
      SEQ(1),
      trustedOutcomeReplayContext(scenario.fixture),
      scenario.evidence,
      scenario.receiptChain.source,
      scenario.receiptChain.terminalReceiptId,
      scenario.receiptChain.context,
    )
    const replayStore = trackingStore()
    await expect(replayAuthoritativeOutcomeEvidenceV1(
      first.loop,
      replayStore.store,
      SEQ(2),
      trustedOutcomeReplayContext(scenario.fixture),
      scenario.evidence,
      scenario.receiptChain.source,
      scenario.receiptChain.terminalReceiptId,
      scenario.receiptChain.context,
    )).rejects.toThrow()
    expect(replayStore.persistCalls()).toBe(0)
    expect(first.loop.length).toBe(1)
  })
})
