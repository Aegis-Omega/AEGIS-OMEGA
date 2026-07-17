// Deploy with --no-verify-jwt. This is the only ingress for billing provider
// webhooks; it verifies the raw payload before inserting an immutable event.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const stripeSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET') ?? ''
const githubSecret = Deno.env.get('GITHUB_WEBHOOK_SECRET') ?? ''

async function hmac(secret: string, value: string): Promise<string> {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(value)))).map(x => x.toString(16).padStart(2, '0')).join('')
}
function equal(a: string, b: string) { if (a.length !== b.length) return false; let diff = 0; for (let i=0;i<a.length;i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i); return diff === 0 }
async function verifiedStripe(raw: string, header: string) {
  const fields = Object.fromEntries(header.split(',').map(x => x.split('=', 2)))
  const age = Math.abs(Math.floor(Date.now()/1000) - Number(fields.t))
  return !!(stripeSecret && fields.t && fields.v1 && age <= 300 && equal(await hmac(stripeSecret, `${fields.t}.${raw}`), fields.v1))
}
function stripeState(type: string, object: Record<string, unknown>) {
  const subscription = (object.subscription as string | undefined) ?? (object.id as string)
  const statusByEvent: Record<string, string> = {
    'customer.subscription.created': String(object.status ?? 'active'), 'customer.subscription.updated': String(object.status ?? 'active'),
    'customer.subscription.deleted': 'canceled', 'invoice.payment_failed': 'past_due', 'invoice.payment_succeeded': 'active',
    'charge.refunded': 'refunded', 'charge.dispute.created': 'disputed', 'customer.subscription.trial_will_end': 'expired',
  }
  const price = (object.items as { data?: Array<{ price?: { id?: string, metadata?: { plan_id?: string } } }> } | undefined)?.data?.[0]?.price
  const plan = price?.metadata?.plan_id ?? (price?.id === Deno.env.get('STRIPE_SELF_SERVE_PRICE_ID') ? 'self_serve' : 'enterprise')
  return { subscription, status: statusByEvent[type], plan, email: ((object.customer_email as string | undefined) ?? (object.customer as string | undefined) ?? ''),
    start: object.current_period_start ? new Date(Number(object.current_period_start)*1000).toISOString() : null,
    end: object.current_period_end ? new Date(Number(object.current_period_end)*1000).toISOString() : null,
    cancel: Boolean(object.cancel_at_period_end) }
}

Deno.serve(async req => {
  if (req.method !== 'POST') return new Response('Method Not Allowed', { status: 405 })
  const provider = new URL(req.url).searchParams.get('provider') ?? 'stripe'
  if (provider !== 'stripe' && provider !== 'github_sponsors') return new Response('Unsupported billing provider', { status: 400 })
  const raw = await req.text()
  const ok = provider === 'stripe'
    ? await verifiedStripe(raw, req.headers.get('stripe-signature') ?? '')
    : !!(githubSecret && equal(await hmac(githubSecret, raw), (req.headers.get('x-hub-signature-256') ?? '').replace(/^sha256=/, '')))
  if (!ok) return new Response(JSON.stringify({ error: 'invalid signature' }), { status: 400 })
  let event: Record<string, unknown>; try { event = JSON.parse(raw) } catch { return new Response('Invalid JSON', { status: 400 }) }
  const eventId = String(event.id ?? req.headers.get('x-github-delivery') ?? '')
  if (!eventId) return new Response('Missing provider event id', { status: 422 })
  if (provider === 'github_sponsors' && req.headers.get('x-github-event') !== 'sponsorship') return new Response(JSON.stringify({ received: true }))
  if (provider === 'github_sponsors' && !['created', 'tier_changed', 'cancelled', 'pending_cancellation'].includes(String(event.action))) return new Response(JSON.stringify({ received: true, ignored: true }))
  const object = provider === 'stripe' ? ((event.data as { object?: Record<string, unknown> }).object ?? {}) : event
  const state = stripeState(String(event.type), object)
  // GitHub sponsorships only map to recurring active/canceled entitlement states.
  if (provider === 'github_sponsors') { state.subscription = String((event.sponsorship as { sponsor?: { login?: string } } | undefined)?.sponsor?.login ?? ''); state.status = ['cancelled','pending_cancellation'].includes(String(event.action)) ? 'canceled' : 'active'; state.plan = 'self_serve' }
  if (!state.subscription || !state.status) return new Response(JSON.stringify({ received: true, ignored: true }))
  const db = createClient(Deno.env.get('SUPABASE_URL') ?? '', Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '')
  const created = Number(event.created ?? 0)
  const { data, error } = await db.rpc('ingest_billing_event', { p_provider: provider, p_event_id: eventId, p_event_type: String(event.type ?? event.action), p_payload: event, p_subscription_id: state.subscription, p_customer_email: state.email, p_plan_id: state.plan, p_status: state.status, p_effective_at: created > 0 ? new Date(created * 1000).toISOString() : new Date().toISOString(), p_period_start: state.start, p_period_end: state.end, p_cancel_at_period_end: state.cancel })
  if (error) return new Response(JSON.stringify({ error: error.message }), { status: 500 })
  return new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } })
})
