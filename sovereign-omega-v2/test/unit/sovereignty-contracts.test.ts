import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  SOVEREIGNTY_SCHEMA_VERSION,
  assertCanonicalStateRootV1,
  canonicalizeSovereigntyRecordV1,
  computeCanonicalStateRootV1,
  hashSovereigntyRecordV1,
  type ApprovalRecordV1,
  type CanonicalStateRootV1,
} from '../../src/sovereignty/contracts.js'

const hash = (digit: string): SHA256Hex => digit.repeat(64) as SHA256Hex

const canonicalState: CanonicalStateRootV1 = {
  schema_version: SOVEREIGNTY_SCHEMA_VERSION,
  repository_commit: '1'.repeat(40),
  repository_tree: '2'.repeat(40),
  constitutional_bundle_hash: hash('3'),
  claims_ledger_root: hash('4'),
  policy_hash: hash('5'),
  deployed_artifact_hash: hash('6'),
  workflow_identity_hash: hash('7'),
  environment_hash: hash('8'),
  signing_identity_hash: hash('9'),
  parent_state_root: hash('0'),
  sequence: '42',
}

describe('operator-sovereignty contracts v1', () => {
  it('produces the pinned canonical state root golden vector', async () => {
    await expect(computeCanonicalStateRootV1(canonicalState)).resolves.toBe(
      'fc66f65381026848fd5a5601d387848ae4efdf78510d66abba488113088eaf3a',
    )
  })

  it('is invariant to JavaScript object insertion order', () => {
    const reordered = {
      sequence: '42',
      parent_state_root: hash('0'),
      signing_identity_hash: hash('9'),
      environment_hash: hash('8'),
      workflow_identity_hash: hash('7'),
      deployed_artifact_hash: hash('6'),
      policy_hash: hash('5'),
      claims_ledger_root: hash('4'),
      constitutional_bundle_hash: hash('3'),
      repository_tree: '2'.repeat(40),
      repository_commit: '1'.repeat(40),
      schema_version: SOVEREIGNTY_SCHEMA_VERSION,
    } satisfies CanonicalStateRootV1

    expect(canonicalizeSovereigntyRecordV1('CANONICAL_STATE_ROOT_V1', reordered)).toEqual(
      canonicalizeSovereigntyRecordV1('CANONICAL_STATE_ROOT_V1', canonicalState),
    )
  })

  it('domain-separates records with identical field values', async () => {
    const approval: ApprovalRecordV1 = {
      schema_version: SOVEREIGNTY_SCHEMA_VERSION,
      approval_id: 'approval-1',
      request_hash: hash('a'),
      authority_domain: 'github:refs/heads/main',
      state: 'APPROVED',
      operator_actor_id: 'operator-1',
      operator_session_id: 'session-1',
      decision_reason_hash: hash('b'),
      decided_at: '2026-07-18T22:00:00Z',
      expires_at: null,
      signer_key_id: 'operator-key-1',
      signature: 'ab'.repeat(64),
    }

    const approvalHash = await hashSovereigntyRecordV1('APPROVAL_RECORD_V1', approval)
    const wrongDomainHash = await hashSovereigntyRecordV1('OPERATOR_NOTIFICATION_V1', approval)
    expect(approvalHash).not.toBe(wrongDomainHash)
  })

  it('fails closed on malformed roots and non-canonical sequences', () => {
    expect(() => assertCanonicalStateRootV1({ ...canonicalState, repository_commit: 'abc' })).toThrow(
      'repository_commit must be a lowercase Git object id',
    )
    expect(() => assertCanonicalStateRootV1({ ...canonicalState, policy_hash: 'A'.repeat(64) as SHA256Hex })).toThrow(
      'policy_hash must be lowercase SHA-256 hex',
    )
    expect(() => assertCanonicalStateRootV1({ ...canonicalState, sequence: '042' })).toThrow(
      'sequence must be a canonical unsigned decimal string',
    )
  })
})
