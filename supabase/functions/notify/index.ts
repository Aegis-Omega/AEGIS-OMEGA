// AEGIS-Ω notification hub — email (Resend) + Slack from one endpoint
// Deploy: supabase functions deploy notify --no-verify-jwt
// Env vars: RESEND_API_KEY, SLACK_WEBHOOK_URL, NOTIFY_EMAIL (default: info@aegisomega.com)
// Called internally by ls-webhook, agent, and any other function.
// Auth: pass internal secret via X-Notify-Secret header (set NOTIFY_SECRET env var)
import { CORS } from '../_shared/cors.ts'

const RESEND_API_KEY    = Deno.env.get('RESEND_API_KEY') ?? ''
const SLACK_WEBHOOK_URL = Deno.env.get('SLACK_WEBHOOK_URL') ?? ''
const NOTIFY_EMAIL      = Deno.env.get('NOTIFY_EMAIL') ?? 'info@aegisomega.com'
const NOTIFY_SECRET     = Deno.env.get('NOTIFY_SECRET') ?? ''

interface NotifyPayload {
  channel: 'email' | 'slack' | 'both'
  subject?: string   // email subject
  text: string       // plain text body (used for Slack, fallback for email)
  html?: string      // optional rich email body
}

async function sendEmail(subject: string, text: string, html?: string): Promise<void> {
  if (!RESEND_API_KEY) { console.warn('RESEND_API_KEY not set — skipping email'); return }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: `AEGIS-Ω <agents@aegisomega.com>`,
      to:   [NOTIFY_EMAIL],
      subject,
      text,
      html: html ?? `<pre style="font-family:monospace">${text}</pre>`,
    }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`Resend error ${res.status}: ${err}`)
  }
}

async function sendSlack(text: string): Promise<void> {
  if (!SLACK_WEBHOOK_URL) { console.warn('SLACK_WEBHOOK_URL not set — skipping Slack'); return }
  const res = await fetch(SLACK_WEBHOOK_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error(`Slack error ${res.status}`)
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: CORS })
  }

  // Internal auth check
  const secret = req.headers.get('x-notify-secret') ?? ''
  if (NOTIFY_SECRET && secret !== NOTIFY_SECRET) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401, headers: CORS })
  }

  const payload = await req.json() as NotifyPayload
  const { channel, subject, text, html } = payload

  if (!text) {
    return new Response(JSON.stringify({ error: 'text is required' }), { status: 400, headers: CORS })
  }

  const results: Record<string, string> = {}

  try {
    if (channel === 'email' || channel === 'both') {
      await sendEmail(subject ?? 'AEGIS-Ω notification', text, html)
      results.email = 'sent'
    }
  } catch (e) {
    results.email = `failed: ${(e as Error).message}`
    console.error('Email failed:', e)
  }

  try {
    if (channel === 'slack' || channel === 'both') {
      await sendSlack(text)
      results.slack = 'sent'
    }
  } catch (e) {
    results.slack = `failed: ${(e as Error).message}`
    console.error('Slack failed:', e)
  }

  return new Response(JSON.stringify({ ok: true, results }), {
    headers: { ...CORS, 'Content-Type': 'application/json' },
  })
})
