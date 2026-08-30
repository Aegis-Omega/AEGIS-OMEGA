// ============================================================
// Analytics — PostHog observational layer
// DETERMINISM CLASS: observational (D0 — read-only telemetry)
// STRATUM: Commercial analytics (NOT governance telemetry)
// Constitutional constraint: no write-back into governance paths.
// BigQuery warehouse → dbt metric layer (transformation only).
// ============================================================

// PostHog is loaded lazily from CDN to keep zero-backend constraint.
// Buyer never needs to configure — key is baked into each product build.
const POSTHOG_KEY = (typeof import.meta !== 'undefined'
  ? (import.meta.env?.VITE_POSTHOG_KEY as string | undefined)
  : undefined) ?? ''

const POSTHOG_HOST = 'https://eu.i.posthog.com'

let _ph: PostHogInstance | null = null

interface PostHogInstance {
  capture: (event: string, props?: Record<string, unknown>) => void
  identify: (id: string, traits?: Record<string, unknown>) => void
}

function ph(): PostHogInstance | null {
  if (_ph) return _ph
  if (typeof window === 'undefined' || !POSTHOG_KEY) return null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const g = window as any
  if (typeof g.posthog?.capture === 'function') {
    _ph = g.posthog as PostHogInstance
    return _ph
  }
  return null
}

export function trackEvent(event: string, properties?: Record<string, unknown>): void {
  ph()?.capture(event, properties)
}

export function trackConversion(product: string, properties?: Record<string, unknown>): void {
  ph()?.capture('conversion', { product, ...properties })
}

export function identifyUser(id: string, traits?: Record<string, unknown>): void {
  ph()?.identify(id, traits)
}

// Initialises PostHog via snippet injection. Call once in each product's App.tsx.
// No-op if key is absent (local dev without analytics configured).
export function initAnalytics(): void {
  if (typeof window === 'undefined' || !POSTHOG_KEY) return
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const g = window as any
  if (typeof g.posthog?.capture === 'function') return  // already loaded

  // Minimal PostHog snippet — loads async, does not block rendering.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(function (t: any, e: string, o: string) {
    t[o] = t[o] || []
    const n = t.document.createElement(e) as HTMLScriptElement
    n.async = true
    n.src = `${POSTHOG_HOST}/static/array.js`
    n.onload = () => {
      t[o].init?.(POSTHOG_KEY, { api_host: POSTHOG_HOST, autocapture: false })
      _ph = t[o] as PostHogInstance
    }
    const s = t.document.getElementsByTagName(e)[0]
    s?.parentNode?.insertBefore(n, s)
  })(window, 'script', 'posthog')
}
