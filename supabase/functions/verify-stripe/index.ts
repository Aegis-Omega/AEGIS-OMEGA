// AEGIS-Ω Stripe webhook handler + API key provisioning
// Deploy: supabase functions deploy verify-stripe --no-verify-jwt
// Stripe → Dashboard → Webhooks → add endpoint:
//   URL: https://rwehltdwpsncnwxzkwik.supabase.co/functions/v1/verify-stripe
//   Events: checkout.session.completed
// Required secrets (supabase secrets set ...):
//   STRIPE_WEBHOOK_SECRET — from the Webhooks page (whsec_...)
//   RESEND_API_KEY        — for key delivery email
//   SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY auto-injected
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

const STRIPE_WEBHOOK_SECRET = Deno.env.get('STRIPE_WEBHOOK_SECRET') ?? ''
const RESEND_API_KEY         = Deno.env.get('RESEND_API_KEY') ?? ''

// Fallback tier detection by amount_total (cents) when metadata.tier is absent
const AMOUNT_TO_TIER: Record<number, string> = {
  4900:  'operator',   // $49.00
  49900: 'sovereign',  // $499.00
}

const STRIPE_REPLAY_WINDOW_SECONDS = 300

async function verifyStripeSignature(
  body: string, sig: string, secret: string,
): Promise<boolean> {
  const parts: Record<string, string> = {}
  for (const part of sig.split(',')) {
    const eq = part.indexOf('=')
    if (eq > 0) parts[part.slice(0, eq)] = part.slice(eq + 1)
  }
  const ts = parts['t']
  const v1 = parts['v1']
  if (!ts || !v1) return false

  // Reject replayed webhooks outside the 5-minute window
  const age = Math.floor(Date.now() / 1000) - parseInt(ts, 10)
  if (isNaN(age) || Math.abs(age) > STRIPE_REPLAY_WINDOW_SECONDS) return false

  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false, ['sign'],
  )
  const sigBuf  = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`${ts}.${body}`))
  const computed = Array.from(new Uint8Array(sigBuf))
    .map(b => b.toString(16).padStart(2, '0')).join('')

  if (computed.length !== v1.length) return false
  let diff = 0
  for (let i = 0; i < computed.length; i++) diff |= computed.charCodeAt(i) ^ v1.toLowerCase().charCodeAt(i)
  return diff === 0
}

async function sendApiKey(email: string, tier: string, rawKey: string): Promise<void> {
  if (!RESEND_API_KEY) return
  const limits: Record<string, string> = { operator: '500', sovereign: 'unlimited' }
  const prices: Record<string, string>  = { operator: '$49', sovereign: '$499' }
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from:    'AEGIS Omega <api@aegisomega.com>',
      to:      [email],
      subject: `Your AEGIS API key — ${tier} tier`,
      html: `<div style="font-family:monospace;max-width:600px;margin:0 auto;padding:24px">
<h2 style="color:#6366f1">Your AEGIS Platform API Key</h2>
<p>Tier: <strong>${tier}</strong> (${prices[tier] ?? ''})<br>Call limit: <strong>${limits[tier] ?? '?'} requests</strong></p>
<div style="background:#0f0f0f;color:#00ff88;padding:16px;border-radius:8px;font-size:14px;word-break:break-all;margin:12px 0">${rawKey}</div>
<p>Use as HTTP header: <code>x-api-key: ${rawKey}</code></p>
<pre style="background:#1a1a1a;color:#ccc;padding:12px;border-radius:6px;font-size:12px;overflow-x:auto">curl -X POST https://aegis-vertex.aegisomega.com/platform/collaborate \\
  -H "x-api-key: ${rawKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"objective":"Analyse our Q2 revenue","mode":"analysis","live":false}'</pre>
<p style="color:#666;font-size:12px">Docs: <a href="https://aegisomega.com/platform">aegisomega.com/platform</a> · Support: <a href="mailto:api@aegisomega.com">api@aegisomega.com</a></p>
</div>`,
    }),
  }).then(async r => { if (!r.ok) console.error('Resend failed:', await r.text()) })
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST')    return new Response('Method Not Allowed', { status: 405 })

  const rawBody = await req.text()
  const sig     = req.headers.get('stripe-signature') ?? ''

  if (!STRIPE_WEBHOOK_SECRET) {
    console.error('STRIPE_WEBHOOK_SECRET not configured — rejecting all webhook requests')
    return new Response(JSON.stringify({ error: 'Webhook secret not configured' }), { status: 500 })
  }
  const valid = await verifyStripeSignature(rawBody, sig, STRIPE_WEBHOOK_SECRET)
  if (!valid) {
    console.error('Stripe signature verification failed')
    return new Response(JSON.stringify({ error: 'Invalid signature' }), { status: 400 })
  }

  // deno-lint-ignore no-explicit-any
  let event: any
  try   { event = JSON.parse(rawBody) }
  catch { return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400 }) }

  // Acknowledge immediately; only process checkout completion
  if (event.type !== 'checkout.session.completed') {
    return new Response(JSON.stringify({ received: true }), { status: 200 })
  }

  const session   = event.data.object
  const email     = ((session.customer_details?.email as string) ?? '').toLowerCase().trim()
  const meta      = (session.metadata as Record<string, string>) ?? {}
  const amount    = session.amount_total as number

  const tierNorm  = (meta['tier'] ?? AMOUNT_TO_TIER[amount] ?? '').toLowerCase().trim()

  if (!['operator', 'sovereign'].includes(tierNorm)) {
    console.error(`Unknown tier: amount=${amount} metadata=${JSON.stringify(meta)} session=${session.id}`)
    return new Response(JSON.stringify({ error: 'Cannot determine tier' }), { status: 422 })
  }
  if (!email) {
    console.error('No email in checkout session:', session.id)
    return new Response(JSON.stringify({ error: 'No email' }), { status: 422 })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  const { data, error } = await supabase.rpc('provision_platform_key', {
    p_customer_email: email,
    p_tier:           tierNorm,
  })
  if (error) {
    console.error('Provision error:', error)
    return new Response(JSON.stringify({ error: error.message }), { status: 500 })
  }

  const rawKey = data as string

  sendApiKey(email, tierNorm, rawKey).catch(e => console.error('sendApiKey failed:', e))

  // Notify owner
  const notifyUrl = `${Deno.env.get('SUPABASE_URL')}/functions/v1/notify`
  const tierLabel = { operator: 'Operator ($49)', sovereign: 'Sovereign ($499)' }
  fetch(notifyUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-notify-secret': Deno.env.get('NOTIFY_SECRET') ?? '',
    },
    body: JSON.stringify({
      channel: 'both',
      subject: `🔑 New AEGIS sale — ${tierLabel[tierNorm as keyof typeof tierLabel]}`,
      text:    `New customer!\n\nEmail: ${email}\nTier: ${tierNorm}\nKey prefix: ${rawKey.slice(0, 14)}...\n\nhttps://aegisomega.com`,
    }),
  }).catch(e => console.error('Notify failed (non-fatal):', e))

  return new Response(JSON.stringify({ received: true }), { status: 200 })
})
