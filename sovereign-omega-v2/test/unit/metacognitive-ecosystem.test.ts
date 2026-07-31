import { describe, expect, it } from 'vitest'
import {
  admitEcosystemIntentV1,
  assertEcosystemAdapterManifestV1,
  reconcileEcosystemEvidenceStateV1,
  type EcosystemAdapterManifestV1,
} from '../../src/scale-os/metacognitive-ecosystem.js'

function manifest(
  overrides: Partial<EcosystemAdapterManifestV1> = {},
): EcosystemAdapterManifestV1 {
  return {
    schema_version: '1.0.0',
    adapter_id: 'github-connector',
    adapter_kind: 'CONNECTOR',
    provider: 'GitHub',
    version: 'connector-v1',
    capabilities: [
      {
        capability_id: 'repository.read',
        description: 'Read repository state and evidence.',
        maximum_authority: 'OBSERVE',
        reversible: true,
        requires_operator_approval: false,
        requires_independent_verification: false,
      },
      {
        capability_id: 'repository.write',
        description: 'Write bounded repository changes.',
        maximum_authority: 'EXECUTE_CONSEQUENTIAL',
        reversible: false,
        requires_operator_approval: true,
        requires_independent_verification: true,
      },
    ],
    evidence_state: 'CONTENT_READ',
    source_locator: 'github:Aegis-Omega/AEGIS-OMEGA',
    content_digest: null,
    observed_at: '2026-07-31T19:00:00Z',
    ...overrides,
  }
}

describe('metacognitive ecosystem contract v1', () => {
  it('admits declared observation without inventing execution authority', () => {
    const decision = admitEcosystemIntentV1([manifest()], {
      intent_id: 'intent-read-1',
      requester_adapter_id: 'github-connector',
      capability_id: 'repository.read',
      requested_authority: 'OBSERVE',
      target: 'Aegis-Omega/AEGIS-OMEGA',
      evidence_refs: [],
      operator_approval_ref: null,
      independent_verification_ref: null,
    })

    expect(decision).toEqual({
      admitted: true,
      reason: 'ADMITTED',
      effective_authority: 'OBSERVE',
    })
  })

  it('denies consequential execution without operator approval', () => {
    const decision = admitEcosystemIntentV1([manifest()], {
      intent_id: 'intent-write-1',
      requester_adapter_id: 'github-connector',
      capability_id: 'repository.write',
      requested_authority: 'EXECUTE_CONSEQUENTIAL',
      target: 'branch:main',
      evidence_refs: ['receipt:repository-map'],
      operator_approval_ref: null,
      independent_verification_ref: 'verification:ci',
    })

    expect(decision.reason).toBe('OPERATOR_APPROVAL_REQUIRED')
    expect(decision.admitted).toBe(false)
  })

  it('denies consequential execution without independent verification', () => {
    const decision = admitEcosystemIntentV1([manifest()], {
      intent_id: 'intent-write-2',
      requester_adapter_id: 'github-connector',
      capability_id: 'repository.write',
      requested_authority: 'EXECUTE_CONSEQUENTIAL',
      target: 'branch:main',
      evidence_refs: ['receipt:repository-map'],
      operator_approval_ref: 'operator:explicit-approval',
      independent_verification_ref: null,
    })

    expect(decision.reason).toBe('INDEPENDENT_VERIFICATION_REQUIRED')
  })

  it('applies the weakest-link evidence rule across adapters', () => {
    expect(reconcileEcosystemEvidenceStateV1([
      'VERIFIED',
      'EXECUTED',
      'CONTENT_READ',
    ])).toBe('CONTENT_READ')
    expect(reconcileEcosystemEvidenceStateV1([
      'VERIFIED',
      'REJECTED',
    ])).toBe('REJECTED')
  })

  it('rejects consequential capabilities that do not require operator approval', () => {
    const invalid = manifest({
      capabilities: [{
        capability_id: 'unsafe.write',
        description: 'Invalid consequential capability.',
        maximum_authority: 'EXECUTE_CONSEQUENTIAL',
        reversible: false,
        requires_operator_approval: false,
        requires_independent_verification: true,
      }],
    })

    expect(() => assertEcosystemAdapterManifestV1(invalid)).toThrow(
      'consequential capability must require operator approval',
    )
  })
})
