import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { createPrivateKey, sign } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  AuthorityResponseError,
  buildAuthorityResponseBindings,
  canonicalHash,
  parseAuthorityProcessResult,
  pythonCanonicalJson,
  validateAuthorityResponse,
} from '../dist/authority-response.js'

const H = (value) => value.repeat(64)
const authorityKeyId = 'authority-test-key'
const authorityPrivateSeed = '4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb'
const authorityPublicKey = '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'
const trustedAuthorityKeys = { [authorityKeyId]: authorityPublicKey }
const authorityPrivateKey = createPrivateKey({
  key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), Buffer.from(authorityPrivateSeed, 'hex')]),
  format: 'der',
  type: 'pkcs8',
})
const request = {
  actionClass: 'D2',
  authorityDomain: 'agent:shared-state',
  requestedCapability: 'mcp.collaborate',
  tool: 'aegis_collaborate',
  target: '/platform/collaborate',
  action: {
    operation: 'collaborate',
    objective: 'Exercise the governed MCP authority boundary',
    mode: 'analysis',
    live: false,
  },
}

const identity = {
  schema_version: '1.0.0',
  repository_identity: 'https://github.com/Aegis-Omega/AEGIS-OMEGA.git',
  repository_root: '.',
  source_commit: 'a'.repeat(40),
  branch_or_ref: 'refs/heads/test',
  project_identity: 'aegis-omega',
  workspace_root: '.',
  workspace_binding: '',
  parent_state_root: H('1'),
  skills_root: H('2'),
  registry_root: H('3'),
  policy_root: H('4'),
  actor_class: 'agent',
  actor_identity: 'agent:test',
  model_identity: 'model:test',
  session_identity: 'session:test',
  physical_executor: 'executor:test',
  tool_identity: 'aegis_collaborate',
  workflow_identity: 'workflow:test',
  authority_domain: 'agent:shared-state',
  requested_capability: 'mcp.collaborate',
  observed_authority: 'observed:test',
  approval_reference: 'approval:test',
  input_digest: H('5'),
  action_digest: canonicalHash('AEGIS_REQUESTED_ACTION_V1', request.action),
  expected_pre_state: H('6'),
  deterministic_nonce: 'nonce:test',
}
identity.workspace_binding = canonicalHash('AEGIS_WORKSPACE_BINDING_V1', {
  repository_remote: identity.repository_identity,
  repository_root: '.',
  project_identity: identity.project_identity,
  source_commit: identity.source_commit,
  operator_authorization: identity.approval_reference,
})

const workspace = {
  actual_cwd: '/workspace',
  remote_origin: identity.repository_identity,
  mutation_target: '/workspace',
  path_views: {},
}
const bindings = buildAuthorityResponseBindings(identity, request, workspace, '/workspace', trustedAuthorityKeys)

// Golden values generated independently by harness.sdk.sovereign_execution.canonical_hash.
assert.equal(bindings.expectedActionDigest, '98b6a4697f2715d903595c3dcee31942e27b317544b718e3a1e0dedc8677ef45')
assert.equal(bindings.expectedWorkspaceBinding, '6f72562c79cc3e87e37318ae3be170804f5be777cfdc0d48f9d7a0d9c2990106')
assert.equal(bindings.expectedIdentityRoot, '25b5396131cb90e561c6809cb1f5973904ce19e4c20f3f8e7d8d37e2ae5fe1ba')
assert.equal(bindings.expectedTargetDigest, '000e1da64150ff19ced3233a3205c295f0591902528ce6f47b3f2ff764477db6')

const modelAction = (system) => ({
  operation: 'governed-model-call',
  prompt_digest: canonicalHash('TEST_PROMPT', 'prompt'),
  system_digest: canonicalHash('TEST_SYSTEM', system),
  provider_payload_digest: canonicalHash('TEST_PAYLOAD', { prompt: 'prompt', system }),
  has_system: true,
})
const modelRequest = (system) => ({
  actionClass: 'D3',
  authorityDomain: 'external:model-call',
  requestedCapability: 'mcp.claude.call',
  tool: 'aegis_governed_claude_call',
  target: '/claude',
  action: modelAction(system),
})
const modelIdentity = (system) => ({
  ...identity,
  tool_identity: 'aegis_governed_claude_call',
  authority_domain: 'external:model-call',
  requested_capability: 'mcp.claude.call',
  action_digest: canonicalHash('AEGIS_REQUESTED_ACTION_V1', modelAction(system)),
})
const systemA = buildAuthorityResponseBindings(modelIdentity('system-a'), modelRequest('system-a'), workspace, '/workspace', trustedAuthorityKeys)
const systemB = buildAuthorityResponseBindings(modelIdentity('system-b'), modelRequest('system-b'), workspace, '/workspace', trustedAuthorityKeys)
assert.notEqual(systemA.expectedActionDigest, systemB.expectedActionDigest)

function fixture() {
  const decisionBody = {
    schema_version: '1.0.0',
    outcome: 'ADMITTED',
    authority_score: '0.900000',
    action_class: request.actionClass,
    authority_domain: request.authorityDomain,
    requested_capability: request.requestedCapability,
    tool: request.tool,
    target_digest: bindings.expectedTargetDigest,
    identity_root: bindings.expectedIdentityRoot,
    workspace_binding: bindings.expectedWorkspaceBinding,
    registry_root: bindings.expectedRegistryRoot,
    policy_root: bindings.expectedPolicyRoot,
    approval_grant_root: H('a'),
    denial_codes: [],
  }
  const policy_decision = {
    ...decisionBody,
    decision_root: canonicalHash('AEGIS_POLICY_DECISION_V1', decisionBody),
  }
  const authority_receipt = {
    receipt_version: '1.0.0',
    issuer_key_id: authorityKeyId,
    execution_identity_root: bindings.expectedIdentityRoot,
    source_commit: bindings.expectedSourceCommit,
    workspace_binding: bindings.expectedWorkspaceBinding,
    expected_pre_state: bindings.expectedPreState,
    policy_decision_root: policy_decision.decision_root,
    policy_root: bindings.expectedPolicyRoot,
    skills_root: bindings.expectedSkillsRoot,
    registry_root: bindings.expectedRegistryRoot,
    approval_grant_root: policy_decision.approval_grant_root,
    authority_score: policy_decision.authority_score,
    authority_domain: request.authorityDomain,
    action_class: request.actionClass,
    requested_capability: request.requestedCapability,
    tool: request.tool,
    target: bindings.expectedTargetDigest,
    requested_action_digest: bindings.expectedActionDigest,
    outcome: 'ADMITTED',
    denial_codes: [],
    signature: '',
  }
  const signingBody = { ...authority_receipt }
  delete signingBody.signature
  authority_receipt.signature = sign(
    null,
    Buffer.from(pythonCanonicalJson({ domain: 'AEGIS_AUTHORITY_DECISION_RECEIPT_V1', value: signingBody }), 'utf8'),
    authorityPrivateKey,
  ).toString('hex')
  const transition_id = H('d')
  const decision_receipt = {
    receipt_kind: 'DECISION_RECEIPT_V1',
    transition_id,
    decision_outcome: 'PERMIT',
    policy_decision_root: policy_decision.decision_root,
  }
  return {
    schema_version: '1.0.0',
    outcome: 'ADMITTED',
    execution_identity_root: bindings.expectedIdentityRoot,
    workspace_binding: bindings.expectedWorkspaceBinding,
    workspace_decision_root: bindings.expectedWorkspaceDecisionRoot,
    policy_decision,
    authority_receipt,
    authority_receipt_root: canonicalHash('AEGIS_AUTHORITY_DECISION_RECEIPT_V1', authority_receipt),
    transition_id,
    decision_receipt,
    decision_receipt_root: canonicalHash('AEGIS_DECISION_RECEIPT_V1', decision_receipt),
    observation: bindings.expectedWorkspaceObservation,
  }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function code(expected) {
  return (error) => error instanceof AuthorityResponseError && error.code === expected
}

const valid = fixture()
assert.equal(valid.policy_decision.decision_root, '9d7ee0746dd1e741a35ae037e8909d92ba4871a4c858d0f8f1164ce429d7e85d')
assert.match(valid.authority_receipt_root, /^[0-9a-f]{64}$/)
const verifiedValid = validateAuthorityResponse(valid, bindings)
assert.equal(verifiedValid.authority_receipt_root, valid.authority_receipt_root)
assert.equal(verifiedValid.transition_id, valid.transition_id)
assert.equal(verifiedValid.decision_receipt_root, valid.decision_receipt_root)
assert.equal(
  parseAuthorityProcessResult({ status: 0, signal: null, stdout: JSON.stringify(valid) }, bindings).outcome,
  'ADMITTED',
)

assert.throws(
  () => parseAuthorityProcessResult({ status: 3, signal: null, stdout: JSON.stringify(valid) }, bindings),
  code('AUTHORITY_PROCESS_FAILED'),
)
assert.throws(
  () => parseAuthorityProcessResult({ status: 0, signal: 'SIGTERM', stdout: JSON.stringify(valid) }, bindings),
  code('AUTHORITY_PROCESS_FAILED'),
)
assert.throws(
  () => parseAuthorityProcessResult({ status: 0, signal: null, stdout: '{' }, bindings),
  code('AUTHORITY_RESPONSE_JSON_MALFORMED'),
)

const missingReceiptField = clone(valid)
delete missingReceiptField.authority_receipt.requested_action_digest
assert.throws(() => validateAuthorityResponse(missingReceiptField, bindings), code('AUTHORITY_RECEIPT_SCHEMA_DRIFT'))

const extraResponseField = clone(valid)
extraResponseField.untrusted = true
assert.throws(() => validateAuthorityResponse(extraResponseField, bindings), code('AUTHORITY_RESPONSE_SCHEMA_DRIFT'))

const receiptRootMismatch = clone(valid)
receiptRootMismatch.authority_receipt_root = H('8')
assert.throws(() => validateAuthorityResponse(receiptRootMismatch, bindings), code('AUTHORITY_RECEIPT_ROOT_MISMATCH'))

const workspaceDecisionMismatch = clone(valid)
workspaceDecisionMismatch.workspace_decision_root = H('8')
assert.throws(() => validateAuthorityResponse(workspaceDecisionMismatch, bindings), code('AUTHORITY_RESPONSE_WORKSPACE_DECISION_MISMATCH'))

const workspaceObservationMismatch = clone(valid)
workspaceObservationMismatch.observation.mutation_target = '/different'
assert.throws(() => validateAuthorityResponse(workspaceObservationMismatch, bindings), code('AUTHORITY_OBSERVATION_BINDING_MISMATCH'))

const signatureMismatch = clone(valid)
signatureMismatch.authority_receipt.signature = '00'.repeat(64)
signatureMismatch.authority_receipt_root = canonicalHash('AEGIS_AUTHORITY_DECISION_RECEIPT_V1', signatureMismatch.authority_receipt)
assert.throws(() => validateAuthorityResponse(signatureMismatch, bindings), code('AUTHORITY_RECEIPT_SIGNATURE_INVALID'))

const actionMismatch = clone(valid)
actionMismatch.authority_receipt.requested_action_digest = H('9')
actionMismatch.authority_receipt_root = canonicalHash('AEGIS_AUTHORITY_DECISION_RECEIPT_V1', actionMismatch.authority_receipt)
assert.throws(() => validateAuthorityResponse(actionMismatch, bindings), code('AUTHORITY_RECEIPT_ACTION_MISMATCH'))

const selfConsistentWrongPolicy = clone(valid)
selfConsistentWrongPolicy.policy_decision.policy_root = H('b')
const changedDecisionBody = { ...selfConsistentWrongPolicy.policy_decision }
delete changedDecisionBody.decision_root
selfConsistentWrongPolicy.policy_decision.decision_root = canonicalHash('AEGIS_POLICY_DECISION_V1', changedDecisionBody)
selfConsistentWrongPolicy.authority_receipt.policy_root = H('b')
selfConsistentWrongPolicy.authority_receipt.policy_decision_root = selfConsistentWrongPolicy.policy_decision.decision_root
selfConsistentWrongPolicy.authority_receipt_root = canonicalHash(
  'AEGIS_AUTHORITY_DECISION_RECEIPT_V1',
  selfConsistentWrongPolicy.authority_receipt,
)
assert.throws(() => validateAuthorityResponse(selfConsistentWrongPolicy, bindings), code('AUTHORITY_POLICY_DECISION_POLICY_MISMATCH'))

const decisionReceiptMismatch = clone(valid)
decisionReceiptMismatch.authority_receipt.authority_score = '0.800000'
decisionReceiptMismatch.authority_receipt_root = canonicalHash(
  'AEGIS_AUTHORITY_DECISION_RECEIPT_V1',
  decisionReceiptMismatch.authority_receipt,
)
assert.throws(() => validateAuthorityResponse(decisionReceiptMismatch, bindings), code('AUTHORITY_RECEIPT_SCORE_MISMATCH'))

const admittedWithDenial = clone(valid)
admittedWithDenial.authority_receipt.denial_codes = ['SHOULD_NOT_EXIST']
admittedWithDenial.authority_receipt_root = canonicalHash(
  'AEGIS_AUTHORITY_DECISION_RECEIPT_V1',
  admittedWithDenial.authority_receipt,
)
assert.throws(() => validateAuthorityResponse(admittedWithDenial, bindings), code('ADMITTED_AUTHORITY_RECEIPT_HAS_DENIAL_CODES'))

const outOfRangeScore = clone(valid)
outOfRangeScore.policy_decision.authority_score = '1.000001'
assert.throws(() => validateAuthorityResponse(outOfRangeScore, bindings), code('AUTHORITY_POLICY_DECISION_SCORE_INVALID'))

// Exercise the real Python producer and validate its complete emitted response.
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const python = process.env.AEGIS_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3')
const sourceCommitResult = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: repoRoot, encoding: 'utf8' })
assert.equal(sourceCommitResult.status, 0)
const remoteResult = spawnSync('git', ['config', '--get', 'remote.origin.url'], { cwd: repoRoot, encoding: 'utf8' })
assert.equal(remoteResult.status, 0)
const actualRemote = remoteResult.stdout.trim()
let canonicalRemote = actualRemote
if (canonicalRemote.startsWith('git@github.com:')) canonicalRemote = `https://github.com/${canonicalRemote.slice('git@github.com:'.length)}`
if (canonicalRemote.startsWith('ssh://git@github.com/')) canonicalRemote = `https://github.com/${canonicalRemote.slice('ssh://git@github.com/'.length)}`
if (!canonicalRemote.endsWith('.git')) canonicalRemote += '.git'
const policy = JSON.parse(readFileSync(join(repoRoot, 'harness', 'policies', 'consequence-policy.v1.json'), 'utf8'))
const registry = JSON.parse(readFileSync(join(repoRoot, 'harness', 'skill_tree.json'), 'utf8'))
const capabilityMap = JSON.parse(readFileSync(join(repoRoot, 'harness', 'policies', 'capability-map.v1.json'), 'utf8'))
const runtimeSkillsRoot = registry.registry_root
const runtimeRegistryRoot = canonicalHash('AEGIS_CAPABILITY_REGISTRY_V1', {
  skills_root: runtimeSkillsRoot,
  capability_map: capabilityMap,
})
const runtimeRequest = {
  actionClass: 'D0',
  authorityDomain: 'mcp:read',
  requestedCapability: 'mcp.platform.status',
  tool: 'aegis_platform_status',
  target: '/platform/status',
  action: { operation: 'read', endpoint: '/platform/status' },
}
const runtimeIdentity = {
  schema_version: '1.0.0',
  repository_identity: canonicalRemote,
  repository_root: '.',
  source_commit: sourceCommitResult.stdout.trim(),
  branch_or_ref: 'refs/heads/mcp-authority-test',
  project_identity: 'AEGIS-OMEGA',
  workspace_root: '.',
  workspace_binding: '',
  parent_state_root: H('1'),
  skills_root: runtimeSkillsRoot,
  registry_root: runtimeRegistryRoot,
  policy_root: canonicalHash('AEGIS_CONSEQUENCE_POLICY_V1', policy.classes),
  actor_class: 'test-agent',
  actor_identity: 'agent:mcp-authority-test',
  model_identity: 'model:none',
  session_identity: 'session:mcp-authority-test',
  physical_executor: 'executor:mcp-authority-test',
  tool_identity: runtimeRequest.tool,
  workflow_identity: 'workflow:mcp-authority-test',
  authority_domain: runtimeRequest.authorityDomain,
  requested_capability: runtimeRequest.requestedCapability,
  observed_authority: '0.000000',
  approval_reference: 'NONE',
  input_digest: H('5'),
  action_digest: canonicalHash('AEGIS_REQUESTED_ACTION_V1', runtimeRequest.action),
  expected_pre_state: H('6'),
  deterministic_nonce: 'nonce:mcp-authority-test',
}
runtimeIdentity.workspace_binding = canonicalHash('AEGIS_WORKSPACE_BINDING_V1', {
  repository_remote: runtimeIdentity.repository_identity,
  repository_root: '.',
  project_identity: runtimeIdentity.project_identity,
  source_commit: runtimeIdentity.source_commit,
  operator_authorization: runtimeIdentity.approval_reference,
})
const runtimeWorkspace = {
  actual_cwd: repoRoot,
  remote_origin: actualRemote,
  mutation_target: repoRoot,
  path_views: {},
}
const runtimeBindings = buildAuthorityResponseBindings(runtimeIdentity, runtimeRequest, runtimeWorkspace, repoRoot, trustedAuthorityKeys)
const runtimePayload = {
  identity: runtimeIdentity,
  workspace: runtimeWorkspace,
  action: runtimeRequest.action,
  request: {
    action_class: runtimeRequest.actionClass,
    authority_domain: runtimeRequest.authorityDomain,
    requested_capability: runtimeRequest.requestedCapability,
    tool: runtimeRequest.tool,
    target: runtimeRequest.target,
    workspace_mode: 'READ_ONLY',
    current_generation: 0,
    idempotency_key: 'NONE',
    compensation_reference: 'NONE',
  },
}
const runtimeResult = spawnSync(python, [join(repoRoot, 'scripts', 'automaton3-authority.py'), 'evaluate'], {
  cwd: repoRoot,
  input: JSON.stringify(runtimePayload),
  encoding: 'utf8',
  timeout: 15_000,
  maxBuffer: 1_048_576,
  env: {
    ...process.env,
    AEGIS_AUTHORITY_ISSUER_KEY_ID: authorityKeyId,
    AEGIS_AUTHORITY_SIGNING_KEY_HEX: authorityPrivateSeed,
    AEGIS_AUTHORITY_VERIFY_KEYS_JSON: JSON.stringify(trustedAuthorityKeys),
    AEGIS_TRUSTED_OPERATOR_KEYS_JSON: '{}',
  },
})
assert.equal(runtimeResult.status, 0, runtimeResult.stderr || runtimeResult.stdout)
const verifiedRuntime = parseAuthorityProcessResult(runtimeResult, runtimeBindings)
assert.equal(verifiedRuntime.outcome, 'ADMITTED')
assert.equal(verifiedRuntime.decision_receipt.receipt_kind, 'DECISION_RECEIPT_V1')
assert.equal(verifiedRuntime.decision_receipt.transition_id, verifiedRuntime.transition_id)
assert.equal(verifiedRuntime.decision_receipt.policy_decision_root, verifiedRuntime.policy_decision.decision_root)

console.log('AUTHORITY_RESPONSE_PASS strict status, schema, binding, signed authority receipt, transition DecisionReceipt, and Python producer parity')
