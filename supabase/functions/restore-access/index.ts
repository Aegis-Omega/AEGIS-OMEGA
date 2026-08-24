// Email → purchase lookup → grant token delivered to the mailbox on file.
//
// The token is never returned in the response. Knowing an address is not the
// same as controlling it, so the grant goes to the address itself and the reply
// is identical whether or not a purchase exists. That closes two holes at once:
// anyone could mint a 365-day entitlement by guessing a customer's email, and
// the old {found: true|false} reply enumerated who had bought and at what tier.
//
// Deploy: supabase functions deploy restore-access --no-verify-jwt
// Env vars: GRANT_PRIVATE_KEY_JWK, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
//           RESEND_API_KEY
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'
import { issueGrantToken } from '../_shared/jwt.ts'

const PLAN_RANK: Record<string, number> = { single: 1, starter: 2, full: 3 }
const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY') ?? ''

/** Same shape as the reply for an address with no purchase. */
function accepted(): Response {
  return new Response(
    JSON.stringify({ ok: true, message: 'If that address has a purchase, its access link is on the way.' }),
    { headers: { ...CORS, 'Content-Type': 'application/json' } },
  )
}

async function mailGrant(email: string, plan: string, token: string): Promise<void> {
  if (!RESEND_API_KEY) {
    console.error('RESEND_API_KEY not set — grant not delivered')
    return
  }
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: 'AEGIS Omega <api@aegisomega.com>',
      to: [email],
      subject: 'Your AEGIS access token',
      html: `<div style="font-family:monospace;max-width:600px;margin:0 auto;padding:24px">`
        + `<h2>Your AEGIS access token</h2>`
        + `<p>Plan: <strong>${plan}</strong></p>`
        + `<div style="background:#0f0f0f;color:#00ff88;padding:16px;border-radius:8px;`
        + `font-size:14px;word-break:break-all">${token}</div>`
        + `<p style="color:#666;font-size:12px">If you did not request this, ignore it — `
        + `nothing changed on your account.</p></div>`,
    }),
  })
  if (!res.ok) console.error('Resend failed:', await res.text())
}

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
    return accepted()
  }

  if (!email || !email.includes('@')) return accepted()

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL') ?? '',
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
  )

  const { data, error } = await supabase
    .from('purchases')
    .select('plan')
    .eq('customer_email', email.toLowerCase().trim())

  if (error) console.error('DB lookup failed:', error)

  if (!error && data?.length) {
    const bestPlan = data.reduce((best, row) => {
      return (PLAN_RANK[row.plan] ?? 0) > (PLAN_RANK[best] ?? 0) ? row.plan : best
    }, 'single')
    await mailGrant(email.toLowerCase().trim(), bestPlan, await issueGrantToken(bestPlan))
  }

  // Identical reply on every path — no purchase, DB error, or token mailed.
  return accepted()
})
