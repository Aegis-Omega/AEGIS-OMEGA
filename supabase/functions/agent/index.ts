// AEGIS-Ω autonomous agent endpoint — Claude API with tools
// Deploy: supabase functions deploy agent --no-verify-jwt
// Env vars: ANTHROPIC_API_KEY, NOTIFY_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
// Accepts: { task: string, context?: string, notify?: boolean }
// Returns: { result: string, actions: string[] }
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

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
async function runAgent(task: string, context?: string): Promise<{ result: string; actions: string[] }> {
  const messages: { role: string; content: unknown }[] = [
    { role: 'user', content: context ? `Context:\n${context}\n\nTask: ${task}` : task },
  ]
  const actions: string[] = []

  for (let turn = 0; turn < 5; turn++) {
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
        max_tokens: 1024,
        system: [{ type: 'text', text: SYSTEM, cache_control: { type: 'ephemeral' } }],
        tools: TOOLS,
        messages,
      }),
    })

    if (!res.ok) {
      const err = await res.text()
      throw new Error(`Anthropic API error ${res.status}: ${err}`)
    }

    const msg = await res.json()
    messages.push({ role: 'assistant', content: msg.content })

    if (msg.stop_reason === 'end_turn') {
      const text = msg.content.find((b: { type: string }) => b.type === 'text')?.text ?? ''
      return { result: text, actions }
    }

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

  if (!ANTHROPIC_API_KEY) {
    return new Response(JSON.stringify({ error: 'ANTHROPIC_API_KEY not configured' }), { status: 503, headers: CORS })
  }

  const { task, context, notify } = await req.json() as { task?: string; context?: string; notify?: boolean }
  if (!task) {
    return new Response(JSON.stringify({ error: 'task is required' }), { status: 400, headers: CORS })
  }

  try {
    const { result, actions } = await runAgent(task, context)

    // Optionally notify owner with the result
    if (notify) {
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
    console.error('Agent error:', e)
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500,
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
