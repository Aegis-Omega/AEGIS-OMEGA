// OpenAI Ads browser measurement helper.
// Pixel ID is public configuration; CAPI credentials remain server-side only.

type Oaiq = ((...args: unknown[]) => void) & { q?: unknown[][] }

declare global {
  interface Window {
    oaiq?: Oaiq
  }
}

const PIXEL_ID = ((import.meta.env.VITE_OPENAI_ADS_PIXEL_ID as string | undefined) ?? '').trim()
const SDK_SRC = 'https://bzrcdn.openai.com/sdk/oaiq.min.js'

function ensureQueue(): Oaiq | null {
  if (typeof window === 'undefined' || !PIXEL_ID) return null
  if (window.oaiq) return window.oaiq

  const q = ((...args: unknown[]) => { q.q!.push(args) }) as Oaiq
  q.q = []
  window.oaiq = q

  const script = document.createElement('script')
  script.async = true
  script.src = SDK_SRC
  script.dataset.openaiAdsPixel = 'true'
  document.head.appendChild(script)

  return q
}

export function initOpenAIAds(): boolean {
  try {
    const q = ensureQueue()
    if (!q) return false
    q('init', { pixelId: PIXEL_ID })
    return true
  } catch {
    return false
  }
}

export function measureOpenAIAds(
  eventName: string,
  data: Record<string, unknown>,
  options?: Record<string, unknown>,
): void {
  try {
    const q = ensureQueue()
    if (!q) return
    if (options) q('measure', eventName, data, options)
    else q('measure', eventName, data)
  } catch {
    // Measurement must never block the product flow.
  }
}

function readCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined
  const prefix = `${name}=`
  for (const part of document.cookie.split(';')) {
    const item = part.trim()
    if (item.startsWith(prefix)) return item.slice(prefix.length)
  }
  return undefined
}

export function openAIAdsWebContext(): {
  source_url: string
  oppref?: string
  obref?: string
} {
  const source_url = typeof window === 'undefined'
    ? 'https://aegisomega.com/pricing'
    : `${window.location.origin}${window.location.pathname}`

  const oppref = readCookie('__oppref')
  const obref = readCookie('__obref')

  return {
    source_url,
    ...(oppref ? { oppref } : {}),
    ...(obref ? { obref } : {}),
  }
}
