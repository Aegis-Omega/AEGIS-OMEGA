// AEGIS-Ω autonomous agent endpoint — Claude API with tools
// Deploy: supabase functions deploy agent --no-verify-jwt
// Env vars: ANTHROPIC_API_KEY, NOTIFY_SECRET, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, AEGIS_AGENT_INVOKE_SECRET
// Accepts: { task: string, dispatch_id: string, context?: string, notify?: boolean }
// Returns: { result: string, actions: string[] }
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

const ANTHROPIC_API_KEY = Deno.env.get('ANTHROPIC_API_KEY') ?? ''
const NOTIFY_SECRET     = Deno.env.get('NOTIFY_SECRET') ?? ''
const SUPABASE_URL      = Deno.env.get('SUPABASE_URL') ?? ''
const SERVICE_KEY       = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
// Explicit team:user pairs; a generic Slack dispatch allowance does not grant
// read access to service-role purchase records. No wildcard or empty default.
const PURCHASE_READERS = new Set((Deno.env.get('AEGIS_PURCHASE_READERS') ?? '')
  .split(',').map(x => x.trim()).filter(x => /^T[A-Za-z0-9]{2,48}:U[A-Za-z0-9]{2,48}$/.test(x)))
function hasPurchaseReaderScope(actorId?: string, teamId?: string): boolean {
  return typeof actorId === 'string' && typeof teamId === 'string' &&
    PURCHASE_READERS.has(teamId + ':' + actorId)
}

const SYSTEM = `You are the AEGIS-Ω autonomous agent. You run tasks for Tarik (aegisomega.com founder).
You have only the read-only purchase-query tool. Never attempt to send email, Slack, or other external notifications as a model tool; results must be delivered through the encrypted operator-authorized outbox.
Be concise. Report findings and clearly flag anything requiring operator attention.`

// ── Tool definitions ──────────────────────────────────────────────────────────
// ONLY read-only model tools here. Outbound notifications and result delivery
// are governed by the encrypted outbox, not by unverified model tool calls.
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

]

// ── Tool execution ────────────────────────────────────────────────────────────
async function runTool(name: string, input: Record<string, unknown>,
                       actorId?: string, teamId?: string): Promise<string> {
  if (name === 'query_purchases') {
    if (!hasPurchaseReaderScope(actorId, teamId)) return 'TOOL_NOT_AUTHORIZED'
    if (!input || typeof input !== 'object' || Array.isArray(input)) return 'INVALID_INPUT'
    // A model-provided argument is untrusted. Never let it expand a
    // service-role query or make an unknown filter silently return all rows.
    const requested = input.limit
    const requestedLimit = typeof requested === 'number' && Number.isFinite(requested)
      ? Math.trunc(requested) : 10
    const limit = Math.max(1, Math.min(25, requestedLimit))
    const supabase = createClient(SUPABASE_URL, SERVICE_KEY)
    let q = supabase.from('purchases').select('customer_email,plan,ls_order_id,updated_at')
    if (input.filter !== undefined && input.filter !== null && input.filter !== '') {
      if (typeof input.filter !== 'string') return 'INVALID_FILTER'
      const f = input.filter.trim()
      if (['single','starter','full'].includes(f)) {
        q = q.eq('plan', f)
      } else if (/^[A-Za-z0-9._+-]{1,64}@[A-Za-z0-9.-]{3,253}$/.test(f) && f.includes('.')) {
        // Exact comparison, not ILIKE + wildcards or substring matching.
        q = q.eq('customer_email', f)
      } else {
        return 'INVALID_FILTER'
      }
    }
    q = q.order('updated_at', { ascending: false }).limit(limit)
    const { data, error } = await q
    if (error) return `DB error: ${error.message}`
    // A missing DB payload is UNKNOWN, not evidence that there are zero rows.
    if (!Array.isArray(data)) return 'DB_RESULT_UNVERIFIED'
    return JSON.stringify(data)
  }


  // The model cannot gain authority by inventing tool names in its response.
  return 'TOOL_NOT_AUTHORIZED'
}

// ── Agentic loop (max 5 turns) ────────────────────────────────────────────────
async function runAgent(task: string, context?: string, actorId?: string, teamId?: string): Promise<{ result: string; actions: string[] }> {
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
        tools: hasPurchaseReaderScope(actorId, teamId) ? TOOLS : [],
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
      if (typeof text !== 'string' || !text.trim()) throw new Error('MODEL_INCOMPLETE')
      return { result: text, actions }
    }

    if (msg.stop_reason === 'tool_use') {
      // Never allow a single model response to fan out into multiple privileged
      // data reads, or launder a database sample into a fabricated aggregate.
      if (!Array.isArray(msg.content)) throw new Error('MODEL_INCOMPLETE')
      const toolRequests = msg.content.filter((b: { type?: string }) => b?.type === 'tool_use')
      if (toolRequests.length !== 1) throw new Error('MODEL_INCOMPLETE')
      const block = toolRequests[0]
      if (block.name !== 'query_purchases' || !hasPurchaseReaderScope(actorId, teamId) ||
          typeof block.id !== 'string' || !block.id.trim()) {
        throw new Error('MODEL_INCOMPLETE')
      }
      const output = await runTool(block.name, block.input, actorId, teamId)
      // A tool failure, malformed result or fabricated model continuation is
      // never evidence. Return *only* machine-observed rows, never a second
      // model-generated assertion about their total/meaning.
      if (output === 'INVALID_INPUT' || output === 'INVALID_FILTER' ||
          output === 'TOOL_NOT_AUTHORIZED' || output === 'DB_RESULT_UNVERIFIED' ||
          output.startsWith('DB error:')) {
        throw new Error('TOOL_VERIFICATION_FAILED')
      }
      let rows: unknown
      try { rows = JSON.parse(output) } catch { throw new Error('TOOL_VERIFICATION_FAILED') }
      if (!Array.isArray(rows) || rows.length > 25 ||
          rows.some(r => !r || typeof r !== 'object' || Array.isArray(r))) {
        throw new Error('TOOL_VERIFICATION_FAILED')
      }
      actions.push('query_purchases(OBSERVED_DB_ROWS)')
      return {result: JSON.stringify({
        schema: 'aegis.purchase_rows.v1',
        status: 'OBSERVED_DB_ROWS',
        source: 'supabase.public.purchases',
        rows,
        returned_row_count: rows.length,
        // Bounded read is never evidence of the table's global row count.
        is_global_total: false,
      }), actions}
    } else {
      // max_tokens/refusal/unknown stop reasons are not completed tasks.
      // Do not issue four additional paid requests for the same partial output.
      throw new Error('MODEL_INCOMPLETE')
    }
  }

  // Exhaustion is an incomplete model outcome, never a completed task artifact.
  throw new Error('MODEL_INCOMPLETE')
}

// ── Encrypted, fail-closed result outbox ───────────────────────────────────────
// No key material, raw customer data or model output is logged. The symmetric
// key is an operator-provisioned base64-encoded 256-bit AES key, separate from
// AEGIS_AGENT_INVOKE_SECRET. Losing/rotating it without re-encryption means
// existing results cannot be recovered. This is deliberate fail-closed behavior.
function configuredResultKey(): string | null {
  const base64 = Deno.env.get('AEGIS_RESULT_ENCRYPTION_KEY_B64') ?? ''
  try {
    const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
    return bytes.length === 32 ? base64 : null
  } catch { return null }
}

async function aesResultKey(key: string): Promise<CryptoKey> {
  return crypto.subtle.importKey('raw', Uint8Array.from(atob(key), c => c.charCodeAt(0)),
    'AES-GCM', false, ['encrypt', 'decrypt'])
}

function b64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
}
function unb64(text: string): Uint8Array {
  return Uint8Array.from(atob(text), c => c.charCodeAt(0))
}
async function sealResult(plain: string, key: string, aad: Uint8Array): Promise<{ciphertext_b64:string, iv_b64:string}> {
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const encrypted = await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:aad}, await aesResultKey(key),
    new TextEncoder().encode(plain))
  return {ciphertext_b64:b64(new Uint8Array(encrypted)), iv_b64:b64(iv)}
}
async function openResult(ciphertext_b64: string, iv_b64: string, key: string, aad: Uint8Array): Promise<string> {
  const iv = unb64(iv_b64)
  if (iv.length !== 12) throw new Error('BAD_RESULT_IV')
  const plain = await crypto.subtle.decrypt({name:'AES-GCM',iv,additionalData:aad}, await aesResultKey(key),
    unb64(ciphertext_b64))
  return new TextDecoder().decode(plain)
}
async function taggedDigest(tag: string, value: string): Promise<string> {
  const input = new TextEncoder().encode(tag + '\0' + value)
  const hash = new Uint8Array(await crypto.subtle.digest('SHA-256',input))
  return Array.from(hash).map(b=>b.toString(16).padStart(2,'0')).join('')
}
const REPLAY_ID = /^slack:(slash|event):[a-zA-Z0-9_.:-]{5,180}$/
const CHANNEL_ID = /^[CDG][A-Za-z0-9]{2,48}$/
const ATTEMPT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

// ── HTTP handler ──────────────────────────────────────────────────────────────
// Server-to-server invocation capability. Never infer access from endpoint reachability.
async function secureEquals(a: string, b: string): Promise<boolean> {
  const enc = new TextEncoder()
  const [aa, bb] = await Promise.all([
    crypto.subtle.digest('SHA-256', enc.encode(a)),
    crypto.subtle.digest('SHA-256', enc.encode(b)),
  ])
  const x = new Uint8Array(aa), y = new Uint8Array(bb)
  let diff = 0
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i]
  return diff === 0 && a.length === b.length
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: CORS })
  }

  // Authorization precedes provider credentials, privileged tools, and paid inference.
  const invokeSecret = Deno.env.get('AEGIS_AGENT_INVOKE_SECRET') ?? ''
  if (invokeSecret.length < 32 || invokeSecret.length > 256) {
    return new Response(JSON.stringify({ error: 'AGENT_AUTH_NOT_CONFIGURED' }), {
      status: 503, headers: CORS,
    })
  }
  const presented = req.headers.get('x-aegis-agent-secret') ?? ''
  if (!presented || presented.length > 256 || !(await secureEquals(presented, invokeSecret))) {
    return new Response(JSON.stringify({ error: 'UNAUTHORIZED' }), {
      status: 401, headers: CORS,
    })
  }

  // This is a privileged and paid tool surface. A stable, signed-Slack-sourced
  // event ID is mandatory; a caller may not invent a retryable execution.
  let payload: unknown
  try {
    payload = await req.json()
  } catch {
    return new Response(JSON.stringify({ error: 'INVALID_JSON' }), { status: 400, headers: CORS })
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return new Response(JSON.stringify({ error: 'INVALID_INPUT' }), { status: 400, headers: CORS })
  }
  const { task, context, notify, dispatch_id, channel_id, actor_id, team_id, operation, attempt_id,
          delivery_accepted } = payload as {
    task?: unknown; context?: unknown; notify?: unknown; dispatch_id?: unknown
    channel_id?: unknown; actor_id?: unknown; team_id?: unknown
    operation?: unknown; attempt_id?: unknown
    delivery_accepted?: unknown
  }
  if (typeof dispatch_id !== 'string' || !REPLAY_ID.test(dispatch_id) ||
      typeof channel_id !== 'string' || !CHANNEL_ID.test(channel_id) ||
      typeof actor_id !== 'string' || !/^U[A-Za-z0-9]{2,48}$/.test(actor_id) ||
      typeof team_id !== 'string' || !/^T[A-Za-z0-9]{2,48}$/.test(team_id)) {
    return new Response(JSON.stringify({error:'INVALID_DISPATCH'}),{status:400,headers:CORS})
  }
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return new Response(JSON.stringify({error:'DISPATCH_STORE_NOT_CONFIGURED'}),
      {status:503,headers:CORS})
  }
  const encryptionKey = configuredResultKey()
  if (!encryptionKey) {
    return new Response(JSON.stringify({error:'RESULT_ENCRYPTION_NOT_CONFIGURED'}),
      {status:503,headers:CORS})
  }
  const event_digest = await taggedDigest('AEGIS_AGENT_DISPATCH_V1',dispatch_id)
  // Bind each encrypted result to workspace + initiating user + channel.
  // An allowed colleague in the same channel must not recover another actor's result.
  const destination_digest = await taggedDigest('AEGIS_SLACK_DESTINATION_V2',
    team_id + '\0' + channel_id + '\0' + actor_id)
  const result_aad = new TextEncoder().encode('AEGIS_OUTBOX_V1\0' + event_digest + '\0' + destination_digest)
  const store = createClient(SUPABASE_URL,SERVICE_KEY)
  const action = operation ?? 'dispatch'
  const response = (code: number,data: Record<string,unknown>) => new Response(
    JSON.stringify(data),{status:code,headers:{...CORS,'Content-Type':'application/json'}})

  if (action === 'claim_delivery') {
    if (typeof attempt_id !== 'string' || !ATTEMPT_ID.test(attempt_id)) {
      return response(400,{error:'INVALID_DELIVERY_ATTEMPT'})
    }
    const {data,error} = await store.rpc('aegis_outbox_claim_delivery_v1',{
      p_event_digest:event_digest,p_destination_digest:destination_digest,p_attempt_id:attempt_id,
    })
    if (error) return response(503,{error:'OUTBOX_CLAIM_UNAVAILABLE'})
    const row = Array.isArray(data) ? data[0] : null
    if (!row) return response(409,{error:'OUTBOX_NOT_AVAILABLE'})
    try {
      const result = await openResult(row.ciphertext_b64,row.iv_b64,encryptionKey,result_aad)
      return response(200,{ok:true,result,status:'DELIVERY_LEASED'})
    } catch {
      // Never unlock ambiguous claimed output automatically.
      return response(503,{error:'OUTBOX_DECRYPT_FAILED'})
    }
  }

  if (action === 'complete_delivery') {
    if (typeof attempt_id !== 'string' || !ATTEMPT_ID.test(attempt_id) ||
        typeof delivery_accepted !== 'boolean') {
      return response(400,{error:'INVALID_DELIVERY_ACK'})
    }
    const {data,error} = await store.rpc('aegis_outbox_complete_delivery_v1',{
      p_event_digest:event_digest,p_destination_digest:destination_digest,
      p_attempt_id:attempt_id,p_delivered:delivery_accepted,
    })
    if (error) return response(503,{error:'OUTBOX_ACK_UNAVAILABLE'})
    if (data !== true) return response(409,{error:'STALE_DELIVERY_ATTEMPT'})
    return response(200,{ok:true,status:delivery_accepted?'DELIVERED':'READY_FOR_RETRY'})
  }

  if (action !== 'dispatch') return response(400,{error:'UNKNOWN_OPERATION'})
  if (!ANTHROPIC_API_KEY) return response(503,{error:'MODEL_NOT_CONFIGURED'})
  if (typeof task !== 'string' || !task.trim() || task.length > 4000 ||
      (context !== undefined && (typeof context !== 'string' || context.length > 6000)) ||
      notify === true) {
    return response(400,{error:'INVALID_TASK'})
  }

  // UNIQUE claim is the paid-inference concurrency gate. Never re-execute on
  // duplicate, including when the previous model call timed out ambiguously.
  const {error:claimError} = await store.from('aegis_agent_dispatch_claims_v1')
    .insert({event_digest})
  if (claimError) {
    return claimError.code === '23505'
      ? response(409,{error:'DUPLICATE_DISPATCH'})
      : response(503,{error:'DISPATCH_CLAIM_UNAVAILABLE'})
  }

  try {
    const {result} = await runAgent(task,context,actor_id,team_id)
    if (typeof result !== 'string' || result.length > 20000) {
      return response(503,{error:'RESULT_EXCEEDS_OUTBOX_LIMIT'})
    }
    const sealed = await sealResult(result,encryptionKey,result_aad)
    const {error:writeError} = await store.from('aegis_agent_result_outbox_v1')
      .insert({event_digest,destination_digest,...sealed})
    if (writeError) {
      // Paid work may have completed, but it was not safely persisted.
      console.error('AEGIS_RESULT_PERSIST_FAILED')
      return response(503,{error:'RESULT_PERSIST_FAILED'})
    }
    return response(200,{ok:true,status:'RESULT_STORED'})
  } catch (e) {
    console.error('AEGIS_MODEL_EXECUTION_FAILED')
    return response(503,{error: e instanceof Error && e.message === 'MODEL_INCOMPLETE'
      ? 'MODEL_INCOMPLETE' : 'MODEL_EXECUTION_UNCONFIRMED'})
  }

})
