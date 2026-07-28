import { describe, expect, it } from 'vitest'
import type { SequenceNumber, SHA256Hex } from '../../src/core/types.js'
import { generateKeypair, signBytes } from '../../src/consensus/crypto.js'
import {
  METACOGNITION_GENESIS_HASH,
  MetacognitiveLoop,
} from '../../src/metacognition/loop.js'
import {
  OutcomeComparisonError,
  assessAdaptationOutcome,
  canonicalizeOutcomeEvidenceCertificateMessageV1,
  canonicalizeOutcomeVerifierTrustPolicyMessageV1,
  hashAdaptationAuthorityBinding,
  hashOutcomeEvidenceBundleV1,
  hashVerifierIdentityV1,
  hashVerifierTrustSetV1,
  recordOutcomeAssessment,
  verifyOutcomeVerifierTrustPolicyV1,
} from '../../src/metacognition/outcome-comparator.js'
import type {
  AdaptationAuthorityEvidenceV1,
  AdaptationOutcomeInput,
  OutcomeEvidenceArtifactStore,
  OutcomeEvidenceArtifactV1,
  OutcomeEvidenceCertificateV1,
  OutcomeVerifierIdentityV1,
  OutcomeVerifierTrustPolicyV1,
  TerminalExecutionEvidenceV1,
  VerificationObservation,
  VerifiedOutcomeVerifierTrustAnchorV1,
} from '../../src/metacognition/outcome-comparator.js'
import {
  hashSelfModelStateRootV1,
  regulateSelf,
} from '../../src/metacognition/self-regulator.js'
import type {
  AdaptationProposal,
  KnowledgeGap,
  SelfModelSnapshot,
  SelfModelStateComponents,
} from '../../src/metacognition/self-regulator.js'

const H = (character: string) => character.repeat(64) as SHA256Hex
const SEQ = (value: number) => BigInt(value) as SequenceNumber
const EXECUTOR_PRINCIPAL = H('d')
const EXECUTOR_WORKLOAD = H('e')
const VERIFIER_PRINCIPAL = H('b')
const VERIFIER_WORKLOAD = H('c')

function memoryArtifactStore() {
  const artifacts = new Map<string, OutcomeEvidenceArtifactV1>()
  const store: OutcomeEvidenceArtifactStore = {
    async persist(artifact) {
      artifacts.set(artifact.artifact_root, artifact)
      return {
        artifact_root: artifact.artifact_root,
        artifact_reference: `memory:${artifact.artifact_root}`,
      }
    },
  }
  return { artifacts, store }
}

const GAP: KnowledgeGap = {
  gap_id: 'gap.outcome.001',
  kind: 'CAPABILITY_DEFICIT',
  severity: 'HIGH',
  evidence_refs: [H('e')],
}

interface TrustContext {
  readonly verifierKeypair: Awaited<ReturnType<typeof generateKeypair>>
  readonly verifier: OutcomeVerifierIdentityV1
  readonly anchor: VerifiedOutcomeVerifierTrustAnchorV1
}

interface Fixture {
  readonly input: AdaptationOutcomeInput
  readonly trust: TrustContext
}

async function trustContext(
  verifierPrincipalRoot = VERIFIER_PRINCIPAL,
  verifierWorkloadIdentityRoot = VERIFIER_WORKLOAD,
): Promise<TrustContext> {
  const operatorKeypair = await generateKeypair(new Uint8Array(32).fill(11))
  const verifierKeypair = await generateKeypair(new Uint8Array(32).fill(23))
  const verifier: OutcomeVerifierIdentityV1 = {
    verifier_key_id: 'outcome-test-verifier',
    verifier_public_key: verifierKeypair.publicKey,
    verifier_identity_root: await hashVerifierIdentityV1(verifierKeypair.publicKey),
    verifier_principal_root: verifierPrincipalRoot,
    verifier_workload_identity_root: verifierWorkloadIdentityRoot,
  }
  const verifierTrustRoot = await hashVerifierTrustSetV1([verifier])
  const unsignedPolicy: Omit<OutcomeVerifierTrustPolicyV1, 'signature'> = {
    schema_version: '1.0.0',
    policy_kind: 'AEGIS_OUTCOME_VERIFIER_TRUST_POLICY_V1',
    governed_policy_root: H('3'),
    verifier_trust_root: verifierTrustRoot,
    verifiers: [verifier],
    signer_key_id: 'operator-test-key',
    signer_public_key: operatorKeypair.publicKey,
  }
  const policy: OutcomeVerifierTrustPolicyV1 = {
    ...unsignedPolicy,
    signature: await signBytes(
      operatorKeypair.privateKey,
      await canonicalizeOutcomeVerifierTrustPolicyMessageV1(unsignedPolicy),
    ),
  }
  const anchor = await verifyOutcomeVerifierTrustPolicyV1(
    policy,
    H('3'),
    operatorKeypair.publicKey,
  )
  return { verifierKeypair, verifier, anchor }
}

async function snapshot(
  verifierTrustRoot: SHA256Hex,
  overrides: Partial<SelfModelStateComponents> = {},
): Promise<SelfModelSnapshot> {
  const components: SelfModelStateComponents = {
    identity_root: H('2'),
    policy_root: H('3'),
    capability_root: H('4'),
    memory_root: H('5'),
    metacognition_root: METACOGNITION_GENESIS_HASH,
    verifier_trust_root: verifierTrustRoot,
    health: {
      t0_verdict: true,
      corruption_count: 0,
      membrane_intact: true,
      entropy_bounded: true,
    },
    ...overrides,
  }
  return { state_root: await hashSelfModelStateRootV1(components), ...components }
}

function proposal(
  parentStateRoot: SHA256Hex,
  overrides: Partial<AdaptationProposal> = {},
): AdaptationProposal {
  return {
    proposal_id: 'proposal.outcome.001',
    objective: 'Close the bounded adaptation outcome loop.',
    consequence_class: 'D2',
    expected_parent_state_root: parentStateRoot,
    addressed_gap_ids: [GAP.gap_id],
    requested_capabilities: ['repo.file.propose'],
    mutations: [{ path: 'src/metacognition/outcome-comparator.ts', operation: 'CREATE' }],
    verification_steps: ['unit', 'integration'],
    rollback_reference: 'git:revert-candidate',
    ...overrides,
  }
}

function verification(verifierIdentityRoot: SHA256Hex): readonly VerificationObservation[] {
  return [0, 1].map(step_index => ({
    step_index,
    verdict: 'PASS' as const,
    evidence_digest: step_index === 0 ? H('a') : H('c'),
    verifier_identity_root: verifierIdentityRoot,
    verification_mode: 'INDEPENDENT' as const,
  }))
}

async function admittedAuthority(
  baselineSnapshot: SelfModelSnapshot,
  baselineGaps: readonly KnowledgeGap[],
  adaptation: AdaptationProposal,
  overrides: Partial<AdaptationAuthorityEvidenceV1> = {},
): Promise<AdaptationAuthorityEvidenceV1> {
  const regulation = await regulateSelf({
    snapshot: baselineSnapshot,
    gaps: baselineGaps,
    proposal: adaptation,
  })
  if (regulation.proposal_digest === null) throw new Error('fixture proposal digest unavailable')
  const action_binding = {
    proposal_digest: regulation.proposal_digest,
    self_regulation_decision_digest: regulation.decision_digest,
    expected_parent_state_root: adaptation.expected_parent_state_root,
  }
  return {
    evidence_kind: 'AUTOMATON3_AUTHORITY_DECISION_V1',
    outcome: 'ADMITTED',
    denial_codes: [],
    execution_identity_root: baselineSnapshot.identity_root,
    workspace_binding: H('7'),
    policy_root: baselineSnapshot.policy_root,
    registry_root: baselineSnapshot.capability_root,
    policy_decision_root: H('8'),
    authority_receipt_root: H('9'),
    executor_principal_root: EXECUTOR_PRINCIPAL,
    executor_workload_identity_root: EXECUTOR_WORKLOAD,
    action_binding,
    requested_action_digest: await hashAdaptationAuthorityBinding(action_binding),
    ...overrides,
  }
}

function terminal(
  authority: AdaptationAuthorityEvidenceV1,
  baselineStateRoot: SHA256Hex,
  postStateRoot: SHA256Hex,
  overrides: Partial<TerminalExecutionEvidenceV1> = {},
): TerminalExecutionEvidenceV1 {
  return {
    evidence_kind: 'AUTOMATON3_TERMINAL_EXECUTION_V1',
    execution_identity_root: authority.execution_identity_root,
    workspace_binding: authority.workspace_binding,
    policy_decision_root: authority.policy_decision_root,
    authority_receipt_root: authority.authority_receipt_root,
    requested_action_digest: authority.requested_action_digest,
    lease_outcome: 'ADMITTED',
    lease_authorization_receipt_root: H('e'),
    durable_execution_root: H('f'),
    durable_status: 'COMPLETED',
    mutation_receipt_root: H('a'),
    receipt_chain_status: 'VERIFIED',
    receipt_chain_verification_root: H('b'),
    outcome: 'SUCCEEDED',
    pre_state_root: baselineStateRoot,
    post_state_root: postStateRoot,
    provider_result_digest: H('c'),
    operator_notification_root: H('d'),
    ...overrides,
  }
}

async function certify(
  input: AdaptationOutcomeInput,
  trust: TrustContext,
): Promise<AdaptationOutcomeInput> {
  const { evidence_certificate: _existingCertificate, ...unsignedInput } = input
  const evidenceBundleDigest = await hashOutcomeEvidenceBundleV1(unsignedInput)
  const unsignedCertificate: Omit<OutcomeEvidenceCertificateV1, 'signature'> = {
    certificate_kind: 'AEGIS_OUTCOME_EVIDENCE_CERTIFICATE_V1',
    verifier_key_id: trust.verifier.verifier_key_id,
    verifier_public_key: trust.verifier.verifier_public_key,
    verifier_identity_root: trust.verifier.verifier_identity_root,
    verifier_principal_root: trust.verifier.verifier_principal_root,
    verifier_workload_identity_root: trust.verifier.verifier_workload_identity_root,
    evidence_bundle_digest: evidenceBundleDigest,
  }
  return {
    ...unsignedInput,
    evidence_certificate: {
      ...unsignedCertificate,
      signature: await signBytes(
        trust.verifierKeypair.privateKey,
        canonicalizeOutcomeEvidenceCertificateMessageV1(unsignedCertificate),
      ),
    },
  }
}

async function fixture(providedTrust?: TrustContext): Promise<Fixture> {
  const trust = providedTrust ?? await trustContext()
  const baselineSnapshot = await snapshot(trust.anchor.verifier_trust_root)
  const postSnapshot = await snapshot(trust.anchor.verifier_trust_root, {
    capability_root: H('a'),
  })
  const adaptation = proposal(baselineSnapshot.state_root)
  const authority = await admittedAuthority(baselineSnapshot, [GAP], adaptation)
  const unsigned: AdaptationOutcomeInput = {
    baseline: { snapshot: baselineSnapshot, gaps: [GAP], proposal: adaptation },
    authority,
    terminal_execution: terminal(
      authority,
      baselineSnapshot.state_root,
      postSnapshot.state_root,
    ),
    post_snapshot: postSnapshot,
    post_gaps: [],
    verification: verification(trust.verifier.verifier_identity_root),
  }
  return { input: await certify(unsigned, trust), trust }
}

describe('assessAdaptationOutcome', () => {
  it('proposes preservation only for an independently verified terminal success', async () => {
    const { input, trust } = await fixture()
    const assessment = await assessAdaptationOutcome(input, trust.anchor)
    expect(assessment.state_disposition).toBe('PRESERVE')
    expect(assessment.evidence_disposition).toBe('CONFIRM')
    expect(assessment.learning_evidence_eligible).toBe(true)
    expect(assessment.required_next_gate).toBe('AUTOMATON_3')
    expect(assessment.grants_authority).toBe(false)
    expect(assessment.executes_mutation).toBe(false)
    expect(assessment.updates_competence).toBe(false)
    expect(assessment.verifier_trust_policy_digest).toBe(trust.anchor.trust_policy_digest)
  })

  it('cannot learn from Automaton-3 authorization evidence alone', async () => {
    const { input, trust } = await fixture()
    const { terminal_execution: _terminal, evidence_certificate: _certificate, ...rest } = input
    const authorizationOnly = await certify({
      ...rest,
      post_snapshot: input.baseline.snapshot,
      post_gaps: input.baseline.gaps,
      verification: [],
    }, trust)
    const assessment = await assessAdaptationOutcome(authorizationOnly, trust.anchor)
    expect(assessment.state_disposition).toBe('NO_STATE_CHANGE')
    expect(assessment.learning_evidence_eligible).toBe(false)
    expect(assessment.reason_codes).toContain('TERMINAL_EXECUTION_EVIDENCE_MISSING')
  })

  it('cannot preserve terminal root claims without a verifier certificate', async () => {
    const { input, trust } = await fixture()
    const { evidence_certificate: _certificate, ...uncertified } = input
    const assessment = await assessAdaptationOutcome(uncertified, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.evidence_disposition).toBe('INCONCLUSIVE')
    expect(assessment.reason_codes).toContain('EVIDENCE_CERTIFICATE_MISSING')
  })

  it('does not accept a caller-constructed trust anchor', async () => {
    const { input, trust } = await fixture()
    await expect(assessAdaptationOutcome(input, { ...trust.anchor })).rejects.toThrow(
      'verifier trust anchor was not authenticated',
    )
  })

  it('rejects a trust policy signed by a key other than the expected operator key', async () => {
    const operator = await generateKeypair(new Uint8Array(32).fill(41))
    const attacker = await generateKeypair(new Uint8Array(32).fill(42))
    const verifier = await generateKeypair(new Uint8Array(32).fill(43))
    const verifierIdentity: OutcomeVerifierIdentityV1 = {
      verifier_key_id: 'rogue-verifier',
      verifier_public_key: verifier.publicKey,
      verifier_identity_root: await hashVerifierIdentityV1(verifier.publicKey),
      verifier_principal_root: H('1'),
      verifier_workload_identity_root: H('2'),
    }
    const unsigned: Omit<OutcomeVerifierTrustPolicyV1, 'signature'> = {
      schema_version: '1.0.0',
      policy_kind: 'AEGIS_OUTCOME_VERIFIER_TRUST_POLICY_V1',
      governed_policy_root: H('3'),
      verifier_trust_root: await hashVerifierTrustSetV1([verifierIdentity]),
      verifiers: [verifierIdentity],
      signer_key_id: 'attacker-key',
      signer_public_key: attacker.publicKey,
    }
    const policy: OutcomeVerifierTrustPolicyV1 = {
      ...unsigned,
      signature: await signBytes(
        attacker.privateKey,
        await canonicalizeOutcomeVerifierTrustPolicyMessageV1(unsigned),
      ),
    }
    await expect(verifyOutcomeVerifierTrustPolicyV1(
      policy,
      H('3'),
      operator.publicKey,
    )).rejects.toThrow('trust policy signer is not the expected operator key')
  })

  it('treats an authority denial with unchanged state as inconclusive evidence', async () => {
    const { input, trust } = await fixture()
    const denied = await admittedAuthority(
      input.baseline.snapshot,
      input.baseline.gaps,
      input.baseline.proposal,
      { outcome: 'DENIED', denial_codes: ['APPROVAL_MISSING'] },
    )
    const { terminal_execution: _terminal, evidence_certificate: _certificate, ...rest } = input
    const deniedInput = await certify({
      ...rest,
      authority: denied,
      post_snapshot: input.baseline.snapshot,
      post_gaps: input.baseline.gaps,
      verification: [],
    }, trust)
    const assessment = await assessAdaptationOutcome(deniedInput, trust.anchor)
    expect(assessment.state_disposition).toBe('NO_STATE_CHANGE')
    expect(assessment.reason_codes).toContain('AUTHORITY_DENIED')
  })

  it('proposes reversion when a changed state lacks complete verification', async () => {
    const { input, trust } = await fixture()
    const incomplete = await certify({ ...input, verification: [input.verification[0]!] }, trust)
    const assessment = await assessAdaptationOutcome(incomplete, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.reason_codes).toContain('VERIFICATION_COVERAGE_INCOMPLETE')
  })

  it('degrades evidence after a terminal execution failure', async () => {
    const { input, trust } = await fixture()
    const failed = await certify({
      ...input,
      terminal_execution: terminal(
        input.authority,
        input.baseline.snapshot.state_root,
        input.post_snapshot.state_root,
        { outcome: 'FAILED', durable_status: 'FAILED' },
      ),
    }, trust)
    const assessment = await assessAdaptationOutcome(failed, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.evidence_disposition).toBe('DEGRADE')
  })

  it('treats a completed rollback to the parent as no state change', async () => {
    const { input, trust } = await fixture()
    const rolledBack = await certify({
      ...input,
      terminal_execution: terminal(
        input.authority,
        input.baseline.snapshot.state_root,
        input.baseline.snapshot.state_root,
        { outcome: 'ROLLED_BACK', durable_status: 'COMPLETED' },
      ),
      post_snapshot: input.baseline.snapshot,
      post_gaps: [GAP],
    }, trust)
    const assessment = await assessAdaptationOutcome(rolledBack, trust.anchor)
    expect(assessment.state_disposition).toBe('NO_STATE_CHANGE')
    expect(assessment.reason_codes).toContain('EXECUTION_ROLLED_BACK')
  })

  it('proposes reversion when post-state health is unsafe', async () => {
    const { input, trust } = await fixture()
    const unsafePost = await snapshot(trust.anchor.verifier_trust_root, {
      capability_root: H('a'),
      health: { ...input.post_snapshot.health, membrane_intact: false },
    })
    const unsafe = await certify({
      ...input,
      post_snapshot: unsafePost,
      terminal_execution: terminal(
        input.authority,
        input.baseline.snapshot.state_root,
        unsafePost.state_root,
      ),
    }, trust)
    const assessment = await assessAdaptationOutcome(unsafe, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.reason_codes).toContain('POST_STATE_UNHEALTHY')
  })

  it('does not learn from executor self-reported verification', async () => {
    const { input, trust } = await fixture()
    const selfReported = await certify({
      ...input,
      verification: input.verification.map((item, index) =>
        index === 0 ? { ...item, verification_mode: 'EXECUTOR_SELF_REPORT' } : item),
    }, trust)
    const assessment = await assessAdaptationOutcome(selfReported, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.learning_evidence_eligible).toBe(false)
    expect(assessment.reason_codes).toContain('VERIFICATION_NOT_INDEPENDENT')
  })

  it('requires distinct verifier principals and workloads', async () => {
    const samePrincipalTrust = await trustContext(EXECUTOR_PRINCIPAL, EXECUTOR_WORKLOAD)
    const { input } = await fixture(samePrincipalTrust)
    const assessment = await assessAdaptationOutcome(input, samePrincipalTrust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.reason_codes).toContain('EVIDENCE_VERIFIER_PRINCIPAL_NOT_INDEPENDENT')
    expect(assessment.reason_codes).toContain('EVIDENCE_VERIFIER_WORKLOAD_NOT_INDEPENDENT')
  })

  it('rejects unresolved executor and verifier identity roots', async () => {
    const { input, trust } = await fixture()
    await expect(assessAdaptationOutcome({
      ...input,
      authority: { ...input.authority, executor_principal_root: H('0') },
    }, trust.anchor)).rejects.toThrow('must resolve to a non-zero identity or evidence root')
    await expect(trustContext(H('0'), VERIFIER_WORKLOAD)).rejects.toThrow(
      'must resolve to a non-zero identity or evidence root',
    )
    await expect(trustContext(VERIFIER_PRINCIPAL, H('0'))).rejects.toThrow(
      'must resolve to a non-zero identity or evidence root',
    )
  })

  it('blocks D2 policy-root transitions even when the evidence is signed', async () => {
    const { input, trust } = await fixture()
    const post = await snapshot(trust.anchor.verifier_trust_root, {
      policy_root: H('f'),
      capability_root: H('a'),
    })
    const changed = await certify({
      ...input,
      post_snapshot: post,
      terminal_execution: terminal(
        input.authority,
        input.baseline.snapshot.state_root,
        post.state_root,
      ),
    }, trust)
    const assessment = await assessAdaptationOutcome(changed, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.reason_codes).toContain('POLICY_TRANSITION_REQUIRES_D4')
  })

  it('does not accept trust-root rotation based only on a D4 label', async () => {
    const { input, trust } = await fixture()
    const d4Proposal = proposal(input.baseline.snapshot.state_root, {
      consequence_class: 'D4',
      operator_approval_reference: 'approval:operator',
      constitutional_change_reference: 'constitution:change-001',
    })
    const authority = await admittedAuthority(input.baseline.snapshot, [GAP], d4Proposal)
    const post = await snapshot(H('f'), { capability_root: H('a') })
    const rotated = await certify({
      ...input,
      baseline: { ...input.baseline, proposal: d4Proposal },
      authority,
      post_snapshot: post,
      terminal_execution: terminal(
        authority,
        input.baseline.snapshot.state_root,
        post.state_root,
      ),
    }, trust)
    const assessment = await assessAdaptationOutcome(rotated, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.reason_codes).toContain('VERIFIER_TRUST_ROTATION_EVIDENCE_REQUIRED')
  })

  it('proposes reversion for new or unaddressed critical invariant gaps', async () => {
    const { input, trust } = await fixture()
    const criticalGap: KnowledgeGap = {
      gap_id: 'gap.outcome.critical',
      kind: 'INVARIANT_BREACH',
      severity: 'CRITICAL',
      evidence_refs: [H('f')],
    }
    const withGap = await certify({ ...input, post_gaps: [criticalGap] }, trust)
    const assessment = await assessAdaptationOutcome(withGap, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.reason_codes).toContain('UNSAFE_POST_GAP')
  })

  it('does not preserve evidence with broken terminal bindings', async () => {
    const { input, trust } = await fixture()
    const broken = await certify({
      ...input,
      terminal_execution: terminal(
        input.authority,
        input.baseline.snapshot.state_root,
        input.post_snapshot.state_root,
        { policy_decision_root: H('6') },
      ),
    }, trust)
    const assessment = await assessAdaptationOutcome(broken, trust.anchor)
    expect(assessment.state_disposition).toBe('REVERT')
    expect(assessment.reason_codes).toContain('TERMINAL_POLICY_DECISION_MISMATCH')
  })

  it('rejects duplicate and out-of-range verification step indices', async () => {
    const { input, trust } = await fixture()
    await expect(assessAdaptationOutcome({
      ...input,
      verification: [input.verification[0]!, { ...input.verification[1]!, step_index: 0 }],
    }, trust.anchor)).rejects.toThrow(OutcomeComparisonError)
    await expect(assessAdaptationOutcome({
      ...input,
      verification: [{ ...input.verification[0]!, step_index: 2 }],
    }, trust.anchor)).rejects.toThrow(OutcomeComparisonError)
  })

  it('is deterministic across semantically equivalent verification ordering', async () => {
    const { input, trust } = await fixture()
    const reversed = await certify({
      ...input,
      verification: [...input.verification].reverse(),
    }, trust)
    const [first, second] = await Promise.all([
      assessAdaptationOutcome(input, trust.anchor),
      assessAdaptationOutcome(reversed, trust.anchor),
    ])
    expect(first.assessment_digest).toBe(second.assessment_digest)
    expect(Object.isFrozen(first)).toBe(true)
  })

  it('reassesses signed evidence inside the append boundary', async () => {
    const { input, trust } = await fixture()
    const { artifacts, store } = memoryArtifactStore()
    const tamperedAfterSigning = {
      ...input,
      post_gaps: [{
        gap_id: 'gap.forged-after-signing',
        kind: 'INVARIANT_BREACH' as const,
        severity: 'CRITICAL' as const,
        evidence_refs: [H('f')],
      }],
    }
    const observed = await recordOutcomeAssessment(
      MetacognitiveLoop.empty(),
      tamperedAfterSigning,
      trust.anchor,
      store,
      SEQ(1),
    )
    expect(observed.assessment.state_disposition).toBe('REVERT')
    expect(observed.assessment.evidence_certificate_verified).toBe(false)
    expect(observed.assessment.reason_codes).toContain('EVIDENCE_BUNDLE_DIGEST_MISMATCH')
    expect(artifacts.get(observed.artifact.artifact_root)).toBe(observed.artifact)
    expect(observed.persistence.artifact_reference).toBe(
      `memory:${observed.artifact.artifact_root}`,
    )
    expect(observed.entry.observation.signal).toContain(observed.artifact.artifact_root)
  })

  it('does not append when outcome evidence persistence fails or lies about the root', async () => {
    const { input, trust } = await fixture()
    const loop = MetacognitiveLoop.empty()
    const failingStore: OutcomeEvidenceArtifactStore = {
      async persist() { throw new Error('store unavailable') },
    }
    await expect(recordOutcomeAssessment(
      loop,
      input,
      trust.anchor,
      failingStore,
      SEQ(1),
    )).rejects.toThrow('outcome evidence persistence failed')
    expect(loop.length).toBe(0)

    const mismatchedStore: OutcomeEvidenceArtifactStore = {
      async persist() {
        return { artifact_root: H('f'), artifact_reference: `memory:${H('f')}` }
      },
    }
    await expect(recordOutcomeAssessment(
      loop,
      input,
      trust.anchor,
      mismatchedStore,
      SEQ(1),
    )).rejects.toThrow('outcome evidence persistence root mismatch')
    expect(loop.length).toBe(0)
  })
})
