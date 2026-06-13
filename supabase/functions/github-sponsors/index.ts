// AEGIS-Ω GitHub Sponsors webhook + claim handler
// Deploy: supabase functions deploy github-sponsors --no-verify-jwt
//
// GitHub: Settings → Webhooks → add webhook
//   Payload URL: https://rwehltdwpsncnwxzkwik.supabase.co/functions/v1/github-sponsors
//   Content-type: application/json
//   Events: Sponsorships
//   Secret: set to value of GITHUB_WEBHOOK_SECRET
//
// Routes:
//   POST /               → GitHub webhook (store sponsorship events)
//   POST /claim          → Sponsor claims API key { github_username, email }
//
// Required secrets:
//   GITHUB_WEBHOOK_SECRET — webhook signing secret from GitHub settings
//   RESEND_API_KEY        — key delivery email
//   SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY auto-injected
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

const GITHUB_WEBHOOK_SECRET = Deno.env.get('GITHUB_WEBHOOK_SECRET') ?? ''
const RESEND_API_KEY         = Deno.env.get('RESEND_API_KEY') ?? ''

function dollarsTotier(monthly: number): string {
  if (monthly >= 499) return 'sovereign'
  if (monthly >= 49)  return 'operator'
  return 'explorer'
}

async function verifyGitHubSignature(body: string, sig: string, secret: string): Promise<boolean> {
  if (!sig.startsWith('sha256=')) return false
  const expected = sig.slice(7)
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  )
  const buf = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(body))
  const computed = Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0')).join('')
  if (computed.length !== expected.length) return false
  let diff = 0
  for (let i = 0; i < computed.length; i++) diff |= computed.charCodeAt(i) ^ expected.charCodeAt(i)
  return diff === 0
}

async function sendApiKey(email: string, tier: string, rawKey: string, githubUsername: string): Promise<void> {
  if (!RESEND_API_KEY) return
  const limits: Record<string, string> = { explorer: '10', operator: '500', sovereign: 'unlimited' }
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from:    'AEGIS Omega <api@aegisomega.com>',
      to:      [email],
      subject: `Your AEGIS API key — ${tier} tier (GitHub Sponsors)`,
      html: `<div style="font-family:monospace;max-width:600px;margin:0 auto;padding:24px">
<h2 style="color:#6366f1">Your AEGIS Platform API Key</h2>
<p>Thanks for sponsoring on GitHub, <strong>@${githubUsername}</strong>!</p>
<p>Tier: <strong>${tier}</strong> · Limit: <strong>${limits[tier] ?? '?'} requests</strong></p>
<div style="background:#0f0f0f;color:#00ff88;padding:16px;border-radius:8px;font-size:14px;word-break:break-all;margin:12px 0">${rawKey}</div>
<p>Use as HTTP header: <code>x-api-key: ${rawKey}</code></p>
<pre style="background:#1a1a1a;color:#ccc;padding:12px;border-radius:6px;font-size:12px;overflow-x:auto">curl -X POST https://aegis-vertex.aegisomega.com/platform/collaborate \\
  -H "x-api-key: ${rawKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"objective":"Review our roadmap","mode":"analysis","live":false}'</pre>
<p style="color:#666;font-size:12px">Support: <a href="mailto:api@aegisomega.com">api@aegisomega.com</a></p>
</div>`,
    }),
  }).then(async r => { if (!r.ok) console.error('Resend failed:', await r.text()) })
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })

  const url  = new URL(req.url)
  const isClaim = url.pathname.endsWith('/claim')

  // ── Claim route ─────────────────────────────────────────────────────────────
  if (isClaim && req.method === 'POST') {
    let body: { github_username?: string; email?: string }
    try { body = await req.json() }
    catch { return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: CORS }) }

    const username = (body.github_username ?? '').toLowerCase().trim()
    const email    = (body.email ?? '').toLowerCase().trim()

    if (!username) return new Response(JSON.stringify({ error: 'github_username required' }), { status: 400, headers: CORS })
    if (!email || !email.includes('@')) return new Response(JSON.stringify({ error: 'Valid email required' }), { status: 400, headers: CORS })

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
    )

    // Check sponsorship exists and is active
    const { data: sponsor, error: lookupErr } = await supabase
      .from('github_sponsors')
      .select('aegis_tier, active, claimed_email')
      .eq('github_username', username)
      .single()

    if (lookupErr || !sponsor)
      return new Response(JSON.stringify({ error: 'No active sponsorship found for @' + username }), { status: 404, headers: CORS })

    if (!sponsor.active)
      return new Response(JSON.stringify({ error: 'Sponsorship is no longer active' }), { status: 403, headers: CORS })

    if (sponsor.claimed_email && sponsor.claimed_email !== email)
      return new Response(
        JSON.stringify({ error: 'This sponsorship was already claimed with a different email. Contact api@aegisomega.com.' }),
        { status: 409, headers: CORS },
      )

    // Provision key
    const { data: rawKey, error: provErr } = await supabase.rpc('provision_platform_key', {
      p_customer_email: email,
      p_tier:           sponsor.aegis_tier,
    })
    if (provErr) {
      console.error('Provision error:', provErr)
      return new Response(JSON.stringify({ error: provErr.message }), { status: 500, headers: CORS })
    }

    // Mark as claimed
    await supabase.from('github_sponsors').update({
      claimed_email: email,
      claimed_at: new Date().toISOString(),
    }).eq('github_username', username)

    sendApiKey(email, sponsor.aegis_tier, rawKey as string, username)
      .catch(e => console.error('sendApiKey failed:', e))

    return new Response(
      JSON.stringify({ api_key: rawKey, tier: sponsor.aegis_tier }),
      { headers: { ...CORS, 'Content-Type': 'application/json' } },
    )
  }

  // ── Webhook route ────────────────────────────────────────────────────────────
  if (req.method !== 'POST')
    return new Response('Method Not Allowed', { status: 405 })

  const rawBody = await req.text()
  const sig     = req.headers.get('x-hub-signature-256') ?? ''
  const event   = req.headers.get('x-github-event') ?? ''

  if (!GITHUB_WEBHOOK_SECRET) {
    console.error('GITHUB_WEBHOOK_SECRET not configured — rejecting all webhook requests')
    return new Response(JSON.stringify({ error: 'Webhook secret not configured' }), { status: 500 })
  }
  const valid = await verifyGitHubSignature(rawBody, sig, GITHUB_WEBHOOK_SECRET)
  if (!valid) {
    console.error('GitHub signature verification failed')
    return new Response(JSON.stringify({ error: 'Invalid signature' }), { status: 400 })
  }

  // deno-lint-ignore no-explicit-any
  let payload: any
  try   { payload = JSON.parse(rawBody) }
  catch { return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400 }) }

  if (event !== 'sponsorship')
    return new Response(JSON.stringify({ received: true }), { status: 200 })

  const action   = payload.action as string
  const username = (payload.sponsorship?.sponsor?.login ?? '').toLowerCase()
  const dollars  = payload.sponsorship?.tier?.monthly_price_in_dollars as number ?? 0

  if (!username) return new Response(JSON.stringify({ error: 'No username' }), { status: 422 })

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  if (action === 'created' || action === 'tier_changed') {
    const aegisTier = dollarsTotier(dollars)
    await supabase.from('github_sponsors').upsert({
      github_username: username,
      tier_dollars:    dollars,
      aegis_tier:      aegisTier,
      active:          true,
      updated_at:      new Date().toISOString(),
    }, { onConflict: 'github_username' })
    console.log(`Sponsor upserted: @${username} $${dollars}/mo → ${aegisTier}`)

    // Notify owner
    const notifyUrl = `${Deno.env.get('SUPABASE_URL')}/functions/v1/notify`
    fetch(notifyUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-notify-secret': Deno.env.get('NOTIFY_SECRET') ?? '' },
      body: JSON.stringify({
        channel: 'both',
        subject: `⭐ New GitHub Sponsor — @${username} ($${dollars}/mo)`,
        text: `New sponsor!\n\n@${username} — $${dollars}/month → ${aegisTier} tier\n\nThey claim their key at https://aegisomega.com/claim-sponsor`,
      }),
    }).catch(() => {})
  } else if (action === 'cancelled' || action === 'pending_cancellation') {
    await supabase.from('github_sponsors')
      .update({ active: false, updated_at: new Date().toISOString() })
      .eq('github_username', username)
    console.log(`Sponsor deactivated: @${username}`)
  }

  return new Response(JSON.stringify({ received: true }), { status: 200 })
})
