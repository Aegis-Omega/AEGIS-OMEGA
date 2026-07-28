import 'fake-indexeddb/auto'

import { describe, expect, it } from 'vitest'
import { hashValue } from '../../src/core/hashing.js'
import {
  MetacognitiveLoop,
  certifyMetacognitiveLoop,
} from '../../src/metacognition/loop.js'
import {
  IndexedDBOutcomeEvidenceArtifactStore,
} from '../../src/metacognition/outcome-evidence-artifact-store.js'
import type {
  ReadableOutcomeEvidenceArtifactStore,
} from '../../src/metacognition/outcome-evidence-artifact-store.js'
import {
  replayAuthenticatedOutcomeEvidenceV1,
} from '../../src/metacognition/outcome-evidence-replay.js'
import type {
  AdaptationOutcomeInput,
  OutcomeEvidenceArtifactV1,
} from '../../src/metacognition/outcome-comparator.js'
import { regulateSelf } from '../../src/metacognition/self-regulator.js'
import {
  H,
  SEQ,
  certifyOutcomeInput,
  certifyUncheckedOutcomeInputForTest,
  createOutcomeClosureFixture,
  outcomeReplayEvidence,
  outcomeSelfModel,
  trustedOutcomeReplayContext,
} from '../helpers/outcome-evidence-fixture.js'

let databaseCounter = 0
function databaseName(): string {
  databaseCounter += 1
  return `metacognitive-outcome-closure-${databaseCounter}`
}

function trackingStore(delegate: ReadableOutcomeEvidenceArtifactStore) {
  let persistCalls = 0
  const store: ReadableOutcomeEvidenceArtifactStore = {
    async persist(artifact) {
      persistCalls += 1
      return delegate.persist(artifact)
    },
    async read(artifactRoot) {
      return delegate.read(artifactRoot)
    },
  }
  return { store, persistCalls: () => persistCalls }
}

describe('metacognitive adaptation outcome closure', () => {
  it('authenticates, reassesses, persists, reads back, appends, and reanchors', async () => {
    const fixture = await createOutcomeClosureFixture()
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()
    const observed = await replayAuthenticatedOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture),
    )

    expect(observed.assessment.state_disposition).toBe('PRESERVE')
    expect(observed.assessment.evidence_certificate_authenticated).toBe(true)
    expect(observed.assessment.evidence_certificate_verified).toBe(true)
    expect(observed.assessment.grants_authority).toBe(false)
    expect(observed.assessment.executes_mutation).toBe(false)
    expect(observed.assessment.updates_competence).toBe(false)
    const restored = await store.read(observed.artifact.artifact_root)
    expect(restored).toEqual(observed.artifact)
    const certificate = await certifyMetacognitiveLoop(observed.loop.getAll())
    expect(certificate.is_valid).toBe(true)
    expect(observed.entry.observation.signal).toContain(observed.artifact.artifact_root)
    expect(observed.artifact.assessment.assessment_digest).toBe(
      observed.assessment.assessment_digest,
    )

    const reanchoredPost = await outcomeSelfModel(fixture.trustPolicy.verifier_trust_root, {
      capability_root: fixture.input.post_snapshot.capability_root,
      metacognition_root: observed.entry.entry_hash,
    })
    expect(reanchoredPost.state_root).not.toBe(fixture.input.post_snapshot.state_root)
    const nextRegulation = await regulateSelf({ snapshot: reanchoredPost, gaps: [] })
    expect(nextRegulation.mode).toBe('NO_CHANGE')
    store.close()
  })

  it('records an authenticated authority denial without inventing a state change', async () => {
    const fixture = await createOutcomeClosureFixture()
    const { evidence_certificate: _certificate, terminal_execution: _terminal, ...unsigned } = fixture.input
    const deniedInput = await certifyOutcomeInput({
      ...unsigned,
      authority: {
        ...fixture.input.authority,
        outcome: 'DENIED',
        denial_codes: ['APPROVAL_MISSING'],
      },
      post_snapshot: fixture.input.baseline.snapshot,
      post_gaps: fixture.input.baseline.gaps,
      verification: [],
    }, fixture.verifier, fixture.verifierKeypair)
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()

    const observed = await replayAuthenticatedOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, deniedInput),
    )
    expect(observed.assessment.state_disposition).toBe('NO_STATE_CHANGE')
    expect(observed.assessment.evidence_certificate_authenticated).toBe(true)
    expect(observed.assessment.learning_evidence_eligible).toBe(false)
    expect(observed.assessment.reason_codes).toContain('AUTHORITY_DENIED')
    expect(await store.read(observed.artifact.artifact_root)).toEqual(observed.artifact)
    store.close()
  })

  it('rejects a tampered trust-policy signature before persistence or append', async () => {
    const fixture = await createOutcomeClosureFixture()
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const signature = fixture.trustPolicy.signature
    const tamperedPolicy = {
      ...fixture.trustPolicy,
      signature: `${signature.startsWith('0') ? '1' : '0'}${signature.slice(1)}`,
    }
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      {
        ...outcomeReplayEvidence(fixture),
        trust_policy: tamperedPolicy,
      },
    )).rejects.toThrow('trust policy signature is invalid')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('rejects unsigned verifier-policy extensions before persistence or append', async () => {
    const fixture = await createOutcomeClosureFixture()
    const extendedPolicy = structuredClone(fixture.trustPolicy) as typeof fixture.trustPolicy & {
      verifiers: Array<typeof fixture.verifier & { unsigned_extension?: string }>
    }
    extendedPolicy.verifiers[0]!.unsigned_extension = 'attacker-controlled'
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      { ...outcomeReplayEvidence(fixture), trust_policy: extendedPolicy },
    )).rejects.toThrow('verifiers[0] has unexpected or missing fields')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('does not let evidence nominate the out-of-band operator key', async () => {
    const fixture = await createOutcomeClosureFixture()
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      {
        ...trustedOutcomeReplayContext(fixture),
        expected_operator_public_key: H('f'),
      },
      outcomeReplayEvidence(fixture),
    )).rejects.toThrow('trust policy signer is not the expected operator key')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('rejects evidence changed after certificate signing before persistence or append', async () => {
    const fixture = await createOutcomeClosureFixture()
    const tamperedInput: AdaptationOutcomeInput = {
      ...fixture.input,
      post_gaps: [{
        gap_id: 'gap.tampered-after-signing',
        kind: 'INVARIANT_BREACH',
        severity: 'CRITICAL',
        evidence_refs: [H('f')],
      }],
    }
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, tamperedInput),
    )).rejects.toThrow('outcome evidence certificate authentication failed')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('rejects signed placeholder terminal roots before persistence or append', async () => {
    const fixture = await createOutcomeClosureFixture()
    const unresolvedInput = await certifyUncheckedOutcomeInputForTest({
      ...fixture.input,
      terminal_execution: {
        ...fixture.input.terminal_execution!,
        lease_authorization_receipt_root: H('0'),
        durable_execution_root: H('0'),
        mutation_receipt_root: H('0'),
        receipt_chain_verification_root: H('0'),
        provider_result_digest: H('0'),
        operator_notification_root: H('0'),
      },
    }, fixture.verifier, fixture.verifierKeypair)
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, unresolvedInput),
    )).rejects.toThrow('terminal_execution.lease_authorization_receipt_root must resolve to a non-zero')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('rejects signed placeholder verification evidence before persistence or append', async () => {
    const fixture = await createOutcomeClosureFixture()
    const unresolvedInput = await certifyUncheckedOutcomeInputForTest({
      ...fixture.input,
      verification: [{ ...fixture.input.verification[0]!, evidence_digest: H('0') }],
    }, fixture.verifier, fixture.verifierKeypair)
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, unresolvedInput),
    )).rejects.toThrow('verification[0].evidence_digest must resolve to a non-zero')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('rejects signed unresolved gap, authority-binding, and verifier roots without writing', async () => {
    const fixture = await createOutcomeClosureFixture()
    const variants: ReadonlyArray<{
      expected: string
      input: AdaptationOutcomeInput
    }> = [{
      expected: 'gaps[0].evidence_refs[0] must resolve to a non-zero root',
      input: {
        ...fixture.input,
        baseline: {
          ...fixture.input.baseline,
          gaps: [{ ...fixture.input.baseline.gaps[0]!, evidence_refs: [H('0')] }],
        },
      },
    }, {
      expected: 'authority.action_binding.proposal_digest must resolve to a non-zero',
      input: {
        ...fixture.input,
        authority: {
          ...fixture.input.authority,
          action_binding: {
            ...fixture.input.authority.action_binding,
            proposal_digest: H('0'),
          },
        },
      },
    }, {
      expected: 'verification[0].verifier_identity_root must resolve to a non-zero',
      input: {
        ...fixture.input,
        verification: [{
          ...fixture.input.verification[0]!,
          verifier_identity_root: H('0'),
          verification_mode: 'EXECUTOR_SELF_REPORT',
        }],
      },
    }]

    for (const variant of variants) {
      const signedInput = await certifyUncheckedOutcomeInputForTest(
        variant.input,
        fixture.verifier,
        fixture.verifierKeypair,
      )
      const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
      await delegate.open()
      const tracked = trackingStore(delegate)
      const loop = MetacognitiveLoop.empty()
      await expect(replayAuthenticatedOutcomeEvidenceV1(
        loop,
        tracked.store,
        SEQ(1),
        trustedOutcomeReplayContext(fixture),
        outcomeReplayEvidence(fixture, signedInput),
      )).rejects.toThrow(variant.expected)
      expect(tracked.persistCalls()).toBe(0)
      expect(loop.length).toBe(0)
      delegate.close()
    }
  })

  it('rejects a signed post-state with an unresolved capability root without writing', async () => {
    const fixture = await createOutcomeClosureFixture()
    const { state_root: _stateRoot, ...postComponents } = fixture.input.post_snapshot
    const unresolvedComponents = { ...postComponents, capability_root: H('0') }
    const unresolvedPost = {
      state_root: await hashValue({
        domain: 'AEGIS_SELF_MODEL_STATE_V1',
        snapshot: unresolvedComponents,
      }),
      ...unresolvedComponents,
    }
    const signedInput = await certifyUncheckedOutcomeInputForTest({
      ...fixture.input,
      post_snapshot: unresolvedPost,
      terminal_execution: {
        ...fixture.input.terminal_execution!,
        post_state_root: unresolvedPost.state_root,
      },
    }, fixture.verifier, fixture.verifierKeypair)
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, signedInput),
    )).rejects.toThrow('snapshot.capability_root must resolve to a non-zero root')
    expect(tracked.persistCalls()).toBe(0)
    delegate.close()
  })

  it('rejects negative-zero aliases before persistence or append', async () => {
    const fixture = await createOutcomeClosureFixture()
    const aliasedInput = {
      ...fixture.input,
      verification: [{ ...fixture.input.verification[0]!, step_index: -0 }],
    }
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, aliasedInput),
    )).rejects.toThrow('negative zero')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('rejects replay accessors without invoking them or persisting', async () => {
    const fixture = await createOutcomeClosureFixture()
    const validInput = fixture.input
    let reads = 0
    const evidence = { trust_policy: fixture.trustPolicy } as {
      input: AdaptationOutcomeInput
      trust_policy: typeof fixture.trustPolicy
    }
    Object.defineProperty(evidence, 'input', {
      enumerable: true,
      get() { reads += 1; return validInput },
    })
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      evidence,
    )).rejects.toThrow('enumerable data property')
    expect(reads).toBe(0)
    expect(tracked.persistCalls()).toBe(0)
    delegate.close()
  })

  it('rejects symbol-keyed replay aliases before persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const evidence = structuredClone(outcomeReplayEvidence(fixture))
    const unsigned = Symbol('unsigned-extension')
    ;(evidence.input.verification as unknown as { [key: symbol]: unknown })[unsigned] =
      'attacker-controlled'
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      evidence,
    )).rejects.toThrow('symbol keys')
    expect(tracked.persistCalls()).toBe(0)
    delegate.close()
  })

  it('rejects a stale metacognitive baseline before persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const prior = await MetacognitiveLoop.empty().observe({
      layer: 'SENSATION',
      signal: 'prior authenticated observation',
      tier: 'T2',
    }, SEQ(1))
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      prior.loop,
      tracked.store,
      SEQ(2),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture),
    )).rejects.toThrow('metacognitive loop head does not match evidence baseline')
    expect(tracked.persistCalls()).toBe(0)
    expect(prior.loop.length).toBe(1)
    delegate.close()
  })

  it('rejects an authenticated verifier policy not bound to the baseline', async () => {
    const fixture = await createOutcomeClosureFixture()
    const staleBaseline = await outcomeSelfModel(H('f'))
    const staleInput: AdaptationOutcomeInput = {
      ...fixture.input,
      baseline: { ...fixture.input.baseline, snapshot: staleBaseline },
    }
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, staleInput),
    )).rejects.toThrow('authenticated verifier trust policy is not bound')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('persists authenticated evidence of an unsafe transition as a negative assessment', async () => {
    const fixture = await createOutcomeClosureFixture()
    const unsafePost = await outcomeSelfModel(fixture.trustPolicy.verifier_trust_root, {
      policy_root: H('f'),
      capability_root: H('9'),
    })
    const unsafeInput = await certifyOutcomeInput({
      ...fixture.input,
      post_snapshot: unsafePost,
      terminal_execution: {
        ...fixture.input.terminal_execution!,
        post_state_root: unsafePost.state_root,
      },
    }, fixture.verifier, fixture.verifierKeypair)
    const store = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await store.open()

    const observed = await replayAuthenticatedOutcomeEvidenceV1(
      MetacognitiveLoop.empty(),
      store,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture, unsafeInput),
    )
    expect(observed.assessment.evidence_certificate_authenticated).toBe(true)
    expect(observed.assessment.evidence_certificate_verified).toBe(false)
    expect(observed.assessment.state_disposition).toBe('REVERT')
    expect(observed.assessment.reason_codes).toContain('POLICY_TRANSITION_REQUIRES_D4')
    expect(await store.read(observed.artifact.artifact_root)).toEqual(observed.artifact)
    store.close()
  })

  it('rejects an invalid host-allocated sequence before persistence', async () => {
    const fixture = await createOutcomeClosureFixture()
    const delegate = new IndexedDBOutcomeEvidenceArtifactStore(databaseName())
    await delegate.open()
    const tracked = trackingStore(delegate)
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      tracked.store,
      SEQ(-1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture),
    )).rejects.toThrow('sequence must be a non-negative bigint')
    expect(tracked.persistCalls()).toBe(0)
    expect(loop.length).toBe(0)
    delegate.close()
  })

  it('does not return an appended loop when persisted evidence cannot be read back', async () => {
    const fixture = await createOutcomeClosureFixture()
    let persistedArtifact: OutcomeEvidenceArtifactV1 | null = null
    const unreadableStore: ReadableOutcomeEvidenceArtifactStore = {
      async persist(artifact) {
        persistedArtifact = artifact
        return {
          artifact_root: artifact.artifact_root,
          artifact_reference: `memory:${artifact.artifact_root}`,
        }
      },
      async read() { return null },
    }
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      unreadableStore,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture),
    )).rejects.toThrow('persisted outcome evidence artifact cannot be resolved')
    expect(persistedArtifact).not.toBeNull()
    expect(loop.length).toBe(0)
  })

  it('does not return an appended loop when read-back bytes differ', async () => {
    const fixture = await createOutcomeClosureFixture()
    let persistedArtifact: OutcomeEvidenceArtifactV1 | null = null
    const mismatchedStore: ReadableOutcomeEvidenceArtifactStore = {
      async persist(artifact) {
        persistedArtifact = artifact
        return {
          artifact_root: artifact.artifact_root,
          artifact_reference: `memory:${artifact.artifact_root}`,
        }
      },
      async read() {
        if (persistedArtifact === null) return null
        return {
          ...persistedArtifact,
          assessment: {
            ...persistedArtifact.assessment,
            reason_codes: [...persistedArtifact.assessment.reason_codes, 'FORGED_READ_BACK'],
          },
        }
      },
    }
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      mismatchedStore,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture),
    )).rejects.toThrow('persisted outcome evidence artifact read-back mismatch')
    expect(loop.length).toBe(0)
  })

  it('does not accept a canonical alias from abstract-store read-back', async () => {
    const fixture = await createOutcomeClosureFixture()
    let persistedArtifact: OutcomeEvidenceArtifactV1 | null = null
    const aliasedStore: ReadableOutcomeEvidenceArtifactStore = {
      async persist(artifact) {
        persistedArtifact = artifact
        return {
          artifact_root: artifact.artifact_root,
          artifact_reference: `memory:${artifact.artifact_root}`,
        }
      },
      async read() {
        if (persistedArtifact === null) return null
        const aliased = structuredClone(persistedArtifact) as OutcomeEvidenceArtifactV1 & {
          evidence_input: AdaptationOutcomeInput & {
            verification: Array<{ step_index: number }>
          }
        }
        aliased.evidence_input.verification[0]!.step_index = -0
        return aliased
      },
    }
    const loop = MetacognitiveLoop.empty()

    await expect(replayAuthenticatedOutcomeEvidenceV1(
      loop,
      aliasedStore,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      outcomeReplayEvidence(fixture),
    )).rejects.toThrow('negative zero')
    expect(loop.length).toBe(0)
  })

  it('reauthenticates reopened evidence and replays it deterministically and idempotently', async () => {
    const fixture = await createOutcomeClosureFixture()
    const name = databaseName()
    const store = new IndexedDBOutcomeEvidenceArtifactStore(name)
    await store.open()
    const loop = MetacognitiveLoop.empty()

    const first = await replayAuthenticatedOutcomeEvidenceV1(
      loop, store, SEQ(1), trustedOutcomeReplayContext(fixture), outcomeReplayEvidence(fixture),
    )
    store.close()
    const reopened = new IndexedDBOutcomeEvidenceArtifactStore(name)
    await reopened.open()
    const restored = await reopened.read(first.artifact.artifact_root)
    if (restored === null) throw new Error('persisted artifact was not restored')
    const second = await replayAuthenticatedOutcomeEvidenceV1(
      loop,
      reopened,
      SEQ(1),
      trustedOutcomeReplayContext(fixture),
      {
        input: restored.evidence_input,
        trust_policy: restored.verifier_trust_anchor.trust_policy,
      },
    )
    expect(second.assessment.assessment_digest).toBe(first.assessment.assessment_digest)
    expect(second.artifact.artifact_root).toBe(first.artifact.artifact_root)
    expect(second.persistence).toEqual(first.persistence)
    expect(second.entry.entry_hash).toBe(first.entry.entry_hash)
    expect(restored).toEqual(first.artifact)

    const tracked = trackingStore(reopened)
    await expect(replayAuthenticatedOutcomeEvidenceV1(
      first.loop,
      tracked.store,
      SEQ(2),
      trustedOutcomeReplayContext(fixture),
      {
        input: restored.evidence_input,
        trust_policy: restored.verifier_trust_anchor.trust_policy,
      },
    )).rejects.toThrow('metacognitive loop head does not match evidence baseline')
    expect(tracked.persistCalls()).toBe(0)
    reopened.close()
  })
})
