import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'
import {
  prepareProviderContribution,
  readNextWork,
  readOrganismStatus,
  recordProviderContribution,
  recordProviderTextContribution,
} from '../dist/organism-client.js'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '../../..')
const temp = mkdtempSync(join(tmpdir(), 'aegis-organism-mcp-'))
const store = join(temp, 'organism.json')
process.env.AEGIS_ORGANISM_STORE = store
process.env.AEGIS_PYTHON = process.env.AEGIS_PYTHON || 'python3'

try {
  const submitted = spawnSync(process.env.AEGIS_PYTHON, ['-m', 'agents.organism', 'submit', '--id', 'mcp-work-1', '--event', 'research_request', '--payload', '{"topic":"cross-provider"}', '--consequence', 'D1'], { cwd: repoRoot, env: process.env, encoding: 'utf8' })
  assert.equal(submitted.status, 0, submitted.stderr)

  const available = readNextWork(repoRoot, 10)
  assert.deepEqual(available.map((x) => x.work_id), ['mcp-work-1'])

  const prepared = prepareProviderContribution(repoRoot, 'mcp-work-1')
  assert.match(prepared.order_digest, /^[0-9a-f]{64}$/)
  assert.match(prepared.state_root, /^[0-9a-f]{64}$/)
  assert.match(prepared.rollback_reference, /organism:mcp-work-1:/)

  const digest = 'a'.repeat(64)
  const contribution = recordProviderContribution(repoRoot, {
    workId: 'mcp-work-1',
    provider: 'openai',
    model: 'gpt-5.6-sol',
    artifactDigest: digest,
    sourceRef: 'mcp:openai',
    rollbackReference: prepared.rollback_reference,
  })
  assert.equal(contribution.authority, 'NON_AUTHORITATIVE_EVIDENCE')
  assert.match(String(contribution.contribution_ref), /provider:openai:model:gpt-5\.6-sol/)
  assert.match(String(contribution.contribution_ref), new RegExp(digest))

  const stale = spawnSync(process.env.AEGIS_PYTHON, ['-m', 'agents.organism', 'contribute', '--id', 'mcp-work-1', '--provider', 'gemini', '--model', 'gemini-3.5-flash', '--artifact-digest', 'b'.repeat(64), '--source-ref', 'mcp:gemini', '--rollback-reference', prepared.rollback_reference], { cwd: repoRoot, env: process.env, encoding: 'utf8' })
  assert.notEqual(stale.status, 0)

  const preparedText = prepareProviderContribution(repoRoot, 'mcp-work-1')
  const textContribution = recordProviderTextContribution(repoRoot, {
    workId: 'mcp-work-1',
    provider: 'claude',
    model: 'opus',
    text: '# Claude contribution\nThis survives the chat.',
    sourceRef: 'mcp:claude',
    mediaType: 'text/markdown',
    rollbackReference: preparedText.rollback_reference,
  })
  assert.equal(textContribution.authority, 'NON_AUTHORITATIVE_EVIDENCE')
  assert.equal(textContribution.artifact.authority, 'NON_AUTHORITATIVE_EVIDENCE')
  assert.match(String(textContribution.artifact.sha256), /^[0-9a-f]{64}$/)
  const stored = JSON.parse(readFileSync(String(textContribution.artifact.artifact_path), 'utf8'))
  assert.equal(stored.content, '# Claude contribution\nThis survives the chat.')

  const status = readOrganismStatus(repoRoot)
  assert.equal(Array.isArray(status.orders), true)
  assert.equal(status.orders.length, 1)
  assert.equal(status.orders[0].status, 'QUEUED')
  assert.equal(status.orders[0].contribution_refs.length, 2)
  assert.match(String(status.state_root), /^[0-9a-f]{64}$/)

  console.log('MCP_ORGANISM_PROVIDER_CONTRIBUTION=PASS')
  console.log('MCP_ORGANISM_NEXT_WORK=PASS')
  console.log('MCP_ORGANISM_CONTENT_ADDRESSED_TEXT=PASS')
  console.log('MCP_ORGANISM_PRESTATE_FENCE=PASS')
} finally {
  rmSync(temp, { recursive: true, force: true })
}
