const GRANT_SECRET = (import.meta as any).env?.VITE_GRANT_SECRET ?? 'aegis-omega-v1'

export type Plan = 'single' | 'starter' | 'full'

export interface GrantPayload {
  plan: Plan
  tools: string[]
  grantedAt: number
  exp: number
  sig: string
}

export interface ServerGrantPayload {
  plan: Plan
  tools: string[]
  grantedAt: number
  exp: number
}

// P-256 public key — counterpart to GRANT_PRIVATE_KEY_JWK in Supabase secrets.
// Public keys are safe to embed; replace both if you rotate the key pair.
const GRANT_PUBLIC_JWK = {
  key_ops: ['verify'], ext: true, kty: 'EC', crv: 'P-256',
  x: 'gOiQCOQ9uqrWGjLWtHy-Rz7_iy-upssUQIChM-594mU',
  y: '8xzK_vJumoNMw5ytMaGijU83XbH5Bl81RUrPokuLt-E',
}

// Verify a server-issued token (ECDSA P-256, format: <payloadB64>.<sigB64>)
export async function verifyServerToken(token: string): Promise<ServerGrantPayload | null> {
  try {
    const dot = token.indexOf('.')
    if (dot === -1) return null
    const payloadB64 = token.slice(0, dot)
    const sigB64     = token.slice(dot + 1)
    const key = await crypto.subtle.importKey(
      'jwk', GRANT_PUBLIC_JWK,
      { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify'],
    )
    const sigBytes = Uint8Array.from(atob(sigB64), c => c.charCodeAt(0))
    const valid = await crypto.subtle.verify(
      { name: 'ECDSA', hash: 'SHA-256' }, key, sigBytes,
      new TextEncoder().encode(payloadB64),
    )
    if (!valid) return null
    const payload = JSON.parse(atob(payloadB64)) as ServerGrantPayload
    if (Date.now() > payload.exp) return null
    return payload
  } catch {
    return null
  }
}

function sign(plan: Plan, grantedAt: number): string {
  const str = `${GRANT_SECRET}:${plan}:${grantedAt}`
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(31, h) + str.charCodeAt(i) | 0
  }
  return Math.abs(h).toString(36)
}

const TOOLS: Record<Plan, string[]> = {
  single:  ['platform-picker'],
  starter: ['platform-picker', 'hook-generator'],
  full:    ['platform-picker', 'hook-generator', 'content-calendar'],
}

export function createGrantToken(plan: Plan): string {
  const grantedAt = Date.now()
  const payload: GrantPayload = {
    plan,
    tools: TOOLS[plan],
    grantedAt,
    exp: grantedAt + 365 * 24 * 60 * 60 * 1000,
    sig: sign(plan, grantedAt),
  }
  return btoa(JSON.stringify(payload))
}

export function verifyGrantToken(token: string): GrantPayload | null {
  try {
    const payload = JSON.parse(atob(token)) as GrantPayload
    if (Date.now() > payload.exp) return null
    if (payload.sig !== sign(payload.plan, payload.grantedAt)) return null
    return payload
  } catch {
    return null
  }
}

const STORAGE_KEY = (product: string) => `aegis_access_${product}`

export function getStoredAccess(product: string): GrantPayload | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY(product))
    if (!raw) return null
    const payload = JSON.parse(raw) as GrantPayload
    if (Date.now() > payload.exp) {
      localStorage.removeItem(STORAGE_KEY(product))
      return null
    }
    return payload
  } catch {
    return null
  }
}

export function storeAccess(product: string, payload: GrantPayload): void {
  localStorage.setItem(STORAGE_KEY(product), JSON.stringify(payload))
}

export function hasAccess(product: string): boolean {
  return getStoredAccess(product) !== null
}

// Server token storage — raw ECDSA P-256 token string keyed per product.
// Counterpart to AccessGate's verifyServerToken flow; key matches the
// localStorage.removeItem(`aegis_srv_${product}`) eviction path on expiry.
const SERVER_STORAGE_KEY = (product: string) => `aegis_srv_${product}`

export function storeServerToken(product: string, token: string): void {
  localStorage.setItem(SERVER_STORAGE_KEY(product), token)
}

export function getStoredServerToken(product: string): string | null {
  return localStorage.getItem(SERVER_STORAGE_KEY(product))
}
