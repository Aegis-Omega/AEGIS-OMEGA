export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface StreamOptions {
  messages: ChatMessage[]
  signal?: AbortSignal
}

async function* readLines(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<string> {
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      if (signal?.aborted) break
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) yield line
    }
    if (buffer) yield buffer
  } finally {
    reader.releaseLock()
  }
}

export async function* streamOllama(opts: StreamOptions): AsyncGenerator<string> {
  const base = import.meta.env.VITE_OLLAMA_BASE_URL ?? 'http://localhost:11434'
  const model = import.meta.env.VITE_OLLAMA_MODEL ?? 'hermes3:8b'

  const res = await fetch(`${base}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages: opts.messages, stream: true }),
    signal: opts.signal,
  })

  if (!res.ok || !res.body) throw new Error(`Ollama ${res.status}: ${await res.text()}`)

  for await (const line of readLines(res.body.getReader(), opts.signal)) {
    if (!line.trim()) continue
    try {
      const chunk = JSON.parse(line) as { message?: { content?: string }; done?: boolean }
      if (chunk.message?.content) yield chunk.message.content
      if (chunk.done) break
    } catch { /* skip malformed lines */ }
  }
}

export async function* streamDashScope(opts: StreamOptions): AsyncGenerator<string> {
  const apiKey = import.meta.env.VITE_DASHSCOPE_API_KEY ?? ''
  if (!apiKey) throw new Error('VITE_DASHSCOPE_API_KEY is not set')

  const model = import.meta.env.VITE_DASHSCOPE_MODEL ?? 'qwen-plus'
  const base = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ model, messages: opts.messages, stream: true }),
    signal: opts.signal,
  })

  if (!res.ok || !res.body) throw new Error(`DashScope ${res.status}: ${await res.text()}`)

  for await (const line of readLines(res.body.getReader(), opts.signal)) {
    if (!line.startsWith('data: ')) continue
    const data = line.slice(6).trim()
    if (data === '[DONE]') break
    try {
      const chunk = JSON.parse(data) as { choices?: { delta?: { content?: string } }[] }
      const content = chunk.choices?.[0]?.delta?.content
      if (content) yield content
    } catch { /* skip malformed SSE */ }
  }
}

export async function* streamClaude(opts: StreamOptions): AsyncGenerator<string> {
  // Routes through the AEGIS bridge (/claude/stream) which applies the constitutional
  // system prompt and keeps the API key server-side. Bridge must be running on port 7890.
  const bridgeUrl = import.meta.env.VITE_BRIDGE_URL ?? 'http://localhost:7890'
  const model = import.meta.env.VITE_CLAUDE_MODEL ?? 'claude-sonnet-4-6'
  const maxTokens = Number(import.meta.env.VITE_CLAUDE_MAX_TOKENS ?? '2048')

  const res = await fetch(`${bridgeUrl}/claude/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: opts.messages.filter(m => m.role !== 'system'),
      model,
      max_tokens: maxTokens,
    }),
    signal: opts.signal,
  })

  if (!res.ok || !res.body) throw new Error(`Claude bridge ${res.status}: ${await res.text()}`)

  for await (const line of readLines(res.body.getReader(), opts.signal)) {
    if (!line.startsWith('data: ')) continue
    const data = line.slice(6).trim()
    try {
      const chunk = JSON.parse(data) as { delta?: string; done?: boolean; error?: string }
      if (chunk.error) throw new Error(`Claude: ${chunk.error}`)
      if (chunk.delta) yield chunk.delta
      if (chunk.done) break
    } catch (e) {
      if (e instanceof SyntaxError) continue
      throw e
    }
  }
}

export type Provider = 'ollama' | 'dashscope' | 'claude'

export async function* streamChat(
  opts: StreamOptions & { provider?: Provider },
): AsyncGenerator<string> {
  const provider = opts.provider ?? (import.meta.env.VITE_PROVIDER as Provider | undefined) ?? 'claude'
  if (provider === 'claude') return yield* streamClaude(opts)
  if (provider === 'ollama') return yield* streamOllama(opts)
  yield* streamDashScope(opts)
}
