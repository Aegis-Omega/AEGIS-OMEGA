import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'
import * as ts from 'typescript'
import { authorizeNebiusCaller } from '../../../supabase/functions/_shared/nebius-auth.ts'

const jwt = 'Bearer header.payload.signature'
const agentSource = readFileSync(new URL('../../../supabase/functions/agent/index.ts', import.meta.url), 'utf8')

describe('AEGIS paid agent endpoint source-bound auth boundary', () => {
  it('runs the existing JWT+explicit operator allowlist before inference or purchase access', () => {
    const handler = agentSource.slice(agentSource.indexOf('Deno.serve(async (req) => {'))
    expect(handler).toContain("req.headers.get('Authorization')")
    expect(handler).toContain("Deno.env.get('AEGIS_AGENT_ALLOWED_USER_IDS') ?? ''")
    expect(handler).toContain('authClient.auth.getUser(jwt)')
    expect(handler).toMatch(/if \(!permitted\) \{[\s\S]*?status: 401/)
    const gate = handler.indexOf('const permitted = await authorizeNebiusCaller(')
    const execution = handler.indexOf('await runAgent(task, context)')
    const bodyParse = handler.indexOf('await req.json()')
    expect(gate).toBeGreaterThan(0)
    expect(gate).toBeLessThan(bodyParse)
    expect(gate).toBeLessThan(execution)
    expect(agentSource).toContain("import { authorizeNebiusCaller } from '../_shared/nebius-auth.ts'")
  })

  it('does not contact identity service without a well-formed JWT or allowlist', async () => {
    const verify = vi.fn(async () => 'operator-1')
    expect(await authorizeNebiusCaller(null, 'operator-1', verify)).toBe(false)
    expect(await authorizeNebiusCaller('Bearer public-anon-key', 'operator-1', verify)).toBe(false)
    expect(await authorizeNebiusCaller(jwt, '', verify)).toBe(false)
    expect(verify).not.toHaveBeenCalled()
  })

  it('denies unknown, failed or unauthorised identity verification', async () => {
    expect(await authorizeNebiusCaller(jwt, 'operator-1', async () => 'another-user')).toBe(false)
    expect(await authorizeNebiusCaller(jwt, 'operator-1', async () => null)).toBe(false)
    expect(await authorizeNebiusCaller(jwt, 'operator-1', async () => { throw Error('auth unavailable') })).toBe(false)
  })

  it('only admits an explicitly allowed server-verified user', async () => {
    const verify = vi.fn(async () => 'operator-1')
    expect(await authorizeNebiusCaller(jwt, 'other-user,operator-1', verify)).toBe(true)
    expect(verify).toHaveBeenCalledOnce()
    expect(verify).toHaveBeenCalledWith('header.payload.signature')
  })
})


/**
 * Executes the actual compiled HTTP handler from this PR with an isolated Deno
 * facade. No credentials, paid inference, outbound HTTP, database or deploy.
 * Unlike text-only tests, deletion/misordering of the gate causes a red test.
 */
describe('AEGIS paid agent HTTP handler execution boundary', () => {
  type ProbeOptions = {
    authorization?: string | null
    allowed?: string
    userId?: string
    authFailure?: boolean
    serviceConfigured?: boolean
  }

  async function probe(options: ProbeOptions = {}) {
    const start = agentSource.indexOf('Deno.serve(async (req) => {')
    expect(start).toBeGreaterThanOrEqual(0)
    const compiled = ts.transpileModule(agentSource.slice(start), {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
    }).outputText

    let requestHandler: ((req: Request) => Promise<Response>) | null = null
    const getUser = vi.fn(async (_jwt: string) => {
      if (options.authFailure) throw Error('mock Supabase Auth unavailable')
      return { data: { user: { id: options.userId ?? 'operator-1' } }, error: null }
    })
    const createClient = vi.fn(() => ({ auth: { getUser } }))
    const runAgent = vi.fn(async (_task: string) => ({ result: 'MOCK_ONLY', actions: [] }))
    const fetch = vi.fn(async () => { throw Error('unexpected external network attempt') })
    const env = { get: (key: string) => key === 'AEGIS_AGENT_ALLOWED_USER_IDS'
      ? options.allowed ?? 'operator-1' : '' }
    const deno = { env, serve: (fn: (req: Request) => Promise<Response>) => { requestHandler = fn } }

    // The only evaluated text is the local, pinned repository handler. Its
    // external dependencies are injected as bounded mock functions.
    const register = new Function(
      'Deno', 'Response', 'CORS', 'ANTHROPIC_API_KEY', 'SUPABASE_URL',
      'SERVICE_KEY', 'createClient', 'authorizeNebiusCaller', 'runAgent',
      'NOTIFY_SECRET', 'fetch', compiled,
    )
    register(
      deno, Response, {}, 'FAKE-NEVER-SENT', 'https://mock.invalid',
      options.serviceConfigured === false ? '' : 'FAKE-SERVICE-KEY',
      createClient, authorizeNebiusCaller, runAgent, '', fetch,
    )
    if (!requestHandler) throw Error('Deno handler was not registered')

    const json = vi.fn(async () => ({ task: 'local-only' }))
    const req = {
      method: 'POST',
      headers: new Headers(options.authorization ? { authorization: options.authorization } : {}),
      json,
    } as unknown as Request
    const response: Response = await (requestHandler as (req: Request) => Promise<Response>)(req)
    return { response, getUser, createClient, runAgent, fetch, json }
  }

  const jwt = 'Bearer header.payload.signature'

  it('denies unauthenticated entry before parsing input or performing work', async () => {
    const result = await probe()
    expect(result.response.status).toBe(401)
    expect(result.createClient).not.toHaveBeenCalled()
    expect(result.runAgent).not.toHaveBeenCalled()
    expect(result.json).not.toHaveBeenCalled()
    expect(result.fetch).not.toHaveBeenCalled()
  })

  it('denies invalid JWT and empty allowlist before auth lookup', async () => {
    for (const opts of [
      { authorization: 'Bearer anon-public-key' },
      { authorization: jwt, allowed: '' },
    ]) {
      const result = await probe(opts)
      expect(result.response.status).toBe(401)
      expect(result.getUser).not.toHaveBeenCalled()
      expect(result.runAgent).not.toHaveBeenCalled()
      expect(result.fetch).not.toHaveBeenCalled()
    }
  })

  it('denies wrong identity, identity service failure and missing runtime keys', async () => {
    for (const opts of [
      { authorization: jwt, userId: 'not-the-operator' },
      { authorization: jwt, authFailure: true },
      { authorization: jwt, serviceConfigured: false },
    ]) {
      const result = await probe(opts)
      expect(result.response.status).toBe(401)
      expect(result.runAgent).not.toHaveBeenCalled()
      expect(result.json).not.toHaveBeenCalled()
      expect(result.fetch).not.toHaveBeenCalled()
    }
  })

  it('permits only the explicit server-verified operator in local mock execution', async () => {
    const result = await probe({ authorization: jwt })
    expect(result.response.status).toBe(200)
    expect(result.getUser).toHaveBeenCalledExactlyOnceWith('header.payload.signature')
    expect(result.runAgent).toHaveBeenCalledExactlyOnceWith('local-only', undefined)
    expect(result.json).toHaveBeenCalledOnce()
    expect(result.fetch).not.toHaveBeenCalled()
  })
})
