// Email → purchase lookup → restore URL pointing to hub/success?plan=X
// Deploy: supabase functions deploy restore-access --no-verify-jwt
// Env vars: HUB_URL (defaults to https://aegisomega.com)
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { CORS } from '../_shared/cors.ts'

const HUB_URL = Deno.env.get('HUB_URL') ?? 'https://aegisomega.com'

// Rank plans so we return the best one the user purchased
const PLAN_RANK: Record<string, number> = { single: 1, starter: 2, full: 3 }

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: CORS })
  }

  const { email } = await req.json() as { email?: string }
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
    .eq('email', email.toLowerCase().trim())

  if (error || !data?.length) {
    return new Response(JSON.stringify({ found: false }), { headers: { ...CORS, 'Content-Type': 'application/json' } })
  }

  // Pick the highest-tier plan the user has purchased
  const bestPlan = data.reduce((best, row) => {
    return (PLAN_RANK[row.plan] ?? 0) > (PLAN_RANK[best] ?? 0) ? row.plan : best
  }, 'single')

  const restoreUrl = `${HUB_URL}/success?plan=${bestPlan}`

  return new Response(
    JSON.stringify({ found: true, restore_url: restoreUrl, plan: bestPlan }),
    { headers: { ...CORS, 'Content-Type': 'application/json' } },
  )
})
