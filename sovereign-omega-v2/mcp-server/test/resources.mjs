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

  const authorityIndex = await client.readResource({ uri: 'aegis://authority/index' })
  assert.match(authorityIndex.contents[0].text, /AEGIS/i)

  const repoMap = await client.readResource({ uri: 'aegis://authority/repo-map' })
  assert.match(repoMap.contents[0].text, /WIRED|DORMANT|BROKEN|DEAD/i)

  console.log('MCP_RESOURCES_PASS 5 read-only key-free resources')
} finally {
  await client.close().catch(() => {})
  await new Promise((resolve) => bridge.close(resolve))
}
