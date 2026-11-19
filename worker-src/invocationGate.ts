/**
 * AEGIS Ω paid invocation admission: fail-closed, atomic quota reservation.
 * No claims of authentication or quota apply to unrelated anonymous research endpoints.
 * Runs BEFORE any provider call and never logs, persists, or returns the raw key.
 */

export interface InvocationGateEnv {
  SUPABASE_URL?: string
  SUPABASE_SERVICE_ROLE_KEY?: string
}

export type AdmissionResult =
  | { admitted: true }
  | { admitted: false; status: 401 | 403 | 503; code: string }

export const ALLOWED_PAID_ORIGINS = new Set([
  'https://aegisomega.com',
  'https://www.aegisomega.com',
])

/** Browser origin isn't authentication: it merely limits cross-origin access. */
export function paidOriginAllowed(origin: string | null): boolean {
  return origin === null || ALLOWED_PAID_ORIGINS.has(origin)
}

export function paidCors(origin: string | null): Record<string, string> {
  const result: Record<string, string> = {
    'Vary': 'Origin',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
    'Access-Control-Max-Age': '600',
  }
  if (origin && ALLOWED_PAID_ORIGINS.has(origin)) {
    result['Access-Control-Allow-Origin'] = origin
  }
  return result
}

function validServiceUrl(value: string | undefined): URL | null {
  if (!value) return null
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) return null
    return url
  } catch { return null }
}

/** Atomic admission relies on SQL RPC in the matching migration. */
export async function reservePaidInvocation(
  request: Request,
  env: InvocationGateEnv,
  fetcher: typeof fetch = fetch,
): Promise<AdmissionResult> {
  const rawKey = request.headers.get('x-api-key') || ''
  if (!/^aegis_[A-Za-z0-9_-]{16,128}$/.test(rawKey)) {
    return { admitted: false, status: 401, code: 'API_KEY_REQUIRED' }
  }
  const url = validServiceUrl(env.SUPABASE_URL)
  const serviceKey = env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !serviceKey) {
    return { admitted: false, status: 503, code: 'AUTH_BACKEND_UNAVAILABLE' }
  }
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(rawKey))
  const hex = Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join('')
  const endpoint = new URL('/rest/v1/rpc/reserve_aegis_edge_collaboration', url)
  try {
    const response = await fetcher(endpoint.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': serviceKey,
        'Authorization': `Bearer ${serviceKey}`,
      },
      body: JSON.stringify({ p_key_hash: hex }),
      signal: AbortSignal.timeout(3500),
      redirect: 'error',
    })
    if (!response.ok) return { admitted: false, status: 503, code: 'AUTH_BACKEND_UNAVAILABLE' }
    // A strict PostgREST boolean is required; malformed result never admits.
    const admitted: unknown = await response.json()
    if (admitted === true) return { admitted: true }
    if (admitted === false) return { admitted: false, status: 403, code: 'KEY_INVALID_REVOKED_OR_LIMIT_REACHED' }
    return { admitted: false, status: 503, code: 'AUTH_BACKEND_INVALID_RESPONSE' }
  } catch {
    return { admitted: false, status: 503, code: 'AUTH_BACKEND_UNAVAILABLE' }
  }
}