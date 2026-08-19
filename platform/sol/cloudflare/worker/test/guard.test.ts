import { describe, expect, it } from 'vitest'

import {
  AccessDeniedError,
  enforceBodyLimit,
  parsePositiveInteger,
  requireAccessIdentity,
} from '../src/guard.js'

describe('SOL edge guards', () => {
  it('requires Cloudflare Access identity', () => {
    expect(() => requireAccessIdentity(new Request('https://example.com/mcp')))
      .toThrow(AccessDeniedError)
  })

  it('accepts complete Cloudflare Access identity', () => {
    const request = new Request('https://example.com/mcp', {
      headers: {
        'cf-access-authenticated-user-email': 'operator@aegisomega.com',
        'cf-access-jwt-assertion': 'signed-jwt',
      },
    })
    expect(requireAccessIdentity(request)).toEqual({
      email: 'operator@aegisomega.com',
      jwt: 'signed-jwt',
    })
  })

  it('rejects oversized request bodies from content-length', () => {
    const request = new Request('https://example.com/mcp', {
      method: 'POST',
      headers: { 'content-length': '2048' },
    })
    expect(() => enforceBodyLimit(request, 1024)).toThrow(AccessDeniedError)
  })

  it('uses a safe fallback for malformed limits', () => {
    expect(parsePositiveInteger('not-a-number', 1024)).toBe(1024)
    expect(parsePositiveInteger('0', 1024)).toBe(1024)
    expect(parsePositiveInteger('4096', 1024)).toBe(4096)
  })
})
