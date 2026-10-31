/** Fail-closed caller authorization for the paid Nebius inference lane. */
export type NebiusUserIdVerifier = (jwt: string) => Promise<string | null>

export async function authorizeNebiusCaller(
  authorization: string | null,
  allowedUserIds: string,
  verifyUserId: NebiusUserIdVerifier,
): Promise<boolean> {
  // A public anon key or a configured provider key never proves a user session.
  const match = /^Bearer ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$/.exec(authorization ?? '')
  if (!match) return false
  const allowlist = new Set(allowedUserIds.split(',').map(id => id.trim()).filter(Boolean))
  if (allowlist.size === 0) return false
  try {
    // Runtime must use Supabase Auth getUser(jwt), not decode unsigned claims.
    const verifiedUserId = await verifyUserId(match[1]!)
    return verifiedUserId !== null && allowlist.has(verifiedUserId)
  } catch {
    return false
  }
}

export function isNebiusRequestBounded(
  message: string,
  system: string,
  history: readonly { content: string }[],
): boolean {
  const maxChars = 4096
  return typeof message === 'string' && message.length > 0 && message.length <= maxChars
    && typeof system === 'string' && system.length <= maxChars
    && Array.isArray(history) && history.length <= 8
    && history.every(h => h !== null && typeof h === 'object'
      && typeof h.content === 'string' && h.content.length <= maxChars)
}
