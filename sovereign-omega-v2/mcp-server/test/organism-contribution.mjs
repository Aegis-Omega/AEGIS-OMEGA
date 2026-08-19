import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'
import { recordProviderContribution, readOrganismStatus } from '../dist/organism-client.js'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '../../..')
const temp = mkdtempSync(join(tmpdir(), 'aegis-organism-mcp-'))
const store = join(temp, 'organism.json')
process.env.AEGIS_ORGANISM_STORE = store
process.env.AEGIS_PYTHON = process.env.AEGIS_PYTHON || 'python3'

try {
  const submitted = spawnSync(process.env.AEGIS_PYTHON, ['-m', 'agents.organism', 'submit', '--id', 'mcp-work-1', '--event', 'research_request', '--payload', '{"topic":"cross-provider"}', '--consequence', 'D1'], { cwd: repoRoot, env: process.env, encoding: 'utf8' })
  assert.equal(submitted.status, 0, submitted.stderr)

  const digest = 'a'.repeat(64)
  const contribution = recordProviderContribution(repoRoot, {
    workId: 'mcp-work-1',
    provider: 'openai',
    model: 'gpt-5.6-sol',
    artifactDigest: digest,
    sourceRef: 'mcp:openai',
  })
  assert.equal(contribution.authority, 'NON_AUTHORITATIVE_EVIDENCE')
  assert.match(String(contribution.contribution_ref), /provider:openai:model:gpt-5\.6-sol/)
  assert.match(String(contribution.contribution_ref), new RegExp(digest))

  const status = readOrganismStatus(repoRoot)
  assert.equal(Array.isArray(status.orders), true)
  assert.equal(status.orders.length, 1)
  assert.equal(status.orders[0].status, 'QUEUED')
  assert.equal(status.orders[0].contribution_refs.length, 1)

  const again = recordProviderContribution(repoRoot, {
    workId: 'mcp-work-1', provider: 'openai', model: 'gpt-5.6-sol', artifactDigest: digest, sourceRef: 'mcp:openai',
  })
  assert.equal(again.contribution_ref, contribution.contribution_ref)
  const status2 = readOrganismStatus(repoRoot)
  assert.equal(status2.orders[0].contribution_refs.length, 1)

  console.log('MCP_ORGANISM_PROVIDER_CONTRIBUTION=PASS')
} finally {
  rmSync(temp, { recursive: true, force: true })
}
