import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  AuthorityResponseError,
  buildAuthorityResponseBindings,
  canonicalHash,
  validateAuthorityResponse,
} from '../dist/authority-response.js'

const code = (expected) => (error) => error instanceof AuthorityResponseError && error.code === expected
const clone = (value) => JSON.parse(JSON.stringify(value))
const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const python = process.env.AEGIS_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3')
const authorityKeyId = 'authority-test-key'
const authorityPrivateSeed = '4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb'
const authorityPublicKey = '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'
const trustedAuthorityKeys = { [authorityKeyId]: authorityPublicKey }

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
const request = {
  actionClass: 'D0',
  authorityDomain: 'mcp:read',
  requestedCapability: 'mcp.platform.status',
  tool: 'aegis_platform_status',
  target: '/platform/status',
  action: { operation: 'read', endpoint: '/platform/status' },
}
const identity = {
  schema_version: '1.0.0',
  repository_identity: canonicalRemote,
  repository_root: '.',
  source_commit: sourceCommitResult.stdout.trim(),
  branch_or_ref: 'refs/heads/pr5a-transition-test',
  project_identity: 'AEGIS-OMEGA',
  workspace_root: '.',
  workspace_binding: '',
  parent_state_root: '1'.repeat(64),
  skills_root: runtimeSkillsRoot,
  registry_root: runtimeRegistryRoot,
  policy_root: canonicalHash('AEGIS_CONSEQUENCE_POLICY_V1', policy.classes),
  actor_class: 'test-agent',
  actor_identity: 'agent:pr5a-transition-test',
  model_identity: 'model:none',
  session_identity: 'session:pr5a-transition-test',
  physical_executor: 'executor:pr5a-transition-test',
  tool_identity: request.tool,
  workflow_identity: 'workflow:pr5a-transition-test',
  authority_domain: request.authorityDomain,
  requested_capability: request.requestedCapability,
  observed_authority: '0.000000',
  approval_reference: 'NONE',
  input_digest: '5'.repeat(64),
  action_digest: canonicalHash('AEGIS_REQUESTED_ACTION_V1', request.action),
  expected_pre_state: '6'.repeat(64),
  deterministic_nonce: 'nonce:pr5a-transition-test',
}
identity.workspace_binding = canonicalHash('AEGIS_WORKSPACE_BINDING_V1', {
  repository_remote: identity.repository_identity,
  repository_root: '.',
  project_identity: identity.project_identity,
  source_commit: identity.source_commit,
  operator_authorization: identity.approval_reference,
})
const workspace = { actual_cwd: repoRoot, remote_origin: actualRemote, mutation_target: repoRoot, path_views: {} }
const bindings = buildAuthorityResponseBindings(identity, request, workspace, repoRoot, trustedAuthorityKeys)
const payload = {
  identity,
  workspace,
  action: request.action,
  request: {
    action_class: request.actionClass,
    authority_domain: request.authorityDomain,
    requested_capability: request.requestedCapability,
    tool: request.tool,
    target: request.target,
    workspace_mode: 'READ_ONLY',
    current_generation: 0,
    idempotency_key: 'NONE',
    compensation_reference: 'NONE',
  },
}
const result = spawnSync(python, [join(repoRoot, 'scripts', 'automaton3-authority.py'), 'evaluate'], {
  cwd: repoRoot,
  input: JSON.stringify(payload),
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
assert.equal(result.status, 0, result.stderr || result.stdout)
const valid = JSON.parse(result.stdout)
const parsed = validateAuthorityResponse(valid, bindings)
assert.equal(parsed.transition_id, valid.transition_id)
assert.equal(parsed.decision_receipt_root, valid.decision_receipt_root)
assert.equal(parsed.decision_receipt.receipt_kind, 'DECISION_RECEIPT_V1')
assert.equal(parsed.decision_receipt.transition_id, parsed.transition_id)
assert.equal(parsed.decision_receipt.policy_decision_root, parsed.policy_decision.decision_root)

const transitionMismatch = clone(valid)
transitionMismatch.transition_id = 'a'.repeat(64)
assert.throws(() => validateAuthorityResponse(transitionMismatch, bindings), code('AUTHORITY_TRANSITION_RECEIPT_TRANSITION_MISMATCH'))

const kindMismatch = clone(valid)
kindMismatch.decision_receipt.receipt_kind = 'EXECUTION_RECEIPT_V1'
assert.throws(() => validateAuthorityResponse(kindMismatch, bindings), code('AUTHORITY_DECISION_RECEIPT_KIND_MISMATCH'))

const rootMismatch = clone(valid)
rootMismatch.decision_receipt_root = 'b'.repeat(64)
assert.throws(() => validateAuthorityResponse(rootMismatch, bindings), code('AUTHORITY_DECISION_RECEIPT_ROOT_MISMATCH'))

const policyRootMismatch = clone(valid)
policyRootMismatch.decision_receipt.policy_decision_root = 'c'.repeat(64)
policyRootMismatch.decision_receipt_root = canonicalHash('AEGIS_DECISION_RECEIPT_V1', policyRootMismatch.decision_receipt)
assert.throws(() => validateAuthorityResponse(policyRootMismatch, bindings), code('AUTHORITY_DECISION_RECEIPT_POLICY_MISMATCH'))

const effectInjection = clone(valid)
effectInjection.effect_receipt = { receipt_kind: 'EFFECT_RECEIPT_V1' }
assert.throws(() => validateAuthorityResponse(effectInjection, bindings), code('AUTHORITY_RESPONSE_SCHEMA_DRIFT'))

const arbitraryExtra = clone(valid)
arbitraryExtra.untrusted = true
assert.throws(() => validateAuthorityResponse(arbitraryExtra, bindings), code('AUTHORITY_RESPONSE_SCHEMA_DRIFT'))

console.log('AUTHORITY_TRANSITION_RECEIPT_PASS strict nominal transition/decision binding with no effect substitution')
