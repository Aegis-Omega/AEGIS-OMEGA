// Server-side P-256 ECDSA token issuer
// Required env var: GRANT_PRIVATE_KEY_JWK (set in Supabase project → Edge Functions → Secrets)
// Public key counterpart lives in packages/shared/lib/access.ts — never swap without regenerating both.

const PLAN_TOOLS: Record<string, string[]> = {
  single:  ['platform-picker'],
  starter: ['platform-picker', 'hook-generator'],
  full:    ['platform-picker', 'hook-generator', 'content-calendar'],
}

export async function issueGrantToken(plan: string): Promise<string> {
  const privJwk = JSON.parse(Deno.env.get('GRANT_PRIVATE_KEY_JWK') ?? 'null')
  if (!privJwk) throw new Error('GRANT_PRIVATE_KEY_JWK not configured')

  const key = await crypto.subtle.importKey(
    'jwk',
    privJwk,
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign'],
  )

  const grantedAt = Date.now()
  const payload = {
    plan,
    tools: PLAN_TOOLS[plan] ?? [],
    grantedAt,
    exp: grantedAt + 365 * 24 * 60 * 60 * 1000,
  }

  const payloadB64 = btoa(JSON.stringify(payload))
  const sigBytes = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    key,
    new TextEncoder().encode(payloadB64),
  )
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sigBytes)))
  return `${payloadB64}.${sigB64}`
}
