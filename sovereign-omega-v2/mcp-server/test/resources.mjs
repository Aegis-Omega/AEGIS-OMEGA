import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import process from 'node:process'

import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'

const responses = new Map([
  ['/node', {
    t0_verdict: true,
    corruption_count: 0,
    constitutional_hash: 'sha256:test-constitutional-hash',
    phi_threshold: 0.6180339887498948,
  }],
  ['/telemetry', {
    epoch: 7,
    pgcs_passes: 3,
    vcg: { drift: 0 },
  }],
  ['/health', {
    ok: true,
    service: 'aegis-test-bridge',
  }],
])

const bridge = createServer((request, response) => {
  const body = responses.get(request.url ?? '')
  if (body === undefined) {
    response.writeHead(404, { 'content-type': 'application/json' })
    response.end(JSON.stringify({ error: 'not found' }))
    return
  }
  assert.equal(request.headers['x-api-key'], undefined, 'fuel-free resources must not send an API key')
  response.writeHead(200, { 'content-type': 'application/json' })
  response.end(JSON.stringify(body))
})

await new Promise((resolve, reject) => {
  bridge.once('error', reject)
  bridge.listen(0, '127.0.0.1', resolve)
})

const address = bridge.address()
assert(address && typeof address === 'object')
const bridgeUrl = `http://127.0.0.1:${address.port}`

const transport = new StdioClientTransport({
  command: process.execPath,
  args: ['dist/index.js'],
  env: {
    ...process.env,
    AEGIS_BRIDGE_URL: bridgeUrl,
    AEGIS_API_KEY: '',
    AEGIS_ENVIRONMENT_MANIFEST_JSON: '',
  },
  stderr: 'pipe',
})
const client = new Client({ name: 'aegis-resource-test', version: '1.0.0' })

try {
  await client.connect(transport)

  const listed = await client.listResources()
  const uris = listed.resources.map((resource) => resource.uri).sort()
  assert.deepEqual(uris, [
    'aegis://authority/index',
    'aegis://authority/repo-map',
    'aegis://health',
    'aegis://node',
    'aegis://nvidia/dlss5',
    'aegis://nvidia/dlss5/runtime-contract',
    'aegis://telemetry',
  ])

  const node = await client.readResource({ uri: 'aegis://node' })
  assert.equal(node.contents.length, 1)
  const nodeValue = JSON.parse(node.contents[0].text)
  assert.equal(nodeValue.t0_verdict, true)
  assert.equal(nodeValue.phi_threshold, 0.6180339887498948)

  const telemetry = await client.readResource({ uri: 'aegis://telemetry' })
  assert.equal(JSON.parse(telemetry.contents[0].text).epoch, 7)

  const health = await client.readResource({ uri: 'aegis://health' })
  assert.equal(JSON.parse(health.contents[0].text).ok, true)

  const dlss5 = await client.readResource({ uri: 'aegis://nvidia/dlss5' })
  const dlss5Value = JSON.parse(dlss5.contents[0].text)
  assert.equal(dlss5Value.technology, 'NVIDIA DLSS 5')
  assert.equal(dlss5Value.feature, '3D-Guided Neural Rendering')
  assert.equal(dlss5Value.streamline.plugin, 'sl.dlss_nr')
  assert.equal(dlss5Value.authority_effect, 'NONE')

  const runtimeContract = await client.readResource({ uri: 'aegis://nvidia/dlss5/runtime-contract' })
  const runtimeContractValue = JSON.parse(runtimeContract.contents[0].text)
  assert.equal(runtimeContractValue.required_plugin, 'sl.dlss_nr')
  assert.equal(runtimeContractValue.minimum_streamline_version, '2.14.0')
  assert.equal(runtimeContractValue.rendering_claim_on_observation, 'NOT_ESTABLISHED')
  assert.equal(runtimeContractValue.authority_effect, 'NONE')

  const tools = await client.listTools()
  const toolNames = tools.tools.map((tool) => tool.name)
  assert(toolNames.includes('aegis_dlss5_reference'))
  assert(toolNames.includes('aegis_dlss5_capability'))
  assert(toolNames.includes('aegis_dlss5_runtime_verify'))

  const capability = await client.callTool({ name: 'aegis_dlss5_capability', arguments: {} })
  const capabilityText = capability.content.find((entry) => entry.type === 'text')
  assert(capabilityText && 'text' in capabilityText)
  const capabilityValue = JSON.parse(capabilityText.text)
  assert.equal(capabilityValue.capability.status, 'NOT_VERIFIED')
  assert.deepEqual(capabilityValue.capability.reason_codes, ['ENVIRONMENT_MANIFEST_MISSING'])
  assert.equal(capabilityValue.capability.execution_release, 'BLOCKED')
  assert.equal(capabilityValue.authority_effect, 'NONE')

  const runtimeMissing = await client.callTool({ name: 'aegis_dlss5_runtime_verify', arguments: { evidence_json: '{}' } })
  const runtimeMissingText = runtimeMissing.content.find((entry) => entry.type === 'text')
  assert(runtimeMissingText && 'text' in runtimeMissingText)
  const runtimeMissingValue = JSON.parse(runtimeMissingText.text)
  assert.equal(runtimeMissingValue.status, 'RUNTIME_PROBE_NOT_VERIFIED')
  assert.deepEqual(runtimeMissingValue.reason_codes, ['RUNTIME_EVIDENCE_INVALID'])
  assert.equal(runtimeMissingValue.rendering_claim, 'NOT_ESTABLISHED')
  assert.equal(runtimeMissingValue.authority_effect, 'NONE')

  const runtimeBadJson = await client.callTool({ name: 'aegis_dlss5_runtime_verify', arguments: { evidence_json: '{x' } })
  const runtimeBadJsonText = runtimeBadJson.content.find((entry) => entry.type === 'text')
  assert(runtimeBadJsonText && 'text' in runtimeBadJsonText)
  const runtimeBadJsonValue = JSON.parse(runtimeBadJsonText.text)
  assert.equal(runtimeBadJsonValue.status, 'RUNTIME_PROBE_NOT_VERIFIED')
  assert.deepEqual(runtimeBadJsonValue.reason_codes, ['RUNTIME_EVIDENCE_JSON_INVALID'])
  assert.equal(runtimeBadJsonValue.execution_release, 'BLOCKED')

  const authorityIndex = await client.readResource({ uri: 'aegis://authority/index' })
  assert.match(authorityIndex.contents[0].text, /AEGIS/i)

  const repoMap = await client.readResource({ uri: 'aegis://authority/repo-map' })
  assert.match(repoMap.contents[0].text, /WIRED|DORMANT|BROKEN|DEAD/i)

  console.log('MCP_RESOURCES_PASS 7 read-only key-free resources + DLSS5 capability/runtime fail-closed tool surface')
} finally {
  await client.close().catch(() => {})
  await new Promise((resolve) => bridge.close(resolve))
}
