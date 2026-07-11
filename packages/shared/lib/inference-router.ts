/**
 * AEGIS Multi-Backend Constitutional Inference Router
 * EPISTEMIC TIER: T2 (engineering hypothesis — routing strategy is empirically configurable)
 * Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
 *
 * The governance layer (audit chain, CCIL-Ψ, martingale) is invariant.
 * The inference backend is pluggable: DashScope, Ollama, Claude, CL-Ψ, any OpenAI-compat.
 *
 * Priority: first backend that responds. Graceful fallback through the chain.
 * Every call — regardless of backend — produces the same ConstitutionalAuditRecord.
 */

export type BackendType = 'dashscope' | 'ollama' | 'claude' | 'cl-psi' | 'openai-compat'

export interface InferenceRequest {
  systemPrompt: string
  userMessage: string
  model?: string
}

export interface InferenceResponse {
  content: string
  backend: BackendType
  model: string
  latency_ms: number
}

// ── Backend implementations ──────────────────────────────────────────────────

async function callDashScopeBackend(req: InferenceRequest): Promise<InferenceResponse> {
  const apiKey = import.meta.env.VITE_DASHSCOPE_API_KEY as string | undefined
  if (!apiKey) throw new Error('VITE_DASHSCOPE_API_KEY not configured')

  const model = req.model ?? (import.meta.env.VITE_DASHSCOPE_MODEL as string | undefined) ?? 'qwen3.7-plus'
  // International endpoint first, fallback to China endpoint
  const base = (import.meta.env.VITE_DASHSCOPE_BASE_URL as string | undefined)
    ?? 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'

  const t0 = Date.now()
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: req.systemPrompt },
        { role: 'user', content: req.userMessage },
      ],
    }),
    signal: AbortSignal.timeout(60_000),
  })
  if (!res.ok) throw new Error(`DashScope ${res.status}: ${await res.text()}`)
  const data = (await res.json()) as { choices: { message: { content: string } }[] }
  return {
    content: data.choices[0]?.message?.content ?? '{}',
    backend: 'dashscope',
    model,
    latency_ms: Date.now() - t0,
  }
}

async function callOllamaBackend(req: InferenceRequest): Promise<InferenceResponse> {
  const base = import.meta.env.VITE_OLLAMA_BASE_URL as string | undefined
  if (!base) throw new Error('VITE_OLLAMA_BASE_URL not configured')

  const model = req.model ?? (import.meta.env.VITE_OLLAMA_MODEL as string | undefined) ?? 'qwen2.5:7b'
  const t0 = Date.now()
  const res = await fetch(`${base}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ollama' },
    body: JSON.stringify({
      model,
      messages: [
        { role: 'system', content: req.systemPrompt },
        { role: 'user', content: req.userMessage },
      ],
      format: 'json',
    }),
    signal: AbortSignal.timeout(120_000),
  })
  if (!res.ok) throw new Error(`Ollama ${res.status}: ${await res.text()}`)
  const data = (await res.json()) as { choices: { message: { content: string } }[] }
  return {
    content: data.choices[0]?.message?.content ?? '{}',
    backend: 'ollama',
    model,
    latency_ms: Date.now() - t0,
  }
}

async function callClaudeBackend(req: InferenceRequest): Promise<InferenceResponse> {
  const apiKey = import.meta.env.VITE_CLAUDE_API_KEY as string | undefined
  if (!apiKey) throw new Error('VITE_CLAUDE_API_KEY not configured')

  const model = req.model ?? (import.meta.env.VITE_CLAUDE_MODEL as string | undefined) ?? 'claude-haiku-4-5-20251001'
  const t0 = Date.now()
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-beta': 'prompt-caching-2024-07-31',
    },
    body: JSON.stringify({
      model,
      max_tokens: 2048,
      system: [{ type: 'text', text: req.systemPrompt + '\n\nRespond with valid JSON only.', cache_control: { type: 'ephemeral' } }],
      messages: [{ role: 'user', content: req.userMessage }],
    }),
    signal: AbortSignal.timeout(60_000),
  })
  if (!res.ok) throw new Error(`Claude ${res.status}: ${await res.text()}`)
  const data = (await res.json()) as { content: { type: string; text: string }[] }
  const text = data.content.find(c => c.type === 'text')?.text ?? '{}'
  return { content: text, backend: 'claude', model, latency_ms: Date.now() - t0 }
}

async function callCLPsiBackend(req: InferenceRequest): Promise<InferenceResponse> {
  const bridgeUrl = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'
  const t0 = Date.now()
  const res = await fetch(`${bridgeUrl}/inference`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      system_prompt: req.systemPrompt,
      user_message: req.userMessage,
      activations: [0.5],  // default activation vector
    }),
    signal: AbortSignal.timeout(30_000),
  })
  if (!res.ok) throw new Error(`CL-Ψ bridge ${res.status}: ${await res.text()}`)
  const data = (await res.json()) as { status?: string; content?: string; reason?: string }
  if (data.status === 'unavailable') throw new Error(`CL-Ψ unavailable: ${data.reason}`)
  return {
    content: data.content ?? JSON.stringify(data),
    backend: 'cl-psi',
    model: 'aegis-cl-psi-v1',
    latency_ms: Date.now() - t0,
  }
}

async function callOpenAIBackend(req: InferenceRequest): Promise<InferenceResponse> {
  // Opt-in flag — NOT a secret. The OpenAI API key itself never reaches the browser:
  // it lives server-side as the Supabase function secret OPENAI_API_KEY, and this
  // backend only ever talks to the chat edge function.
  if ((import.meta.env.VITE_ENABLE_OPENAI as string | undefined) !== 'true') {
    throw new Error('VITE_ENABLE_OPENAI not enabled')
  }

  const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
    ?? 'https://rwehltdwpsncnwxzkwik.supabase.co'
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

  const t0 = Date.now()
  const res = await fetch(`${supabaseUrl}/functions/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(anonKey ? { Authorization: `Bearer ${anonKey}` } : {}),
    },
    body: JSON.stringify({
      provider: 'openai',
      message: req.userMessage,
      system: req.systemPrompt + '\n\nRespond with valid JSON only.',
    }),
    signal: AbortSignal.timeout(60_000),
  })
  if (!res.ok) throw new Error(`OpenAI proxy ${res.status}: ${await res.text()}`)
  const data = (await res.json()) as { reply?: string; error?: string }
  if (data.error || !data.reply) throw new Error(`OpenAI proxy: ${data.error ?? 'empty reply'}`)
  return {
    content: data.reply,
    backend: 'openai-compat',
    model: req.model ?? 'gpt-5.5-mini',  // server default; actual model is set server-side via OPENAI_MODEL
    latency_ms: Date.now() - t0,
  }
}

// ── Priority-ordered backend registry ────────────────────────────────────────

type BackendFn = (req: InferenceRequest) => Promise<InferenceResponse>

// Order: CL-Ψ (local, private) → OpenAI (opt-in, key server-side) → Ollama (local) → Claude → DashScope
// Each backend is tried in sequence; first success wins.
const BACKEND_CHAIN: Array<[BackendType, BackendFn]> = [
  ['cl-psi',        callCLPsiBackend],
  ['openai-compat', callOpenAIBackend],
  ['ollama',        callOllamaBackend],
  ['claude',        callClaudeBackend],
  ['dashscope',     callDashScopeBackend],
]

// ── Router ────────────────────────────────────────────────────────────────────

export interface RouterResult {
  content: string
  backend: BackendType
  model: string
  latency_ms: number
  fallback_count: number  // how many backends failed before success
}

/**
 * Route inference request through the constitutional backend chain.
 * Returns first successful response. Throws only if ALL backends fail.
 */
export async function routeInference(req: InferenceRequest): Promise<RouterResult> {
  const errors: string[] = []

  for (const [, fn] of BACKEND_CHAIN) {
    try {
      const result = await fn(req)
      return { ...result, fallback_count: errors.length }
    } catch (e) {
      errors.push(e instanceof Error ? e.message : String(e))
    }
  }

  throw new Error(`All inference backends failed:\n${errors.map((e, i) => `  [${i}] ${e}`).join('\n')}`)
}

/** Returns which backends are configured (not necessarily reachable) */
export function configuredBackends(): BackendType[] {
  const active: BackendType[] = []
  if (import.meta.env.VITE_BRIDGE_URL || true) active.push('cl-psi')       // always try bridge
  if (import.meta.env.VITE_ENABLE_OPENAI === 'true') active.push('openai-compat')
  if (import.meta.env.VITE_OLLAMA_BASE_URL) active.push('ollama')
  if (import.meta.env.VITE_CLAUDE_API_KEY) active.push('claude')
  if (import.meta.env.VITE_DASHSCOPE_API_KEY) active.push('dashscope')
  return active
}
