// Lemon Squeezy webhook → purchase record
// Deploy: supabase functions deploy ls-webhook --no-verify-jwt
// Env vars: LS_WEBHOOK_SECRET, LS_PLAN_MAP (JSON variant_id→plan)
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

const LS_WEBHOOK_SECRET = Deno.env.get('LS_WEBHOOK_SECRET') ?? ''
const LS_PLAN_MAP: Record<string, string> = JSON.parse(Deno.env.get('LS_PLAN_MAP') ?? '{}')

async function verifySignature(secret: string, body: string, sig: string): Promise<boolean> {
  const sigBytes = new Uint8Array(sig.match(/.{2}/g)?.map(b => parseInt(b, 16)) ?? [])
  // Reject obviously wrong-length signatures before importing the key
  if (sigBytes.length !== 32) return false
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify'],
  )
  // crypto.subtle.verify is constant-time — prevents timing attacks on the secret
  return crypto.subtle.verify('HMAC', key, sigBytes, new TextEncoder().encode(body))
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

  if (!email) {
    return new Response(JSON.stringify({ error: 'No email in payload' }), { status: 400, headers: CORS })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  const { error } = await supabase.from('purchases').upsert({
    customer_email: email,
    ls_order_id:    orderId,
    ls_variant_id:  variantId,
    ls_product_id:  productId,
    plan,
    updated_at: new Date().toISOString(),
  }, { onConflict: 'ls_order_id' })

  if (error) {
    console.error('DB upsert failed:', error)
    return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: CORS })
  }

  // Notify owner — fire and forget
  const notifyUrl = `${Deno.env.get('SUPABASE_URL')}/functions/v1/notify`
  const notifySecret = Deno.env.get('NOTIFY_SECRET') ?? ''
  const planLabel: Record<string, string> = { single: 'Single tool ($19)', starter: 'Starter 2-pack ($29)', full: 'Full bundle ($39)' }
  fetch(notifyUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-notify-secret': notifySecret },
    body: JSON.stringify({
      channel: 'both',
      subject: `💰 New AEGIS purchase — ${planLabel[plan] ?? plan}`,
      text: `New purchase on AEGIS Omega!\n\nCustomer: ${email}\nPlan: ${planLabel[plan] ?? plan}\nOrder ID: ${orderId}\n\nhttps://aegisomega.com`,
    }),
  }).catch(e => console.error('Notify failed (non-fatal):', e))

  return new Response(JSON.stringify({ ok: true }), { headers: { ...CORS, 'Content-Type': 'application/json' } })
})
