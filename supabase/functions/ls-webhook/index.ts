// Lemon Squeezy webhook → purchase record + API key provisioning
// Deploy: supabase functions deploy ls-webhook --no-verify-jwt
// Env vars:
//   LS_WEBHOOK_SECRET        — from LS dashboard
//   LS_PLAN_MAP              — JSON: variant_id → "single"|"starter"|"full"
//   LS_API_PLAN_MAP          — JSON: variant_id → "explorer"|"operator"|"sovereign"
//   RESEND_API_KEY           — for customer key delivery emails
//   NOTIFY_SECRET            — for internal owner notification
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

const LS_WEBHOOK_SECRET = Deno.env.get('LS_WEBHOOK_SECRET') ?? ''
const LS_PLAN_MAP: Record<string, string> = JSON.parse(Deno.env.get('LS_PLAN_MAP') ?? '{}')
const LS_API_PLAN_MAP: Record<string, string> = JSON.parse(Deno.env.get('LS_API_PLAN_MAP') ?? '{}')
const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY') ?? ''

async function verifySignature(secret: string, body: string, sig: string): Promise<boolean> {
  const sigBytes = new Uint8Array(sig.match(/.{2}/g)?.map(b => parseInt(b, 16)) ?? [])
  if (sigBytes.length !== 32) return false
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify'],
  )
  return crypto.subtle.verify('HMAC', key, sigBytes, new TextEncoder().encode(body))
}

async function sendApiKey(email: string, tier: string, rawKey: string): Promise<void> {
  if (!RESEND_API_KEY) {
    console.warn('RESEND_API_KEY not set — skipping key email')
    return
  }
  const limits: Record<string, string> = { explorer: '10', operator: '500', sovereign: '1,000,000' }
  const prices: Record<string, string> = { explorer: 'free', operator: '$49/mo', sovereign: '$299/mo' }
  const body = {
    from: 'AEGIS Omega <api@aegisomega.com>',
    to: [email],
    subject: `Your AEGIS API key — ${tier} tier`,
    html: `<div style="font-family:monospace;max-width:600px;margin:0 auto;padding:24px"><h2>Your AEGIS Platform API Key</h2><p>Tier: <strong>${tier}</strong> (${prices[tier] ?? ''})<br>Call limit: <strong>${limits[tier] ?? '?'} requests</strong></p><div style="background:#0f0f0f;color:#00ff88;padding:16px;border-radius:8px;font-size:14px;word-break:break-all">${rawKey}</div><p style="margin-top:16px">Use as HTTP header:<br><code>x-api-key: ${rawKey}</code></p><h3>Quick start</h3><pre style="background:#1a1a1a;padding:12px;border-radius:6px;font-size:12px">curl -X POST https://aegis-vertex.aegisomega.com/platform/collaborate -H "x-api-key: ${rawKey}" -H "Content-Type: application/json" -d '{"objective":"Analyse our Q2 revenue","mode":"analysis","live":false}'</pre><p style="color:#666;font-size:12px">Docs: <a href="https://aegisomega.com/platform">aegisomega.com/platform</a><br>Support: api@aegisomega.com</p></div>`,
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) console.error('Resend failed:', await res.text())
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })

  const sig  = req.headers.get('x-signature') ?? ''
  const body = await req.text()

  if (!(await verifySignature(LS_WEBHOOK_SECRET, body, sig))) {
    return new Response(JSON.stringify({ error: 'Invalid signature' }), { status: 401, headers: CORS })
  }

  const event = JSON.parse(body)
  if (event.meta?.event_name !== 'order_created') {
    return new Response(JSON.stringify({ ok: true }), { headers: { ...CORS, 'Content-Type': 'application/json' } })
  }

  const attrs     = event.data?.attributes ?? {}
  const email     = (attrs.user_email ?? '').toLowerCase().trim()
  const orderId   = String(event.data?.id ?? '')
  const variantId = String(attrs.first_order_item?.variant_id ?? '')
  const productId = String(attrs.first_order_item?.product_id ?? '')
  const plan      = LS_PLAN_MAP[variantId] ?? 'single'
  const apiTier   = LS_API_PLAN_MAP[variantId] ?? ''

  if (!email) {
    return new Response(JSON.stringify({ error: 'No email in payload' }), { status: 400, headers: CORS })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  const { error: dbErr } = await supabase.from('purchases').upsert({
    customer_email: email,
    ls_order_id:    orderId,
    ls_variant_id:  variantId,
    ls_product_id:  productId,
    plan,
    updated_at: new Date().toISOString(),
  }, { onConflict: 'ls_order_id' })

  if (dbErr) {
    console.error('DB upsert failed:', dbErr)
    return new Response(JSON.stringify({ error: dbErr.message }), { status: 500, headers: CORS })
  }

  if (apiTier) {
    const { data: rawKey, error: keyErr } = await supabase.rpc('provision_platform_key', {
      p_customer_email: email,
      p_tier: apiTier,
    })
    if (keyErr) {
      console.error('provision_platform_key failed:', keyErr)
    } else if (rawKey) {
      await sendApiKey(email, apiTier, rawKey as string)
    }
  }

  const notifyUrl = `${Deno.env.get('SUPABASE_URL')}/functions/v1/notify`
  const notifySecret = Deno.env.get('NOTIFY_SECRET') ?? ''
  const planLabel: Record<string, string> = {
    single: 'Single tool ($19)', starter: 'Starter 2-pack ($29)', full: 'Full bundle ($39)',
    explorer: 'API Explorer (free)', operator: 'API Operator ($49)', sovereign: 'API Sovereign ($299)',
  }
  fetch(notifyUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-notify-secret': notifySecret },
    body: JSON.stringify({
      channel: 'both',
      subject: `💰 New AEGIS purchase — ${planLabel[apiTier || plan] ?? plan}`,
      text: `New purchase!\n\nCustomer: ${email}\nPlan: ${planLabel[apiTier || plan] ?? plan}\nOrder: ${orderId}\nAPI key issued: ${apiTier ? 'yes' : 'no'}\n\nhttps://aegisomega.com`,
    }),
  }).catch(e => console.error('Notify failed (non-fatal):', e))

  return new Response(JSON.stringify({ ok: true }), { headers: { ...CORS, 'Content-Type': 'application/json' } })
})
