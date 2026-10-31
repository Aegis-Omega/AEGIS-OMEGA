import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { Agent, Runner, tool, setTracingDisabled } from 'npm:@openai/agents@0.19.0'
import { z } from 'npm:zod@4.1.12'
setTracingDisabled(true)

const env = (key: string) => (Deno.env.get(key) ?? '').trim()
const headers = { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' }
const respond = (status: number, result: Record<string, unknown>) => new Response(JSON.stringify(result), { status, headers })
const permittedModels = new Set(['gpt-4.1-nano', 'gpt-4.1-mini'])

async function operatorAuthenticated(req: Request): Promise<'OK' | 'DENIED' | 'UNCONFIGURED'> {
  const operator = env('AEGIS_AGENT_OPERATOR_USER_ID')
  const base = env('SUPABASE_URL')
  const anon = env('SUPABASE_ANON_KEY')
  if (!operator || !base || !anon) return 'UNCONFIGURED'
  const bearer = req.headers.get('Authorization') ?? ''
  if (!/^Bearer\s+\S+$/.test(bearer)) return 'DENIED'
  try {
    const response = await fetch(base + '/auth/v1/user', {
      headers: { Authorization: bearer, apikey: anon },
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) return 'DENIED'
    const user = await response.json() as { id?: unknown }
    return user.id === operator ? 'OK' : 'DENIED'
  } catch { return 'DENIED' }
}

async function safeSnapshot() {
  const base = env('SUPABASE_URL')
  const secret = env('SUPABASE_SERVICE_ROLE_KEY')
  if (!base || !secret) return { state: 'UNAVAILABLE' }
  try {
    const res = await fetch(base + '/rest/v1/provider_runtime_latest_v1?select=provider_id,observation_state,expires_at&limit=12', {
      headers: { apikey: secret, Authorization: 'Bearer ' + secret },
      signal: AbortSignal.timeout(5000),
    })
    if (!res.ok) return { state: 'UNAVAILABLE' }
    const rows: unknown = await res.json()
    if (!Array.isArray(rows)) return { state: 'UNAVAILABLE' }
    return { state: 'OBSERVED_NOT_ADMITTED', providers: rows.slice(0, 12).map((row: Record<string, unknown>) => ({
      provider_id: String(row.provider_id ?? '').slice(0, 50),
      observation_state: String(row.observation_state ?? '').slice(0, 60),
      expires_at: String(row.expires_at ?? '').slice(0, 40),
    })) }
  } catch { return { state: 'UNAVAILABLE' } }
}

Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return respond(405, { error: 'METHOD_NOT_ALLOWED' })
  const auth = await operatorAuthenticated(req)
  if (auth === 'UNCONFIGURED') return respond(503, { error: 'OPERATOR_BINDING_REQUIRED' })
  if (auth !== 'OK') return respond(403, { error: 'OPERATOR_AUTHORIZATION_FAILED' })
  let input: { mode?: unknown; objective?: unknown }
  try {
    if (Number(req.headers.get('content-length') ?? 0) > 2048) return respond(413, { error: 'BODY_TOO_LARGE' })
    const text = await req.text()
    if (new TextEncoder().encode(text).length > 2048) return respond(413, { error: 'BODY_TOO_LARGE' })
    input = JSON.parse(text)
    if (input === null || typeof input !== 'object' || Array.isArray(input)) throw new Error()
  } catch { return respond(400, { error: 'BAD_REQUEST' }) }
  if (input.mode === 'status') return respond(200, {
    schema: 'aegis.openai-agents.v1', sdk: '@openai/agents@0.19.0',
    enabled: env('AEGIS_OPENAI_AGENTS_ENABLED') === 'true',
    model_key_present: Boolean(env('OPENAI_API_KEY')), paid_calls: 0,
    authority_effect: 'NONE',
  })
  if (input.mode !== 'run' || typeof input.objective !== 'string' ||
      input.objective.length < 5 || input.objective.length > 800) {
    return respond(400, { error: 'INVALID_OBJECTIVE' })
  }
  if (env('AEGIS_OPENAI_AGENTS_ENABLED') !== 'true') return respond(503, { error: 'AGENTS_DISABLED' })
  if (!env('OPENAI_API_KEY')) return respond(503, { error: 'MODEL_KEY_NOT_CONFIGURED' })
  const model = env('AEGIS_OPENAI_MODEL') || 'gpt-4.1-nano'
  if (!permittedModels.has(model)) return respond(503, { error: 'MODEL_NOT_ALLOWED' })

  const readState = tool({
    name: 'read_aegis_provider_state',
    description: 'Read only bounded provider status metadata from AEGIS. No personal data, credentials, writes or execution authority.',
    parameters: z.object({}),
    execute: async () => JSON.stringify(await safeSnapshot()),
  })
  const agent = new Agent({
    name: 'AEGIS Evidence Analyst',
    model,
    instructions: 'Read-only AEGIS evidence analysis. Do not guess provider readiness. Distinguish observed facts, stale records and unknowns. Never invent proofs, secrets, authorizations or deployments. Use only the read tool. Summarize concisely.',
    tools: [readState],
    modelSettings: { maxTokens: 192, timeoutMs: 12000, parallelToolCalls: false, store: false, retry: { maxRetries: 0 } },
  })
  try {
    const runner = new Runner({ tracingDisabled: true })
    const result = await runner.run(agent, input.objective, { maxTurns: 2 })
    return respond(200, {
      schema: 'aegis.openai-agents.v1', model,
      output: String(result.finalOutput ?? '').slice(0, 1700),
      authority_effect: 'NONE',
      max_turns: 2,
    })
  } catch {
    return respond(502, { error: 'AGENT_RUN_FAILED', authority_effect: 'NONE' })
  }
})
