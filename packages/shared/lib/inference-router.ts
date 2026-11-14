/**
 * AEGIS Multi-Backend Constitutional Inference Router
 * EPISTEMIC TIER: T2 (engineering hypothesis — routing strategy is empirically configurable)
 * Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
 *
 * The governance layer (audit chain, CCIL-Ψ, martingale) is invariant.
 * The inference backend is pluggable: DashScope, Ollama, Claude, CL-Ψ, any OpenAI-compat.
 *
 * Default fallback is limited to local backends. Hosted providers require explicit
 * selection and a user session; provider credentials remain on the server.
 * This router returns provenance; it does not itself certify a governance audit.
 */

export type BackendType = 'dashscope' | 'ollama' | 'claude' | 'cl-psi' | 'openai-compat' | 'nebius-token-factory' | 'azure-openai'

export interface InferenceRequest {
  systemPrompt: string
  userMessage: string
  model?: string
  /** Explicit backend selection disables cross-provider failover. */
  backend?: BackendType
  /** Supabase Auth user-session JWT. Required for every hosted chat provider. */
  userAccessToken?: string
}

export interface InferenceResponse {
  content: string
  backend: BackendType
  model: string
  latency_ms: number
}

// ── Backend implementations ──────────────────────────────────────────────────

/** All hosted chat providers share one authenticated, server-side-key path. */
async function callChatBackend(
  req: InferenceRequest,
  backend: BackendType,
  provider: 'dashscope' | 'openai' | 'nebius' | 'azure',
  enabled: boolean,
): Promise<InferenceResponse> {
  if (!enabled) throw new Error(`${provider} is not enabled`)
  const token = req.userAccessToken?.trim()
  const publicKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined
  if (!token || token === publicKey?.trim()) {
    throw new Error(`${provider} requires a Supabase Auth user session`)
  }
  const configuredUrl = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
    ?? 'https://rwehltdwpsncnwxzkwik.supabase.co'
  const origin = new URL(configuredUrl)
  if (origin.protocol !== 'https:' || origin.username || origin.password ||
      origin.search || origin.hash || origin.pathname !== '/') {
    throw new Error('Invalid chat proxy origin')
  }
  const t0 = Date.now()
  const res = await fetch(`${origin.origin}/functions/v1/chat`, {
    method: 'POST',
    redirect: 'error',
    headers: {
      'Content-Type': 'application/json',
      ...(publicKey ? { apikey: publicKey } : {}),
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      provider,
      message: req.userMessage,
      system: req.systemPrompt + '\n\nRespond with valid JSON only.',
    }),
    signal: AbortSignal.timeout(60_000),
  })
  // Do not echo upstream bodies, which can contain private request data.
  if (!res.ok) throw new Error(`${provider} proxy HTTP ${res.status}`)
  const data = await res.json() as { reply?: unknown; error?: unknown; model?: unknown }
  if (data.error) throw new Error(`${provider} proxy unavailable`)
  if (typeof data.reply !== 'string' || !data.reply.trim() ||
      typeof data.model !== 'string' || !data.model.trim()) {
    throw new Error(`${provider} proxy returned an incomplete response`)
  }
  return { content: data.reply, backend, model: data.model, latency_ms: Date.now() - t0 }
}

async function callDashScopeBackend(req: InferenceRequest): Promise<InferenceResponse> {
  return callChatBackend(req, 'dashscope', 'dashscope', import.meta.env.VITE_ENABLE_DASHSCOPE === 'true')
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

async function callClaudeBackend(_req: InferenceRequest): Promise<InferenceResponse> {
  throw new Error('Claude requires an authenticated server proxy; browser provider keys are unsupported')
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
  return callChatBackend(req, 'openai-compat', 'openai', import.meta.env.VITE_ENABLE_OPENAI === 'true')
}

async function callNebiusBackend(req: InferenceRequest): Promise<InferenceResponse> {
  return callChatBackend(req, 'nebius-token-factory', 'nebius', import.meta.env.VITE_ENABLE_NEBIUS === 'true')
}

async function callAzureBackend(req: InferenceRequest): Promise<InferenceResponse> {
  return callChatBackend(req, 'azure-openai', 'azure', import.meta.env.VITE_ENABLE_AZURE === 'true')
}

// ── Priority-ordered backend registry ────────────────────────────────────────

type BackendFn = (req: InferenceRequest) => Promise<InferenceResponse>

// Registry of supported targets. Hosted targets run only when explicitly selected.
const BACKEND_CHAIN: Array<[BackendType, BackendFn]> = [
  ['cl-psi',        callCLPsiBackend],
  ['openai-compat',         callOpenAIBackend],
  ['nebius-token-factory',  callNebiusBackend],
  ['azure-openai',           callAzureBackend],
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
 * With no explicit backend, try only local targets. An explicit target is never
 * replaced or retried through a different provider on failure.
 */
export async function routeInference(req: InferenceRequest): Promise<RouterResult> {
  const errors: string[] = []
  // An explicit backend selection may never execute a different provider.
  const chain = req.backend === undefined
    ? BACKEND_CHAIN.filter(([id]) => id === 'cl-psi' || id === 'ollama')
    : BACKEND_CHAIN.filter(([id]) => id === req.backend)
  if (chain.length === 0) throw new Error(`Unknown inference backend: ${String(req.backend)}`)
  for (const [id, fn] of chain) {
    try {
      const result = await fn(req)
      if (result.backend !== id) throw new Error(`Inference provider mismatch: expected ${id}, received ${result.backend}`)
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
  if (import.meta.env.VITE_ENABLE_NEBIUS === 'true') active.push('nebius-token-factory')
  if (import.meta.env.VITE_ENABLE_AZURE === 'true') active.push('azure-openai')
  if (import.meta.env.VITE_OLLAMA_BASE_URL) active.push('ollama')
  if (import.meta.env.VITE_ENABLE_DASHSCOPE === 'true') active.push('dashscope')
  return active
}

