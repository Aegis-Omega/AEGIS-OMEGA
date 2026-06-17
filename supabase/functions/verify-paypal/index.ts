// AEGIS-Ω PayPal order capture + API key provisioning
// Deploy: supabase functions deploy verify-paypal --no-verify-jwt
// Required secrets (supabase secrets set ...):
//   PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MODE (sandbox|live)
//   SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY auto-injected by Supabase
//   NOTIFY_SECRET (optional, for owner alerts)
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

const PAYPAL_CLIENT_ID     = Deno.env.get('PAYPAL_CLIENT_ID') ?? ''
const PAYPAL_CLIENT_SECRET = Deno.env.get('PAYPAL_CLIENT_SECRET') ?? ''
const PAYPAL_MODE          = Deno.env.get('PAYPAL_MODE') ?? 'sandbox'
const RESEND_API_KEY       = Deno.env.get('RESEND_API_KEY') ?? ''
const PAYPAL_BASE          = PAYPAL_MODE === 'live'
  ? 'https://api-m.paypal.com'
  : 'https://api-m.sandbox.paypal.com'

// Canonical prices (USD). Any captured amount below floor → reject.
const TIER_MIN_USD: Record<string, number> = {
  operator:  48.00,  // allow $1 tolerance for currency rounding
  sovereign: 498.00,
}

// Free tier: max 1 active key per email, max 100 new keys per day globally
const EXPLORER_PER_EMAIL_LIMIT  = 1
const EXPLORER_GLOBAL_DAILY_CAP = 100

async function getPayPalToken(): Promise<string> {
  const creds = btoa(`${PAYPAL_CLIENT_ID}:${PAYPAL_CLIENT_SECRET}`)
  const resp = await fetch(`${PAYPAL_BASE}/v1/oauth2/token`, {
    method:  'POST',
    headers: { 'Authorization': `Basic ${creds}`, 'Content-Type': 'application/x-www-form-urlencoded' },
    body:    'grant_type=client_credentials',
  })
  const data = await resp.json()
  if (!resp.ok) throw new Error(`PayPal auth: ${JSON.stringify(data)}`)
  return data.access_token as string
}

interface CaptureResult { status: string; capturedUSD: number }

async function sendApiKey(email: string, tier: string, rawKey: string): Promise<void> {
  if (!RESEND_API_KEY) return
  const limits: Record<string, string> = { explorer: '10', operator: '500', sovereign: 'unlimited' }
  const prices: Record<string, string> = { explorer: 'free', operator: '$49', sovereign: '$499' }
  const body = {
    from: 'AEGIS Omega <api@aegisomega.com>',
    to: [email],
    subject: `Your AEGIS API key — ${tier} tier`,
    html: `<div style="font-family:monospace;max-width:600px;margin:0 auto;padding:24px"><h2>Your AEGIS Platform API Key</h2><p>Tier: <strong>${tier}</strong> (${prices[tier] ?? ''})<br>Call limit: <strong>${limits[tier] ?? '?'} requests</strong></p><div style="background:#0f0f0f;color:#00ff88;padding:16px;border-radius:8px;font-size:14px;word-break:break-all">${rawKey}</div><p style="margin-top:16px">Use as HTTP header:<br><code>x-api-key: ${rawKey}</code></p><pre style="background:#1a1a1a;padding:12px;border-radius:6px;font-size:12px">curl -X POST https://aegis-vertex.aegisomega.com/platform/collaborate -H "x-api-key: ${rawKey}" -H "Content-Type: application/json" -d '{"objective":"Analyse our Q2 revenue","mode":"analysis","live":false}'</pre><p style="color:#666;font-size:12px">Docs: <a href="https://aegisomega.com/platform">aegisomega.com/platform</a><br>Support: api@aegisomega.com</p></div>`,
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) console.error('Resend failed:', await res.text())
}

async function captureOrder(token: string, orderId: string): Promise<CaptureResult> {
  const resp = await fetch(`${PAYPAL_BASE}/v2/checkout/orders/${orderId}/capture`, {
    method:  'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  const data = await resp.json()
  if (!resp.ok) throw new Error(`PayPal capture: ${JSON.stringify(data)}`)
  // Extract captured amount from the first purchase unit → first capture
  const capturedUSD = parseFloat(
    // deno-lint-ignore no-explicit-any
    (data as any)?.purchase_units?.[0]?.payments?.captures?.[0]?.amount?.value ?? '0'
  )
  return { status: data.status as string, capturedUSD }
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST')    return new Response('Method Not Allowed', { status: 405 })

  let body: { order_id?: string; tier?: string; email?: string }
  try { body = await req.json() }
  catch { return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400, headers: CORS }) }

  const tierNorm  = (body.tier  ?? '').toLowerCase().trim()
  const emailNorm = (body.email ?? '').toLowerCase().trim()

  if (!['explorer', 'operator', 'sovereign'].includes(tierNorm))
    return new Response(JSON.stringify({ error: 'Invalid tier' }), { status: 400, headers: CORS })
  if (!emailNorm || !emailNorm.includes('@'))
    return new Response(JSON.stringify({ error: 'Valid email required' }), { status: 400, headers: CORS })

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  // Explorer rate limiting: per-email dedup + global daily cap
  if (tierNorm === 'explorer') {
    const { count: emailCount, error: emailErr } = await supabase
      .from('api_key_store')
      .select('id', { count: 'exact', head: true })
      .eq('customer_email', emailNorm)
      .eq('tier', 'explorer')
      .eq('revoked', false)

    if (emailErr) {
      console.error('Rate-limit check failed:', emailErr)
      return new Response(JSON.stringify({ error: 'Rate-limit check failed' }), { status: 500, headers: CORS })
    }
    if ((emailCount ?? 0) >= EXPLORER_PER_EMAIL_LIMIT)
      return new Response(
        JSON.stringify({ error: 'You already have an active Explorer key. Upgrade to Operator or Sovereign for more runs.' }),
        { status: 429, headers: CORS },
      )

    const oneDayAgo = new Date(Date.now() - 86_400_000).toISOString()
    const { count: dailyCount, error: dailyErr } = await supabase
      .from('api_key_store')
      .select('id', { count: 'exact', head: true })
      .eq('tier', 'explorer')
      .gte('created_at', oneDayAgo)

    if (dailyErr) {
      console.error('Daily cap check failed:', dailyErr)
      return new Response(JSON.stringify({ error: 'Rate-limit check failed' }), { status: 500, headers: CORS })
    }
    if ((dailyCount ?? 0) >= EXPLORER_GLOBAL_DAILY_CAP)
      return new Response(
        JSON.stringify({ error: 'Free tier is at daily capacity. Try again tomorrow or upgrade.' }),
        { status: 429, headers: CORS },
      )
  }

  // Paid tiers: capture PayPal order + verify amount matches tier price
  if (tierNorm !== 'explorer') {
    const orderId = (body.order_id ?? '').trim()
    if (!orderId)
      return new Response(JSON.stringify({ error: 'order_id required for paid tiers' }), { status: 400, headers: CORS })
    if (!PAYPAL_CLIENT_ID || !PAYPAL_CLIENT_SECRET)
      return new Response(JSON.stringify({ error: 'PayPal not configured' }), { status: 503, headers: CORS })

    try {
      const ppToken = await getPayPalToken()
      const { status, capturedUSD } = await captureOrder(ppToken, orderId)
      if (status !== 'COMPLETED')
        return new Response(JSON.stringify({ error: `Order not completed (status: ${status})` }), { status: 402, headers: CORS })

      const minUSD = TIER_MIN_USD[tierNorm] ?? 0
      if (capturedUSD < minUSD)
        return new Response(
          JSON.stringify({ error: `Payment amount $${capturedUSD.toFixed(2)} below minimum $${minUSD.toFixed(2)} for ${tierNorm} tier` }),
          { status: 402, headers: CORS },
        )
    } catch (e) {
      console.error('PayPal capture error:', e)
      return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: CORS })
    }
  }

  // Provision API key via SQL function (security definer, runs with elevated privileges)
  const { data, error } = await supabase.rpc('provision_platform_key', {
    p_customer_email: emailNorm,
    p_tier:           tierNorm,
  })
  if (error) {
    console.error('Provision error:', error)
    return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: CORS })
  }

  const rawKey = data as string

  // Email key to customer — fire and forget (graceful if RESEND_API_KEY unset)
  sendApiKey(emailNorm, tierNorm, rawKey).catch(e => console.error('sendApiKey failed:', e))

  // Notify owner — fire and forget
  const notifyUrl    = `${Deno.env.get('SUPABASE_URL')}/functions/v1/notify`
  const notifySecret = Deno.env.get('NOTIFY_SECRET') ?? ''
  const tierLabel    = { explorer: 'Explorer (free)', operator: 'Operator ($49)', sovereign: 'Sovereign ($499)' }
  fetch(notifyUrl, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'x-notify-secret': notifySecret },
    body:    JSON.stringify({
      channel: 'both',
      subject: `🔑 New AEGIS API key — ${tierLabel[tierNorm as keyof typeof tierLabel]}`,
      text:    `New API key provisioned!\n\nCustomer: ${emailNorm}\nTier: ${tierNorm}\nKey prefix: ${rawKey.slice(0, 14)}...\n\nhttps://aegisomega.com`,
    }),
  }).catch(e => console.error('Notify failed (non-fatal):', e))

  return new Response(
    JSON.stringify({ api_key: rawKey, tier: tierNorm }),
    { headers: { ...CORS, 'Content-Type': 'application/json' } },
  )
})
