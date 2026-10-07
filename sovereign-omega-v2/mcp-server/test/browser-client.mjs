import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'

const clientUrl = new URL('../web/client.mjs', import.meta.url)
test('browser client performs a real MCP lifecycle and validates correlated responses', async () => {
  assert.ok(existsSync(clientUrl), 'Missing browser MCP transport implementation')
  const { BrowserMcpClient } = await import(clientUrl)
  const calls = []
  const client = new BrowserMcpClient({
    endpoint: 'http://127.0.0.1:7891/mcp',
    localToken: 'test-only-connection-token',
    fetchImpl: async (url, init) => {
      const message = init.body ? JSON.parse(init.body) : null
      calls.push({ url, init, message })
      if (init.method === 'DELETE') return new Response(null, { status: 200 })
      if (message.method === 'notifications/initialized') return new Response(null, { status: 202 })
      const result = message.method === 'initialize'
        ? { protocolVersion: '2025-11-25', capabilities: { tools: {} }, serverInfo: { name: 'fixture', version: '1' } }
        : message.method === 'tools/list' ? { tools: [{ name: 'aegis_authority_policy' }] }
        : { content: [{ type: 'text', text: '{"observed":true}' }] }
      return new Response(JSON.stringify({ jsonrpc: '2.0', id: message.id, result }), {
        headers: { 'Content-Type': 'application/json', 'Mcp-Session-Id': 'fixture-session' },
      })
    },
  })
  await client.initialize()
  assert.equal((await client.listTools()).tools[0].name, 'aegis_authority_policy')
  await client.callTool('aegis_authority_policy', {})
  assert.deepEqual(calls.map(c => c.message?.method), ['initialize', 'notifications/initialized', 'tools/list', 'tools/call'])
  for (const c of calls.slice(1)) {
    assert.equal(c.init.headers['Mcp-Session-Id'], 'fixture-session')
    assert.equal(c.init.headers['MCP-Protocol-Version'], '2025-11-25')
  }
  assert.match(calls[0].init.headers.Accept, /application\/json.*text\/event-stream/)
  assert.equal(JSON.stringify(client.trace).includes('test-only-connection-token'), false)
  assert.equal(JSON.stringify(client.trace).includes('fixture-session'), false)
  await client.close()
  await assert.rejects(() => client.listTools(), /initialized/i)
})

test('browser client consumes fragmented SSE without accepting a different RPC id', async () => {
  assert.ok(existsSync(clientUrl), 'Missing browser MCP transport implementation')
  const { readRpcResponse } = await import(clientUrl)
  const encoder = new TextEncoder()
  const chunks = ['event: message\r\ndata: {"jsonrpc":"2.0","method":"notifications/message","params":{}}\r\n\r\n',
    'data: {"jsonrpc":"2.0","id":7,', '"result":{"ok":true}}\r\n\r\n']
  const response = new Response(new ReadableStream({ start(controller) {
    for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
    controller.close()
  } }), { headers: { 'content-type': 'text/event-stream' } })
  assert.deepEqual((await readRpcResponse(response, 7)).result, { ok: true })
  await assert.rejects(() => readRpcResponse(new Response('{"jsonrpc":"2.0","id":8,"result":{}}',
    { headers: { 'content-type': 'application/json' } }), 7), /id|correlat/i)
})

test('evidence validation rejects changed policy bytes, fake denials, bad ids, status and missing session binding', async (t) => {
  const { validateDemoTrace, sha256 } = await import(clientUrl)
  const raw = JSON.stringify({ schema_version: '1.0.0', classes: { D3: { approval: 'EXPLICIT' } } })
  const policy = { source: { path: 'harness/policies/consequence-policy.v1.json', sha256: await sha256(raw) },
    policy_json: raw, policy: JSON.parse(raw), authority_effect: 'NONE', external_effect: 'NONE' }
  const denied = { authority: { outcome: 'DENIED', denial_codes: ['IDENTITY_UNAVAILABLE'] }, external_effect: 'NOT_EXECUTED' }
  const text = body => ({ content: [{ type: 'text', text: JSON.stringify(body) }] })
  const event = (method, id, result, params = {}) => ({ method, status: 200, request: { jsonrpc: '2.0', id, method, params },
    request_headers: { session_present: true, protocol_version: '2025-11-25' }, response: { jsonrpc: '2.0', id, result } })
  const trace = [event('initialize', 1, { protocolVersion: '2025-11-25' }),
    { method: 'notifications/initialized', request: { jsonrpc: '2.0', method: 'notifications/initialized' },
      status: 202, response: null, request_headers: { session_present: true, protocol_version: '2025-11-25' } },
    event('tools/list', 2, { tools: [{ name: 'aegis_authority_policy' }, { name: 'aegis_governed_claude_call' }] }),
    event('tools/call', 3, text(policy), { name: 'aegis_authority_policy' }),
    event('tools/call', 4, { ...text(denied), isError: true }, { name: 'aegis_governed_claude_call' })]
  // This is a validator unit fixture, never an actual HTTP observation.
  assert.equal((await validateDemoTrace(trace)).verdict, 'PASS')
  const changes = [
    ['missing exchange', copy => copy.pop(), /incomplete/],
    ['wrong RPC id', copy => { copy[4].response.id = 99 }, /correlat/],
    ['HTTP failure', copy => { copy[4].status = 500 }, /HTTP/],
    ['missing session', copy => { copy[4].request_headers.session_present = false }, /session/],
    ['wrong version', copy => { copy[3].request_headers.protocol_version = '1900-01-01' }, /protocol/],
    ['fake admission', copy => { copy[4].response.result = { ...text({ ...denied, authority: { outcome: 'ADMITTED' } }), isError: true } }, /denied/],
    ['execution occurred', copy => { copy[4].response.result = { ...text({ ...denied, external_effect: 'EXECUTED' }), isError: true } }, /denied/],
    ['policy bytes changed', copy => { copy[3].response.result = text({ ...policy, policy_json: raw + ' ' }) }, /sha256/],
    ['policy hash changed', copy => { copy[3].response.result = text({ ...policy, source: { ...policy.source, sha256: '0'.repeat(64) } }) }, /sha256/],
    ['tool error mislabelled success', copy => { copy[4].response.result.isError = false }, /denied/],
  ]
  for (const [name, mutate, pattern] of changes) await t.test(name, async () => {
    const copy = structuredClone(trace); mutate(copy)
    await assert.rejects(() => validateDemoTrace(copy), pattern)
  })
})
