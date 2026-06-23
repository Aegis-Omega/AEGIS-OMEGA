/**
 * Stratum II — cockpit agent provider type contracts
 * Tests: Provider discriminant exhaustiveness, ChatMessage role types,
 * streaming provider selection logic via mocked fetch
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import type { ChatMessage, Provider } from '../../../cockpit/src/lib/agent.js'

// Validate the exported types without calling live network functions
describe('ChatMessage — role type contract', () => {
  it('accepts user role', () => {
    const m: ChatMessage = { role: 'user', content: 'hello' }
    expect(m.role).toBe('user')
  })

  it('accepts assistant role', () => {
    const m: ChatMessage = { role: 'assistant', content: 'response' }
    expect(m.role).toBe('assistant')
  })

  it('accepts system role', () => {
    const m: ChatMessage = { role: 'system', content: 'system prompt' }
    expect(m.role).toBe('system')
  })

  it('content is a string', () => {
    const m: ChatMessage = { role: 'user', content: 'test' }
    expect(typeof m.content).toBe('string')
  })
})

describe('Provider type — discriminant exhaustiveness', () => {
  const PROVIDERS: Provider[] = ['ollama', 'dashscope', 'claude']

  it('has exactly three providers', () => {
    expect(PROVIDERS).toHaveLength(3)
  })

  it('includes ollama', () => {
    expect(PROVIDERS).toContain('ollama')
  })

  it('includes dashscope (Qwen backend)', () => {
    expect(PROVIDERS).toContain('dashscope')
  })

  it('includes claude (bridge-routed backend)', () => {
    expect(PROVIDERS).toContain('claude')
  })
})

describe('streamOllama — SSE parsing (unit)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('yields content chunks from Ollama streaming response', async () => {
    const lines = [
      JSON.stringify({ message: { content: 'Hello' }, done: false }),
      JSON.stringify({ message: { content: ' world' }, done: false }),
      JSON.stringify({ message: { content: '' }, done: true }),
    ].join('\n')

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(ctrl) {
        ctrl.enqueue(encoder.encode(lines))
        ctrl.close()
      },
    })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: stream,
    }))

    const { streamOllama } = await import('../../../cockpit/src/lib/agent.js')
    const chunks: string[] = []
    for await (const chunk of streamOllama({ messages: [{ role: 'user', content: 'hi' }] })) {
      chunks.push(chunk)
    }
    expect(chunks).toEqual(['Hello', ' world'])
  })

  it('throws when Ollama returns non-ok status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => 'Service Unavailable',
    }))

    const { streamOllama } = await import('../../../cockpit/src/lib/agent.js')
    const gen = streamOllama({ messages: [] })
    await expect(gen.next()).rejects.toThrow('Ollama 503')
  })
})

describe('streamDashScope — SSE parsing (unit)', () => {
  afterEach(() => vi.restoreAllMocks())

  it('yields content from SSE data lines', async () => {
    const lines = [
      'data: ' + JSON.stringify({ choices: [{ delta: { content: 'chunk1' } }] }),
      'data: ' + JSON.stringify({ choices: [{ delta: { content: 'chunk2' } }] }),
      'data: [DONE]',
    ].join('\n')

    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: new ReadableStream({
        start(ctrl) { ctrl.enqueue(encoder.encode(lines)); ctrl.close() },
      }),
    }))

    // Patch import.meta.env so VITE_DASHSCOPE_API_KEY is set
    vi.stubEnv('VITE_DASHSCOPE_API_KEY', 'test-key')

    const { streamDashScope } = await import('../../../cockpit/src/lib/agent.js')
    const chunks: string[] = []
    for await (const c of streamDashScope({ messages: [{ role: 'user', content: 'hi' }] })) {
      chunks.push(c)
    }
    expect(chunks).toEqual(['chunk1', 'chunk2'])
  })

  it('skips malformed SSE lines without throwing', async () => {
    const lines = [
      'data: not-json',
      'data: ' + JSON.stringify({ choices: [{ delta: { content: 'ok' } }] }),
      'data: [DONE]',
    ].join('\n')

    const encoder = new TextEncoder()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: new ReadableStream({
        start(ctrl) { ctrl.enqueue(encoder.encode(lines)); ctrl.close() },
      }),
    }))
    vi.stubEnv('VITE_DASHSCOPE_API_KEY', 'test-key')

    const { streamDashScope } = await import('../../../cockpit/src/lib/agent.js')
    const chunks: string[] = []
    for await (const c of streamDashScope({ messages: [] })) {
      chunks.push(c)
    }
    expect(chunks).toEqual(['ok'])
  })

  it('throws when API key is missing', async () => {
    vi.stubEnv('VITE_DASHSCOPE_API_KEY', '')

    const { streamDashScope } = await import('../../../cockpit/src/lib/agent.js')
    const gen = streamDashScope({ messages: [] })
    await expect(gen.next()).rejects.toThrow('VITE_DASHSCOPE_API_KEY is not set')
  })
})
