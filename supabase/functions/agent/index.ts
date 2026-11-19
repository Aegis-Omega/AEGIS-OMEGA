// AEGIS-Ω autonomous agent endpoint — Claude API with tools
// Runtime: explicit Supabase JWT and approved-user allowlist required before paid actions
// Env vars: ANTHROPIC_API_KEY, NOTIFY_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
// Accepts: { task: string, context?: string, notify?: boolean }
// Returns: { result: string, actions: string[] }
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'
import { authorizeNebiusCaller, isNebiusRequestBounded } from '../_shared/nebius-auth.ts'
import { authorizeSlackMachine, readBoundedBody } from '../_shared/slack-agent-auth.ts'
import { reserveAgentExecution } from '../_shared/agent-budget.ts'

const ANTHROPIC_API_KEY = Deno.env.get('ANTHROPIC_API_KEY') ?? ''
const NOTIFY_SECRET     = Deno.env.get('NOTIFY_SECRET') ?? ''
const SUPABASE_URL      = Deno.env.get('SUPABASE_URL') ?? ''
const SERVICE_KEY       = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''

const SYSTEM = `You are the AEGIS-Ω autonomous agent. You run tasks for Tarik (aegisomega.com founder).
You have tools to: query purchases from the database, send notifications via email/Slack.
Be concise. Report what you did and any findings. If something needs human attention, say so clearly.`

// ── Tool definitions ──────────────────────────────────────────────────────────
const TOOLS = [
  {
    name: 'query_purchases',
    description: 'Query the purchases table. Returns recent purchases, stats, or specific lookups.',
    input_schema: {
      type: 'object',
      properties: {
        filter: { type: 'string', description: 'Optional: filter by plan (single/starter/full) or email' },
        limit:  { type: 'number', description: 'Max rows to return (default 10)' },
      },
    },
  },
  {
    name: 'send_notification',
    description: 'Send an email or Slack message to Tarik.',
    input_schema: {
      type: 'object',
      required: ['channel', 'text'],
      properties: {
        channel: { type: 'string', enum: ['email', 'slack', 'both'] },
        subject: { type: 'string', description: 'Email subject (optional)' },
        text:    { type: 'string', description: 'Message body' },
      },
    },
  },
]

// ── Tool execution ────────────────────────────────────────────────────────────
async function runTool(name: string, input: Record<string, unknown>): Promise<string> {
  if (name === 'query_purchases') {
    const supabase = createClient(SUPABASE_URL, SERVICE_KEY)
    let q = supabase.from('purchases').select('customer_email,plan,ls_order_id,updated_at')
    if (input.filter) {
      const f = String(input.filter)
      if (['single','starter','full'].includes(f)) {
        q = q.eq('plan', f)
      } else if (f.includes('@')) {
        q = q.ilike('customer_email', `%${f}%`)
      }
    }
    q = q.order('updated_at', { ascending: false }).limit(Number(input.limit ?? 10))
    const { data, error } = await q
    if (error) return `DB error: ${error.message}`
    return JSON.stringify(data ?? [])
  }

  if (name === 'send_notification') {
    const notifyUrl = `${SUPABASE_URL}/functions/v1/notify`
    const res = await fetch(notifyUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-notify-secret': NOTIFY_SECRET },
      body: JSON.stringify(input),
    })
    return res.ok ? 'Notification sent' : `Notify failed: ${res.status}`
  }

  return `Unknown tool: ${name}`
}

// ── Agentic loop (max 5 turns) ────────────────────────────────────────────────
async function runAgent(task: string, context?: string, mode: 'operator' | 'slack' = 'operator'): Promise<{ result: string; actions: string[] }> {
  const messages: { role: string; content: unknown }[] = [
    { role: 'user', content: context ? `Context:\n${context}\n\nTask: ${task}` : task },
  ]
  const actions: string[] = []

  for (let turn = 0; turn < (mode === 'slack' ? 1 : 5); turn++) {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'anthropic-beta': 'prompt-caching-2024-07-31',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5',
        max_tokens: mode === 'slack' ? 256 : 1024,
        system: [{ type: 'text', text: mode === 'slack'
          ? 'Answer the Slack question briefly. No database, account data, tools, mutations or notifications.'
          : SYSTEM, cache_control: { type: 'ephemeral' } }],
        tools: mode === 'slack' ? [] : TOOLS,
        messages,
      }),
    })

    if (!res.ok) {
      // Do not read or log provider response bodies, which can contain sensitive data.
      throw new Error(`Provider request failed: HTTP ${res.status}`)
    }

    const msg = await res.json()
    messages.push({ role: 'assistant', content: msg.content })

    if (msg.stop_reason === 'end_turn') {
      const text = msg.content.find((b: { type: string }) => b.type === 'text')?.text ?? ''
      return { result: text, actions }
    }

    // A Slack machine identity is never authorized to execute DB or notification tools.
    if (mode === 'slack') return { result: 'No tool execution is available for Slack requests.', actions: [] }

    if (msg.stop_reason === 'tool_use') {
      const toolResults = []
      for (const block of msg.content) {
        if (block.type !== 'tool_use') continue
        actions.push(`${block.name}(${JSON.stringify(block.input)})`)
        const output = await runTool(block.name, block.input)
        toolResults.push({ type: 'tool_result', tool_use_id: block.id, content: output })
      }
      messages.push({ role: 'user', content: toolResults })
    }
  }

  return { result: 'Agent reached max turns without completing task.', actions }
}

// ── HTTP handler ──────────────────────────────────────────────────────────────
Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: CORS })
  }

  // Never combine user JWT authorization and Slack machine authentication.
  // JWT is always verified by Supabase Auth; machine credentials are HMAC,
  // bound to this request, audience, Slack actor, TTL and a separate capability.
  const machineHeaders = ['x-aegis-machine-key-id', 'x-aegis-machine-ts',
    'x-aegis-machine-nonce', 'x-aegis-machine-sig']
  const hasMachineHeaders = machineHeaders.some(key => req.headers.has(key))
  const requestUrl = new URL(req.url)
  if (hasMachineHeaders && (requestUrl.pathname !== '/functions/v1/agent' || requestUrl.search)) {
    return Response.json({ error: 'Machine audience mismatch' }, { status: 401, headers: CORS })
  }
  if (hasMachineHeaders && req.headers.has('authorization')) {
    return Response.json({ error: 'Conflicting credentials' }, { status: 401, headers: CORS })
  }

  let mode: 'operator' | 'slack'
  let actorId: string
  let eventKey: string
  let raw: string | null
  let machineBody: Awaited<ReturnType<typeof authorizeSlackMachine>> = null

  if (hasMachineHeaders) {
    raw = await readBoundedBody(req)
    if (raw === null) return Response.json({ error: 'Invalid body' }, { status: 413, headers: CORS })
    machineBody = await authorizeSlackMachine(req.headers, raw, {
      key: Deno.env.get('AEGIS_SLACK_AGENT_HMAC_KEY') ?? '',
      keyId: Deno.env.get('AEGIS_SLACK_AGENT_KEY_ID') ?? '',
      allowedTeams: Deno.env.get('AEGIS_SLACK_ALLOWED_TEAM_IDS') ?? '',
      allowedUsers: Deno.env.get('AEGIS_SLACK_ALLOWED_USER_IDS') ?? '',
      allowedActors: Deno.env.get('AEGIS_SLACK_ALLOWED_ACTORS') ?? '',
    })
    if (!machineBody) {
      return Response.json({ error: 'Unauthorized machine caller' }, { status: 401, headers: CORS })
    }
    mode = 'slack'
    actorId = `${machineBody.slack.team_id}:${machineBody.slack.user_id}`
    eventKey = `slack:${machineBody.slack.team_id}:${machineBody.slack.event_id}`
  } else {
    let operatorId: string | null = null
    const permitted = await authorizeNebiusCaller(
      req.headers.get('Authorization'),
      Deno.env.get('AEGIS_AGENT_ALLOWED_USER_IDS') ?? '',
      async (jwt) => {
        if (!SUPABASE_URL || !SERVICE_KEY) return null
        const authClient = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } })
        const { data, error } = await authClient.auth.getUser(jwt)
        operatorId = error ? null : data.user?.id ?? null
        return operatorId
      },
    )
    if (!permitted || !operatorId) {
      return Response.json({ error: 'Authenticated operator required' }, { status: 401, headers: CORS })
    }
    mode = 'operator'
    actorId = operatorId
    eventKey = `operator:${crypto.randomUUID()}`
    raw = await readBoundedBody(req)
    if (raw === null) return Response.json({ error: 'Invalid body' }, { status: 413, headers: CORS })
  }

  if (!ANTHROPIC_API_KEY || !SUPABASE_URL || !SERVICE_KEY) {
    return Response.json({ error: 'Agent unavailable' }, { status: 503, headers: CORS })
  }
  if (!req.headers.get('content-type')?.includes('application/json')) {
    return Response.json({ error: 'Content type required' }, { status: 415, headers: CORS })
  }
  let body: unknown
  try { body = JSON.parse(raw) } catch {
    return Response.json({ error: 'invalid JSON body' }, { status: 400, headers: CORS })
  }
  if (body === null || typeof body !== 'object' || Array.isArray(body)) {
    return Response.json({ error: 'invalid request body' }, { status: 400, headers: CORS })
  }
  const { task, context, notify } = body as Record<string, unknown>
  if (typeof task !== 'string' || (context !== undefined && typeof context !== 'string')
    || (notify !== undefined && typeof notify !== 'boolean')) {
    return Response.json({ error: 'invalid request fields' }, { status: 400, headers: CORS })
  }
  if (mode === 'slack' && (notify !== undefined || context !== undefined || !machineBody)) {
    return Response.json({ error: 'Slack scope violation' }, { status: 403, headers: CORS })
  }
  const boundedContext = mode === 'slack'
    ? `Slack team ${machineBody!.slack.team_id}, user ${machineBody!.slack.user_id}`
    : context === undefined ? undefined : context
  if (!isNebiusRequestBounded(task, boundedContext ?? '', [])) {
    return Response.json({ error: 'task or context exceeds request bounds' }, { status: 400, headers: CORS })
  }

  // Both user and Slack paths require one atomic, durable replay+quota admission.
  // Missing RPC/schema or database failure => unavailable; never spend on fail-open.
  const budgetClient = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } })
  const admission = await reserveAgentExecution(budgetClient, mode, actorId, eventKey)
  if (admission === 'unavailable') {
    return Response.json({ error: 'Budget control unavailable' }, { status: 503, headers: CORS })
  }
  if (admission === 'denied') {
    return Response.json({ error: 'Duplicate or quota reached' }, { status: 429, headers: CORS })
  }

  try {
    const { result, actions } = await runAgent(task, boundedContext, mode)

    // Optionally notify owner with the result
    if (mode === 'operator' && notify) {
      const notifyUrl = `${SUPABASE_URL}/functions/v1/notify`
      await fetch(notifyUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-notify-secret': NOTIFY_SECRET },
        body: JSON.stringify({ channel: 'both', subject: `Agent result: ${task.slice(0, 60)}`, text: result }),
      }).catch(console.error)
    }

    return new Response(JSON.stringify({ ok: true, result, actions }), {
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  } catch (e) {
    console.error('Agent execution failed (details redacted)')
    return new Response(JSON.stringify({ error: 'Agent execution failed' }), {
      status: 502,
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
