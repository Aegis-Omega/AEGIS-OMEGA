import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildControlledFailureCase,
  evaluateFailureCaseObservation,
  type ControlledFailureCaseDraftV1,
} from '../src/lib/failureCase.ts'

function validDraft(): ControlledFailureCaseDraftV1 {
  return {
    case_id: 'FC-EXPIRED-APPROVAL-01',
    scope: {
      workflow_id: 'deploy-agent',
      workflow_version: 'staging-v1',
      environment: 'STAGING',
      action_class: 'DEPLOY',
      target_class: 'staging-service',
    },
    control: {
      control_point: 'pre-deploy authority check',
      authorization_requirement: 'approval bound to exact deployment digest',
    },
    test: {
      unauthorized_condition: 'EXPIRED_APPROVAL',
      fixture_id: 'FIXTURE-EXPIRED-APPROVAL-01',
      preconditions: ['synthetic expired approval metadata'],
      input_descriptors: ['staging-only deployment descriptor'],
      expected_behavior: 'ACTION_BLOCKED',
    },
    requested_effect: 'NONE',
    evidence_contract: {
      required_observables: ['decision outcome', 'external-effect observation'],
      required_artifacts: ['decision record', 'tested version identifier'],
    },
  }
}

function readyManifest() {
  const decision = buildControlledFailureCase(validDraft())
  assert.equal(decision.readiness, 'PACK_READY_FOR_MANUAL_REVIEW')
  assert.ok(decision.manifest)
  return decision.manifest
}

test('valid staging missing-approval case is ready', () => {
  const draft = validDraft()
  draft.test.unauthorized_condition = 'MISSING_APPROVAL'
  assert.equal(buildControlledFailureCase(draft).readiness, 'PACK_READY_FOR_MANUAL_REVIEW')
})

test('expired approval case is ready', () => {
  assert.equal(buildControlledFailureCase(validDraft()).readiness, 'PACK_READY_FOR_MANUAL_REVIEW')
})

test('wrong target case is ready', () => {
  const draft = validDraft()
  draft.test.unauthorized_condition = 'WRONG_TARGET'
  assert.equal(buildControlledFailureCase(draft).readiness, 'PACK_READY_FOR_MANUAL_REVIEW')
})

test('replayed approval case is ready', () => {
  const draft = validDraft()
  draft.test.unauthorized_condition = 'REPLAYED_APPROVAL'
  assert.equal(buildControlledFailureCase(draft).readiness, 'PACK_READY_FOR_MANUAL_REVIEW')
})

test('production environment is blocked', () => {
  const draft = validDraft()
  draft.scope.environment = 'PRODUCTION'
  const decision = buildControlledFailureCase(draft)
  assert.equal(decision.readiness, 'BLOCKED_UNSAFE_TEST_SCOPE')
  assert.ok(decision.reasons.includes('UNSAFE_OR_UNSUPPORTED_ENVIRONMENT'))
})

test('real financial effect is blocked', () => {
  const draft = validDraft()
  draft.requested_effect = 'REAL_FINANCIAL_EFFECT'
  assert.equal(buildControlledFailureCase(draft).readiness, 'BLOCKED_UNSAFE_TEST_SCOPE')
})

test('real external message effect is blocked', () => {
  const draft = validDraft()
  draft.requested_effect = 'REAL_EXTERNAL_MESSAGE'
  assert.equal(buildControlledFailureCase(draft).readiness, 'BLOCKED_UNSAFE_TEST_SCOPE')
})

test('destructive delete effect is blocked', () => {
  const draft = validDraft()
  draft.requested_effect = 'DESTRUCTIVE_DELETE'
  assert.equal(buildControlledFailureCase(draft).readiness, 'BLOCKED_UNSAFE_TEST_SCOPE')
})

test('missing workflow version is incomplete', () => {
  const draft = validDraft()
  draft.scope.workflow_version = ''
  assert.equal(buildControlledFailureCase(draft).readiness, 'INCOMPLETE_TEST_DEFINITION')
})

test('missing fixture id is incomplete', () => {
  const draft = validDraft()
  draft.test.fixture_id = ''
  assert.equal(buildControlledFailureCase(draft).readiness, 'INCOMPLETE_TEST_DEFINITION')
})

test('missing expected behavior is incomplete', () => {
  const draft = validDraft()
  draft.test.expected_behavior = ''
  assert.equal(buildControlledFailureCase(draft).readiness, 'INCOMPLETE_TEST_DEFINITION')
})

test('empty observables are incomplete', () => {
  const draft = validDraft()
  draft.evidence_contract.required_observables = []
  assert.equal(buildControlledFailureCase(draft).readiness, 'INCOMPLETE_TEST_DEFINITION')
})

test('empty evidence artifacts are incomplete', () => {
  const draft = validDraft()
  draft.evidence_contract.required_artifacts = []
  assert.equal(buildControlledFailureCase(draft).readiness, 'INCOMPLETE_TEST_DEFINITION')
})

test('secret-like fixture input is blocked for quarantine', () => {
  const draft = validDraft()
  draft.test.input_descriptors = ['api_key="sk-abcdefghijklmnopqrstuvwxyz123456"']
  const decision = buildControlledFailureCase(draft)
  assert.equal(decision.readiness, 'BLOCKED_UNSAFE_TEST_SCOPE')
  assert.ok(decision.reasons.includes('SECRET_LIKE_INPUT_REQUIRES_SEPARATE_QUARANTINE'))
})

test('generated manifest is deterministic and authority-neutral', () => {
  const first = buildControlledFailureCase(validDraft()).manifest
  const second = buildControlledFailureCase(validDraft()).manifest
  assert.deepEqual(first, second)
  assert.equal(first?.execution_performed, false)
  assert.equal(first?.production_authorized, false)
  assert.equal(first?.claim_status, 'TEST_DEFINITION_ONLY')
  assert.equal(first?.authority_effect, 'NONE')
})

test('manifest prohibits all consequential real effects', () => {
  const manifest = readyManifest()
  assert.deepEqual(manifest.prohibited_effects, [
    'PRODUCTION_MUTATION',
    'REAL_FINANCIAL_EFFECT',
    'REAL_EXTERNAL_MESSAGE',
    'CREDENTIAL_CHANGE',
    'DESTRUCTIVE_DELETE',
  ])
})

test('blocked observation with evidence is fail-closed', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: manifest.test.fixture_id,
    tested_workflow_version: manifest.scope.workflow_version,
    controlled_case_performed: true,
    observed_action: 'BLOCKED',
    external_effect_observed: false,
    evidence_refs: ['receipt:synthetic-01'],
  })
  assert.equal(result.state, 'DEMONSTRATED_FAIL_CLOSED')
})

test('proceeded observation is fail-open', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: manifest.test.fixture_id,
    tested_workflow_version: manifest.scope.workflow_version,
    controlled_case_performed: true,
    observed_action: 'PROCEEDED',
    external_effect_observed: false,
    evidence_refs: ['receipt:synthetic-02'],
  })
  assert.equal(result.state, 'DEMONSTRATED_FAIL_OPEN')
})

test('not observed is not verified', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: manifest.test.fixture_id,
    tested_workflow_version: manifest.scope.workflow_version,
    controlled_case_performed: true,
    observed_action: 'NOT_OBSERVED',
    external_effect_observed: 'UNKNOWN',
    evidence_refs: ['receipt:synthetic-03'],
  })
  assert.equal(result.state, 'NOT_VERIFIED')
})

test('missing evidence refs are not verified', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: manifest.test.fixture_id,
    tested_workflow_version: manifest.scope.workflow_version,
    controlled_case_performed: true,
    observed_action: 'BLOCKED',
    external_effect_observed: false,
    evidence_refs: [],
  })
  assert.equal(result.state, 'NOT_VERIFIED')
})

test('fixture mismatch cannot reuse an observation', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: 'FIXTURE-OTHER-01',
    tested_workflow_version: manifest.scope.workflow_version,
    controlled_case_performed: true,
    observed_action: 'BLOCKED',
    external_effect_observed: false,
    evidence_refs: ['receipt:synthetic-04'],
  })
  assert.equal(result.state, 'NOT_VERIFIED')
  assert.ok(result.reasons.includes('FIXTURE_ID_MISMATCH'))
})

test('workflow version mismatch cannot reuse an observation', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: manifest.test.fixture_id,
    tested_workflow_version: 'different-version',
    controlled_case_performed: true,
    observed_action: 'BLOCKED',
    external_effect_observed: false,
    evidence_refs: ['receipt:synthetic-05'],
  })
  assert.equal(result.state, 'NOT_VERIFIED')
  assert.ok(result.reasons.includes('WORKFLOW_VERSION_MISMATCH'))
})

test('external effect under unauthorized condition is fail-open', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: manifest.test.fixture_id,
    tested_workflow_version: manifest.scope.workflow_version,
    controlled_case_performed: true,
    observed_action: 'BLOCKED',
    external_effect_observed: true,
    evidence_refs: ['receipt:synthetic-06'],
  })
  assert.equal(result.state, 'DEMONSTRATED_FAIL_OPEN')
})

test('unknown external effect is not verified', () => {
  const manifest = readyManifest()
  const result = evaluateFailureCaseObservation(manifest, {
    case_id: manifest.case_id,
    fixture_id: manifest.test.fixture_id,
    tested_workflow_version: manifest.scope.workflow_version,
    controlled_case_performed: true,
    observed_action: 'BLOCKED',
    external_effect_observed: 'UNKNOWN',
    evidence_refs: ['receipt:synthetic-07'],
  })
  assert.equal(result.state, 'NOT_VERIFIED')
})
