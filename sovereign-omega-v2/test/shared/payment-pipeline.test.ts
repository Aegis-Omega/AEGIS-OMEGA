/**
 * Payment/licensing pipeline — end-to-end business logic tests
 * Covers: SuccessPage token generation, webhook HMAC verification,
 * plan ranking, restore-access lookup, AccessGate integration.
 *
 * Edge functions (Deno) are not runnable in vitest — their business logic
 * is ported here as pure functions and tested identically.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createGrantToken, verifyGrantToken, getStoredAccess, storeAccess } from '../../../packages/shared/lib/access.js'
import type { Plan, GrantPayload } from '../../../packages/shared/lib/access.js'

// ─── Plan constants mirroring SuccessPage and ls-webhook ─────────────────────────────────

const PLAN_TOOLS: Record<Plan, string[]> = {
  single:  ['platform-picker'],
  starter: ['platform-picker', 'hook-generator'],
  full:    ['platform-picker', 'hook-generator', 'content-calendar'],
}

const PLAN_RANK: Record<string, number> = { single: 1, starter: 2, full: 3 }

const TOOL_URLS: Record<string, string> = {
  'platform-picker':  'https://platform.aegisomega.com',
  'hook-generator':   'https://hooks.aegisomega.com',
  'content-calendar': 'https://calendar.aegisomega.com',
}

// ─── SuccessPage logic (ported from hub/src/components/SuccessPage.tsx) ─────────

function buildToolLinks(plan: Plan, token: string): Record<string, string> {
  const tools = PLAN_TOOLS[plan]
  return Object.fromEntries(
    tools.map(tool => [tool, `${TOOL_URLS[tool]}?aegis_token=${encodeURIComponent(token)}`]),
  )
}

function parseSuccessPagePlan(search: string): Plan | null {
  const params = new URLSearchParams(search)
  const p = params.get('plan')
  if (p && ['single', 'starter', 'full'].includes(p)) return p as Plan
  return null
}

// ─── Restore-access business logic (ported from supabase/functions/) ────────────

function pickBestPlan(rows: Array<{ plan: string }>): string {
  return rows.reduce((best, row) => {
    return (PLAN_RANK[row.plan] ?? 0) > (PLAN_RANK[best] ?? 0) ? row.plan : best
  }, 'single')
}

function buildRestoreUrl(hubUrl: string, plan: string): string {
  return `${hubUrl}/success?plan=${plan}`
}

function normaliseEmail(email: string): string {
  return email.toLowerCase().trim()
}

// ─── Webhook HMAC verification (ported from supabase/functions/ls-webhook/) ───

async function computeHmacSha256Hex(secret: string, body: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const raw = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(body))
  return Array.from(new Uint8Array(raw)).map(b => b.toString(16).padStart(2, '0')).join('')
}

async function verifyWebhookSignature(secret: string, body: string, sig: string): Promise<boolean> {
  const computed = await computeHmacSha256Hex(secret, body)
  return computed === sig
}

// ─── LS plan map logic ────────────────────────────────────────────────────────────

function mapVariantToPlan(variantId: string, planMap: Record<string, string>): string {
  return planMap[variantId] ?? 'single'
}

// =============================================================================

beforeEach(() => {
  localStorage.clear()
})

describe('SuccessPage — URL plan parsing', () => {
  it('parses valid plan param from search string', () => {
    expect(parseSuccessPagePlan('?plan=single')).toBe('single')
    expect(parseSuccessPagePlan('?plan=starter')).toBe('starter')
    expect(parseSuccessPagePlan('?plan=full')).toBe('full')
  })

  it('returns null for missing plan param', () => {
    expect(parseSuccessPagePlan('')).toBeNull()
    expect(parseSuccessPagePlan('?foo=bar')).toBeNull()
  })

  it('returns null for invalid plan value', () => {
    expect(parseSuccessPagePlan('?plan=enterprise')).toBeNull()
    expect(parseSuccessPagePlan('?plan=')).toBeNull()
  })
})

describe('SuccessPage — tool link generation', () => {
  it('single plan generates only platform-picker link', () => {
    const token = createGrantToken('single')
    const links = buildToolLinks('single', token)
    expect(Object.keys(links)).toEqual(['platform-picker'])
    expect(links['platform-picker']).toContain('aegis_token=')
    expect(links['platform-picker']).toContain('platform.aegisomega.com')
  })

  it('starter plan generates platform-picker and hook-generator links', () => {
    const token = createGrantToken('starter')
    const links = buildToolLinks('starter', token)
    expect(Object.keys(links)).toEqual(['platform-picker', 'hook-generator'])
  })

  it('full plan generates all three tool links', () => {
    const token = createGrantToken('full')
    const links = buildToolLinks('full', token)
    expect(Object.keys(links)).toEqual(['platform-picker', 'hook-generator', 'content-calendar'])
    expect(links['content-calendar']).toContain('calendar.aegisomega.com')
  })

  it('token is URL-encoded in each link', () => {
    const token = createGrantToken('full')
    const links = buildToolLinks('full', token)
    for (const url of Object.values(links)) {
      // base64 token in URL should be encoded (= → %3D etc)
      expect(url).toContain('aegis_token=')
      expect(url).not.toContain(' ')
    }
  })

  it('token in link is a valid grant token when decoded', () => {
    const token = createGrantToken('full')
    const links = buildToolLinks('full', token)
    const url = new URL(links['platform-picker']!)
    const extracted = decodeURIComponent(url.searchParams.get('aegis_token') ?? '')
    const payload = verifyGrantToken(extracted)
    expect(payload).not.toBeNull()
    expect(payload!.plan).toBe('full')
  })
})

describe('restore-access — plan ranking', () => {
  it('picks single when only one row', () => {
    expect(pickBestPlan([{ plan: 'single' }])).toBe('single')
  })

  it('picks highest-ranked plan from multiple rows', () => {
    expect(pickBestPlan([{ plan: 'single' }, { plan: 'full' }])).toBe('full')
    expect(pickBestPlan([{ plan: 'starter' }, { plan: 'single' }])).toBe('starter')
    expect(pickBestPlan([{ plan: 'full' }, { plan: 'starter' }, { plan: 'single' }])).toBe('full')
  })

  it('defaults to single for empty rows', () => {
    expect(pickBestPlan([])).toBe('single')
  })

  it('handles unknown plan gracefully (falls back to single)', () => {
    // Unknown plan has rank 0, so single (rank 1) wins
    expect(pickBestPlan([{ plan: 'enterprise' }])).toBe('single')
  })

  it('builds correct restore URL', () => {
    const url = buildRestoreUrl('https://aegisomega.com', 'full')
    expect(url).toBe('https://aegisomega.com/success?plan=full')
    expect(parseSuccessPagePlan(new URL(url).search)).toBe('full')
  })
})

describe('restore-access — email normalisation', () => {
  it('lowercases email', () => {
    expect(normaliseEmail('User@Example.COM')).toBe('user@example.com')
  })

  it('trims whitespace', () => {
    expect(normaliseEmail('  user@example.com  ')).toBe('user@example.com')
  })

  it('lowercases and trims together', () => {
    expect(normaliseEmail('  TARIK@GMAIL.COM  ')).toBe('tarik@gmail.com')
  })
})

describe('ls-webhook — HMAC-SHA256 signature verification', () => {
  const SECRET = 'test-webhook-secret-32-chars-long'
  const BODY = JSON.stringify({ meta: { event_name: 'order_created' }, data: { id: '42' } })

  it('valid signature is accepted', async () => {
    const sig = await computeHmacSha256Hex(SECRET, BODY)
    expect(await verifyWebhookSignature(SECRET, BODY, sig)).toBe(true)
  })

  it('wrong secret produces invalid signature', async () => {
    const sig = await computeHmacSha256Hex(SECRET, BODY)
    expect(await verifyWebhookSignature('wrong-secret', BODY, sig)).toBe(false)
  })

  it('tampered body produces invalid signature', async () => {
    const sig = await computeHmacSha256Hex(SECRET, BODY)
    const tampered = BODY + ' '
    expect(await verifyWebhookSignature(SECRET, tampered, sig)).toBe(false)
  })

  it('empty signature is rejected', async () => {
    expect(await verifyWebhookSignature(SECRET, BODY, '')).toBe(false)
  })

  it('HMAC output is 64-char hex string', async () => {
    const sig = await computeHmacSha256Hex(SECRET, BODY)
    expect(sig).toMatch(/^[0-9a-f]{64}$/)
  })

  it('same body + secret always produces same HMAC (determinism)', async () => {
    const sig1 = await computeHmacSha256Hex(SECRET, BODY)
    const sig2 = await computeHmacSha256Hex(SECRET, BODY)
    expect(sig1).toBe(sig2)
  })
})

describe('ls-webhook — variant-to-plan mapping', () => {
  const PLAN_MAP: Record<string, string> = {
    '111': 'single',
    '222': 'starter',
    '333': 'full',
  }

  it('maps known variant IDs to plans', () => {
    expect(mapVariantToPlan('111', PLAN_MAP)).toBe('single')
    expect(mapVariantToPlan('222', PLAN_MAP)).toBe('starter')
    expect(mapVariantToPlan('333', PLAN_MAP)).toBe('full')
  })

  it('defaults to single for unknown variant', () => {
    expect(mapVariantToPlan('999', PLAN_MAP)).toBe('single')
    expect(mapVariantToPlan('', PLAN_MAP)).toBe('single')
  })
})

describe('AccessGate — stored access integration', () => {
  it('full-plan token grants access to all three tools', () => {
    const token = createGrantToken('full')
    const payload = verifyGrantToken(token)!
    storeAccess('platform-picker', payload)
    storeAccess('hook-generator', payload)
    storeAccess('content-calendar', payload)

    expect(getStoredAccess('platform-picker')).not.toBeNull()
    expect(getStoredAccess('hook-generator')).not.toBeNull()
    expect(getStoredAccess('content-calendar')).not.toBeNull()
  })

  it('single-plan token stored for platform-picker does not grant hook-generator', () => {
    const token = createGrantToken('single')
    const payload = verifyGrantToken(token)!
    storeAccess('platform-picker', payload)

    // platform-picker is accessible
    const pp = getStoredAccess('platform-picker')
    expect(pp).not.toBeNull()
    expect(pp!.tools).toContain('platform-picker')

    // hook-generator was never stored → null
    expect(getStoredAccess('hook-generator')).toBeNull()
  })

  it('post-payment flow: parse plan → create token → verify → store → retrieve', () => {
    // Simulate what SuccessPage does after Lemon Squeezy redirect
    const plan = parseSuccessPagePlan('?plan=starter')!
    expect(plan).toBe('starter')

    const token = createGrantToken(plan)
    const links = buildToolLinks(plan, token)

    // Simulate what AccessGate does on tool open
    for (const [product, url] of Object.entries(links)) {
      const urlObj = new URL(url)
      const raw = decodeURIComponent(urlObj.searchParams.get('aegis_token') ?? '')
      const payload = verifyGrantToken(raw)
      expect(payload).not.toBeNull()
      storeAccess(product, payload!)
    }

    // Verify stored access for starter tools
    expect(getStoredAccess('platform-picker')).not.toBeNull()
    expect(getStoredAccess('hook-generator')).not.toBeNull()
    expect(getStoredAccess('content-calendar')).toBeNull() // not in starter
  })
})
