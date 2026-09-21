import { useState } from 'react'
import {
  getStoredAnalyticsConsent,
  setGa4AnalyticsConsent,
  type AnalyticsConsent,
} from '../lib/analytics.js'

export function AnalyticsConsentBanner() {
  const [consent, setConsent] = useState<AnalyticsConsent>(() => getStoredAnalyticsConsent())

  if (consent !== 'unset') return null

  const choose = (granted: boolean) => {
    setGa4AnalyticsConsent(granted)
    setConsent(granted ? 'granted' : 'denied')
  }

  return (
    <aside
      aria-label="Analytics preferences"
      className="fixed bottom-4 left-4 right-4 z-[100] mx-auto max-w-2xl rounded-xl border border-aegis-border bg-aegis-surface/95 p-4 shadow-2xl backdrop-blur"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="m-0 text-sm leading-6 text-aegis-secondary">
          AEGIS can use privacy-limited analytics to measure site usage. Advertising storage stays disabled.
        </p>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => choose(false)}
            className="rounded-lg border border-aegis-border-medium px-3 py-2 text-sm text-aegis-secondary hover:bg-aegis-hover"
          >
            Decline
          </button>
          <button
            type="button"
            onClick={() => choose(true)}
            className="rounded-lg bg-aegis-phi px-3 py-2 text-sm font-semibold text-aegis-void hover:bg-aegis-phi-glow"
          >
            Allow analytics
          </button>
        </div>
      </div>
    </aside>
  )
}
