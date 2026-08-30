// AEGIS-Ω — NOUS interaction primitives.
// The shared button/pill language so every interactive element across the
// platform resembles NOUS: glass surface, gold/indigo glow, a refined lift on
// hover. Encoded once; inherited everywhere. Self-contained inline styles so it
// drops into any page (landing, console, pricing, docs) without CSS coupling.

import { useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { T } from './consoleTokens.js'

type Variant = 'primary' | 'ghost'
type Size = 'md' | 'lg'

interface NousButtonProps {
  children: ReactNode
  href?: string
  onClick?: () => void
  variant?: Variant
  size?: Size
  style?: CSSProperties
}

const PAD: Record<Size, string> = { md: '10px 22px', lg: '14px 30px' }
const FS: Record<Size, number> = { md: 13, lg: 15 }

export function NousButton({ children, href, onClick, variant = 'primary', size = 'md', style }: NousButtonProps) {
  const [hover, setHover] = useState(false)
  const base: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 9,
    padding: PAD[size], fontSize: FS[size], fontWeight: 600,
    borderRadius: 12, textDecoration: 'none', cursor: 'pointer',
    fontFamily: 'inherit', letterSpacing: '0.01em', whiteSpace: 'nowrap',
    transition: 'transform 0.22s cubic-bezier(0.2,0.8,0.2,1), box-shadow 0.3s, border-color 0.3s, background 0.3s',
    transform: hover ? 'translateY(-1.5px)' : 'translateY(0)',
    border: '1px solid',
  }
  const skin: CSSProperties = variant === 'primary'
    ? {
        color: '#0A0A0C',
        background: hover
          ? 'linear-gradient(180deg, #FFF8EA 0%, #D8B97E 100%)'
          : 'linear-gradient(180deg, #F3ECDC 0%, #C8A96E 100%)',
        borderColor: 'rgba(255,255,255,0.18)',
        boxShadow: hover
          ? `0 10px 40px ${T.phi}55, inset 0 1px 0 rgba(255,255,255,0.5)`
          : `0 6px 24px ${T.phi}33, inset 0 1px 0 rgba(255,255,255,0.4)`,
      }
    : {
        color: hover ? T.text : T.sub,
        background: hover ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
        borderColor: hover ? 'rgba(255,255,255,0.22)' : 'rgba(255,255,255,0.10)',
        boxShadow: hover ? `0 8px 30px rgba(0,0,0,0.4), 0 0 30px ${T.indigo}1A` : 'none',
        backdropFilter: 'blur(8px)',
      }
  const props = {
    style: { ...base, ...skin, ...style },
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    onFocus: () => setHover(true),
    onBlur: () => setHover(false),
  }
  return href
    ? <a href={href} onClick={onClick} {...props}>{children}</a>
    : <button type="button" onClick={onClick} {...props}>{children}</button>
}

// Arrow glyph that drifts on hover — pairs with NousButton primary.
export function ArrowR() {
  return <span style={{ fontSize: '1.05em', lineHeight: 1, transform: 'translateY(0.5px)' }}>→</span>
}

// Small status/eyebrow pill in the NOUS language.
export function NousPill({ children, accent = T.phi }: { children: ReactNode; accent?: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '6px 14px', borderRadius: 100, fontSize: 11,
      fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', color: accent,
      background: `${accent}10`, border: `1px solid ${accent}30`,
      backdropFilter: 'blur(8px)',
    }}>{children}</span>
  )
}
