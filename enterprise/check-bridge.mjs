// Usage: node enterprise/check-bridge.mjs <bridge URL> [dashboard origin]
import { createHash } from 'node:crypto'
import { pathToFileURL } from 'node:url'

const checks = {
  '/node': (data) => {
    const { sequence, epoch, corruption_count: corruption, constitutional_hash: hash } = data
    if (![sequence, epoch, corruption].every(Number.isSafeInteger)) return false
    const expected = createHash('sha256')
      .update(`seq=${sequence}:epoch=${epoch}:corruption=${corruption}`).digest('hex')
    return hash === expected && typeof data.t0_verdict === 'boolean'
  },
  '/network': (data) => Array.isArray(data.peers) && data.peer_count === data.peers.length,
  '/resonance': (data) => typeof data.is_resonant === 'boolean',
  '/telemetry': (data) => Number.isSafeInteger(data.sequence),
  '/coherence': (data) => typeof data.global_section_exists === 'boolean',
  '/pipeline': (data) => typeof data.replay_fingerprint === 'string',
  '/drift': (data) => typeof data.current_drift_class === 'string',
}

function parseUrl(value, originOnly = false) {
  const url = new URL(value)
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
  if (
    (url.protocol !== 'https:' && !(loopback && url.protocol === 'http:')) ||
    url.username || url.password || url.search || url.hash ||
    (originOnly && url.pathname !== '/')
  ) {
    throw new Error('Use an HTTPS URL without credentials, query, or fragment. HTTP is allowed on loopback.')
  }
  return url
}

export async function checkBridge(bridgeUrl, dashboardOrigin) {
  const base = parseUrl(bridgeUrl).href.replace(/\/$/, '')
  const origin = dashboardOrigin ? parseUrl(dashboardOrigin, true).origin : undefined

  return Promise.all(Object.entries(checks).map(async ([path, validate]) => {
    try {
      const response = await fetch(base + path, {
        headers: origin ? { Origin: origin } : undefined,
        redirect: 'error',
        signal: AbortSignal.timeout(4_000),
      })
      if (!response.ok) return { path, error: `HTTP ${response.status}` }
      const allowedOrigin = response.headers.get('access-control-allow-origin')
      if (origin && new URL(base).origin !== origin && allowedOrigin !== '*' && allowedOrigin !== origin) {
        return { path, error: 'Dashboard origin is not allowed by CORS' }
      }
      const data = await response.json()
      if (!data || typeof data !== 'object' || Array.isArray(data) || !validate(data)) {
        return { path, error: 'Unexpected bridge response' }
      }
      return { path, error: null }
    } catch {
      return { path, error: 'Request failed, timed out, or returned invalid JSON' }
    }
  }))
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [bridgeUrl, dashboardOrigin, ...extra] = process.argv.slice(2)
  if (!bridgeUrl || extra.length) {
    console.error('Usage: node enterprise/check-bridge.mjs <bridge URL> [dashboard origin]')
    process.exitCode = 2
  } else {
    try {
      const results = await checkBridge(bridgeUrl, dashboardOrigin)
      for (const { path, error } of results) {
        console.log(error ? `FAIL ${path} — ${error}` : `PASS ${path}`)
      }
      process.exitCode = Number(results.some(({ error }) => error !== null))
    } catch {
      console.error('Provide a valid bridge URL and, optionally, a dashboard origin. Remote URLs require HTTPS.')
      process.exitCode = 2
    }
  }
}
