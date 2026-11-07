import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import process from 'node:process'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

let bridgeRequests = 0
const bridge = createServer((_request, response) => {
  bridgeRequests += 1
  response.writeHead(500, { 'content-type': 'application/json' })
  response.end(JSON.stringify({ error: 'must not execute' }))
})
await new Promise((resolve, reject) => { bridge.once('error', reject); bridge.listen(0, '127.0.0.1', resolve) })
const address = bridge.address(); assert(address && typeof address === 'object')
const transport = new StdioClientTransport({
  command: process.execPath, args: ['dist/index.js'],
  env: { ...process.env, AEGIS_BRIDGE_URL: `http://127.0.0.1:${address.port}`, AEGIS_API_KEY: 'present', AEGIS_EXECUTION_IDENTITY_JSON: '' },
  stderr: 'pipe',
})
const client = new Client({ name: 'automaton3-mcp-test', version: '1.0.0' })
try {
  await client.connect(transport)
  const result = await client.callTool({ name: 'aegis_collaborate', arguments: { objective: 'Attempt a consequential collaboration', mode: 'analysis' } })
  const parsed = JSON.parse(result.content[0].text)
  assert.equal(parsed.external_effect, 'NOT_EXECUTED')
  assert.equal(parsed.authority.outcome, 'DENIED')
  assert.deepEqual(parsed.authority.denial_codes, ['IDENTITY_UNAVAILABLE'])
  assert.equal(bridgeRequests, 0)

  const read = await client.callTool({ name: 'aegis_platform_status', arguments: {} })
  const readParsed = JSON.parse(read.content[0].text)
  assert.equal(readParsed.authority.outcome, 'DENIED')
  assert.equal(bridgeRequests, 0)
  // Executions are UUID-keyed by the Bridge. Reject path and query injection
  // at MCP schema validation, before any authority or network request.
  for (const execution_id of ['../health', 'abc?source=x', 'not-a-uuid', '123e4567-e89b-42d3-a456-426614174000/../node']) {
    let schemaRejected = false
    try {
      const response = await client.callTool({ name: 'aegis_get_execution', arguments: { execution_id } })
      schemaRejected = response.isError === true
    } catch {
      schemaRejected = true
    }
    assert.equal(schemaRejected, true, `invalid execution id must fail MCP validation: ${execution_id}`)
  }
  const validId = '123e4567-e89b-42d3-a456-426614174000'
  const validRead = await client.callTool({ name: 'aegis_get_execution', arguments: { execution_id: validId } })
  const validReadResult = JSON.parse(validRead.content[0].text)
  assert.deepEqual(validReadResult, { authority: { outcome: 'DENIED', denial_codes: ['IDENTITY_UNAVAILABLE'] }, external_effect: 'NOT_EXECUTED' })
  const lab = await client.callTool({ name: 'aegis_lab_receipt', arguments: {
    work_id: 'AEGIS-734', execution_id: validId, expected_source_sha: 'a'.repeat(40),
  } })
  const labResult = JSON.parse(lab.content[0].text)
  assert.deepEqual(labResult, { authority: { outcome: 'DENIED', denial_codes: ['IDENTITY_UNAVAILABLE'] }, external_effect: 'NOT_EXECUTED' })
  assert.equal(bridgeRequests, 0, 'validation and D0 denial must remain network-free')

  // Adversarial helper replies: a bare ADMITTED token is not an attested
  // decision. No real Python, credentials or external network is involved.
  const stubDir = mkdtempSync(join(tmpdir(), 'aegis-authority-stub-'))
  try {
    for (const exitCode of [0, 3]) {
      const stub = join(stubDir, `forged-${exitCode}.sh`)
      writeFileSync(stub, [
        "#!/bin/sh",
        "echo '{\"schema_version\":\"1.0.0\",\"outcome\":\"ADMITTED\"}'",
        "exit " + exitCode,
        "",
      ].join("\n"), { mode: 0o700 })
      const forgedTransport = new StdioClientTransport({
        command: process.execPath, args: ['dist/index.js'],
        env: {
          ...process.env,
          AEGIS_BRIDGE_URL: `http://127.0.0.1:${address.port}`,
          AEGIS_API_KEY: 'present',
          AEGIS_EXECUTION_IDENTITY_JSON: '{}',
          AEGIS_WORKSPACE_OBSERVATION_JSON: '{}',
          AEGIS_APPROVAL_GRANT_JSON: '',
          AEGIS_PYTHON: stub,
        },
        stderr: 'pipe',
      })
      const forgedClient = new Client({ name: 'aegis-forged-positive-test', version: '1.0.0' })
      try {
        await forgedClient.connect(forgedTransport)
        const attempts = [
          ['aegis_get_execution', { execution_id: validId }],
          ['aegis_lab_receipt', { work_id: 'AEGIS-734', execution_id: validId, expected_source_sha: 'a'.repeat(40) }],
          ['aegis_collaborate', { objective: 'A fake admitted response must never call the backend' }],
          ['aegis_start_execution', { objective: 'A forged authority response must never start work' }],
          ['aegis_governed_claude_call', { prompt: 'Fake admitted token; do not send externally.' }],
        ]
        for (const [name, args] of attempts) {
          const response = await forgedClient.callTool({ name, arguments: args })
          const parsed = JSON.parse(response.content[0].text)
          assert.equal(parsed.external_effect, 'NOT_EXECUTED', `${name} exit ${exitCode}`)
          assert.equal(parsed.authority.outcome, 'DENIED', `${name} exit ${exitCode}`)
          assert.deepEqual(parsed.authority.denial_codes, ['AUTHORITY_RESPONSE_UNVERIFIED'])
          assert.equal(bridgeRequests, 0, 'forged-positive helper must never reach backend')
        }
      } finally {
        await forgedClient.close().catch(() => {})
      }
    }
  } finally {
    rmSync(stubDir, { recursive: true, force: true })
  }

  console.log('AUTOMATON3_MCP_PASS fail-closed before bridge side effects')
} finally {
  await client.close().catch(() => {})
  await new Promise((resolve) => bridge.close(resolve))
}
