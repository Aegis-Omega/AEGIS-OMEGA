import { readFileSync } from 'node:fs'
import { describe, expect, it, vi } from 'vitest'
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
