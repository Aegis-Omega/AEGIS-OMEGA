type GtagCommand = 'js' | 'config' | 'consent' | 'event'
export type AnalyticsConsent = 'granted' | 'denied' | 'unset'

declare global {
  interface Window {
    dataLayer?: IArguments[]
    gtag?: (command: GtagCommand, ...args: unknown[]) => void
    __aegisGa4Initialized?: boolean
  }
}

const CONSENT_KEY = 'aegis.analytics.consent.v1'
const measurementId = (import.meta.env.VITE_GA4_MEASUREMENT_ID as string | undefined)?.trim()
const GA4_ID =
  measurementId &&
  measurementId !== 'G-XXXXXXXXXX' &&
  /^G-[A-Z0-9]+$/.test(measurementId)
    ? measurementId
    : undefined

function ensureGtag(): void {
  window.dataLayer ??= []
  window.gtag ??= function gtag() {
    window.dataLayer!.push(arguments)
  }
}

export function getStoredAnalyticsConsent(): AnalyticsConsent {
  if (typeof window === 'undefined') return 'unset'
  try {
    const value = window.localStorage.getItem(CONSENT_KEY)
    return value === 'granted' || value === 'denied' ? value : 'unset'
  } catch {
    return 'unset'
  }
}

export function initGa4(): boolean {
  if (!GA4_ID || typeof window === 'undefined' || typeof document === 'undefined') return false
  if (getStoredAnalyticsConsent() !== 'granted') return false
  if (window.__aegisGa4Initialized) return true

  ensureGtag()
  window.gtag!('consent', 'default', {
    analytics_storage: 'granted',
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
  })

  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA4_ID)}`
  script.dataset.aegisAnalytics = 'ga4'
  document.head.appendChild(script)

  window.gtag!('js', new Date())
  window.gtag!('config', GA4_ID, { send_page_view: true })
  window.__aegisGa4Initialized = true
  return true
}

export function setGa4AnalyticsConsent(granted: boolean): void {
  if (typeof window === 'undefined') return

  try {
    window.localStorage.setItem(CONSENT_KEY, granted ? 'granted' : 'denied')
  } catch {
    // Storage can be unavailable in hardened/private browser contexts.
  }

  if (granted) {
    if (!window.__aegisGa4Initialized) {
      initGa4()
      return
    }
    ensureGtag()
    window.gtag!('consent', 'update', { analytics_storage: 'granted' })
    return
  }

  if (window.__aegisGa4Initialized) {
    ensureGtag()
    window.gtag!('consent', 'update', { analytics_storage: 'denied' })
  }
}

export function trackGa4Event(name: string, params: Record<string, unknown> = {}): void {
  if (!GA4_ID || typeof window === 'undefined' || !window.__aegisGa4Initialized) return
  ensureGtag()
  window.gtag!('event', name, params)
}
