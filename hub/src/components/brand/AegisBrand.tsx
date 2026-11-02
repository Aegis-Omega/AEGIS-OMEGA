import type { CSSProperties } from 'react'
import { T } from '../console/consoleTokens.js'

/**
 * AEGIS Ω brand component. Additive, candidate only.
 * Place at hub/src/components/brand/AegisBrand.tsx.
 * Source geometry: Frontier Identity v1 Cut mark, unchanged.
 * AEGIS token reference: hub/src/components/console/consoleTokens.ts.
 */
const PATHS = [
  'M37 147 L92 40 L115 40 L78 116 L120 116 L108 142 L65 142 L53 165 Z',
  'M119 38 L164 38 L185 81 L167 114 L148 77 Z',
  'M132 126 L187 126 L174 154 L117 154 Z',
] as const

export type AegisBrandProps = {
  mode?: 'mark' | 'lockup'
  tone?: 'light' | 'dark' | 'phi'
  size?: number
  company?: boolean
  className?: string
}

const BRAND_NAME = 'AEGIS Ω'
const COMPANY_NAME = 'Aegis Omega Labs'

function brandColor(tone: NonNullable<AegisBrandProps['tone']>): string {
  if (tone === 'dark') return T.void
  if (tone === 'phi') return T.phi
  return T.text
}

export function AegisBrand({ mode = 'lockup', tone = 'light', size = 44, company = true, className }: AegisBrandProps) {
  const ink = brandColor(tone)
  const decorative = mode === 'lockup'
  const icon = (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 220"
      width={size} height={size} fill="currentColor" aria-hidden={decorative ? true : undefined}
      role={decorative ? undefined : 'img'} aria-label={decorative ? undefined : BRAND_NAME}
      focusable="false" style={{ flex: 'none', display: 'block' }}>
      {!decorative && <title>{BRAND_NAME}</title>}
      {PATHS.map((d, i) => <path key={i} d={d} />)}
    </svg>
  )
  const style: CSSProperties = { color: ink, display: 'inline-flex', alignItems: 'center', gap: Math.max(6, Math.round(size * 0.13)) }
  if (mode === 'mark') return <span className={className} style={style}>{icon}</span>
  return (
    <span className={className} style={style} aria-label={company ? `${BRAND_NAME}, ${COMPANY_NAME}` : BRAND_NAME}>
      {icon}
      <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.16 }}>
        <span style={{ fontWeight: 700, fontSize: Math.max(14, Math.round(size * 0.36)), letterSpacing: '0.04em' }}>{BRAND_NAME}</span>
        {company && <span style={{ fontWeight: 400, fontSize: Math.max(10, Math.round(size * 0.2)), letterSpacing: '0.06em', marginTop: 4 }}>{COMPANY_NAME}</span>}
      </span>
    </span>
  )
}
