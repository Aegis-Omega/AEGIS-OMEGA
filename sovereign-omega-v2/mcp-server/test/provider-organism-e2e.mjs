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

const authorityKeyId = 'authority-test-key'
const authorityPrivateSeed = '4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb'
const authorityPublicKey = '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'
const providerEnv = {
  ...process.env,
  AEGIS_PYTHON: process.env.AEGIS_PYTHON || 'python3',
  AEGIS_ORGANISM_STORE: organismStore,
  AEGIS_PROVIDER_ID: 'openai',
  AEGIS_MODEL_ID: 'gpt-5.6-sol',
  AEGIS_PROVIDER_SESSION_ID: 'e2e-openai-001',
  AEGIS_AUTHORITY_ISSUER_KEY_ID: authorityKeyId,
  AEGIS_AUTHORITY_SIGNING_KEY_HEX: authorityPrivateSeed,
  AEGIS_AUTHORITY_VERIFY_KEYS_JSON: JSON.stringify({ [authorityKeyId]: authorityPublicKey }),
  AEGIS_TRUSTED_OPERATOR_KEYS_JSON: '{}',
}
delete providerEnv.AEGIS_EXECUTION_IDENTITY_JSON
delete providerEnv.AEGIS_WORKSPACE_OBSERVATION_JSON

autoSubmit()

function autoSubmit() {
  const submitted = spawnSync(
    providerEnv.AEGIS_PYTHON,
    ['-m', 'agents.organism', 'submit', '--id', 'provider-e2e-work', '--event', 'research_request', '--payload', '{"topic":"cross-provider durable contribution"}', '--consequence', 'D1'],
    { cwd: repoRoot, env: providerEnv, encoding: 'utf8' },
  )
  assert.equal(submitted.status, 0, submitted.stderr || submitted.stdout)
}

function parseTool(result) {
  assert.equal(Array.isArray(result.content), true)
  assert.equal(result.content.length > 0, true)
  assert.equal(result.content[0].type, 'text')
  return JSON.parse(result.content[0].text)
}

const transport = new StdioClientTransport({
  command: process.execPath,
  args: ['dist/index.js'],
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
    arguments: { work_id: 'provider-e2e-work', text: contributionText, media_type: 'text/markdown' },
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

  console.log('MCP_PROVIDER_SESSION_BOOTSTRAP_E2E=PASS')
  console.log('MCP_PROVIDER_NEXT_WORK_E2E=PASS')
  console.log('MCP_PROVIDER_CONTRIBUTE_TEXT_E2E=PASS')
  console.log('MCP_PROVIDER_AUTHORITY_SELF_PROMOTION=ABSENT')
} finally {
  await client.close().catch(() => {})
  rmSync(temp, { recursive: true, force: true })
}
