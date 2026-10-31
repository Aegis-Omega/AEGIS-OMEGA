import { describe, expect, it, vi } from 'vitest'
import {
  authorizeNebiusCaller,
  isNebiusRequestBounded,
} from '../../../supabase/functions/_shared/nebius-auth.ts'

const jwt = 'header.payload.signature'

describe('Nebius funded backend caller authorization', () => {
  it('denies missing JWT before invoking identity provider', async () => {
    const verify = vi.fn(async () => 'approved-user')
    expect(await authorizeNebiusCaller(null, 'approved-user', verify)).toBe(false)
    expect(verify).not.toHaveBeenCalled()
  })

  it('rejects public anon keys and malformed authorization headers', async () => {
    const verify = vi.fn(async () => 'approved-user')
    for (const value of ['Bearer anon-key', 'Basic '+jwt, 'Bearer '+jwt+' extra', 'Bearer x']) {
      expect(await authorizeNebiusCaller(value, 'approved-user', verify)).toBe(false)
    }
    expect(verify).not.toHaveBeenCalled()
  })

  it('denies when the operator allowlist is empty', async () => {
    const verify = vi.fn(async () => 'approved-user')
    expect(await authorizeNebiusCaller('Bearer '+jwt, '', verify)).toBe(false)
    expect(verify).not.toHaveBeenCalled()
  })

  it('denies a verified user outside the explicit allowlist', async () => {
    expect(await authorizeNebiusCaller('Bearer '+jwt, 'approved-user', async () => 'other-user')).toBe(false)
  })

  it('denies invalid or failed remote Supabase Auth validation', async () => {
    expect(await authorizeNebiusCaller('Bearer '+jwt, 'approved-user', async () => null)).toBe(false)
    expect(await authorizeNebiusCaller('Bearer '+jwt, 'approved-user', async () => { throw Error('network failure') })).toBe(false)
  })

  it('accepts only a verified explicitly permitted user', async () => {
    const verify = vi.fn(async (_token: string) => 'approved-user')
    expect(await authorizeNebiusCaller('Bearer '+jwt, 'other-user, approved-user', verify)).toBe(true)
    expect(verify).toHaveBeenCalledWith(jwt)
  })

  it('enforces bounded prompts and history before paid inference', () => {
    expect(isNebiusRequestBounded('hello', 'system', [])).toBe(true)
    expect(isNebiusRequestBounded('x'.repeat(4097), 'system', [])).toBe(false)
    expect(isNebiusRequestBounded('hello', 'x'.repeat(4097), [])).toBe(false)
    expect(isNebiusRequestBounded('hello', 'system', [{content:'x'.repeat(4097)}])).toBe(false)
    expect(isNebiusRequestBounded('hello', 'system', Array.from({length:9}, () => ({content:'x'})))).toBe(false)
  })
})
