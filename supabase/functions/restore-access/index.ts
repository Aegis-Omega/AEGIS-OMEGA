// Email → purchase lookup → server-issued grant token
// Deploy: supabase functions deploy restore-access --no-verify-jwt
// Env vars: GRANT_PRIVATE_KEY_JWK, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'
import { issueGrantToken } from '../_shared/jwt.ts'

const PLAN_RANK: Record<string, number> = { single: 1, starter: 2, full: 3 }

// In-memory rate limit: max 5 lookups per IP per 15 minutes
const RATE_WINDOW_MS = 15 * 60 * 1000
const RATE_LIMIT     = 5
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

  let email: string | undefined
  try {
    const body = await req.json() as { email?: string }
    email = body.email
  } catch {
    return new Response(JSON.stringify({ found: false }), { headers: { ...CORS, 'Content-Type': 'application/json' } })
  }

  if (!email || !email.includes('@')) {
    return new Response(JSON.stringify({ found: false }), { headers: { ...CORS, 'Content-Type': 'application/json' } })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  const { data, error } = await supabase
    .from('purchases')
    .select('plan')
    .eq('customer_email', email.toLowerCase().trim())

  if (error || !data?.length) {
    return new Response(JSON.stringify({ found: false }), { headers: { ...CORS, 'Content-Type': 'application/json' } })
  }

  const bestPlan = data.reduce((best, row) => {
    return (PLAN_RANK[row.plan] ?? 0) > (PLAN_RANK[best] ?? 0) ? row.plan : best
  }, 'single')

  const aegis_token = await issueGrantToken(bestPlan)

  return new Response(
    JSON.stringify({ found: true, aegis_token }),
    { headers: { ...CORS, 'Content-Type': 'application/json' } },
  )
})
