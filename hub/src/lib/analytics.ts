type GtagCommand = 'js' | 'config' | 'consent' | 'event'

declare global {
  interface Window {
    dataLayer?: unknown[]
    gtag?: (command: GtagCommand, ...args: unknown[]) => void
    __aegisGa4Initialized?: boolean
  }
}

const measurementId = (import.meta.env.VITE_GA4_MEASUREMENT_ID as string | undefined)?.trim()
const GA4_ID = /^G-[A-Z0-9]+$/.test(measurementId ?? '') ? measurementId : undefined

function ensureGtag(): void {
  window.dataLayer ??= []
  window.gtag ??= (command: GtagCommand, ...args: unknown[]) => {
    window.dataLayer!.push([command, ...args])
  }
}

export function initGa4(): boolean {
  if (!GA4_ID || typeof window === 'undefined' || typeof document === 'undefined') return false
  if (window.__aegisGa4Initialized) return true

  ensureGtag()

  window.gtag!('consent', 'default', {
    analytics_storage: 'denied',
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    wait_for_update: 500,
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
  if (!GA4_ID || typeof window === 'undefined') return
  ensureGtag()
  window.gtag!('consent', 'update', {
    analytics_storage: granted ? 'granted' : 'denied',
  })
}

export function trackGa4Event(name: string, params: Record<string, unknown> = {}): void {
  if (!GA4_ID || typeof window === 'undefined' || !window.__aegisGa4Initialized) return
  ensureGtag()
  window.gtag!('event', name, params)
}
