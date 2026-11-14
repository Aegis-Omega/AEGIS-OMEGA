import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import * as ts from 'typescript'

// Vitest rewrites import.meta.url in some runners. Use checked-out source.
const candidates = [
  resolve(process.cwd(), '../supabase/functions/notify/index.ts'),
  resolve(process.cwd(), 'supabase/functions/notify/index.ts'),
]
const path = candidates.find((candidate) => existsSync(candidate))
if (!path) throw Error('Checked-out notify function source is missing')
const source = readFileSync(path, 'utf8')
const start = source.indexOf('Deno.serve(async (req) => {')
if (start < 0) throw Error('Expected notify handler is missing')
const handler = source.slice(start)

describe('AEGIS notification authorization, source-bound', () => {
  it('checks configured secret before body parsing or notification side effects', () => {
    const guard = handler.indexOf('if (!NOTIFY_SECRET.trim() || secret !== NOTIFY_SECRET) {')
    const body = handler.indexOf('await req.json()')
    const sendEmail = handler.indexOf('await sendEmail(')
    const sendSlack = handler.indexOf('await sendSlack(')
    expect(guard).toBeGreaterThan(0)
    expect(guard).toBeLessThan(body)
    expect(guard).toBeLessThan(sendEmail)
    expect(guard).toBeLessThan(sendSlack)
    expect(handler).toMatch(/if \(!NOTIFY_SECRET\.trim\(\) \|\| secret !== NOTIFY_SECRET\) \{[\s\S]*?status: 401/)
  })

  async function invoke(configured: string, supplied?: string) {
    const compiled = ts.transpileModule(handler, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
    }).outputText

    let registered: ((req: Request) => Promise<Response>) | null = null
    const deno = { serve: (fn: (req: Request) => Promise<Response>) => { registered = fn } }
    const sendEmail = vi.fn(async (_subject: string, _body: string, _html?: string) => {})
    const sendSlack = vi.fn(async (_text: string) => {})

    // Only execute repository-owned handler; all effects use local mocks.
    const register = new Function(
      'Deno', 'Response', 'CORS', 'NOTIFY_SECRET', 'sendEmail', 'sendSlack', compiled,
    )
    register(deno, Response, {}, configured, sendEmail, sendSlack)
    if (!registered) throw Error('Notify HTTP handler was not registered')

    const json = vi.fn(async () => ({ channel: 'both', subject: 'unit test', text: 'local-only' }))
    const req = {
      method: 'POST',
      headers: new Headers(supplied === undefined ? {} : { 'x-notify-secret': supplied }),
      json,
    } as unknown as Request
    const response: Response = await (registered as (req: Request) => Promise<Response>)(req)
    return { response, json, sendEmail, sendSlack }
  }

  it('denies absent configuration regardless of caller header', async () => {
    for (const supplied of [undefined, '', 'made-up']) {
      const result = await invoke('', supplied)
      expect(result.response.status).toBe(401)
      expect(result.json).not.toHaveBeenCalled()
      expect(result.sendEmail).not.toHaveBeenCalled()
      expect(result.sendSlack).not.toHaveBeenCalled()
    }
  })

  it('denies whitespace-only configuration and invalid credentials', async () => {
    for (const [configured, supplied] of [
      ['   ', '   '],
      ['private-test-only', undefined],
      ['private-test-only', 'wrong'],
    ] as Array<[string, string | undefined]>) {
      const result = await invoke(configured, supplied)
      expect(result.response.status).toBe(401)
      expect(result.json).not.toHaveBeenCalled()
      expect(result.sendEmail).not.toHaveBeenCalled()
      expect(result.sendSlack).not.toHaveBeenCalled()
    }
  })

  it('preserves authorized notification behavior without sending anything', async () => {
    const result = await invoke('private-test-only', 'private-test-only')
    expect(result.response.status).toBe(200)
    expect(result.json).toHaveBeenCalledExactlyOnceWith()
    expect(result.sendEmail).toHaveBeenCalledExactlyOnceWith('unit test', 'local-only', undefined)
    expect(result.sendSlack).toHaveBeenCalledExactlyOnceWith('local-only')
    expect(await result.response.json()).toEqual({ ok: true, results: { email: 'sent', slack: 'sent' } })
  })
})
