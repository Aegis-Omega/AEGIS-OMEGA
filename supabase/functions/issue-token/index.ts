// Order-verified token issuer — closes the post-purchase client-side minting gap.
// Deploy: supabase functions deploy issue-token --no-verify-jwt
// Env vars: GRANT_PRIVATE_KEY_JWK, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
//
// LS product redirect URL must be set to:
//   https://aegisomega.com/success?order_id={order_id}
// The {order_id} template variable is replaced by Lemon Squeezy at checkout.
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'
import { issueGrantToken } from '../_shared/jwt.ts'

// 10 requests per IP per 15 minutes — enough for retries, blocks brute-force
const RATE_WINDOW_MS = 15 * 60 * 1000
const RATE_LIMIT     = 10
const ipCounters     = new Map<string, { count: number; reset: number }>()

function checkRateLimit(ip: string): boolean {
  const now   = Date.now()
  const entry = ipCounters.get(ip)
  if (!entry || entry.reset < now) {
    ipCounters.set(ip, { count: 1, reset: now + RATE_WINDOW_MS })
    return true
  }
  if (entry.count >= RATE_LIMIT) return false
  entry.count++
  return true
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: CORS })
  }

  const ip = req.headers.get('x-forwarded-for')?.split(',')[0].trim() ?? 'unknown'
  if (!checkRateLimit(ip)) {
    return new Response(
      JSON.stringify({ error: 'Too many requests — try again later.' }),
      { status: 429, headers: { ...CORS, 'Content-Type': 'application/json' } },
    )
  }

  let order_id: string | undefined
  try {
    const body = await req.json() as { order_id?: string }
    order_id = String(body.order_id ?? '').trim()
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid request body' }), { status: 400, headers: CORS })
  }

  if (!order_id) {
    return new Response(JSON.stringify({ error: 'order_id required' }), { status: 400, headers: CORS })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  const { data, error } = await supabase
    .from('purchases')
    .select('plan')
    .eq('ls_order_id', order_id)
    .maybeSingle()

  if (error) {
    console.error('DB lookup failed:', error)
    return new Response(JSON.stringify({ error: 'DB error' }), { status: 500, headers: CORS })
  }

  if (!data) {
    // 404 means the ls-webhook hasn't delivered yet — client should retry with backoff
    return new Response(
      JSON.stringify({ error: 'Order not found — webhook may still be in transit' }),
      { status: 404, headers: { ...CORS, 'Content-Type': 'application/json' } },
    )
  }

  const aegis_token = await issueGrantToken(data.plan)

  return new Response(
    JSON.stringify({ aegis_token }),
    { headers: { ...CORS, 'Content-Type': 'application/json' } },
  )
})
