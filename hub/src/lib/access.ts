const GRANT_SECRET = (import.meta as any).env?.VITE_GRANT_SECRET ?? 'aegis-omega-v1'

export type Plan = 'single' | 'starter' | 'full'

export interface GrantPayload {
  plan: Plan
  tools: string[]
  grantedAt: number
  exp: number
  sig: string
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
