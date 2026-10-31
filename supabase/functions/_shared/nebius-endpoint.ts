/** Strict Token Factory endpoint allowlist. No credentials may reach arbitrary hosts. */
const ALLOWED_HOSTS = new Set([
  'api.tokenfactory.nebius.com',
  'api.tokenfactory.us-north1.nebius.com',
  'api.tokenfactory.us-central1.nebius.com',
])
export function getNebiusChatUrl(baseUrl: string): string | null {
  try {
    const u = new URL(baseUrl)
    if (u.protocol !== 'https:' || !ALLOWED_HOSTS.has(u.hostname)
      || u.port || u.username || u.password || u.search || u.hash
      || !['/v1', '/v1/'].includes(u.pathname)) return null
    return `https://${u.hostname}/v1/chat/completions`
  } catch {
    return null
  }
}
