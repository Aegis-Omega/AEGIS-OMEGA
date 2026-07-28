import { describe, expect, it } from 'vitest'
import type { SequenceNumber, SHA256Hex } from '../../src/core/types.js'
import { generateKeypair, signBytes } from '../../src/consensus/crypto.js'
import {
  METACOGNITION_GENESIS_HASH,
  MetacognitiveLoop,
  certifyMetacognitiveLoop,
} from '../../src/metacognition/loop.js'
import {
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
  AdaptationOutcomeInput,
  OutcomeEvidenceArtifactV1,
  OutcomeEvidenceCertificateV1,
  OutcomeVerifierIdentityV1,
  OutcomeVerifierTrustPolicyV1,
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

async function selfModel(
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

describe('metacognitive adaptation outcome closure', () => {
  it('reassesses signed evidence, appends it, and reanchors the next self-model', async () => {
    const operatorKeypair = await generateKeypair(new Uint8Array(32).fill(29))
    const verifierKeypair = await generateKeypair(new Uint8Array(32).fill(31))
    const verifier: OutcomeVerifierIdentityV1 = {
      verifier_key_id: 'metacognitive-closure-test-verifier',
      verifier_public_key: verifierKeypair.publicKey,
      verifier_identity_root: await hashVerifierIdentityV1(verifierKeypair.publicKey),
      verifier_principal_root: H('a'),
      verifier_workload_identity_root: H('b'),
    }
    const verifierTrustRoot = await hashVerifierTrustSetV1([verifier])
    const unsignedTrustPolicy: Omit<OutcomeVerifierTrustPolicyV1, 'signature'> = {
      schema_version: '1.0.0',
      policy_kind: 'AEGIS_OUTCOME_VERIFIER_TRUST_POLICY_V1',
      governed_policy_root: H('3'),
      verifier_trust_root: verifierTrustRoot,
      verifiers: [verifier],
      signer_key_id: 'closure-operator-key',
      signer_public_key: operatorKeypair.publicKey,
    }
    const trustPolicy: OutcomeVerifierTrustPolicyV1 = {
      ...unsignedTrustPolicy,
      signature: await signBytes(
        operatorKeypair.privateKey,
        await canonicalizeOutcomeVerifierTrustPolicyMessageV1(unsignedTrustPolicy),
      ),
    }
    const trustAnchor = await verifyOutcomeVerifierTrustPolicyV1(
      trustPolicy,
      H('3'),
      operatorKeypair.publicKey,
    )

    const gap: KnowledgeGap = {
      gap_id: 'gap.closure.001',
      kind: 'CAPABILITY_DEFICIT',
      severity: 'HIGH',
      evidence_refs: [H('8')],
    }
    const baseline = await selfModel(verifierTrustRoot)
    const proposal: AdaptationProposal = {
      proposal_id: 'proposal.closure.001',
      objective: 'Exercise the governed outcome-learning closure.',
      consequence_class: 'D2',
      expected_parent_state_root: baseline.state_root,
      addressed_gap_ids: [gap.gap_id],
      requested_capabilities: ['repo.file.propose'],
      mutations: [{ path: 'src/metacognition/outcome-comparator.ts', operation: 'CREATE' }],
      verification_steps: ['closure integration'],
      rollback_reference: 'git:revert-candidate',
    }
    const regulation = await regulateSelf({ snapshot: baseline, gaps: [gap], proposal })
    expect(regulation.mode).toBe('READY_FOR_AUTHORITY')
    if (regulation.proposal_digest === null) throw new Error('proposal digest unavailable')

    const action_binding = {
      proposal_digest: regulation.proposal_digest,
      self_regulation_decision_digest: regulation.decision_digest,
      expected_parent_state_root: baseline.state_root,
    }
    const authority = {
      evidence_kind: 'AUTOMATON3_AUTHORITY_DECISION_V1' as const,
      outcome: 'ADMITTED' as const,
      denial_codes: [],
      execution_identity_root: baseline.identity_root,
      workspace_binding: H('7'),
      policy_root: baseline.policy_root,
      registry_root: baseline.capability_root,
      policy_decision_root: H('8'),
      authority_receipt_root: H('9'),
      executor_principal_root: H('c'),
      executor_workload_identity_root: H('d'),
      action_binding,
      requested_action_digest: await hashAdaptationAuthorityBinding(action_binding),
    }
    const post = await selfModel(verifierTrustRoot, { capability_root: H('9') })
    const unsignedInput: AdaptationOutcomeInput = {
      baseline: { snapshot: baseline, gaps: [gap], proposal },
      authority,
      terminal_execution: {
        evidence_kind: 'AUTOMATON3_TERMINAL_EXECUTION_V1',
        execution_identity_root: authority.execution_identity_root,
        workspace_binding: authority.workspace_binding,
        policy_decision_root: authority.policy_decision_root,
        authority_receipt_root: authority.authority_receipt_root,
        requested_action_digest: authority.requested_action_digest,
        lease_outcome: 'ADMITTED',
        lease_authorization_receipt_root: H('a'),
        durable_execution_root: H('b'),
        durable_status: 'COMPLETED',
        mutation_receipt_root: H('c'),
        receipt_chain_status: 'VERIFIED',
        receipt_chain_verification_root: H('d'),
        outcome: 'SUCCEEDED',
        pre_state_root: baseline.state_root,
        post_state_root: post.state_root,
        provider_result_digest: H('e'),
        operator_notification_root: H('f'),
      },
      post_snapshot: post,
      post_gaps: [],
      verification: [{
        step_index: 0,
        verdict: 'PASS',
        evidence_digest: H('a'),
        verifier_identity_root: verifier.verifier_identity_root,
        verification_mode: 'INDEPENDENT',
      }],
    }
    const evidenceBundleDigest = await hashOutcomeEvidenceBundleV1(unsignedInput)
    const unsignedCertificate: Omit<OutcomeEvidenceCertificateV1, 'signature'> = {
      certificate_kind: 'AEGIS_OUTCOME_EVIDENCE_CERTIFICATE_V1',
      verifier_key_id: verifier.verifier_key_id,
      verifier_public_key: verifier.verifier_public_key,
      verifier_identity_root: verifier.verifier_identity_root,
      verifier_principal_root: verifier.verifier_principal_root,
      verifier_workload_identity_root: verifier.verifier_workload_identity_root,
      evidence_bundle_digest: evidenceBundleDigest,
    }
    const input: AdaptationOutcomeInput = {
      ...unsignedInput,
      evidence_certificate: {
        ...unsignedCertificate,
        signature: await signBytes(
          verifierKeypair.privateKey,
          canonicalizeOutcomeEvidenceCertificateMessageV1(unsignedCertificate),
        ),
      },
    }

    const observed = await recordOutcomeAssessment(
      MetacognitiveLoop.empty(),
      input,
      trustAnchor,
      {
        async persist(artifact: OutcomeEvidenceArtifactV1) {
          return {
            artifact_root: artifact.artifact_root,
            artifact_reference: `memory:${artifact.artifact_root}`,
          }
        },
      },
      SEQ(1),
    )
    expect(observed.assessment.state_disposition).toBe('PRESERVE')
    expect(observed.assessment.grants_authority).toBe(false)
    const certificate = await certifyMetacognitiveLoop(observed.loop.getAll())
    expect(certificate.is_valid).toBe(true)
    expect(observed.entry.observation.signal).toContain(observed.artifact.artifact_root)
    expect(observed.artifact.assessment.assessment_digest).toBe(
      observed.assessment.assessment_digest,
    )

    const reanchoredPost = await selfModel(verifierTrustRoot, {
      capability_root: post.capability_root,
      metacognition_root: observed.entry.entry_hash,
    })
    expect(reanchoredPost.state_root).not.toBe(post.state_root)
    const nextRegulation = await regulateSelf({ snapshot: reanchoredPost, gaps: [] })
    expect(nextRegulation.mode).toBe('NO_CHANGE')
  })
})
