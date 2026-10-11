// AEGIS-Ω Slack event handler — slash commands + app mentions → autonomous agent
// Deploy: supabase functions deploy slack-events --no-verify-jwt
// Env vars: SLACK_SIGNING_SECRET, SLACK_BOT_TOKEN, SUPABASE_URL, NOTIFY_SECRET, AEGIS_AGENT_INVOKE_SECRET, AEGIS_SLACK_ALLOWED_USER_IDS, AEGIS_SLACK_ALLOWED_CHANNEL_IDS, AEGIS_SLACK_ALLOWED_TEAM_IDS
//
// Slack app setup (api.slack.com/apps):
//   1. Incoming Webhooks → ON → install to #aegis-alerts → copy URL → SLACK_WEBHOOK_URL secret
//   2. Slash Commands → /aegis → Request URL: https://rwehltdwpsncnwxzkwik.supabase.co/functions/v1/slack-events
//   3. Event Subscriptions → Request URL same as above → Subscribe to: app_mention, message.im
//   4. OAuth Scopes: chat:write, commands, app_mentions:read, im:read, im:write
//   5. Install app → copy Bot Token → SLACK_BOT_TOKEN secret
//   6. Copy Signing Secret → SLACK_SIGNING_SECRET secret

const SLACK_SIGNING_SECRET = Deno.env.get('SLACK_SIGNING_SECRET') ?? ''
const SLACK_BOT_TOKEN      = Deno.env.get('SLACK_BOT_TOKEN') ?? ''
const SUPABASE_URL         = Deno.env.get('SUPABASE_URL') ?? ''
const NOTIFY_SECRET        = Deno.env.get('NOTIFY_SECRET') ?? ''
const AGENT_INVOKE_SECRET  = Deno.env.get('AEGIS_AGENT_INVOKE_SECRET') ?? ''
// An authenticated Slack workspace event does not authenticate its author as
// AEGIS operator. Reject all execution when the explicit allowlist is absent.
const ALLOWED_SLACK_USERS = new Set(
  (Deno.env.get('AEGIS_SLACK_ALLOWED_USER_IDS') ?? '')
    .split(',').map(x => x.trim()).filter(Boolean),
)
// Inference results may contain purchase/customer data. A signed, allowed
// caller must not route sensitive output into an unapproved Slack channel.
const ALLOWED_SLACK_CHANNELS = new Set(
  (Deno.env.get('AEGIS_SLACK_ALLOWED_CHANNEL_IDS') ?? '')
    .split(',').map(x => x.trim()).filter(Boolean),
)
const ALLOWED_SLACK_TEAMS = new Set(
  (Deno.env.get('AEGIS_SLACK_ALLOWED_TEAM_IDS') ?? '')
    .split(',').map(x => x.trim()).filter(Boolean),
)

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

// Verify Slack request signature (HMAC-SHA256)
async function verifySlackSignature(body: string, timestamp: string, sig: string): Promise<boolean> {
  // Public webhook: missing signature configuration MUST never turn auth off.
  if (!SLACK_SIGNING_SECRET || !timestamp || !/^v0=[0-9a-f]{64}$/.test(sig)) return false
  const sentAt = Number(timestamp)
  if (!Number.isSafeInteger(sentAt) || sentAt <= 0 ||
      Math.abs(Date.now() / 1000 - sentAt) > 300) return false

  const baseString = `v0:${timestamp}:${body}`
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(SLACK_SIGNING_SECRET),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  )
  const raw = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(baseString))
  const computed = 'v0=' + Array.from(new Uint8Array(raw)).map(b => b.toString(16).padStart(2, '0')).join('')
  return computed === sig
}

// Edge Functions may retire the isolate as soon as the HTTP request returns.
// Register all expensive agent work so a quick Slack ACK cannot discard it.
// If the host lacks this execution guarantee, reject rather than acknowledge work.
function dispatchBackground(work: () => Promise<void>): boolean {
  // Never spend on a task if the approved result-delivery channel is unavailable.
  // This only proves local configuration, NOT Slack token validity or delivery.
  if (!SLACK_BOT_TOKEN || !SUPABASE_URL ||
      AGENT_INVOKE_SECRET.length < 32 || AGENT_INVOKE_SECRET.length > 256) {
    return false
  }
  if (typeof EdgeRuntime === 'undefined' || typeof EdgeRuntime.waitUntil !== 'function') {
    return false
  }
  EdgeRuntime.waitUntil(work())
  return true
}

// Post a message back to Slack
async function slackReply(channel: string, text: string, thread_ts?: string): Promise<void> {
  if (!ALLOWED_SLACK_CHANNELS.has(channel)) throw new Error('SLACK_CHANNEL_NOT_AUTHORIZED')
  if (!SLACK_BOT_TOKEN) throw new Error('SLACK_DELIVERY_UNCONFIGURED')
  const res = await fetch('https://slack.com/api/chat.postMessage', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${SLACK_BOT_TOKEN}`, 'Content-Type': 'application/json' },
    // Untrusted LLM content is readable plain text, never executable Slack mrkdwn.
    body: JSON.stringify({ channel, text, thread_ts, mrkdwn: false, parse: 'none', link_names: false }),
  })
  // Slack may return HTTP 200 with {ok:false, error:...}. HTTP success alone
  // must never count as verified delivery of an already-paid inference result.
  if (!res.ok) throw new Error(`SLACK_DELIVERY_HTTP_${res.status}`)
  let payload: unknown
  try { payload = await res.json() } catch { throw new Error('SLACK_DELIVERY_INVALID_JSON') }
  if (!payload || typeof payload !== 'object' ||
      (payload as {ok?: unknown}).ok !== true) {
    throw new Error('SLACK_DELIVERY_REJECTED')
  }
  // HTTP 200 and ok:true alone do not establish where an output was posted.
  // Require the exact channel and a Slack-assigned message timestamp.
  // Missing/mismatched receipt evidence is ambiguous: leave outbox SENDING.
  const receipt = payload as {channel?: unknown, ts?: unknown}
  if (receipt.channel !== channel || typeof receipt.ts !== 'string' ||
      !/^\d{10,}\.\d{6}$/.test(receipt.ts)) {
    throw new Error('SLACK_DELIVERY_ACK_UNVERIFIED')
  }
}

// Same authenticated worker route owns dispatch, encrypted outbox and delivery
// leases. A Slack retry may recover its result; it NEVER reruns model inference.
async function invokeAgent(payload: Record<string, unknown>): Promise<Response> {
  return fetch(`${SUPABASE_URL}/functions/v1/agent`, {
    method: 'POST',
    headers: { 'Content-Type':'application/json', 'x-aegis-agent-secret':AGENT_INVOKE_SECRET },
    body: JSON.stringify(payload),
  })
}

async function runAgent(task: string, dispatchId: string, channel: string,
                        actorId: string, teamId: string, context?: string): Promise<void> {
  if (AGENT_INVOKE_SECRET.length < 32 || AGENT_INVOKE_SECRET.length > 256) {
    throw new Error('AGENT_AUTH_NOT_CONFIGURED')
  }
  const res = await invokeAgent({task,context,dispatch_id:dispatchId,channel_id:channel,
    actor_id:actorId,team_id:teamId})
  if (res.status === 409) return // Prior event: try to recover output, no second paid inference.
  if (!res.ok) throw new Error('AGENT_DISPATCH_UNAVAILABLE')
  const body = await res.json()
  if (body?.status !== 'RESULT_STORED') throw new Error('RESULT_NOT_PERSISTED')
}

async function completeDelivery(dispatchId: string, channel: string,
                                actorId: string, teamId: string,
                                attemptId: string, accepted: boolean): Promise<void> {
  const r = await invokeAgent({operation:'complete_delivery',dispatch_id:dispatchId,
    channel_id:channel,actor_id:actorId,team_id:teamId,
    attempt_id:attemptId,delivery_accepted:accepted})
  if (!r.ok) throw new Error('RESULT_DELIVERY_ACK_UNCONFIRMED')
}

async function deliverStoredResult(dispatchId: string, channel: string,
                                   actorId: string, teamId: string, threadTs?: string): Promise<void> {
  const attemptId = crypto.randomUUID()
  const res = await invokeAgent({operation:'claim_delivery',dispatch_id:dispatchId,
    channel_id:channel,actor_id:actorId,team_id:teamId,attempt_id:attemptId})
  if (res.status === 409) return // Pending/claimed/delivered/expired: no duplicate output.
  if (!res.ok) throw new Error('RESULT_OUTBOX_UNAVAILABLE')
  const data = await res.json()
  if (data?.status !== 'DELIVERY_LEASED' || typeof data.result !== 'string') {
    throw new Error('RESULT_OUTBOX_INVALID')
  }
  try {
    await slackReply(channel, `AEGIS Ω — ${data.result}`, threadTs)
  } catch (error) {
    // Only an EXPLICIT Slack ok:false means the provider definitively refused.
    // All network/HTTP/JSON ambiguity remains SENDING for manual reconciliation.
    if (error instanceof Error && error.message === 'SLACK_DELIVERY_REJECTED') {
      await completeDelivery(dispatchId,channel,actorId,teamId,attemptId,false)
    }
    throw new Error('RESULT_DELIVERY_NOT_CONFIRMED')
  }
  // Never infer delivery merely from our own successful HTTP request.
  await completeDelivery(dispatchId,channel,actorId,teamId,attemptId,true)
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })

  const body = await req.text()
  const timestamp = req.headers.get('x-slack-request-timestamp') ?? ''
  const sig       = req.headers.get('x-slack-signature') ?? ''

  if (!(await verifySlackSignature(body, timestamp, sig))) {
    return new Response('Unauthorized', { status: 401 })
  }

  const contentType = req.headers.get('content-type') ?? ''

  // ── Slash command (/aegis <task>) — form-encoded ──────────────────────────
  if (contentType.includes('application/x-www-form-urlencoded')) {
    const params = new URLSearchParams(body)
    const task    = params.get('text')?.trim() ?? ''
    const channel = params.get('channel_id') ?? ''
    const user    = params.get('user_name') ?? 'unknown'
    const userId  = params.get('user_id') ?? ''
    const teamId = params.get('team_id') ?? ''
    if (!/^T[A-Za-z0-9]{2,48}$/.test(teamId) || !ALLOWED_SLACK_TEAMS.has(teamId) ||
        !/^U[A-Za-z0-9]{2,48}$/.test(userId) || !ALLOWED_SLACK_USERS.has(userId) ||
        !ALLOWED_SLACK_CHANNELS.has(channel)) {
      return new Response('Operator or channel not authorized', { status: 403 })
    }
    const ts      = params.get('message_ts') ?? undefined
    const triggerId = params.get('trigger_id') ?? ''
    if (!/^[a-zA-Z0-9_.:-]{5,180}$/.test(triggerId)) {
      return new Response('Missing valid Slack trigger ID', { status: 400 })
    }
    const dispatchId = 'slack:slash:' + triggerId

    if (!task) {
      return new Response(JSON.stringify({
        response_type: 'ephemeral',
        text: 'Usage: `/aegis <task>` — e.g. `/aegis how many purchases today?`',
      }), { headers: { 'Content-Type': 'application/json' } })
    }

    // Explicit operator-driven output recovery from Slack/mobile.
    // It never calls runAgent(), and therefore never replays paid inference.
    if (task.startsWith('recover ')) {
      const originalId = task.slice('recover '.length).trim()
      if (!/^slack:(slash|event):[a-zA-Z0-9_.:-]{5,180}$/.test(originalId)) {
        return new Response('Invalid recovery reference', { status: 400 })
      }
      const accepted = dispatchBackground(async () => {
        try { await deliverStoredResult(originalId,channel,userId,teamId,ts) }
        catch { console.error('AEGIS_MANUAL_RECOVERY_UNCONFIRMED') }
      })
      if (!accepted) return new Response('Recovery unavailable', { status: 503 })
      return new Response(JSON.stringify({response_type:'ephemeral',
        text:'Output-only recovery requested. No new model call was made.'}),
        {headers:{'Content-Type':'application/json'}})
    }

    // Acknowledge immediately (Slack requires <3s response)
    const ackResponse = new Response(JSON.stringify({
      response_type: 'ephemeral',
      text: `Task accepted. Recovery reference: ${dispatchId}. Use /aegis recover ${dispatchId} if result delivery is rejected.`,
    }), { headers: { 'Content-Type': 'application/json' } })

    // Explicitly bind background lifetime to Supabase EdgeRuntime.
    const registered = dispatchBackground(async () => {
      try {
        await runAgent(task, dispatchId, channel, userId, teamId, `Requested by @${user} in Slack`)
        await deliverStoredResult(dispatchId,channel,userId,teamId,ts)
      } catch (e) {
        // Do not leak provider/DB errors into Slack. A second delivery failure
        // is observable in the Edge log, never silently treated as success.
        console.error('AEGIS_SLACK_DISPATCH_FAILED')
        try {
          await slackReply(channel, 'AEGIS task or result delivery failed; contact the Operator.', ts)
        } catch (deliveryError) {
          console.error('AEGIS_SLACK_RESULT_UNDELIVERED')
        }
      }
    })
    if (!registered) return new Response('Agent dispatch unavailable', { status: 503 })
    return ackResponse
  }

  // ── Event API (app_mention, url_verification) — JSON ─────────────────────
  if (contentType.includes('application/json')) {
    const event = JSON.parse(body)

    // URL verification challenge (required during app setup)
    if (event.type === 'url_verification') {
      return new Response(JSON.stringify({ challenge: event.challenge }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // App mention: @AEGIS-Ω <task>
    if (event.event?.type === 'app_mention') {
      const userId = event.event.user ?? ''
      const channel = event.event.channel ?? ''
      const teamId = event.team_id ?? ''
      if (!/^T[A-Za-z0-9]{2,48}$/.test(teamId) || !ALLOWED_SLACK_TEAMS.has(teamId) ||
          !/^U[A-Za-z0-9]{2,48}$/.test(userId) || !ALLOWED_SLACK_USERS.has(userId) ||
          !ALLOWED_SLACK_CHANNELS.has(channel)) {
        return new Response('Operator or channel not authorized', { status: 403 })
      }
      const text    = (event.event.text ?? '').replace(/<@[A-Z0-9]+>/g, '').trim()
      const ts      = event.event.ts
      const eventId = event.event_id
      if (typeof eventId !== 'string' || !/^[a-zA-Z0-9_.:-]{5,180}$/.test(eventId)) {
        return new Response('Missing valid Slack event ID', { status: 400 })
      }
      const dispatchId = 'slack:event:' + eventId

      if (text) {
        const registered = dispatchBackground(async () => {
          try {
            await slackReply(channel, '_Running an approved task..._', ts)
            await runAgent(text, dispatchId, channel, userId, teamId, 'Requested via @AEGIS-Ω mention in Slack')
            await deliverStoredResult(dispatchId,channel,userId,teamId,ts)
          } catch (e) {
            console.error('AEGIS_SLACK_DISPATCH_FAILED')
            try {
              await slackReply(channel, 'AEGIS task or result delivery failed; contact the Operator.', ts)
            } catch (deliveryError) {
              console.error('AEGIS_SLACK_RESULT_UNDELIVERED')
            }
          }
        })
        if (!registered) return new Response('Agent dispatch unavailable', { status: 503 })
      }

      return new Response('ok', { status: 200 })
    }
  }

  return new Response('ok', { status: 200 })
})
