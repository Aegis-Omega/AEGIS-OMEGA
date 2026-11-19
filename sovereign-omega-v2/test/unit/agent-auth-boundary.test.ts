// TAR-21 additive replacement for PR #800's original agent-auth-boundary.test.ts.
// Preserves JWT/allowlist and actual HTTP negative tests, adding scoped Slack identity.
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import * as ts from 'typescript'
import {
  authorizeNebiusCaller, isNebiusRequestBounded,
} from '../../../supabase/functions/_shared/nebius-auth.ts'
import {
  authorizeSlackMachine, readBoundedBody, signSlackAgentRequest,
} from '../../../supabase/functions/_shared/slack-agent-auth.ts'
import { reserveAgentExecution } from '../../../supabase/functions/_shared/agent-budget.ts'

const candidates = [
  resolve(process.cwd(), '../supabase/functions/agent/index.ts'),
  resolve(process.cwd(), 'supabase/functions/agent/index.ts'),
]
const sourcePath = candidates.find(existsSync)
if (!sourcePath) throw Error('AEGIS agent source missing')
const agentSource = readFileSync(sourcePath, 'utf8')
const jwt = 'Bearer header.payload.signature'
const localKey = 'LOCAL_ONLY_NOT_A_REAL_SECRET_1234567890123456'
const machineBody = {
  task: 'status', scope: 'slack:answer' as const,
  slack: { team_id: 'T12345', user_id: 'U12345', event_id: 'Ev12345678' },
}

describe('AEGIS agent caller authorization, inherited PR #800 invariants', () => {
  it('keeps verified operator JWT/allowlist before operator input, budget or inference', () => {
    const handler = agentSource.slice(agentSource.indexOf('Deno.serve(async (req) => {'))
    expect(handler).toContain("req.headers.get('Authorization')")
    expect(handler).toContain("Deno.env.get('AEGIS_AGENT_ALLOWED_USER_IDS') ?? ''")
    expect(handler).toContain('authClient.auth.getUser(jwt)')
    expect(handler).toContain('if (!permitted || !operatorId)')
    const userBranch = handler.slice(handler.indexOf('let operatorId: string | null = null'))
    expect(userBranch.indexOf('const permitted = await authorizeNebiusCaller(')).toBeGreaterThanOrEqual(0)
    expect(userBranch.indexOf('const permitted = await authorizeNebiusCaller(')).toBeLessThan(userBranch.indexOf('raw = await readBoundedBody(req)'))
    expect(userBranch.indexOf('raw = await readBoundedBody(req)')).toBeLessThan(userBranch.indexOf('reserveAgentExecution('))
    expect(handler).toContain("await runAgent(task, boundedContext, mode)")
    expect(agentSource).toContain("import { authorizeNebiusCaller, isNebiusRequestBounded } from '../_shared/nebius-auth.ts'")
  })

  it('never contacts identity service without JWT and allowlist', async () => {
    const verify = vi.fn(async () => 'operator-1')
    expect(await authorizeNebiusCaller(null, 'operator-1', verify)).toBe(false)
    expect(await authorizeNebiusCaller('Bearer anon-public-key', 'operator-1', verify)).toBe(false)
    expect(await authorizeNebiusCaller(jwt, '', verify)).toBe(false)
    expect(verify).not.toHaveBeenCalled()
  })

  it('denies wrong identity, null verification and identity-service failure', async () => {
    expect(await authorizeNebiusCaller(jwt, 'operator-1', async () => 'other-user')).toBe(false)
    expect(await authorizeNebiusCaller(jwt, 'operator-1', async () => null)).toBe(false)
    expect(await authorizeNebiusCaller(jwt, 'operator-1', async () => { throw Error('mock auth unavailable') })).toBe(false)
  })

  it('only accepts explicitly allowlisted server-verified operator', async () => {
    const verify = vi.fn(async () => 'operator-1')
    expect(await authorizeNebiusCaller(jwt, 'other-user,operator-1', verify)).toBe(true)
    expect(verify).toHaveBeenCalledExactlyOnceWith('header.payload.signature')
  })
})

describe('AEGIS actual TS HTTP handler, mocks only and no outbound network', () => {
  type Options = {
    bearer?: string | null
    machine?: { rawBody: string; headers: Record<string, string> }
    allowed?: string
    userId?: string
    authFailure?: boolean
    body?: unknown
    malformed?: boolean
    budgetDecision?: boolean
    budgetError?: boolean
    allowedActors?: string
  }
  async function probe(opts: Options = {}) {
    const source = agentSource.slice(agentSource.indexOf('Deno.serve(async (req) => {'))
    const compiled = ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
    }).outputText
    let handler: ((req: Request) => Promise<Response>) | null = null
    const getUser = vi.fn(async () => opts.authFailure
      ? { data: null, error: Error('mock unavailable') }
      : { data: { user: { id: opts.userId ?? 'operator-1' } }, error: null })
    const rpc = vi.fn(async () => opts.budgetError
      ? { data: null, error: { code: 'PGRST202' } }
      : { data: opts.budgetDecision ?? true, error: null })
    const createClient = vi.fn(() => ({ auth: { getUser }, rpc }))
    const runAgent = vi.fn(async () => ({ result: 'MOCK_ONLY', actions: [] }))
    const fetch = vi.fn(async () => { throw Error('Unexpected outbound call') })
    const env = { get: (key: string) => ({
      AEGIS_AGENT_ALLOWED_USER_IDS: opts.allowed ?? 'operator-1',
      AEGIS_SLACK_AGENT_HMAC_KEY: localKey,
      AEGIS_SLACK_AGENT_KEY_ID: 'test-v1',
      AEGIS_SLACK_ALLOWED_TEAM_IDS: 'T12345',
      AEGIS_SLACK_ALLOWED_USER_IDS: 'U12345',
      AEGIS_SLACK_ALLOWED_ACTORS: opts.allowedActors ?? 'T12345:U12345',
    } as Record<string, string>)[key] ?? '' }
    const deno = { env, serve: (fn: (req: Request) => Promise<Response>) => { handler = fn } }
    new Function('Deno', 'Response', 'CORS', 'ANTHROPIC_API_KEY', 'SUPABASE_URL',
      'SERVICE_KEY', 'createClient', 'authorizeNebiusCaller', 'isNebiusRequestBounded',
      'authorizeSlackMachine', 'readBoundedBody', 'reserveAgentExecution', 'runAgent',
      'NOTIFY_SECRET', 'fetch', 'crypto', compiled)(
      deno, Response, {}, 'MOCK_NEVER_SENT', 'https://mock.invalid',
      'FAKE_DB_KEY_ONLY', createClient, authorizeNebiusCaller, isNebiusRequestBounded,
      authorizeSlackMachine, readBoundedBody, reserveAgentExecution, runAgent, '', fetch, crypto,
    )
    if (!handler) throw Error('Handler not registered')
    const raw = opts.machine?.rawBody ?? (opts.malformed ? '{not-json' : JSON.stringify(
      Object.hasOwn(opts, 'body') ? opts.body : { task: 'local-only' },
    ))
    const headers = new Headers({
      'content-type': 'application/json',
      ...(opts.bearer ? { authorization: opts.bearer } : {}),
      ...(opts.machine ? opts.machine.headers : {}),
    })
    const res = await (handler as (req: Request) => Promise<Response>)(new Request('https://mock.invalid/functions/v1/agent', {
      method: 'POST', headers, body: raw,
    }))
    return { res, getUser, rpc, createClient, runAgent, fetch }
  }

  it('denies unauthenticated entry before auth, quota or execution', async () => {
    const p = await probe()
    expect(p.res.status).toBe(401)
    expect(p.createClient).not.toHaveBeenCalled()
    expect(p.rpc).not.toHaveBeenCalled()
    expect(p.runAgent).not.toHaveBeenCalled()
  })

  it('denies public key / missing allowlist without identity lookup', async () => {
    for (const opts of [{ bearer: 'Bearer anon-public-key' }, { bearer: jwt, allowed: '' }]) {
      const p = await probe(opts)
      expect(p.res.status).toBe(401)
      expect(p.getUser).not.toHaveBeenCalled()
      expect(p.rpc).not.toHaveBeenCalled()
    }
  })

  it('denies wrong user and identity-service failure before quota', async () => {
    for (const opts of [{ bearer: jwt, userId: 'wrong-user' }, { bearer: jwt, authFailure: true }]) {
      const p = await probe(opts)
      expect(p.res.status).toBe(401)
      expect(p.rpc).not.toHaveBeenCalled()
      expect(p.runAgent).not.toHaveBeenCalled()
    }
  })

  it('runs verified operator with an atomic budget reservation', async () => {
    const p = await probe({ bearer: jwt })
    expect(p.res.status).toBe(200)
    expect(p.getUser).toHaveBeenCalledExactlyOnceWith('header.payload.signature')
    expect(p.rpc).toHaveBeenCalledOnce()
    expect(p.runAgent).toHaveBeenCalledExactlyOnceWith('local-only', undefined, 'operator')
    expect(p.fetch).not.toHaveBeenCalled()
  })

  it('rejects malformed and oversized requests before quota or inference', async () => {
    const bad: Options[] = [
      { body: { task: 'x'.repeat(4097) } }, { body: { task: 'ok', context: 'x'.repeat(4097) } },
      { body: { task: 7 } }, { body: { task: 'ok', context: { raw: true } } },
      { body: { task: 'ok', notify: 'yes' } }, { body: null }, { malformed: true },
    ]
    for (const opts of bad) {
      const p = await probe({ bearer: jwt, ...opts })
      expect(p.res.status).toBe(400)
      expect(p.rpc).not.toHaveBeenCalled()
      expect(p.runAgent).not.toHaveBeenCalled()
    }
  })

  it('accepts HMAC-bound Slack machine actor with no user JWT, no notify and scoped mode', async () => {
    const signed = await signSlackAgentRequest(machineBody, localKey, 'test-v1')
    const p = await probe({ machine: { rawBody: signed.rawBody, headers: signed.headers } })
    expect(p.res.status).toBe(200)
    expect(p.getUser).not.toHaveBeenCalled()
    expect(p.rpc).toHaveBeenCalledOnce()
    expect(p.runAgent).toHaveBeenCalledExactlyOnceWith('status', 'Slack team T12345, user U12345', 'slack')
    expect(p.fetch).not.toHaveBeenCalled()
  })

  it('denies mixed credentials, unauthorized Slack actor and RPC failure', async () => {
    const signed = await signSlackAgentRequest(machineBody, localKey, 'test-v1')
    const machine = { rawBody: signed.rawBody, headers: signed.headers }
    for (const opts of [
      { machine, bearer: jwt },
      { machine, allowedActors: '' },
      { machine, budgetDecision: false },
      { machine, budgetError: true },
    ]) {
      const p = await probe(opts)
      expect([401, 429, 503]).toContain(p.res.status)
      expect(p.runAgent).not.toHaveBeenCalled()
    }
  })
})
