export type AccessIdentity = {
  email: string
  jwt: string
}

export class AccessDeniedError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'AccessDeniedError'
  }
}

export function parsePositiveInteger(value: string, fallback: number): number {
  const parsed = Number(value)
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : fallback
}

export function enforceBodyLimit(request: Request, maxBytes: number): void {
  const raw = request.headers.get('content-length')
  if (raw === null) return
  const length = Number(raw)
  if (!Number.isSafeInteger(length) || length < 0 || length > maxBytes) {
    throw new AccessDeniedError('request body exceeds admitted size')
  }
}

export function requireAccessIdentity(request: Request): AccessIdentity {
  const email = request.headers.get('cf-access-authenticated-user-email')?.trim() ?? ''
  const jwt = request.headers.get('cf-access-jwt-assertion')?.trim() ?? ''
  if (!email || !jwt) {
    throw new AccessDeniedError('Cloudflare Access identity is required')
  }
  return { email, jwt }
}

export function jsonResponse(status: number, payload: unknown): Response {
  return Response.json(payload, {
    status,
    headers: {
      'cache-control': 'no-store',
      'content-security-policy': "default-src 'none'; frame-ancestors 'none'",
      'referrer-policy': 'no-referrer',
      'x-content-type-options': 'nosniff',
    },
  })
}
