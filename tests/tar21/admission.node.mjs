/** Source-bound TAR-21 regression tests. All network, Deno, secrets and provider calls mocked. */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const ts = require('typescript')
import {
  authorizeSlackMachine, signSlackAgentRequest, verifySlackSignature,
  allowedSlackActor, readBoundedBody, parseSlackPayload,
} from '../../supabase/functions/_shared/slack-agent-auth.ts'
import { reserveAgentExecution } from '../../supabase/functions/_shared/agent-budget.ts'
import { authorizeNebiusCaller, isNebiusRequestBounded } from '../../supabase/functions/_shared/nebius-auth.ts'

const root = resolve(import.meta.dirname, '../..')
const agentSource = readFileSync(resolve(root, 'supabase/functions/agent/index.ts'), 'utf8')
const slackSource = readFileSync(resolve(root, 'supabase/functions/slack-events/index.ts'), 'utf8')
const key = 'LOCAL_TEST_NON_PRODUCTION_MACHINE_KEY_1234567890'
const signingSecret = 'LOCAL_TEST_NON_PRODUCTION_SLACK_SIGNING_123456789'
const keyId = 'tar21-test-v1'
const now = () => Math.floor(Date.now() / 1000)
const baseBody = () => ({ task: 'Status?', scope: 'slack:answer', slack: {
  team_id: 'T12345', user_id: 'U12345', event_id: 'Ev12345678',
} })
const config = (opts = {}) => ({ key, keyId, allowedTeams: 'T12345', allowedUsers: 'U12345', allowedActors: 'T12345:U12345', ...opts })
const makeMachineRequest = async (body = baseBody(), extraHeaders = {}) => {
  const signed = await signSlackAgentRequest(body, key, keyId)
  return {
    rawBody: signed.rawBody,
    headers: new Headers({ ...signed.headers, ...extraHeaders }),
  }
}

// Pure credential properties, including wrong key, wrong identity, stale timestamp.
test('HMAC machine assertion binds exact request body and actor', async () => {
  const valid = await makeMachineRequest()
  assert.deepEqual(await authorizeSlackMachine(valid.headers, valid.rawBody, config()), baseBody())
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody + ' ', config()), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ key: 'B'.repeat(40) })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ allowedTeams: 'T99999' })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ allowedUsers: 'U99999' })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ allowedUsers: '' })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ allowedTeams: '' })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ allowedActors: '' })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ allowedActors: 'T99999:U12345' })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody, config({ key: '' })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody,
    config({ nowSeconds: now() + 61 })), null)
  assert.equal(await authorizeSlackMachine(valid.headers, valid.rawBody,
    config({ nowSeconds: now() - 31 })), null)
  const both = await makeMachineRequest(baseBody(), { authorization: 'Bearer header.payload.signature' })
  assert.equal(await authorizeSlackMachine(both.headers, both.rawBody, config()), null)
  const invalidScope = await makeMachineRequest({ ...baseBody(), scope: 'slack:admin' })
  assert.equal(await authorizeSlackMachine(invalidScope.headers, invalidScope.rawBody, config()), null)
  const elevated = await makeMachineRequest({ ...baseBody(), notify: true })
  assert.equal(await authorizeSlackMachine(elevated.headers, elevated.rawBody, config()), null)
  const excessive = await makeMachineRequest({ ...baseBody(), task: 'x'.repeat(513) })
  assert.equal(await authorizeSlackMachine(excessive.headers, excessive.rawBody, config()), null)
  const headerTampered = await makeMachineRequest()
  headerTampered.headers.set('x-aegis-machine-key-id', 'other')
  assert.equal(await authorizeSlackMachine(headerTampered.headers, headerTampered.rawBody, config()), null)
})

test('Slack ingress signature: verified, missing secret denied, altered/stale/bad time denied', async () => {
  const raw = 'command=%2Faegis&team_id=T12345&user_id=U12345&channel_id=C12345&text=hello'
  const tsNow = String(now())
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(signingSecret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  const mac = await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(`v0:${tsNow}:${raw}`))
  const signature = 'v0=' + Buffer.from(mac).toString('hex')
  assert.equal(await verifySlackSignature(raw, tsNow, signature, signingSecret), true)
  assert.equal(await verifySlackSignature(raw, tsNow, signature, ''), false)
  assert.equal(await verifySlackSignature(raw + 'x', tsNow, signature, signingSecret), false)
  assert.equal(await verifySlackSignature(raw, 'NaN', signature, signingSecret), false)
  assert.equal(await verifySlackSignature(raw, tsNow, signature, signingSecret, now() + 301), false)
  assert.equal(await verifySlackSignature(raw, tsNow, 'v0=0', signingSecret), false)
  assert.equal(allowedSlackActor('T12345', 'U12345', 'T12345', 'U12345', 'T12345:U12345'), true)
  assert.equal(allowedSlackActor('T12345', 'U12345', '', 'U12345', 'T12345:U12345'), false)
  const parsed = await parseSlackPayload(raw, 'application/x-www-form-urlencoded', tsNow)
  assert.equal(parsed?.kind, 'task')
  assert.equal(parsed?.job?.slack.team_id, 'T12345')
  assert.equal(parsed?.job?.slack.user_id, 'U12345')
  assert.equal(parsed?.job?.slack.event_id.length, 64)
})

test('Signed Slack event fixture enforces team/user and rejects bot events', async () => {
  const event = {
    type: 'event_callback', team_id: 'T12345', event_id: 'Ev12345678',
    event: { type: 'app_mention', user: 'U12345', channel: 'C12345', ts: '100.22', text: '<@U5555> report' },
  }
  const parsed = await parseSlackPayload(JSON.stringify(event), 'application/json', String(now()))
  assert.equal(parsed?.kind, 'task')
  assert.equal(parsed?.job?.task, 'report')
  assert.equal(parsed?.job?.threadTs, '100.22')
  const bot = structuredClone(event)
  bot.event.bot_id = 'B12345'
  assert.equal((await parseSlackPayload(JSON.stringify(bot), 'application/json', String(now())))?.kind, 'ignore')
})

test('Transport body reading rejects both declared and streamed overflow', async () => {
  assert.equal(await readBoundedBody(new Request('https://mock.invalid/', { method: 'POST', body: 'abc' })), 'abc')
  const oversized = new Request('https://mock.invalid/', { method: 'POST', body: 'x'.repeat(16385) })
  assert.equal(await readBoundedBody(oversized), null)
  const declared = new Request('https://mock.invalid/', {
    method: 'POST', body: 'abc', headers: { 'content-length': '999999' },
  })
  assert.equal(await readBoundedBody(declared), null)
})

test('Budget RPC handles duplicates, exhausted quotas, missing RPC and malformed actors without fail-open', async () => {
  const calls = []
  const rpc = async (name, args) => { calls.push([name, args]); return { data: true, error: null } }
  assert.equal(await reserveAgentExecution({ rpc }, 'slack', 'T12345:U12345', 'slack:T12345:Ev12345678'), 'reserved')
  assert.equal(calls[0][0], 'aegis_agent_reserve_budget')
  assert.deepEqual(calls[0][1], { p_kind: 'slack', p_actor_id: 'T12345:U12345', p_request_key: 'slack:T12345:Ev12345678' })
  assert.equal(await reserveAgentExecution({ rpc: async () => ({ data: false, error: null }) },
    'slack', 'T12345:U12345', 'slack:T12345:Ev12345678'), 'denied')
  assert.equal(await reserveAgentExecution({ rpc: async () => ({ data: null, error: { code: 'PGRST202' } }) },
    'slack', 'T12345:U12345', 'slack:T12345:Ev12345678'), 'unavailable')
  assert.equal(await reserveAgentExecution({ rpc: async () => { throw Error('network unavailable') } },
    'slack', 'T12345:U12345', 'slack:T12345:Ev12345678'), 'unavailable')
  assert.equal(await reserveAgentExecution({ rpc }, 'slack', 'bad actor/escape', 'slack:T12345:Ev12345678'), 'denied')
  assert.equal(calls.length, 1)
})

function compileTail(source, marker) {
  const index = source.indexOf(marker)
  assert.ok(index >= 0, `Handler marker missing: ${marker}`)
  return ts.transpileModule(source.slice(index), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
    reportDiagnostics: true,
  }).outputText
}

function agentProbe(options = {}) {
  let handler = null
  const calls = { user: [], rpc: [], inference: [], notify: [] }
  const getUser = async jwt => {
    calls.user.push(jwt)
    if (options.authFailure) return { data: null, error: Error('mock auth failure') }
    return { data: { user: { id: options.userId ?? 'operator-1' } }, error: null }
  }
  const createClient = () => ({ auth: { getUser }, rpc: async (name, args) => {
    calls.rpc.push({ name, args })
    return options.rpcError ? { data: null, error: { code: 'PGRST202' } }
      : { data: options.admit ?? true, error: null }
  } })
  const env = { get: keyName => ({
    AEGIS_AGENT_ALLOWED_USER_IDS: options.allowed ?? 'operator-1',
    AEGIS_SLACK_AGENT_HMAC_KEY: options.machineKey ?? key,
    AEGIS_SLACK_AGENT_KEY_ID: keyId,
    AEGIS_SLACK_ALLOWED_TEAM_IDS: options.allowedTeams ?? 'T12345',
    AEGIS_SLACK_ALLOWED_USER_IDS: options.allowedUsers ?? 'U12345',
    AEGIS_SLACK_ALLOWED_ACTORS: options.allowedActors ?? 'T12345:U12345',
  })[keyName] ?? '' }
  const deno = { env, serve: callback => { handler = callback } }
  const runAgent = async (task, context, mode) => {
    calls.inference.push({ task, context, mode })
    return { result: 'MOCK_ONLY', actions: [] }
  }
  const fetch = async (...args) => { calls.notify.push(args); throw Error('unexpected fetch') }
  const compiled = compileTail(agentSource, 'Deno.serve(async (req) => {')
  new Function('Deno', 'Response', 'CORS', 'ANTHROPIC_API_KEY', 'SUPABASE_URL',
    'SERVICE_KEY', 'createClient', 'authorizeNebiusCaller', 'isNebiusRequestBounded',
    'authorizeSlackMachine', 'readBoundedBody', 'reserveAgentExecution', 'runAgent',
    'NOTIFY_SECRET', 'fetch', 'crypto', compiled)(
    deno, Response, {}, 'MOCK_NEVER_SENT', 'https://mock.invalid', 'MOCK_NOT_REAL',
    createClient, authorizeNebiusCaller, isNebiusRequestBounded,
    authorizeSlackMachine, readBoundedBody, reserveAgentExecution, runAgent,
    '', fetch, crypto,
  )
  return { handler, calls }
}

const callAgent = async (handler, raw, headers) => handler(new Request('https://mock.invalid/functions/v1/agent', {
  method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: raw,
}))

test('Actual agent handler denies no credentials before paid work and parsing', async () => {
  const { handler, calls } = agentProbe()
  const response = await callAgent(handler, JSON.stringify({ task: 'status' }))
  assert.equal(response.status, 401)
  assert.equal(calls.user.length, 0)
  assert.equal(calls.rpc.length, 0)
  assert.equal(calls.inference.length, 0)
})

test('Actual agent handler keeps strict JWT and existing allowlist path', async () => {
  const { handler, calls } = agentProbe()
  const good = await callAgent(handler, JSON.stringify({ task: 'status' }),
    { authorization: 'Bearer header.payload.signature' })
  assert.equal(good.status, 200)
  assert.deepEqual(calls.user, ['header.payload.signature'])
  assert.equal(calls.rpc.length, 1)
  assert.equal(calls.rpc[0].args.p_kind, 'operator')
  assert.equal(calls.inference[0].mode, 'operator')
  for (const bad of [
    agentProbe({ allowed: '' }), agentProbe({ userId: 'unauthorized-user' }), agentProbe({ authFailure: true }),
  ]) {
    const response = await callAgent(bad.handler, JSON.stringify({ task: 'status' }),
      { authorization: 'Bearer header.payload.signature' })
    assert.equal(response.status, 401)
    assert.equal(bad.calls.rpc.length, 0)
    assert.equal(bad.calls.inference.length, 0)
  }
})

test('Actual agent machine path grants ONLY no-tools Slack scope after durable reservation', async () => {
  const { rawBody, headers } = await makeMachineRequest()
  const { handler, calls } = agentProbe()
  const response = await callAgent(handler, rawBody, Object.fromEntries(headers.entries()))
  assert.equal(response.status, 200)
  assert.equal(calls.user.length, 0)
  assert.equal(calls.rpc.length, 1)
  assert.equal(calls.rpc[0].args.p_request_key, 'slack:T12345:Ev12345678')
  assert.equal(calls.inference[0].mode, 'slack')
  assert.equal(calls.notify.length, 0)
})

test('Actual agent machine handler rejects forged, replayed, exhausted, unavailable and mixed credentials', async () => {
  const signed = await makeMachineRequest()
  const invalid = [
    { hdr: { 'x-aegis-machine-key-id': keyId }, body: JSON.stringify({ task: 'hello' }) },
    { hdr: Object.fromEntries(signed.headers.entries()), body: signed.rawBody + ' ' },
    { hdr: { ...Object.fromEntries(signed.headers.entries()), authorization: 'Bearer header.payload.signature' }, body: signed.rawBody },
  ]
  for (const input of invalid) {
    const p = agentProbe()
    const res = await callAgent(p.handler, input.body, input.hdr)
    assert.equal(res.status, 401)
    assert.equal(p.calls.rpc.length, 0)
    assert.equal(p.calls.inference.length, 0)
  }
  for (const [opts, status] of [
    [{ admit: false }, 429], [{ rpcError: true }, 503], [{ allowedUsers: '' }, 401],
    [{ machineKey: 'other-machine-key-string-12345678' }, 401],
  ]) {
    const p = agentProbe(opts)
    const res = await callAgent(p.handler, signed.rawBody, Object.fromEntries(signed.headers.entries()))
    assert.equal(res.status, status)
    assert.equal(p.calls.inference.length, 0)
  }
})

test('Actual agent handler bounds payload before reservation and inference', async () => {
  for (const body of [{ task: 'x'.repeat(4097) }, { task: 'status', notify: 'yes' }, { task: 1 }, null]) {
    const p = agentProbe()
    const res = await callAgent(p.handler, JSON.stringify(body), { authorization: 'Bearer header.payload.signature' })
    assert.equal(res.status, 400)
    assert.equal(p.calls.rpc.length, 0)
    assert.equal(p.calls.inference.length, 0)
  }
})

test('Actual compiled agent model loop grants Slack a single call, zero tools and 256 max tokens', async () => {
  const marker = 'async function runAgent('
  const start = agentSource.indexOf(marker)
  const stop = agentSource.indexOf('// ── HTTP handler', start)
  assert.ok(start >= 0 && stop > start)
  const code = ts.transpileModule(agentSource.slice(start, stop), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
  }).outputText
  const requests = [], toolCalls = []
  const fakeFetch = async (_url, init) => {
    requests.push(JSON.parse(init.body))
    return { ok: true, json: async () => ({ stop_reason: 'tool_use', content: [
      { type: 'tool_use', id: 'tool123', name: 'query_purchases', input: {} },
    ] }) }
  }
  const runAgent = new Function('fetch', 'ANTHROPIC_API_KEY', 'SYSTEM', 'TOOLS', 'runTool',
    `${code}\nreturn runAgent;`)(fakeFetch, 'NO_REAL_KEY', 'MOCK_SYSTEM', [{ name: 'query_purchases' }],
    async name => { toolCalls.push(name); return 'should-not-run' })
  const result = await runAgent('status?', undefined, 'slack')
  assert.equal(requests.length, 1)
  assert.equal(requests[0].max_tokens, 256)
  assert.deepEqual(requests[0].tools, [])
  assert.deepEqual(toolCalls, [])
  assert.deepEqual(result.actions, [])
})

// Slack HTTP handler uses only in-memory mocked dependencies and EdgeRuntime.waitUntil.
function slackProbe(opts = {}) {
  let handler = null
  const background = [], jobs = [], replies = []
  const env = { get: keyName => ({
    SLACK_SIGNING_SECRET: opts.signingSecret ?? signingSecret,
    SLACK_BOT_TOKEN: 'MOCK_BOT_NO_NETWORK', SUPABASE_URL: 'https://mock.supabase.co',
    AEGIS_SLACK_ALLOWED_TEAM_IDS: opts.allowedTeams ?? 'T12345',
    AEGIS_SLACK_ALLOWED_USER_IDS: opts.allowedUsers ?? 'U12345',
    AEGIS_SLACK_ALLOWED_ACTORS: opts.allowedActors ?? 'T12345:U12345',
    AEGIS_SLACK_AGENT_HMAC_KEY: key, AEGIS_SLACK_AGENT_KEY_ID: keyId,
  })[keyName] ?? '' }
  const previous = globalThis.EdgeRuntime
  globalThis.EdgeRuntime = { waitUntil: value => background.push(value) }
  const code = compileTail(slackSource, 'Deno.serve(async (req) => {')
  new Function('Deno', 'Response', 'SLACK_SIGNING_SECRET', 'SLACK_BOT_TOKEN',
    'SUPABASE_URL', 'SLACK_ALLOWED_TEAM_IDS', 'SLACK_ALLOWED_USER_IDS', 'SLACK_ALLOWED_ACTORS',
    'MACHINE_KEY', 'MACHINE_KEY_ID', 'readBoundedBody', 'verifySlackSignature',
    'parseSlackPayload', 'allowedSlackActor', 'runAgent', 'slackReply', code)(
    { env, serve: cb => { handler = cb } }, Response, env.get('SLACK_SIGNING_SECRET'), env.get('SLACK_BOT_TOKEN'),
    env.get('SUPABASE_URL'), env.get('AEGIS_SLACK_ALLOWED_TEAM_IDS'),
    env.get('AEGIS_SLACK_ALLOWED_USER_IDS'), env.get('AEGIS_SLACK_ALLOWED_ACTORS'), env.get('AEGIS_SLACK_AGENT_HMAC_KEY'),
    env.get('AEGIS_SLACK_AGENT_KEY_ID'), readBoundedBody, verifySlackSignature,
    parseSlackPayload, allowedSlackActor,
    async job => { jobs.push(job); return 'Mock answer' },
    async (...args) => replies.push(args),
  )
  return { handler, background, jobs, replies, restore: () => { globalThis.EdgeRuntime = previous } }
}

async function signedSlackRequest(raw) {
  const timestamp = String(now())
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(signingSecret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  const bytes = await crypto.subtle.sign('HMAC', k, new TextEncoder().encode(`v0:${timestamp}:${raw}`))
  return new Request('https://mock.invalid/functions/v1/slack-events', { method: 'POST', body: raw,
    headers: { 'content-type': 'application/x-www-form-urlencoded',
      'x-slack-request-timestamp': timestamp, 'x-slack-signature': 'v0=' + Buffer.from(bytes).toString('hex') },
  })
}

test('Actual Slack handler accepts an allowed, signed slash command without user JWT or notify secret', async () => {
  const p = slackProbe()
  try {
    const raw = new URLSearchParams({ command: '/aegis', text: 'status?', team_id: 'T12345',
      user_id: 'U12345', channel_id: 'C12345' }).toString()
    const response = await p.handler(await signedSlackRequest(raw))
    assert.equal(response.status, 200)
    assert.equal(p.background.length, 1)
    await Promise.all(p.background)
    assert.equal(p.jobs.length, 1)
    assert.equal(p.jobs[0].scope, 'slack:answer')
    assert.equal(p.jobs[0].slack.user_id, 'U12345')
    assert.equal(p.replies.length, 1)
  } finally { p.restore() }
})

test('Actual Slack handler fail-closes missing signing secret and unapproved actors before dispatch', async () => {
  const raw = new URLSearchParams({ command: '/aegis', text: 'status?', team_id: 'T12345',
    user_id: 'U12345', channel_id: 'C12345' }).toString()
  for (const [opts, expectedStatus] of [
    [{ signingSecret: '' }, 503], [{ allowedTeams: 'T90000' }, 403],
    [{ allowedUsers: 'U90000' }, 403], [{ allowedUsers: '' }, 503],
    [{ allowedActors: '' }, 503], [{ allowedActors: 'T99999:U12345' }, 403],
  ]) {
    const p = slackProbe(opts)
    try {
      assert.equal((await p.handler(await signedSlackRequest(raw))).status, expectedStatus)
      assert.equal(p.jobs.length, 0)
      assert.equal(p.background.length, 0)
    } finally { p.restore() }
  }
})
