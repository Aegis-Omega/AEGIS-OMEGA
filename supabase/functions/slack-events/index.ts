// TAR-21: signed Slack ingress with scoped, request-bound agent machine identity.
// No Supabase user JWT or NOTIFY_SECRET is used for Slack-to-agent authorization.
import {
  allowedSlackActor, parseSlackPayload, readBoundedBody,
  signSlackAgentRequest, verifySlackSignature,
  type SlackMachineBody,
} from '../_shared/slack-agent-auth.ts'

const SLACK_SIGNING_SECRET = Deno.env.get('SLACK_SIGNING_SECRET') ?? ''
const SLACK_BOT_TOKEN = Deno.env.get('SLACK_BOT_TOKEN') ?? ''
const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? ''
const SLACK_ALLOWED_TEAM_IDS = Deno.env.get('AEGIS_SLACK_ALLOWED_TEAM_IDS') ?? ''
const SLACK_ALLOWED_USER_IDS = Deno.env.get('AEGIS_SLACK_ALLOWED_USER_IDS') ?? ''
const SLACK_ALLOWED_ACTORS = Deno.env.get('AEGIS_SLACK_ALLOWED_ACTORS') ?? ''
const MACHINE_KEY = Deno.env.get('AEGIS_SLACK_AGENT_HMAC_KEY') ?? ''
const MACHINE_KEY_ID = Deno.env.get('AEGIS_SLACK_AGENT_KEY_ID') ?? ''

async function slackReply(channel: string, text: string, threadTs?: string): Promise<void> {
  // Bot key never goes to the agent; the channel and thread come from signed Slack data.
  const response = await fetch('https://slack.com/api/chat.postMessage', {
    method: 'POST',
    headers: { Authorization: `Bearer ${SLACK_BOT_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel, text: text.slice(0, 1400), thread_ts: threadTs }),
    signal: AbortSignal.timeout(10_000),
  })
  if (!response.ok) throw Error('Slack transport failure')
  const data = await response.json().catch(() => null)
  if (!data?.ok) throw Error('Slack delivery failure')
}

async function runAgent(job: SlackMachineBody): Promise<string> {
  // Fail closed if the configured project URL is malformed or points away from Supabase.
  const agentBase = new URL(SUPABASE_URL)
  if (agentBase.protocol !== 'https:' || !agentBase.hostname.endsWith('.supabase.co')
    || agentBase.pathname !== '/') throw Error('agent endpoint unavailable')
  const { rawBody, headers } = await signSlackAgentRequest(job, MACHINE_KEY, MACHINE_KEY_ID)
  const res = await fetch(new URL('/functions/v1/agent', agentBase), {
    method: 'POST', headers, body: rawBody, signal: AbortSignal.timeout(25_000),
  })
  if (!res.ok) return `Agent request denied (${res.status})`
  const data = await res.json()
  return typeof data?.result === 'string' ? data.result.slice(0, 1200) : 'No result'
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('Method not allowed', { status: 405 })
  // No skip-in-dev path; absent settings shut down the endpoint before execution.
  if (!SLACK_SIGNING_SECRET || !SLACK_ALLOWED_TEAM_IDS || !SLACK_ALLOWED_USER_IDS
    || !SLACK_ALLOWED_ACTORS || new TextEncoder().encode(MACHINE_KEY).length < 32
    || !/^[A-Za-z0-9_-]{1,48}$/.test(MACHINE_KEY_ID) || !SUPABASE_URL) {
    return new Response('Gateway unavailable', { status: 503 })
  }
  const raw = await readBoundedBody(req)
  if (raw === null) return new Response('Invalid or oversized body', { status: 413 })
  const timestamp = req.headers.get('x-slack-request-timestamp') ?? ''
  if (!(await verifySlackSignature(raw, timestamp,
    req.headers.get('x-slack-signature') ?? '', SLACK_SIGNING_SECRET))) {
    return new Response('Unauthorized', { status: 401 })
  }
  const parsed = await parseSlackPayload(raw, req.headers.get('content-type') ?? '', timestamp)
  if (!parsed) return new Response('Invalid Slack payload', { status: 400 })
  if (parsed.kind === 'challenge') {
    return Response.json({ challenge: parsed.challenge })
  }
  if (parsed.kind === 'ignore') return new Response('ok')
  const { job } = parsed
  const { team_id, user_id } = job.slack
  if (!allowedSlackActor(team_id, user_id, SLACK_ALLOWED_TEAM_IDS, SLACK_ALLOWED_USER_IDS, SLACK_ALLOWED_ACTORS)) {
    return new Response('Forbidden', { status: 403 })
  }
  // No paid task without a durable background lifetime and an actual reply channel.
  const runtime = (globalThis as { EdgeRuntime?: { waitUntil?: (p: Promise<unknown>) => void } }).EdgeRuntime
  if (!SLACK_BOT_TOKEN || typeof runtime?.waitUntil !== 'function') {
    return new Response('Gateway unavailable', { status: 503 })
  }
  const jobPromise = (async () => {
    try {
      const result = await runAgent({ task: job.task, scope: job.scope, slack: job.slack })
      await slackReply(job.channel, `*AEGIS-Ω:* ${result}`, job.threadTs)
    } catch {
      // Never post or log secrets, upstream content, or stack traces to Slack.
      await slackReply(job.channel, 'AEGIS agent request unavailable.', job.threadTs).catch(() => {})
    }
  })()
  runtime.waitUntil(jobPromise)
  return req.headers.get('content-type')?.includes('application/x-www-form-urlencoded')
    ? Response.json({ response_type: 'ephemeral', text: 'AEGIS request received for authorization.' })
    : new Response('ok', { status: 200 })
})
