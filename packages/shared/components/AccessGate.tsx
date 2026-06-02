import { useState, useEffect, type ReactNode } from 'react'
import { Shield, Zap, CheckCircle } from 'lucide-react'
import { verifyGrantToken, verifyServerToken, getStoredAccess, storeAccess, storeServerToken, getStoredServerToken } from '../lib/access.js'

interface AccessGateProps {
  product: 'platform-picker' | 'hook-generator' | 'content-calendar'
  accentColor?: string
  buyUrl?: string
  children: ReactNode
}

const DEV_BYPASS = (import.meta as any).env?.VITE_SKIP_LICENSE === 'true'

const PRODUCT_NAMES: Record<string, string> = {
  'platform-picker':  'Platform Picker',
  'hook-generator':   'Hook Generator',
  'content-calendar': 'Content Calendar',
}

const HUB_URL = (import.meta as any).env?.VITE_HUB_URL ?? 'https://aegisomega.com'

export function AccessGate({ product, accentColor = '#6366F1', buyUrl, children }: AccessGateProps) {
  const [unlocked, setUnlocked] = useState(false)
  const [checking, setChecking] = useState(true)
  const [justGranted, setJustGranted] = useState(false)

  useEffect(() => {
    if (DEV_BYPASS) { setUnlocked(true); setChecking(false); return }

    ;(async () => {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('aegis_token')

      if (token) {
        // Try ECDSA-signed server token first (cryptographically secure)
        const serverPayload = await verifyServerToken(token)
        if (serverPayload && serverPayload.tools.includes(product)) {
          storeServerToken(product, token)
          const url = new URL(window.location.href)
          url.searchParams.delete('aegis_token')
          window.history.replaceState({}, '', url.toString())
          setJustGranted(true)
          setTimeout(() => { setUnlocked(true); setJustGranted(false) }, 1200)
          setChecking(false)
          return
        }
        // Fall back to legacy HMAC token (backwards compatibility)
        const payload = verifyGrantToken(token)
        if (payload && payload.tools.includes(product)) {
          storeAccess(product, payload)
          const url = new URL(window.location.href)
          url.searchParams.delete('aegis_token')
          window.history.replaceState({}, '', url.toString())
          setJustGranted(true)
          setTimeout(() => { setUnlocked(true); setJustGranted(false) }, 1200)
          setChecking(false)
          return
        }
      }

      // Check stored ECDSA server token
      const serverToken = getStoredServerToken(product)
      if (serverToken) {
        const serverPayload = await verifyServerToken(serverToken)
        if (serverPayload) { setUnlocked(true); setChecking(false); return }
        localStorage.removeItem(`aegis_srv_${product}`)
      }

      // Check stored legacy token
      const stored = getStoredAccess(product)
      if (stored) { setUnlocked(true) }
      setChecking(false)
    })()
  }, [product])

  if (checking) return null

  if (unlocked) return <>{children}</>

  if (justGranted) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#08090C' }}>
        <div className="text-center">
          <CheckCircle size={48} style={{ color: accentColor }} className="mx-auto mb-4" />
          <div className="text-xl font-bold mb-2" style={{ color: '#EDEAE3' }}>Access granted</div>
          <div className="text-sm" style={{ color: '#6B6E80' }}>Loading {PRODUCT_NAMES[product]}…</div>
        </div>
      </div>
    )
  }

  const purchaseUrl = buyUrl ?? `${HUB_URL}/#pricing`

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: '#08090C' }}>
      <div className="w-full max-w-sm text-center">
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-6"
          style={{ background: `${accentColor}18`, border: `1px solid ${accentColor}40` }}
        >
          <Shield size={24} style={{ color: accentColor }} />
        </div>
        <h1 className="text-xl font-bold mb-2" style={{ color: '#EDEAE3' }}>
          {PRODUCT_NAMES[product]}
        </h1>
        <p className="text-sm mb-8" style={{ color: '#6B6E80' }}>
          One-time purchase. Instant access. No subscriptions.
        </p>
        <a
          href={purchaseUrl}
          className="inline-flex items-center justify-center gap-2 w-full py-3.5 rounded-xl font-semibold text-sm transition-opacity hover:opacity-90"
          style={{ background: accentColor, color: '#ffffff' }}
        >
          <Zap size={15} />
          Get access — $19
        </a>
        <p className="text-xs mt-4" style={{ color: '#6B6E80' }}>
          Already purchased?{' '}
          <a href={`${HUB_URL}/success`} style={{ color: accentColor }}>
            Restore access →
          </a>
        </p>
      </div>
    </div>
  )
}
