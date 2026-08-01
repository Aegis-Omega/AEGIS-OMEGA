import { createHash, createPublicKey, verify } from 'node:crypto'
import { relative, resolve, sep } from 'node:path'

export type ActionClass = 'D0' | 'D1' | 'D2' | 'D3' | 'D4'

export type AuthorityDecisionReceipt = {
  receipt_version: '1.0.0'
  issuer_key_id: string
  execution_identity_root: string
  source_commit: string
  workspace_binding: string
  expected_pre_state: string
  skills_root: string
  policy_decision_root: string
  policy_root: string
  registry_root: string
  approval_grant_root: string
  authority_score: string
  authority_domain: string
  action_class: ActionClass
  requested_capability: string
  tool: string
  target: string
  requested_action_digest: string
  outcome: 'ADMITTED'
  denial_codes: []
  signature: string
}

export type VerifiedAuthorityDecision = {
  schema_version: '1.0.0'
  outcome: 'ADMITTED'
  execution_identity_root: string
  workspace_binding: string
  workspace_decision_root: string
  policy_decision: Record<string, unknown> & { decision_root: string }
  authority_receipt: AuthorityDecisionReceipt
  authority_receipt_root: string
  observation: Record<string, unknown>
}

export type AuthorityRequestBindings = {
  actionClass: ActionClass
  authorityDomain: string
  requestedCapability: string
  tool: string
  target: string
  action: Record<string, unknown>
}

export type AuthorityResponseBindings = AuthorityRequestBindings & {
  expectedIdentityRoot: string
  expectedWorkspaceBinding: string
  expectedPolicyRoot: string
  expectedSkillsRoot: string
  expectedRegistryRoot: string
  expectedActionDigest: string
  expectedTargetDigest: string
  expectedProjectIdentity: string
  expectedRepositoryIdentity: string
  expectedSourceCommit: string
  expectedPreState: string
  expectedWorkspaceDecisionRoot: string
  expectedWorkspaceObservation: Record<string, unknown>
  trustedAuthorityKeys: Record<string, string>
}

export type WorkspaceRequestBindings = {
  actual_cwd: string
  remote_origin: string
  mutation_target: string
  path_views?: Record<string, string>
}

export type AuthorityProcessResult = {
  status: number | null
  signal?: string | null
  stdout?: string | null
  stderr?: string | null
  error?: Error
}

export class AuthorityResponseError extends Error {
  constructor(readonly code: string) {
    super(code)
    this.name = 'AuthorityResponseError'
  }
}

const HASH_RE = /^[0-9a-f]{64}$/
const GIT_RE = /^[0-9a-f]{40,64}$/
const SCORE_RE = /^(?:0\.[0-9]{6}|1\.000000)$/
const SAFE_ID_RE = /^[A-Za-z0-9._:/@+#=-]+$/
const ACTION_CLASSES = new Set<ActionClass>(['D0', 'D1', 'D2', 'D3', 'D4'])

const IDENTITY_KEYS = [
  'schema_version', 'repository_identity', 'repository_root', 'source_commit',
  'branch_or_ref', 'project_identity', 'workspace_root', 'workspace_binding',
  'parent_state_root', 'skills_root', 'registry_root', 'policy_root', 'actor_class',
  'actor_identity', 'model_identity', 'session_identity', 'physical_executor',
  'tool_identity', 'workflow_identity', 'authority_domain', 'requested_capability',
  'observed_authority', 'approval_reference', 'input_digest', 'action_digest',
  'expected_pre_state', 'deterministic_nonce',
] as const

const POLICY_DECISION_KEYS = [
  'schema_version', 'outcome', 'authority_score', 'action_class', 'authority_domain',
  'requested_capability', 'tool', 'target_digest', 'identity_root', 'workspace_binding',
  'registry_root', 'policy_root', 'approval_grant_root', 'denial_codes', 'decision_root',
] as const

const RECEIPT_KEYS = [
  'receipt_version', 'issuer_key_id', 'execution_identity_root', 'source_commit',
  'workspace_binding', 'expected_pre_state', 'policy_decision_root', 'policy_root',
  'skills_root', 'registry_root', 'approval_grant_root', 'authority_score',
  'authority_domain', 'action_class', 'requested_capability', 'tool', 'target',
  'requested_action_digest', 'outcome', 'denial_codes', 'signature',
] as const

const RESPONSE_KEYS = [
  'schema_version', 'outcome', 'execution_identity_root', 'workspace_binding',
  'workspace_decision_root', 'policy_decision', 'authority_receipt',
  'authority_receipt_root', 'observation',
] as const

const OBSERVATION_KEYS = [
  'declared_project', 'actual_cwd', 'resolved_repository_root', 'remote_origin',
  'mutation_target', 'path_views',
] as const

function fail(code: string): never {
  throw new AuthorityResponseError(code)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function record(value: unknown, code: string): Record<string, unknown> {
  if (!isRecord(value)) fail(code)
  return value
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[], code: string): void {
  const actual = Object.keys(value).sort(compareCodePoints)
  const expected = [...keys].sort(compareCodePoints)
  if (actual.length !== expected.length || actual.some((item, index) => item !== expected[index])) fail(code)
}

function requiredString(value: Record<string, unknown>, key: string, code: string): string {
  const candidate = value[key]
  if (typeof candidate !== 'string' || candidate.length === 0) fail(code)
  return candidate
}

function requiredHash(value: Record<string, unknown>, key: string, code: string): string {
  const candidate = requiredString(value, key, code)
  if (!HASH_RE.test(candidate)) fail(code)
  return candidate
}

function equal(actual: unknown, expected: unknown, code: string): void {
  if (actual !== expected) fail(code)
}

function compareCodePoints(left: string, right: string): number {
  const a = Array.from(left, (value) => value.codePointAt(0) as number)
  const b = Array.from(right, (value) => value.codePointAt(0) as number)
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
    if (a[index] !== b[index]) return (a[index] as number) - (b[index] as number)
  }
  return a.length - b.length
}

function canonicalGitHubRemote(value: string): string {
  let remote = value.trim()
  if (remote.startsWith('git@github.com:')) remote = `https://github.com/${remote.slice('git@github.com:'.length)}`
  if (remote.startsWith('ssh://git@github.com/')) remote = `https://github.com/${remote.slice('ssh://git@github.com/'.length)}`
  if (!remote.startsWith('https://github.com/')) fail('EXECUTION_IDENTITY_REMOTE_NOT_CANONICAL')
  if (!remote.endsWith('.git')) remote += '.git'
  return remote
}

function assertUnicodeScalarString(value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index)
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1)
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail('CANONICAL_UNPAIRED_SURROGATE')
      index += 1
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      fail('CANONICAL_UNPAIRED_SURROGATE')
    }
  }
}

/**
 * Python json.dumps(..., ensure_ascii=False, allow_nan=False, sort_keys=True,
 * separators=(",", ":")) parity for the JSON subset accepted at this boundary.
 * Non-integer numbers are denied because Python and ECMAScript exponent/float
 * rendering is not byte-identical for every finite IEEE-754 value.
 */
export function pythonCanonicalJson(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') {
    assertUnicodeScalarString(value)
    return JSON.stringify(value)
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) fail('CANONICAL_NUMBER_UNSUPPORTED')
    return Object.is(value, -0) ? '0' : String(value)
  }
  if (Array.isArray(value)) return `[${value.map(pythonCanonicalJson).join(',')}]`
  if (isRecord(value)) {
    const keys = Object.keys(value).sort(compareCodePoints)
    return `{${keys.map((key) => {
      if (value[key] === undefined) fail('CANONICAL_UNDEFINED_VALUE')
      return `${pythonCanonicalJson(key)}:${pythonCanonicalJson(value[key])}`
    }).join(',')}}`
  }
  fail('CANONICAL_VALUE_UNSUPPORTED')
}

export function canonicalHash(domain: string, value: unknown): string {
  return createHash('sha256')
    .update(pythonCanonicalJson({ domain, value }), 'utf8')
    .digest('hex')
}

function expectedWorkspaceEvidence(
  workspace: WorkspaceRequestBindings,
  repositoryRoot: string,
  projectIdentity: string,
  sourceCommit: string,
  workspaceBinding: string,
): { observation: Record<string, unknown>; decisionRoot: string } {
  const resolvedRoot = resolve(repositoryRoot)
  const actualCwd = resolve(workspace.actual_cwd)
  const mutationTarget = resolve(workspace.mutation_target)
  const relativeTargetRaw = relative(resolvedRoot, mutationTarget)
  const mutationTargetRelative = relativeTargetRaw === ''
    ? '.'
    : relativeTargetRaw.startsWith('..') || resolve(resolvedRoot, relativeTargetRaw) !== mutationTarget
      ? 'OUTSIDE_REPOSITORY'
      : relativeTargetRaw.split(sep).join('/')
  const remote = canonicalGitHubRemote(workspace.remote_origin)
  const observation = {
    declared_project: projectIdentity,
    actual_cwd: actualCwd,
    resolved_repository_root: resolvedRoot,
    remote_origin: remote,
    mutation_target: mutationTarget,
    path_views: workspace.path_views ?? {},
  }
  const decisionRoot = canonicalHash('AEGIS_WORKSPACE_DECISION_V1', {
    outcome: 'ADMITTED',
    workspace_binding: workspaceBinding,
    denial_codes: [],
    declared_project: projectIdentity,
    remote_origin: remote,
    source_commit: sourceCommit,
    mutation_target_relative: mutationTargetRelative,
  })
  return { observation, decisionRoot }
}

function validateIdentity(
  identity: unknown,
  request: AuthorityRequestBindings,
  workspace: WorkspaceRequestBindings,
  repositoryRoot: string,
  trustedAuthorityKeys: Record<string, string>,
): AuthorityResponseBindings {
  const body = record(identity, 'EXECUTION_IDENTITY_MALFORMED')
  exactKeys(body, IDENTITY_KEYS, 'EXECUTION_IDENTITY_SCHEMA_DRIFT')
  equal(body['schema_version'], '1.0.0', 'EXECUTION_IDENTITY_SCHEMA_UNSUPPORTED')
  for (const key of IDENTITY_KEYS) requiredString(body, key, `EXECUTION_IDENTITY_FIELD_INVALID:${key}`)
  for (const key of [
    'workspace_binding', 'parent_state_root', 'skills_root', 'registry_root',
    'policy_root', 'input_digest', 'action_digest', 'expected_pre_state',
  ]) requiredHash(body, key, `EXECUTION_IDENTITY_HASH_INVALID:${key}`)
  if (!GIT_RE.test(body['source_commit'] as string)) fail('EXECUTION_IDENTITY_SOURCE_COMMIT_INVALID')
  equal(body['repository_root'], '.', 'EXECUTION_IDENTITY_REPOSITORY_ROOT_INVALID')
  equal(body['workspace_root'], '.', 'EXECUTION_IDENTITY_WORKSPACE_ROOT_INVALID')
  const remote = body['repository_identity'] as string
  equal(remote, canonicalGitHubRemote(remote), 'EXECUTION_IDENTITY_REMOTE_NOT_CANONICAL')
  for (const key of [
    'branch_or_ref', 'project_identity', 'actor_class', 'actor_identity', 'model_identity',
    'session_identity', 'physical_executor', 'tool_identity', 'workflow_identity',
    'authority_domain', 'requested_capability', 'observed_authority', 'approval_reference',
    'deterministic_nonce',
  ]) {
    if (!SAFE_ID_RE.test(body[key] as string)) fail(`EXECUTION_IDENTITY_AUTHORITY_STRING_INVALID:${key}`)
  }

  const expectedActionDigest = canonicalHash('AEGIS_REQUESTED_ACTION_V1', request.action)
  const expectedTargetDigest = canonicalHash('AEGIS_AUTHORITY_TARGET_V1', request.target)
  equal(body['action_digest'], expectedActionDigest, 'EXECUTION_IDENTITY_ACTION_DIGEST_MISMATCH')
  equal(body['authority_domain'], request.authorityDomain, 'EXECUTION_IDENTITY_AUTHORITY_DOMAIN_MISMATCH')
  equal(body['requested_capability'], request.requestedCapability, 'EXECUTION_IDENTITY_CAPABILITY_MISMATCH')
  equal(body['tool_identity'], request.tool, 'EXECUTION_IDENTITY_TOOL_MISMATCH')

  const expectedWorkspaceBinding = canonicalHash('AEGIS_WORKSPACE_BINDING_V1', {
    repository_remote: remote,
    repository_root: '.',
    project_identity: body['project_identity'],
    source_commit: body['source_commit'],
    operator_authorization: body['approval_reference'],
  })
  equal(body['workspace_binding'], expectedWorkspaceBinding, 'EXECUTION_IDENTITY_WORKSPACE_BINDING_MISMATCH')
  const workspaceEvidence = expectedWorkspaceEvidence(
    workspace,
    repositoryRoot,
    body['project_identity'] as string,
    body['source_commit'] as string,
    expectedWorkspaceBinding,
  )

  return {
    ...request,
    expectedIdentityRoot: canonicalHash('AEGIS_EXECUTION_IDENTITY_V1', body),
    expectedWorkspaceBinding,
    expectedPolicyRoot: body['policy_root'] as string,
    expectedSkillsRoot: body['skills_root'] as string,
    expectedRegistryRoot: body['registry_root'] as string,
    expectedActionDigest,
    expectedTargetDigest,
    expectedProjectIdentity: body['project_identity'] as string,
    expectedRepositoryIdentity: remote,
    expectedSourceCommit: body['source_commit'] as string,
    expectedPreState: body['expected_pre_state'] as string,
    expectedWorkspaceDecisionRoot: workspaceEvidence.decisionRoot,
    expectedWorkspaceObservation: workspaceEvidence.observation,
    trustedAuthorityKeys,
  }
}

export function buildAuthorityResponseBindings(
  identity: unknown,
  request: AuthorityRequestBindings,
  workspace: WorkspaceRequestBindings,
  repositoryRoot: string,
  trustedAuthorityKeys: Record<string, string>,
): AuthorityResponseBindings {
  return validateIdentity(identity, request, workspace, repositoryRoot, trustedAuthorityKeys)
}

function validateSortedUniqueCodes(value: unknown, code: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || item.length === 0)) fail(code)
  const items = value as string[]
  const canonical = [...new Set(items)].sort(compareCodePoints)
  if (canonical.length !== items.length || canonical.some((item, index) => item !== items[index])) fail(code)
  return items
}

function validatePolicyDecision(value: unknown, expected: AuthorityResponseBindings): Record<string, unknown> & { decision_root: string } {
  const decision = record(value, 'AUTHORITY_POLICY_DECISION_MALFORMED')
  exactKeys(decision, POLICY_DECISION_KEYS, 'AUTHORITY_POLICY_DECISION_SCHEMA_DRIFT')
  equal(decision['schema_version'], '1.0.0', 'AUTHORITY_POLICY_DECISION_SCHEMA_UNSUPPORTED')
  equal(decision['outcome'], 'ADMITTED', 'AUTHORITY_POLICY_DECISION_NOT_ADMITTED')
  const score = requiredString(decision, 'authority_score', 'AUTHORITY_POLICY_DECISION_SCORE_INVALID')
  if (!SCORE_RE.test(score)) fail('AUTHORITY_POLICY_DECISION_SCORE_INVALID')
  const actionClass = requiredString(decision, 'action_class', 'AUTHORITY_POLICY_DECISION_CLASS_INVALID')
  if (!ACTION_CLASSES.has(actionClass as ActionClass)) fail('AUTHORITY_POLICY_DECISION_CLASS_INVALID')
  validateSortedUniqueCodes(decision['denial_codes'], 'AUTHORITY_POLICY_DECISION_DENIAL_CODES_INVALID')
  if ((decision['denial_codes'] as string[]).length !== 0) fail('ADMITTED_POLICY_DECISION_HAS_DENIAL_CODES')
  for (const key of ['target_digest', 'identity_root', 'workspace_binding', 'registry_root', 'policy_root', 'approval_grant_root', 'decision_root']) {
    requiredHash(decision, key, `AUTHORITY_POLICY_DECISION_HASH_INVALID:${key}`)
  }
  for (const key of ['authority_domain', 'requested_capability', 'tool']) {
    const item = requiredString(decision, key, `AUTHORITY_POLICY_DECISION_FIELD_INVALID:${key}`)
    if (!SAFE_ID_RE.test(item)) fail(`AUTHORITY_POLICY_DECISION_FIELD_INVALID:${key}`)
  }
  equal(decision['action_class'], expected.actionClass, 'AUTHORITY_POLICY_DECISION_CLASS_MISMATCH')
  equal(decision['authority_domain'], expected.authorityDomain, 'AUTHORITY_POLICY_DECISION_DOMAIN_MISMATCH')
  equal(decision['requested_capability'], expected.requestedCapability, 'AUTHORITY_POLICY_DECISION_CAPABILITY_MISMATCH')
  equal(decision['tool'], expected.tool, 'AUTHORITY_POLICY_DECISION_TOOL_MISMATCH')
  equal(decision['target_digest'], expected.expectedTargetDigest, 'AUTHORITY_POLICY_DECISION_TARGET_MISMATCH')
  equal(decision['identity_root'], expected.expectedIdentityRoot, 'AUTHORITY_POLICY_DECISION_IDENTITY_MISMATCH')
  equal(decision['workspace_binding'], expected.expectedWorkspaceBinding, 'AUTHORITY_POLICY_DECISION_WORKSPACE_MISMATCH')
  equal(decision['registry_root'], expected.expectedRegistryRoot, 'AUTHORITY_POLICY_DECISION_REGISTRY_MISMATCH')
  equal(decision['policy_root'], expected.expectedPolicyRoot, 'AUTHORITY_POLICY_DECISION_POLICY_MISMATCH')
  const body = { ...decision }
  delete body['decision_root']
  equal(decision['decision_root'], canonicalHash('AEGIS_POLICY_DECISION_V1', body), 'AUTHORITY_POLICY_DECISION_ROOT_MISMATCH')
  return decision as Record<string, unknown> & { decision_root: string }
}

function validateAuthorityReceipt(
  value: unknown,
  receiptRoot: unknown,
  decision: Record<string, unknown> & { decision_root: string },
  expected: AuthorityResponseBindings,
): AuthorityDecisionReceipt {
  const receipt = record(value, 'AUTHORITY_RECEIPT_MALFORMED')
  exactKeys(receipt, RECEIPT_KEYS, 'AUTHORITY_RECEIPT_SCHEMA_DRIFT')
  equal(receipt['receipt_version'], '1.0.0', 'AUTHORITY_RECEIPT_SCHEMA_UNSUPPORTED')
  equal(receipt['outcome'], 'ADMITTED', 'AUTHORITY_RECEIPT_NOT_ADMITTED')
  const codes = validateSortedUniqueCodes(receipt['denial_codes'], 'AUTHORITY_RECEIPT_DENIAL_CODES_INVALID')
  if (codes.length !== 0) fail('ADMITTED_AUTHORITY_RECEIPT_HAS_DENIAL_CODES')
  const score = requiredString(receipt, 'authority_score', 'AUTHORITY_RECEIPT_SCORE_INVALID')
  if (!SCORE_RE.test(score)) fail('AUTHORITY_RECEIPT_SCORE_INVALID')
  const actionClass = requiredString(receipt, 'action_class', 'AUTHORITY_RECEIPT_CLASS_INVALID')
  if (!ACTION_CLASSES.has(actionClass as ActionClass)) fail('AUTHORITY_RECEIPT_CLASS_INVALID')
  for (const key of [
    'execution_identity_root', 'workspace_binding', 'expected_pre_state', 'policy_decision_root', 'policy_root',
    'skills_root', 'registry_root', 'approval_grant_root', 'target', 'requested_action_digest',
  ]) requiredHash(receipt, key, `AUTHORITY_RECEIPT_HASH_INVALID:${key}`)
  const sourceCommit = requiredString(receipt, 'source_commit', 'AUTHORITY_RECEIPT_SOURCE_COMMIT_INVALID')
  if (!GIT_RE.test(sourceCommit)) fail('AUTHORITY_RECEIPT_SOURCE_COMMIT_INVALID')
  for (const key of ['issuer_key_id', 'authority_domain', 'requested_capability', 'tool']) {
    const item = requiredString(receipt, key, `AUTHORITY_RECEIPT_FIELD_INVALID:${key}`)
    if (!SAFE_ID_RE.test(item)) fail(`AUTHORITY_RECEIPT_FIELD_INVALID:${key}`)
  }
  const signature = requiredString(receipt, 'signature', 'AUTHORITY_RECEIPT_SIGNATURE_INVALID')
  if (!/^[0-9a-f]{128}$/.test(signature)) fail('AUTHORITY_RECEIPT_SIGNATURE_INVALID')

  const pairs: Array<[string, unknown, string]> = [
    ['execution_identity_root', expected.expectedIdentityRoot, 'AUTHORITY_RECEIPT_IDENTITY_MISMATCH'],
    ['source_commit', expected.expectedSourceCommit, 'AUTHORITY_RECEIPT_SOURCE_COMMIT_MISMATCH'],
    ['workspace_binding', expected.expectedWorkspaceBinding, 'AUTHORITY_RECEIPT_WORKSPACE_MISMATCH'],
    ['expected_pre_state', expected.expectedPreState, 'AUTHORITY_RECEIPT_PRE_STATE_MISMATCH'],
    ['policy_decision_root', decision.decision_root, 'AUTHORITY_RECEIPT_DECISION_MISMATCH'],
    ['policy_root', expected.expectedPolicyRoot, 'AUTHORITY_RECEIPT_POLICY_MISMATCH'],
    ['skills_root', expected.expectedSkillsRoot, 'AUTHORITY_RECEIPT_SKILLS_ROOT_MISMATCH'],
    ['registry_root', expected.expectedRegistryRoot, 'AUTHORITY_RECEIPT_REGISTRY_MISMATCH'],
    ['approval_grant_root', decision['approval_grant_root'], 'AUTHORITY_RECEIPT_APPROVAL_MISMATCH'],
    ['authority_score', decision['authority_score'], 'AUTHORITY_RECEIPT_SCORE_MISMATCH'],
    ['authority_domain', expected.authorityDomain, 'AUTHORITY_RECEIPT_DOMAIN_MISMATCH'],
    ['action_class', expected.actionClass, 'AUTHORITY_RECEIPT_CLASS_MISMATCH'],
    ['requested_capability', expected.requestedCapability, 'AUTHORITY_RECEIPT_CAPABILITY_MISMATCH'],
    ['tool', expected.tool, 'AUTHORITY_RECEIPT_TOOL_MISMATCH'],
    ['target', expected.expectedTargetDigest, 'AUTHORITY_RECEIPT_TARGET_MISMATCH'],
    ['requested_action_digest', expected.expectedActionDigest, 'AUTHORITY_RECEIPT_ACTION_MISMATCH'],
  ]
  for (const [key, valueToMatch, code] of pairs) equal(receipt[key], valueToMatch, code)

  const issuerKeyId = receipt['issuer_key_id'] as string
  const publicKeyHex = expected.trustedAuthorityKeys[issuerKeyId]
  if (!publicKeyHex) fail('AUTHORITY_RECEIPT_ISSUER_UNTRUSTED')
  if (!HASH_RE.test(publicKeyHex)) fail('AUTHORITY_RECEIPT_PUBLIC_KEY_INVALID')
  const signingBody = { ...receipt }
  delete signingBody['signature']
  try {
    const publicKey = createPublicKey({
      key: Buffer.concat([Buffer.from('302a300506032b6570032100', 'hex'), Buffer.from(publicKeyHex, 'hex')]),
      format: 'der',
      type: 'spki',
    })
    const ok = verify(
      null,
      Buffer.from(pythonCanonicalJson({ domain: 'AEGIS_AUTHORITY_DECISION_RECEIPT_V1', value: signingBody }), 'utf8'),
      publicKey,
      Buffer.from(signature, 'hex'),
    )
    if (!ok) fail('AUTHORITY_RECEIPT_SIGNATURE_INVALID')
  } catch (error) {
    if (error instanceof AuthorityResponseError) throw error
    fail('AUTHORITY_RECEIPT_SIGNATURE_INVALID')
  }

  const root = requiredString({ root: receiptRoot }, 'root', 'AUTHORITY_RECEIPT_ROOT_INVALID')
  if (!HASH_RE.test(root)) fail('AUTHORITY_RECEIPT_ROOT_INVALID')
  equal(root, canonicalHash('AEGIS_AUTHORITY_DECISION_RECEIPT_V1', receipt), 'AUTHORITY_RECEIPT_ROOT_MISMATCH')
  return receipt as AuthorityDecisionReceipt
}

function validateObservation(value: unknown): Record<string, unknown> {
  const observation = record(value, 'AUTHORITY_OBSERVATION_MALFORMED')
  exactKeys(observation, OBSERVATION_KEYS, 'AUTHORITY_OBSERVATION_SCHEMA_DRIFT')
  for (const key of ['declared_project', 'actual_cwd', 'resolved_repository_root', 'remote_origin', 'mutation_target']) {
    requiredString(observation, key, `AUTHORITY_OBSERVATION_FIELD_INVALID:${key}`)
  }
  const views = record(observation['path_views'], 'AUTHORITY_OBSERVATION_PATH_VIEWS_INVALID')
  if (Object.values(views).some((item) => typeof item !== 'string')) fail('AUTHORITY_OBSERVATION_PATH_VIEWS_INVALID')
  return observation
}

export function validateAuthorityResponse(value: unknown, expected: AuthorityResponseBindings): VerifiedAuthorityDecision {
  const response = record(value, 'AUTHORITY_RESPONSE_MALFORMED')
  exactKeys(response, RESPONSE_KEYS, 'AUTHORITY_RESPONSE_SCHEMA_DRIFT')
  equal(response['schema_version'], '1.0.0', 'AUTHORITY_RESPONSE_SCHEMA_UNSUPPORTED')
  equal(response['outcome'], 'ADMITTED', 'AUTHORITY_RESPONSE_NOT_ADMITTED')
  equal(requiredHash(response, 'execution_identity_root', 'AUTHORITY_RESPONSE_IDENTITY_INVALID'), expected.expectedIdentityRoot, 'AUTHORITY_RESPONSE_IDENTITY_MISMATCH')
  equal(requiredHash(response, 'workspace_binding', 'AUTHORITY_RESPONSE_WORKSPACE_INVALID'), expected.expectedWorkspaceBinding, 'AUTHORITY_RESPONSE_WORKSPACE_MISMATCH')
  equal(
    requiredHash(response, 'workspace_decision_root', 'AUTHORITY_RESPONSE_WORKSPACE_DECISION_INVALID'),
    expected.expectedWorkspaceDecisionRoot,
    'AUTHORITY_RESPONSE_WORKSPACE_DECISION_MISMATCH',
  )
  const decision = validatePolicyDecision(response['policy_decision'], expected)
  const receipt = validateAuthorityReceipt(response['authority_receipt'], response['authority_receipt_root'], decision, expected)
  const observation = validateObservation(response['observation'])
  equal(observation['declared_project'], expected.expectedProjectIdentity, 'AUTHORITY_OBSERVATION_PROJECT_MISMATCH')
  equal(canonicalGitHubRemote(observation['remote_origin'] as string), expected.expectedRepositoryIdentity, 'AUTHORITY_OBSERVATION_REMOTE_MISMATCH')
  equal(
    pythonCanonicalJson(observation),
    pythonCanonicalJson(expected.expectedWorkspaceObservation),
    'AUTHORITY_OBSERVATION_BINDING_MISMATCH',
  )
  equal(response['authority_receipt_root'], canonicalHash('AEGIS_AUTHORITY_DECISION_RECEIPT_V1', receipt), 'AUTHORITY_RESPONSE_RECEIPT_ROOT_MISMATCH')
  return {
    schema_version: '1.0.0',
    outcome: 'ADMITTED',
    execution_identity_root: response['execution_identity_root'] as string,
    workspace_binding: response['workspace_binding'] as string,
    workspace_decision_root: response['workspace_decision_root'] as string,
    policy_decision: decision,
    authority_receipt: receipt,
    authority_receipt_root: response['authority_receipt_root'] as string,
    observation,
  }
}

export function parseAuthorityProcessResult(result: AuthorityProcessResult, expected: AuthorityResponseBindings): VerifiedAuthorityDecision {
  if (result.error || result.signal !== null && result.signal !== undefined || result.status !== 0) fail('AUTHORITY_PROCESS_FAILED')
  if (typeof result.stdout !== 'string' || result.stdout.trim().length === 0) fail('AUTHORITY_RESPONSE_EMPTY')
  let parsed: unknown
  try {
    parsed = JSON.parse(result.stdout)
  } catch {
    fail('AUTHORITY_RESPONSE_JSON_MALFORMED')
  }
  return validateAuthorityResponse(parsed, expected)
}
