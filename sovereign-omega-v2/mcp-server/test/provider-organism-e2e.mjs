import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import process from 'node:process'

import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '../../..')
const temp = mkdtempSync(join(tmpdir(), 'aegis-provider-e2e-'))
const organismStore = join(temp, 'organism.json')
const PROVIDER = 'openai'
const MODEL = 'gpt-5.6-sol'
const SESSION = 'e2e-openai-001'

const authorityKeyId = 'authority-test-key'
const authorityPrivateSeed = '4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb'
const authorityPublicKey = '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'
const providerEnv = {
  ...process.env,
  AEGIS_PYTHON: process.env.AEGIS_PYTHON || 'python3',
  AEGIS_ORGANISM_STORE: organismStore,
  AEGIS_PROVIDER_SESSION_ID: SESSION,
  AEGIS_AUTHORITY_ISSUER_KEY_ID: authorityKeyId,
  AEGIS_AUTHORITY_SIGNING_KEY_HEX: authorityPrivateSeed,
  AEGIS_AUTHORITY_VERIFY_KEYS_JSON: JSON.stringify({ [authorityKeyId]: authorityPublicKey }),
  AEGIS_TRUSTED_OPERATOR_KEYS_JSON: '{}',
}
delete providerEnv.AEGIS_PROVIDER_ID
delete providerEnv.AEGIS_MODEL_ID
delete providerEnv.AEGIS_EXECUTION_IDENTITY_JSON
delete providerEnv.AEGIS_WORKSPACE_OBSERVATION_JSON

autoSubmit()
canonicalD0AuthorityPreflight()

function autoSubmit() {
  const submitted = spawnSync(
    providerEnv.AEGIS_PYTHON,
    ['-m', 'agents.organism', 'submit', '--id', 'provider-e2e-work', '--event', 'research_request', '--payload', '{"topic":"cross-provider durable contribution"}', '--consequence', 'D1'],
    { cwd: repoRoot, env: providerEnv, encoding: 'utf8' },
  )
  assert.equal(submitted.status, 0, submitted.stderr || submitted.stdout)
}

function canonicalD0AuthorityPreflight() {
  const action = { operation: 'read-next-work', limit: 10 }
  const bootstrapInput = {
    provider: PROVIDER,
    model: MODEL,
    session: SESSION,
    action_class: 'D0',
    authority_domain: 'organism:read',
    requested_capability: 'mcp.organism.next',
    tool: 'aegis_next_work',
    target: '.aegis/runtime/organism.json',
    mutation_target: '.',
    action,
  }
  const bootstrapped = spawnSync(
    providerEnv.AEGIS_PYTHON,
    ['scripts/provider-session-bootstrap.py'],
    { cwd: repoRoot, env: providerEnv, input: JSON.stringify(bootstrapInput), encoding: 'utf8' },
  )
  assert.equal(bootstrapped.status, 0, `PROVIDER_BOOTSTRAP_FAILED stdout=${bootstrapped.stdout} stderr=${bootstrapped.stderr}`)
  const session = JSON.parse(bootstrapped.stdout)
  assert.equal(session.authority, 'IDENTITY_ONLY_NOT_AUTHORIZATION')

  const payload = {
    identity: session.identity,
    workspace: session.workspace,
    action,
    request: {
      action_class: 'D0',
      authority_domain: 'organism:read',
      requested_capability: 'mcp.organism.next',
      tool: 'aegis_next_work',
      target: '.aegis/runtime/organism.json',
      workspace_mode: 'READ_ONLY',
      current_generation: 0,
      rollback_reference: 'NONE',
      idempotency_key: 'NONE',
      compensation_reference: 'NONE',
    },
  }
  const authority = spawnSync(
    providerEnv.AEGIS_PYTHON,
    ['scripts/automaton3-authority.py', 'evaluate'],
    { cwd: repoRoot, env: providerEnv, input: JSON.stringify(payload), encoding: 'utf8' },
  )
  assert.equal(authority.status, 0, `CANONICAL_PROVIDER_D0_DENIED stdout=${authority.stdout} stderr=${authority.stderr}`)
  const response = JSON.parse(authority.stdout)
  assert.equal(response.outcome, 'ADMITTED', JSON.stringify(response))
  console.log('CANONICAL_PROVIDER_D0_AUTHORITY_PREFLIGHT=PASS')
}

function parseTool(result) {
  assert.equal(Array.isArray(result.content), true)
  assert.equal(result.content.length > 0, true)
  assert.equal(result.content[0].type, 'text')
  return JSON.parse(result.content[0].text)
}

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [join(repoRoot, 'scripts', 'aegis-provider-mcp.mjs'), PROVIDER, MODEL],
  env: providerEnv,
  stderr: 'pipe',
})
const client = new Client({ name: 'aegis-provider-organism-e2e', version: '1.0.0' })

try {
  await client.connect(transport)

  const listed = await client.listTools()
  const names = listed.tools.map((tool) => tool.name)
  assert(names.includes('aegis_next_work'))
  assert(names.includes('aegis_contribute_text'))

  const next = parseTool(await client.callTool({ name: 'aegis_next_work', arguments: { limit: 10 } }))
  assert.equal(next.authority.outcome, 'ADMITTED', JSON.stringify(next))
  assert.equal(next.work.length, 1)
  assert.equal(next.work[0].work_id, 'provider-e2e-work')
  assert.equal(next.lease, 'NONE')
  assert.equal(next.claim, 'NONE')

  const contributionText = '# Provider contribution\nOpenAI worker completed bounded research output.'
  const contributed = parseTool(await client.callTool({
    name: 'aegis_contribute_text',
    arguments: {
      work_id: 'provider-e2e-work',
      provider: PROVIDER,
      model: MODEL,
      text: contributionText,
      media_type: 'text/markdown',
      source_ref: 'mcp:e2e-openai-001',
    },
  }))
  assert.equal(contributed.authority.outcome, 'ADMITTED', JSON.stringify(contributed))
  assert.equal(contributed.epistemic_status, 'NON_AUTHORITATIVE_EVIDENCE')
  assert.equal(contributed.admission_effect, 'NONE')
  assert.equal(contributed.contribution.authority, 'NON_AUTHORITATIVE_EVIDENCE')
  assert.equal(contributed.contribution.artifact.content, contributionText)
  assert.match(contributed.contribution.artifact.sha256, /^[0-9a-f]{64}$/)
  assert.match(contributed.contribution.rollback_reference, /^organism:/)

  const status = spawnSync(providerEnv.AEGIS_PYTHON, ['-m', 'agents.organism', 'status'], { cwd: repoRoot, env: providerEnv, encoding: 'utf8' })
  assert.equal(status.status, 0, status.stderr)
  const organism = JSON.parse(status.stdout)
  assert.equal(organism.orders.length, 1)
  assert.equal(organism.orders[0].status, 'QUEUED')
  assert.equal(organism.orders[0].contribution_refs.length, 1)
  assert.match(organism.state_root, /^[0-9a-f]{64}$/)

  console.log('MCP_PROVIDER_SHARED_LAUNCHER_E2E=PASS')
  console.log('MCP_PROVIDER_SESSION_BOOTSTRAP_E2E=PASS')
  console.log('MCP_PROVIDER_NEXT_WORK_E2E=PASS')
  console.log('MCP_PROVIDER_CONTRIBUTE_TEXT_E2E=PASS')
  console.log('MCP_PROVIDER_AUTHORITY_SELF_PROMOTION=ABSENT')
} finally {
  await client.close().catch(() => {})
  rmSync(temp, { recursive: true, force: true })
}
