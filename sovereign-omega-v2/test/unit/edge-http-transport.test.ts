/**
 * Shared Supabase Edge HTTP transport tests.
 * EPISTEMIC TIER: T1 executable unit coverage.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  fetchWithTimeout,
  readTextBounded,
} from '../../../supabase/functions/_shared/http.ts'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchWithTimeout', () => {
  it('attaches a timeout signal when the caller does not supply one', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response('ok'))
    vi.stubGlobal('fetch', fetchSpy)

    await fetchWithTimeout('https://example.invalid/test', {}, 1_234)

    const init = fetchSpy.mock.calls[0]![1] as RequestInit
    expect(init.signal).toBeDefined()
  })

  it('preserves an explicit caller signal', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response('ok'))
    vi.stubGlobal('fetch', fetchSpy)
    const ctrl = new AbortController()

    await fetchWithTimeout('https://example.invalid/test', { signal: ctrl.signal }, 1_234)

    const init = fetchSpy.mock.calls[0]![1] as RequestInit
    expect(init.signal).toBe(ctrl.signal)
  })

  it('falls back to the default timeout for an invalid bound', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response('ok'))
    vi.stubGlobal('fetch', fetchSpy)

    await fetchWithTimeout('https://example.invalid/test', {}, 0)

    const init = fetchSpy.mock.calls[0]![1] as RequestInit
    expect(init.signal).toBeDefined()
  })
})

describe('readTextBounded', () => {
  it('returns a complete small body', async () => {
    await expect(readTextBounded(new Response('small'), 64)).resolves.toBe('small')
  })

  it('never returns more bytes than the configured bound for ASCII error bodies', async () => {
    const value = await readTextBounded(new Response('x'.repeat(10_000)), 2_048)
    expect(value).toHaveLength(2_048)
  })
})
