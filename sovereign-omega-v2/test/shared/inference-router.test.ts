/**
 * Inference router — opt-in OpenAI backend gating
 * The OpenAI backend is explicitly opt-in via VITE_ENABLE_OPENAI === 'true'.
 * When the flag is unset the backend must be skipped silently (no request to
 * the chat edge function). The OpenAI key itself never appears client-side:
 * the backend only ever calls the Supabase chat function.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { routeInference, configuredBackends } from '../../../packages/shared/lib/inference-router.js'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('opt-in OpenAI backend gating', () => {
  it('never calls the chat edge function when VITE_ENABLE_OPENAI is unset', async () => {
    fetchMock.mockRejectedValue(new Error('network down'))

    await expect(routeInference({ systemPrompt: 'S', userMessage: 'U' }))
      .rejects.toThrow(/All inference backends failed/)

    const urls = fetchMock.mock.calls.map(c => String(c[0]))
    expect(urls.some(u => u.includes('/functions/v1/chat'))).toBe(false)
  })

  it('routes through the chat edge function with provider "openai" when the flag is "true"', async () => {
    vi.stubEnv('VITE_ENABLE_OPENAI', 'true')
    fetchMock.mockImplementation((url: unknown) => {
      if (String(url).includes('/functions/v1/chat')) {
        // Edge function reports the model it actually used (server-side OPENAI_MODEL).
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ reply: '{"ok":true}', model: 'gpt-4o-mini' }) })
      }
      return Promise.reject(new Error('network down'))
    })

    const r = await routeInference({ systemPrompt: 'S', userMessage: 'U' })
    expect(r.backend).toBe('openai-compat')
    expect(r.content).toBe('{"ok":true}')
    expect(r.model).toBe('gpt-4o-mini')

    const call = fetchMock.mock.calls.find(c => String(c[0]).includes('/functions/v1/chat'))
    expect(call).toBeDefined()
    const body = JSON.parse((call![1] as RequestInit).body as string) as { provider: string }
    expect(body.provider).toBe('openai')
  })

  it('configuredBackends lists openai-compat only when the flag is exactly "true"', () => {
    expect(configuredBackends()).not.toContain('openai-compat')
    vi.stubEnv('VITE_ENABLE_OPENAI', 'true')
    expect(configuredBackends()).toContain('openai-compat')
  })

  // CLM-007 (provenance half): the router records the model the edge function
  // reports (data.model), NOT the caller's requested model. The server-side
  // provider gate itself lives in the Deno chat function (inspection-only here).
  it('records the server-reported model, not the caller req.model', async () => {
    vi.stubEnv('VITE_ENABLE_OPENAI', 'true')
    fetchMock.mockImplementation((url: unknown) => {
      if (String(url).includes('/functions/v1/chat')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ reply: '{"ok":true}', model: 'server-chosen-model' }) })
      }
      return Promise.reject(new Error('network down'))
    })

    const r = await routeInference({ systemPrompt: 'S', userMessage: 'U', model: 'client-requested-model' })
    expect(r.model).toBe('server-chosen-model')
    expect(r.model).not.toBe('client-requested-model')
  })
})

describe('opt-in Azure OpenAI backend gating', () => {
  it('never calls the chat edge function when VITE_ENABLE_AZURE is unset', async () => {
    fetchMock.mockRejectedValue(new Error('network down'))

    await expect(routeInference({ systemPrompt: 'S', userMessage: 'U' }))
      .rejects.toThrow(/All inference backends failed/)

    const urls = fetchMock.mock.calls.map(c => String(c[0]))
    expect(urls.some(u => u.includes('/functions/v1/chat'))).toBe(false)
  })

  it('routes through the chat edge function with provider "azure" when the flag is "true"', async () => {
    vi.stubEnv('VITE_ENABLE_AZURE', 'true')
    fetchMock.mockImplementation((url: unknown) => {
      if (String(url).includes('/functions/v1/chat')) {
        // Edge function reports the deployment it actually used (AZURE_OPENAI_DEPLOYMENT).
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ reply: '{"ok":true}', model: 'aegis-gpt4o' }) })
      }
      return Promise.reject(new Error('network down'))
    })

    const r = await routeInference({ systemPrompt: 'S', userMessage: 'U' })
    expect(r.backend).toBe('azure-openai')
    expect(r.content).toBe('{"ok":true}')
    expect(r.model).toBe('aegis-gpt4o')

    const call = fetchMock.mock.calls.find(c => String(c[0]).includes('/functions/v1/chat'))
    expect(call).toBeDefined()
    const body = JSON.parse((call![1] as RequestInit).body as string) as { provider: string }
    expect(body.provider).toBe('azure')
  })

  it('configuredBackends lists azure-openai only when the flag is exactly "true"', () => {
    expect(configuredBackends()).not.toContain('azure-openai')
    vi.stubEnv('VITE_ENABLE_AZURE', 'true')
    expect(configuredBackends()).toContain('azure-openai')
  })

  // CLM-007 (provenance half): the router records the deployment the edge
  // function reports (data.model), NOT the caller's requested model.
  it('records the server-reported deployment, not the caller req.model', async () => {
    vi.stubEnv('VITE_ENABLE_AZURE', 'true')
    fetchMock.mockImplementation((url: unknown) => {
      if (String(url).includes('/functions/v1/chat')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ reply: '{"ok":true}', model: 'server-deployment' }) })
      }
      return Promise.reject(new Error('network down'))
    })

    const r = await routeInference({ systemPrompt: 'S', userMessage: 'U', model: 'client-requested-model' })
    expect(r.model).toBe('server-deployment')
    expect(r.model).not.toBe('client-requested-model')
  })
})
