// AEGIS-Ω Slack event handler — slash commands + app mentions → autonomous agent
// Deploy: supabase functions deploy slack-events --no-verify-jwt
// Env vars: SLACK_SIGNING_SECRET, SLACK_BOT_TOKEN, SUPABASE_URL, NOTIFY_SECRET
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

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

// Verify Slack request signature (HMAC-SHA256)
async function verifySlackSignature(body: string, timestamp: string, sig: string): Promise<boolean> {
  if (!SLACK_SIGNING_SECRET) return true // skip in dev
  const age = Math.abs(Date.now() / 1000 - Number(timestamp))
  if (age > 300) return false // replay attack

  const baseString = `v0:${timestamp}:${body}`
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(SLACK_SIGNING_SECRET),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  )
  const raw = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(baseString))
  const computed = 'v0=' + Array.from(new Uint8Array(raw)).map(b => b.toString(16).padStart(2, '0')).join('')
  return computed === sig
}

// Post a message back to Slack
async function slackReply(channel: string, text: string, thread_ts?: string): Promise<void> {
  if (!SLACK_BOT_TOKEN) return
  await fetch('https://slack.com/api/chat.postMessage', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${SLACK_BOT_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel, text, thread_ts }),
  })
}

// Call the agent function with a task
async function runAgent(task: string, context?: string): Promise<string> {
  const agentUrl = `${SUPABASE_URL}/functions/v1/agent`
  const res = await fetch(agentUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-notify-secret': NOTIFY_SECRET },
    body: JSON.stringify({ task, context }),
  })
  if (!res.ok) return `Agent error: ${res.status}`
  const data = await res.json()
  return data.result ?? 'No result'
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
    const ts      = params.get('message_ts') ?? undefined

    if (!task) {
      return new Response(JSON.stringify({
        response_type: 'ephemeral',
        text: 'Usage: `/aegis <task>` — e.g. `/aegis how many purchases today?`',
      }), { headers: { 'Content-Type': 'application/json' } })
    }

    // Acknowledge immediately (Slack requires <3s response)
    const ackResponse = new Response(JSON.stringify({
      response_type: 'in_channel',
      text: `_Running: "${task}"..._`,
    }), { headers: { 'Content-Type': 'application/json' } })

    // Run agent in background and post result
    ;(async () => {
      try {
        const result = await runAgent(task, `Requested by @${user} in Slack`)
        await slackReply(channel, `*AEGIS-Ω:* ${result}`, ts)
      } catch (e) {
        await slackReply(channel, `Agent error: ${(e as Error).message}`, ts)
      }
    })()

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
      const text    = (event.event.text ?? '').replace(/<@[A-Z0-9]+>/g, '').trim()
      const channel = event.event.channel
      const ts      = event.event.ts

      if (text) {
        ;(async () => {
          try {
            await slackReply(channel, `_On it: "${text}"..._`, ts)
            const result = await runAgent(text, 'Requested via @AEGIS-Ω mention in Slack')
            await slackReply(channel, `*AEGIS-Ω:* ${result}`, ts)
          } catch (e) {
            await slackReply(channel, `Error: ${(e as Error).message}`, ts)
          }
        })()
      }

      return new Response('ok', { status: 200 })
    }
  }

  return new Response('ok', { status: 200 })
})
