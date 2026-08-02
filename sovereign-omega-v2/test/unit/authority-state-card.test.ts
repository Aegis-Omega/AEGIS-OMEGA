import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  computeAuthorityCardCanonicalHash,
  validateAuthorityStateCardV2,
  type AuthorityStateCardV2,
} from '../../src/sovereignty/authority-state-card.js'

const hash = (digit: string): SHA256Hex => digit.repeat(64) as SHA256Hex

function baseCard(): AuthorityStateCardV2 {
  return {
    schema_version: '2.0.0',
    subject_binding: {
      repository: 'Aegis-Omega/AEGIS-OMEGA',
      candidate_commit: '1'.repeat(40),
      candidate_tree: '2'.repeat(40),
      expected_parent_sha: '3'.repeat(40),
      expected_parent_state_root: hash('4'),
      policy: { path: 'policy.md', blob_id: '5'.repeat(40) },
      claims_ledger: { path: 'claims.json', root: hash('6') },
      admission_workflow: { path: 'admission.yml', blob_id: '7'.repeat(40) },
      admission_executable: { path: 'validate.ts', blob_id: '8'.repeat(40) },
    },
    authority_state: { current: 'REVIEW', must_not: ['MUTATE', 'DEPLOY'] },
    claims: {
      implementation_present: {
        value: true,
        origin_class: 'COMPUTED',
        source: { kind: 'git-blob', locator: 'src/file.ts', digest_or_id: '9'.repeat(40) },
        verifier: { identity: 'git-object-verifier-v1', execution_reference: 'run:1', result: 'PASS' },
        blocking: true,
      },
    },
    verification_matrix: Object.fromEntries(
      [
        'schema_validation',
        'subject_binding',
        'source_entailment',
        'canonicalization',
        'exact_head_tests',
        'ledger_synchronization',
        'independent_replay',
      ].map((id) => [
        id,
        {
          mandatory: true as const,
          status: 'PASS' as const,
          command_or_verifier: id,
          execution_reference: `run:${id}`,
          artifact_digest: hash('a'),
        },
      ]),
    ),
    source_entailment: [
      {
        claim_id: 'implementation_present',
        source_locator: 'src/file.ts',
        source_digest: hash('b'),
        verifier: 'source-entails-v1:run:1',
        status: 'PASS',
      },
    ],
    replay_verifiability: {
      status: 'PASS',
      verified_at: '2026-08-02T09:00:00.000Z',
      valid_until: '2026-08-02T12:00:00.000Z',
      custody_manifest: {
        path: 'evidence/custody.json',
        digest: hash('c'),
        custodian: 'github-actions-artifact',
        availability_status: 'AVAILABLE',
      },
      replay_package_digest: hash('d'),
    },
    audit_ledger: {
      root: hash('e'),
      synchronization: {
        status: 'PASS',
        verifier: 'independent-ledger-replay-v1',
        execution_reference: 'run:ledger:1',
        compared_roots: [hash('e'), hash('e')],
      },
    },
    attestation: {
      canonicalization: 'RFC8785_JCS',
      preimage_rule:
        'canonicalize the complete card after replacing /attestation/canonical_hash and /attestation/signature with null',
      canonical_hash: null,
      signer: 'github-oidc:key-1',
      signature: 'signed-attestation',
    },
    external_anchor: {
      status: 'PRESENT',
      provider: 'github-pr-comment',
      locator: 'comment:1',
      anchored_hash: null,
      anchored_at: '2026-08-02T09:10:00.000Z',
    },
    deployment_decision: {
      value: 'APPROVE',
      computed_by: 'authority-card-validator-v2',
      execution_reference: 'run:decision:1',
      rule:
        'APPROVE iff every mandatory verification is PASS, every source_entailment status is PASS, replay is PASS and unexpired, ledger synchronization is PASS, attestation hash and signature exist, and an external anchor is PRESENT',
    },
  }
}

async function completeCard(): Promise<AuthorityStateCardV2> {
  const card = baseCard()
  const canonicalHash = await computeAuthorityCardCanonicalHash(card)
  return {
    ...card,
    attestation: { ...card.attestation, canonical_hash: canonicalHash },
    external_anchor: { ...card.external_anchor, anchored_hash: canonicalHash },
  }
}

describe('authority state card v2', () => {
  it('rejects APPROVE when every mandatory verifier is NOT_RUN', async () => {
    const card = await completeCard()
    const verification_matrix = Object.fromEntries(
      Object.entries(card.verification_matrix).map(([id, entry]) => [
        id,
        { ...entry, status: 'NOT_RUN' as const, execution_reference: null, artifact_digest: null },
      ]),
    )

    const result = await validateAuthorityStateCardV2(
      { ...card, verification_matrix },
      '2026-08-02T10:00:00.000Z',
    )

    expect(result.valid).toBe(false)
    expect(result.decision).toBe('DENY')
    expect(result.failures).toContain('MANDATORY_CHECK_NOT_RUN:exact_head_tests')
    expect(result.failures).toContain('APPROVE_WITH_UNSATISFIED_GATES')
  })

  it('rejects a declared claim when it is load-bearing', async () => {
    const card = await completeCard()
    const result = await validateAuthorityStateCardV2(
      {
        ...card,
        claims: {
          implementation_present: {
            ...card.claims['implementation_present']!,
            origin_class: 'DECLARED',
          },
        },
      },
      '2026-08-02T10:00:00.000Z',
    )

    expect(result.valid).toBe(false)
    expect(result.failures).toContain('BLOCKING_CLAIM_DECLARED:implementation_present')
  })

  it('rejects replay after its custody-bound validity window', async () => {
    const card = await completeCard()
    const result = await validateAuthorityStateCardV2(card, '2026-08-02T12:00:00.001Z')

    expect(result.valid).toBe(false)
    expect(result.failures).toContain('REPLAY_EXPIRED')
  })

  it('accepts APPROVE only when all blocking gates and anchors pass', async () => {
    const card = await completeCard()
    const result = await validateAuthorityStateCardV2(card, '2026-08-02T10:00:00.000Z')

    expect(result.valid).toBe(true)
    expect(result.decision).toBe('APPROVE')
    expect(result.failures).toEqual([])
  })
})
