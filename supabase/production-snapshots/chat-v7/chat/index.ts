import { createClient } from 'jsr:@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'
import { fetchWithTimeout, readTextBounded } from '../_shared/http.ts'

const DASHSCOPE_API_KEY_ENV = Deno.env.get('DASHSCOPE_API_KEY') ?? ''
const DASHSCOPE_URL = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions'
const OPENAI_API_KEY = Deno.env.get('OPENAI_API_KEY') ?? ''
const OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
// OPENAI_MODEL is REQUIRED for the OpenAI provider — no hardcoded default, since
// an invalid/guessed model id would be rejected by the paid backend. If unset,
// the OpenAI branch returns the friendly-unavailable response instead of calling out.
const OPENAI_MODEL = Deno.env.get('OPENAI_MODEL') ?? ''
const NEBIUS_API_KEY = Deno.env.get('NEBIUS_API_KEY') ?? ''
const NEBIUS_URL = 'https://api.tokenfactory.nebius.com/v1/chat/completions'
const NEBIUS_MODEL = Deno.env.get('NEBIUS_MODEL') ?? ''
// Server-side provider gates. `provider` arrives in the public request body, so
// the client-side VITE_ENABLE_* flags cannot actually gate the paid backends.
// A requested provider is only honored when its server flag is explicitly 'true';
// otherwise the request is denied. An explicit provider is never rerouted.
const CHAT_ENABLE_OPENAI = Deno.env.get('CHAT_ENABLE_OPENAI') === 'true'
const CHAT_ENABLE_NEBIUS = Deno.env.get('CHAT_ENABLE_NEBIUS') === 'true'
const CHAT_ENABLE_AZURE  = Deno.env.get('CHAT_ENABLE_AZURE') === 'true'
const AZURE_OPENAI_ENDPOINT = Deno.env.get('AZURE_OPENAI_ENDPOINT') ?? ''
const AZURE_OPENAI_API_KEY = Deno.env.get('AZURE_OPENAI_API_KEY') ?? ''
const AZURE_OPENAI_DEPLOYMENT = Deno.env.get('AZURE_OPENAI_DEPLOYMENT') ?? ''
const AZURE_OPENAI_API_VERSION = Deno.env.get('AZURE_OPENAI_API_VERSION') ?? '2024-10-21'
const DEFAULT_SYSTEM = `You are the AEGIS Omega AI assistant helping content creators. Be concise, direct, and practical.`
function readPositiveIntEnv(name: string, fallback: number): number {
  const raw = Deno.env.get(name)
  if (!raw) return fallback

  const parsed = Number(raw)
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback
}

// One bounded transport policy for every paid/free model provider. Deliberately
// no automatic retry for POST inference: without provider-level idempotency a
// retry could duplicate execution and cost.
const CHAT_UPSTREAM_TIMEOUT_MS = readPositiveIntEnv('CHAT_UPSTREAM_TIMEOUT_MS', 60_000)

let dashScopeKeyCache: string | null | undefined

async function loadDashScopeApiKey(): Promise<string> {
  if (DASHSCOPE_API_KEY_ENV) return DASHSCOPE_API_KEY_ENV
  if (dashScopeKeyCache !== undefined) return dashScopeKeyCache ?? ''

  const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
  const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
  if (!supabaseUrl || !serviceRoleKey) {
    dashScopeKeyCache = null
    return ''
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  })
  const { data, error } = await supabase.rpc('get_provider_secret_v1', {
    p_name: 'aegis-dashscope-api-key',
  })
  if (error || typeof data !== 'string' || !data) {
    if (error) console.error('DashScope Vault lookup failed:', error.message)
    dashScopeKeyCache = null
    return ''
  }

  dashScopeKeyCache = data
  return data
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: CORS })

  try {
    const { message, history = [], system = DEFAULT_SYSTEM, provider = 'dashscope' } = await req.json() as {
      message: string
      history?: { role: string; content: string }[]
      system?: string
      provider?: 'dashscope' | 'openai' | 'nebius' | 'azure'
    }

    if (!message?.trim()) {
      return new Response(JSON.stringify({ error: 'message required' }), { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } })
    }

    const messages = [
      { role: 'system', content: system },
      ...history.filter(m => m.role === 'user' || m.role === 'assistant').slice(-8),
      { role: 'user', content: message },
    ]

    // The TypeScript request annotation is not a runtime validation boundary.
    // Unknown or disabled providers must not silently select another paid backend.
    if (provider !== 'dashscope' && provider !== 'openai' && provider !== 'nebius' && provider !== 'azure') {
      return new Response(JSON.stringify({ error: 'unsupported provider' }), {
        status: 400, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const useOpenAI = provider === 'openai'
    const useNebius = provider === 'nebius'
    const useAzure = provider === 'azure'
    const providerId = useAzure
      ? 'azure-openai'
      : useOpenAI
        ? 'openai'
        : useNebius
          ? 'nebius-token-factory'
          : 'dashscope'

    // Preserve the established HTTP 200 unavailable response contract while
    // stopping before mesh/Vault reads, inference, or cross-provider fallback.
    if ((useOpenAI && !CHAT_ENABLE_OPENAI) || (useNebius && !CHAT_ENABLE_NEBIUS) || (useAzure && !CHAT_ENABLE_AZURE)) {
      return new Response(JSON.stringify({
        error: 'AI unavailable',
        reply: "The requested AI provider is disabled. No alternative provider was called.",
        provider_status: 'disabled',
        provider: providerId,
      }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    // An explicit model and credential are both required. Do not attempt an
    // empty Bearer credential, infer API access from ChatGPT, or choose a model.
    if (useOpenAI && (!OPENAI_MODEL.trim() || !OPENAI_API_KEY.trim())) {
      return new Response(JSON.stringify({
        error: 'AI unavailable',
        reply: "The requested AI provider is not configured. No alternative provider was called.",
        provider_status: 'unconfigured',
        provider: providerId,
      }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    if (!supabaseUrl || !serviceRoleKey) {
      console.error('Provider Mesh gate unavailable: Supabase runtime credentials missing')
      return new Response(JSON.stringify({
        error: 'AI unavailable',
        reply: "I'm having trouble connecting right now. Try again in a moment.",
        provider_status: 'mesh_unavailable',
      }), {
        status: 200,
        headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const providerMesh = createClient(supabaseUrl, serviceRoleKey, {
      auth: { persistSession: false },
    })
    const { data: candidates, error: candidateError } = await providerMesh.rpc(
      'get_provider_runtime_candidate_v1',
      {
        p_capability: 'MODEL_INFERENCE',
        p_provider_id: providerId,
      },
    )
    const candidate = Array.isArray(candidates) && candidates.length > 0
      ? candidates[0]
      : null

    if (candidateError || !candidate) {
      if (candidateError) {
        console.error('Provider Mesh candidate lookup failed:', candidateError.message)
      }
      return new Response(JSON.stringify({
        error: 'AI unavailable',
        reply: "I'm having trouble connecting right now. Try again in a moment.",
        provider_status: candidateError ? 'mesh_error' : 'not_observed_available',
        provider: providerId,
      }), {
        status: 200,
        headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    // Nebius also requires an explicit model and credential.
    if (useNebius && (!NEBIUS_MODEL || !NEBIUS_API_KEY)) {
      console.error('Nebius error: NEBIUS_MODEL and NEBIUS_API_KEY must be set')
      return new Response(JSON.stringify({ error: 'AI unavailable', reply: "I'm having trouble connecting right now. Try again in a moment." }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    if (useAzure && (!AZURE_OPENAI_ENDPOINT || !AZURE_OPENAI_DEPLOYMENT || !AZURE_OPENAI_API_KEY)) {
      console.error('Azure OpenAI error: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT and AZURE_OPENAI_API_KEY must be set')
      return new Response(JSON.stringify({ error: 'AI unavailable', reply: "I'm having trouble connecting right now. Try again in a moment." }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const dashScopeApiKey = useOpenAI || useNebius || useAzure
      ? ''
      : await loadDashScopeApiKey()

    if (!useOpenAI && !useNebius && !useAzure && !dashScopeApiKey) {
      console.error('DashScope error: no environment or Vault credential is configured')
      return new Response(JSON.stringify({ error: 'AI unavailable', reply: "I'm having trouble connecting right now. Try again in a moment." }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const url = useAzure
      ? `${AZURE_OPENAI_ENDPOINT}/openai/deployments/${AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version=${AZURE_OPENAI_API_VERSION}`
      : useOpenAI ? OPENAI_URL
        : useNebius ? NEBIUS_URL
          : DASHSCOPE_URL

    const resp = await fetchWithTimeout(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(useAzure
          ? { 'api-key': AZURE_OPENAI_API_KEY }
          : {
              'Authorization': `Bearer ${useOpenAI
                ? OPENAI_API_KEY
                : useNebius
                  ? NEBIUS_API_KEY
                  : dashScopeApiKey}`,
            }),
      },
      body: JSON.stringify(useAzure ? {
        // model is implied by the Azure deployment; gpt-5-family deployments
        // reject max_tokens/temperature, so mirror the OpenAI branch shape.
        messages,
        max_completion_tokens: 1024,
      } : useOpenAI ? {
        model: OPENAI_MODEL,
        messages,
        max_completion_tokens: 1024,
      } : useNebius ? {
        model: NEBIUS_MODEL,
        messages,
        max_tokens: 1024,
      } : {
        model: 'qwen-plus',
        messages,
        max_tokens: 512,
        temperature: 0.7,
      }),
    }, CHAT_UPSTREAM_TIMEOUT_MS)

    if (!resp.ok) {
      const err = await readTextBounded(resp)
      console.error(
        useAzure
          ? 'Azure OpenAI error:'
          : useOpenAI
            ? 'OpenAI error:'
            : useNebius
              ? 'Nebius Token Factory error:'
              : 'DashScope error:',
        resp.status,
        err,
      )
      return new Response(JSON.stringify({ error: 'AI unavailable', reply: "I'm having trouble connecting right now. Try again in a moment." }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const data = await resp.json()
    const reply = data.choices?.[0]?.message?.content ?? "Sorry, I didn't get a response."

    // Report the model/deployment actually used so callers (inference-router)
    // record real provenance instead of a client-side guess.
    const usedModel = useAzure ? AZURE_OPENAI_DEPLOYMENT : useOpenAI ? OPENAI_MODEL : useNebius ? NEBIUS_MODEL : 'qwen-plus'

    return new Response(JSON.stringify({ reply, model: usedModel }), {
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  } catch (e) {
    const detail = e instanceof Error ? `${e.name}: ${e.message}` : String(e)
    console.error('chat function error:', detail)
    return new Response(JSON.stringify({ reply: "Something went wrong. Please try again." }), {
      status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
