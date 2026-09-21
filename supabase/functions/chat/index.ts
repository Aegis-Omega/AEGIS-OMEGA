import { createClient } from 'jsr:@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

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
// otherwise the request falls back to the default (dashscope).
const CHAT_ENABLE_OPENAI = Deno.env.get('CHAT_ENABLE_OPENAI') === 'true'
const CHAT_ENABLE_NEBIUS = Deno.env.get('CHAT_ENABLE_NEBIUS') === 'true'
const CHAT_ENABLE_AZURE  = Deno.env.get('CHAT_ENABLE_AZURE') === 'true'
const AZURE_OPENAI_ENDPOINT = Deno.env.get('AZURE_OPENAI_ENDPOINT') ?? ''
const AZURE_OPENAI_API_KEY = Deno.env.get('AZURE_OPENAI_API_KEY') ?? ''
const AZURE_OPENAI_DEPLOYMENT = Deno.env.get('AZURE_OPENAI_DEPLOYMENT') ?? ''
const AZURE_OPENAI_API_VERSION = Deno.env.get('AZURE_OPENAI_API_VERSION') ?? '2024-10-21'
const DEFAULT_SYSTEM = `You are the AEGIS Omega AI assistant helping content creators. Be concise, direct, and practical.`

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

    let useOpenAI = provider === 'openai'
    let useNebius = provider === 'nebius'
    let useAzure = provider === 'azure'

    // Server-side gate: a client cannot force a paid backend by setting `provider`.
    // If the provider's server flag is off, fall back to the default (dashscope).
    if (useOpenAI && !CHAT_ENABLE_OPENAI) {
      console.error('OpenAI provider requested but CHAT_ENABLE_OPENAI is not "true" — falling back to dashscope')
      useOpenAI = false
    }
    if (useNebius && !CHAT_ENABLE_NEBIUS) {
      console.error('Nebius provider requested but CHAT_ENABLE_NEBIUS is not "true" — falling back to dashscope')
      useNebius = false
    }
    if (useAzure && !CHAT_ENABLE_AZURE) {
      console.error('Azure provider requested but CHAT_ENABLE_AZURE is not "true" — falling back to dashscope')
      useAzure = false
    }

    // OpenAI and Nebius require explicit models — never send guessed model ids.
    if (useOpenAI && !OPENAI_MODEL) {
      console.error('OpenAI error: OPENAI_MODEL must be set (no hardcoded default)')
      return new Response(JSON.stringify({ error: 'AI unavailable', reply: "I'm having trouble connecting right now. Try again in a moment." }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

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

    const resp = await fetch(url, {
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
    })

    if (!resp.ok) {
      const err = await resp.text()
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
    console.error('chat function error:', e)
    return new Response(JSON.stringify({ reply: "Something went wrong. Please try again." }), {
      status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
