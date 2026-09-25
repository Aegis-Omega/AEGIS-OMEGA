export type TestEnvironment = 'LOCAL' | 'TEST' | 'STAGING'

export type ActionClass =
  | 'EXTERNAL_MESSAGE'
  | 'REPOSITORY_MUTATION'
  | 'MERGE'
  | 'DEPLOY'
  | 'PRODUCTION_CONFIG'
  | 'FINANCIAL'
  | 'DELETE_DATA'
  | 'IDENTITY_OR_CREDENTIAL'
  | 'OTHER'

export type UnauthorizedCondition =
  | 'MISSING_APPROVAL'
  | 'EXPIRED_APPROVAL'
  | 'STALE_APPROVAL'
  | 'WRONG_TARGET'
  | 'WRONG_PARAMETERS'
  | 'REPLAYED_APPROVAL'
  | 'MISSING_POLICY'
  | 'OTHER'

export type ExpectedBehavior =
  | 'ACTION_BLOCKED'
  | 'REQUEST_REJECTED'
  | 'NO_EXTERNAL_EFFECT'

export type ProhibitedEffect =
  | 'PRODUCTION_MUTATION'
  | 'REAL_FINANCIAL_EFFECT'
  | 'REAL_EXTERNAL_MESSAGE'
  | 'CREDENTIAL_CHANGE'
  | 'DESTRUCTIVE_DELETE'

export type UnsafeRequestedEffect = 'NONE' | ProhibitedEffect

export type ReproducerReadiness =
  | 'PACK_READY_FOR_MANUAL_REVIEW'
  | 'INCOMPLETE_TEST_DEFINITION'
  | 'BLOCKED_UNSAFE_TEST_SCOPE'

export type FailureCaseFindingState =
  | 'DEMONSTRATED_FAIL_CLOSED'
  | 'DEMONSTRATED_FAIL_OPEN'
  | 'NOT_VERIFIED'

export interface ControlledFailureCaseDraftV1 {
  case_id: string
  scope: {
    workflow_id: string
    workflow_version: string
    environment: string
    action_class: string
    target_class: string
  }
  control: {
    control_point: string
    authorization_requirement: string
  }
  test: {
    unauthorized_condition: string
    fixture_id: string
    preconditions: string[]
    input_descriptors: string[]
    expected_behavior: string
  }
  requested_effect: UnsafeRequestedEffect
  evidence_contract: {
    required_observables: string[]
    required_artifacts: string[]
  }
}

export interface ControlledFailureCaseV1 {
  schema_version: 'AEGIS_CONTROLLED_FAILURE_CASE_V1'
  case_id: string
  scope: {
    workflow_id: string
    workflow_version: string
    environment: TestEnvironment
    action_class: ActionClass
    target_class: string
  }
  control: {
    control_point: string
    authorization_requirement: string
  }
  test: {
    unauthorized_condition: UnauthorizedCondition
    fixture_id: string
    preconditions: string[]
    input_descriptors: string[]
    expected_behavior: ExpectedBehavior
  }
  prohibited_effects: ProhibitedEffect[]
  evidence_contract: {
    required_observables: string[]
    required_artifacts: string[]
    result_states: [
      'DEMONSTRATED_FAIL_CLOSED',
      'DEMONSTRATED_FAIL_OPEN',
      'NOT_VERIFIED',
    ]
  }
  execution_performed: false
  production_authorized: false
  claim_status: 'TEST_DEFINITION_ONLY'
  authority_effect: 'NONE'
}

export interface FailureCaseBuildDecisionV1 {
  readiness: ReproducerReadiness
  reasons: string[]
  manifest?: ControlledFailureCaseV1
}

export interface FailureCaseObservationV1 {
  case_id: string
  fixture_id: string
  tested_workflow_version: string
  controlled_case_performed: boolean
  observed_action: 'BLOCKED' | 'PROCEEDED' | 'NOT_OBSERVED'
  external_effect_observed: false | true | 'UNKNOWN'
  evidence_refs: string[]
}

export interface FailureCaseObservationDecisionV1 {
  state: FailureCaseFindingState
  reasons: string[]
}

const ALLOWED_ENVIRONMENTS = new Set<TestEnvironment>(['LOCAL', 'TEST', 'STAGING'])
const ALLOWED_ACTION_CLASSES = new Set<ActionClass>([
  'EXTERNAL_MESSAGE',
  'REPOSITORY_MUTATION',
  'MERGE',
  'DEPLOY',
  'PRODUCTION_CONFIG',
  'FINANCIAL',
  'DELETE_DATA',
  'IDENTITY_OR_CREDENTIAL',
  'OTHER',
])
const ALLOWED_UNAUTHORIZED_CONDITIONS = new Set<UnauthorizedCondition>([
  'MISSING_APPROVAL',
  'EXPIRED_APPROVAL',
  'STALE_APPROVAL',
  'WRONG_TARGET',
  'WRONG_PARAMETERS',
  'REPLAYED_APPROVAL',
  'MISSING_POLICY',
  'OTHER',
])
const ALLOWED_EXPECTED_BEHAVIORS = new Set<ExpectedBehavior>([
  'ACTION_BLOCKED',
  'REQUEST_REJECTED',
  'NO_EXTERNAL_EFFECT',
])

const PROHIBITED_EFFECTS: ProhibitedEffect[] = [
  'PRODUCTION_MUTATION',
  'REAL_FINANCIAL_EFFECT',
  'REAL_EXTERNAL_MESSAGE',
  'CREDENTIAL_CHANGE',
  'DESTRUCTIVE_DELETE',
]

const CASE_ID_RE = /^FC-[A-Z0-9][A-Z0-9_-]{2,63}$/
const FIXTURE_ID_RE = /^FIXTURE-[A-Z0-9][A-Z0-9_-]{2,63}$/

const SECRET_PATTERNS = [
  /sk-[A-Za-z0-9]{20,}/,
  /ghp_[A-Za-z0-9]{20,}/,
  /AIza[A-Za-z0-9_-]{30,}/,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  /authorization\s*:\s*bearer\s+\S+/i,
  /(?:api[_-]?key|token|password|secret)\s*[:=]\s*["']?[A-Za-z0-9._-]{12,}/i,
]

function nonEmpty(value: string): boolean {
  return value.trim().length > 0
}

function compact(values: string[]): string[] {
  return values.map(value => value.trim()).filter(Boolean)
}

function containsSecretCandidate(values: string[]): boolean {
  return values.some(value => SECRET_PATTERNS.some(pattern => pattern.test(value)))
}

export function buildControlledFailureCase(
  draft: ControlledFailureCaseDraftV1,
): FailureCaseBuildDecisionV1 {
  const unsafeReasons: string[] = []
  const missingReasons: string[] = []

  if (!ALLOWED_ENVIRONMENTS.has(draft.scope.environment as TestEnvironment)) {
    unsafeReasons.push('UNSAFE_OR_UNSUPPORTED_ENVIRONMENT')
  }
  if (draft.requested_effect !== 'NONE') {
    unsafeReasons.push(`REAL_EFFECT_REQUIRED:${draft.requested_effect}`)
  }

  const candidateText = [
    draft.scope.workflow_id,
    draft.scope.workflow_version,
    draft.scope.target_class,
    draft.control.control_point,
    draft.control.authorization_requirement,
    ...draft.test.preconditions,
    ...draft.test.input_descriptors,
    ...draft.evidence_contract.required_observables,
    ...draft.evidence_contract.required_artifacts,
  ]
  if (containsSecretCandidate(candidateText)) {
    unsafeReasons.push('SECRET_LIKE_INPUT_REQUIRES_SEPARATE_QUARANTINE')
  }

  if (!CASE_ID_RE.test(draft.case_id)) missingReasons.push('CASE_ID_INVALID')
  if (!nonEmpty(draft.scope.workflow_id)) missingReasons.push('WORKFLOW_ID_MISSING')
  if (!nonEmpty(draft.scope.workflow_version)) missingReasons.push('WORKFLOW_VERSION_MISSING')
  if (!ALLOWED_ACTION_CLASSES.has(draft.scope.action_class as ActionClass)) {
    missingReasons.push('ACTION_CLASS_INVALID')
  }
  if (!nonEmpty(draft.scope.target_class)) missingReasons.push('TARGET_CLASS_MISSING')
  if (!nonEmpty(draft.control.control_point)) missingReasons.push('CONTROL_POINT_MISSING')
  if (!nonEmpty(draft.control.authorization_requirement)) {
    missingReasons.push('AUTHORIZATION_REQUIREMENT_MISSING')
  }
  if (!ALLOWED_UNAUTHORIZED_CONDITIONS.has(
    draft.test.unauthorized_condition as UnauthorizedCondition,
  )) {
    missingReasons.push('UNAUTHORIZED_CONDITION_INVALID')
  }
  if (!FIXTURE_ID_RE.test(draft.test.fixture_id)) missingReasons.push('FIXTURE_ID_INVALID')
  if (compact(draft.test.input_descriptors).length === 0) {
    missingReasons.push('INPUT_DESCRIPTOR_MISSING')
  }
  if (!ALLOWED_EXPECTED_BEHAVIORS.has(draft.test.expected_behavior as ExpectedBehavior)) {
    missingReasons.push('EXPECTED_BEHAVIOR_INVALID')
  }

  const observables = compact(draft.evidence_contract.required_observables)
  const artifacts = compact(draft.evidence_contract.required_artifacts)
  if (observables.length === 0) missingReasons.push('REQUIRED_OBSERVABLE_MISSING')
  if (artifacts.length === 0) missingReasons.push('REQUIRED_ARTIFACT_MISSING')

  if (unsafeReasons.length > 0) {
    return {
      readiness: 'BLOCKED_UNSAFE_TEST_SCOPE',
      reasons: [...new Set(unsafeReasons)].sort(),
    }
  }

  if (missingReasons.length > 0) {
    return {
      readiness: 'INCOMPLETE_TEST_DEFINITION',
      reasons: [...new Set(missingReasons)].sort(),
    }
  }

  const manifest: ControlledFailureCaseV1 = {
    schema_version: 'AEGIS_CONTROLLED_FAILURE_CASE_V1',
    case_id: draft.case_id,
    scope: {
      workflow_id: draft.scope.workflow_id.trim(),
      workflow_version: draft.scope.workflow_version.trim(),
      environment: draft.scope.environment as TestEnvironment,
      action_class: draft.scope.action_class as ActionClass,
      target_class: draft.scope.target_class.trim(),
    },
    control: {
      control_point: draft.control.control_point.trim(),
      authorization_requirement: draft.control.authorization_requirement.trim(),
    },
    test: {
      unauthorized_condition: draft.test.unauthorized_condition as UnauthorizedCondition,
      fixture_id: draft.test.fixture_id,
      preconditions: compact(draft.test.preconditions),
      input_descriptors: compact(draft.test.input_descriptors),
      expected_behavior: draft.test.expected_behavior as ExpectedBehavior,
    },
    prohibited_effects: [...PROHIBITED_EFFECTS],
    evidence_contract: {
      required_observables: observables,
      required_artifacts: artifacts,
      result_states: [
        'DEMONSTRATED_FAIL_CLOSED',
        'DEMONSTRATED_FAIL_OPEN',
        'NOT_VERIFIED',
      ],
    },
    execution_performed: false,
    production_authorized: false,
    claim_status: 'TEST_DEFINITION_ONLY',
    authority_effect: 'NONE',
  }

  return {
    readiness: 'PACK_READY_FOR_MANUAL_REVIEW',
    reasons: [],
    manifest,
  }
}

export function evaluateFailureCaseObservation(
  manifest: ControlledFailureCaseV1,
  observation: FailureCaseObservationV1,
): FailureCaseObservationDecisionV1 {
  const reasons: string[] = []

  if (observation.case_id !== manifest.case_id) reasons.push('CASE_ID_MISMATCH')
  if (observation.fixture_id !== manifest.test.fixture_id) reasons.push('FIXTURE_ID_MISMATCH')
  if (observation.tested_workflow_version !== manifest.scope.workflow_version) {
    reasons.push('WORKFLOW_VERSION_MISMATCH')
  }
  if (!observation.controlled_case_performed) reasons.push('CONTROLLED_CASE_NOT_PERFORMED')
  if (compact(observation.evidence_refs).length === 0) reasons.push('EVIDENCE_REFERENCE_MISSING')

  if (reasons.length > 0 || observation.observed_action === 'NOT_OBSERVED') {
    if (observation.observed_action === 'NOT_OBSERVED') reasons.push('ACTION_NOT_OBSERVED')
    return { state: 'NOT_VERIFIED', reasons: [...new Set(reasons)].sort() }
  }

  if (observation.observed_action === 'PROCEEDED' || observation.external_effect_observed === true) {
    return {
      state: 'DEMONSTRATED_FAIL_OPEN',
      reasons: observation.external_effect_observed === true
        ? ['FORBIDDEN_EXTERNAL_EFFECT_OBSERVED']
        : ['ACTION_PROCEEDED_UNDER_UNAUTHORIZED_CONDITION'],
    }
  }

  if (observation.observed_action === 'BLOCKED' && observation.external_effect_observed === false) {
    return {
      state: 'DEMONSTRATED_FAIL_CLOSED',
      reasons: ['ACTION_BLOCKED_WITHOUT_EXTERNAL_EFFECT'],
    }
  }

  return {
    state: 'NOT_VERIFIED',
    reasons: ['EXTERNAL_EFFECT_NOT_OBSERVED'],
  }
}

export function formatFailureCaseManifest(manifest: ControlledFailureCaseV1): string {
  return JSON.stringify(manifest, null, 2)
}
