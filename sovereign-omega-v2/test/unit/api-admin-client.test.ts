// ============================================================
// SOVEREIGN OMEGA — AdminClient tests
// EPISTEMIC TIER: T2
//
// Tests for src/api/admin-client.ts:
//   Constructor (explicit key, env fallback, missing key)
//   _fetch error handling
//   getOrg, listApiKeys, listWorkspaces, createWorkspace, summary
// ============================================================

import { describe, it, expect, vi, afterEach } from 'vitest'
import { AdminClient, ADMIN_CLIENT_SCHEMA_VERSION } from '../../src/api/admin-client.js'

afterEach(() => {
  vi.unstubAllGlobals()
})

function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(String(status) + ' error body'),
  })
}

// ── Constants ─────────────────────────────────────────────

describe('ADMIN_CLIENT_SCHEMA_VERSION', () => {
  it('is a non-empty string', () => {
    expect(typeof ADMIN_CLIENT_SCHEMA_VERSION).toBe('string')
    expect(ADMIN_CLIENT_SCHEMA_VERSION.length).toBeGreaterThan(0)
  })
})

// ── Constructor ───────────────────────────────────────────

describe('AdminClient constructor', () => {
  it('accepts an explicit admin key without error', () => {
    expect(() => new AdminClient('explicit-admin-key')).not.toThrow()
  })

  it('falls back to ANTHROPIC_ADMIN_API_KEY env var when no key supplied', () => {
    const saved = process.env.ANTHROPIC_ADMIN_API_KEY
    process.env.ANTHROPIC_ADMIN_API_KEY = 'env-admin-key'
    expect(() => new AdminClient()).not.toThrow()
    if (saved !== undefined) {
      process.env.ANTHROPIC_ADMIN_API_KEY = saved
    } else {
      delete process.env.ANTHROPIC_ADMIN_API_KEY
    }
  })

  it('throws when neither explicit key nor env var is available', () => {
    const saved = process.env.ANTHROPIC_ADMIN_API_KEY
    delete process.env.ANTHROPIC_ADMIN_API_KEY
    expect(() => new AdminClient()).toThrow('[ADMIN_CLIENT] ANTHROPIC_ADMIN_API_KEY not set')
    if (saved !== undefined) process.env.ANTHROPIC_ADMIN_API_KEY = saved
  })
})

// ── _fetch error path ─────────────────────────────────────

describe('AdminClient._fetch error handling', () => {
  it('throws an error describing the HTTP status when response is not ok', async () => {
    vi.stubGlobal('fetch', mockFetch('Bad Request', false, 400))
    const client = new AdminClient('test-key')
    await expect(client.getOrg()).rejects.toThrow('[ADMIN_API] 400')
  })
})

// ── Happy-path method tests ────────────────────────────────

describe('AdminClient.getOrg', () => {
  it('returns the org object from the API response', async () => {
    vi.stubGlobal('fetch', mockFetch({ id: 'org-123', name: 'Test Org', type: 'organization' }))
    const org = await new AdminClient('test-key').getOrg()
    expect(org.id).toBe('org-123')
    expect(org.type).toBe('organization')
  })
})

describe('AdminClient.listApiKeys', () => {
  it('returns the data array from the response', async () => {
    vi.stubGlobal('fetch', mockFetch({ data: [{ id: 'k1', name: 'Key', status: 'active', created_at: '' }] }))
    const keys = await new AdminClient('test-key').listApiKeys()
    expect(keys).toHaveLength(1)
    expect(keys[0]!.id).toBe('k1')
  })

  it('returns empty array when response has no data field (null-safe ?? [])', async () => {
    vi.stubGlobal('fetch', mockFetch({}))
    const keys = await new AdminClient('test-key').listApiKeys()
    expect(keys).toEqual([])
  })
})

describe('AdminClient.listWorkspaces', () => {
  it('returns workspace list', async () => {
    vi.stubGlobal('fetch', mockFetch({ data: [{ id: 'ws-1', name: 'WS', created_at: '' }] }))
    const ws = await new AdminClient('test-key').listWorkspaces()
    expect(ws).toHaveLength(1)
  })

  it('returns empty array when data field absent', async () => {
    vi.stubGlobal('fetch', mockFetch({}))
    const ws = await new AdminClient('test-key').listWorkspaces()
    expect(ws).toEqual([])
  })
})

describe('AdminClient.createWorkspace', () => {
  it('returns the new workspace object', async () => {
    vi.stubGlobal('fetch', mockFetch({ id: 'ws-new', name: 'New', created_at: '' }))
    const ws = await new AdminClient('test-key').createWorkspace('New')
    expect(ws.id).toBe('ws-new')
  })
})

describe('AdminClient.summary', () => {
  it('returns org, key count, and workspace count from parallel calls', async () => {
    // summary() calls getOrg, listApiKeys, listWorkspaces via Promise.all — dispatch by URL
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if ((url as string).includes('/organizations/me')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ id: 'org-1', name: 'Org', type: 'organization' }) })
      }
      if ((url as string).includes('api_keys')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: [{ id: 'k1', name: 'K1', status: 'active', created_at: '' }, { id: 'k2', name: 'K2', status: 'active', created_at: '' }] }) })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ data: [{ id: 'ws-1', name: 'W', created_at: '' }] }) })
    }))
    const s = await new AdminClient('test-key').summary()
    expect(s.org.type).toBe('organization')
    expect(s.activeKeyCount).toBe(2)
    expect(s.workspaceCount).toBe(1)
  })
})
