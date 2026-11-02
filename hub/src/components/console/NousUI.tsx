// AEGIS-Ω — NOUS interaction primitives.
// One shared button and label language for Pricing, Compliance and Docs.
// Solid information planes; editorial form, restrained motion and real focus.
// Local inline styles preserve standalone use outside the Holon shell.

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
    borderRadius: 4, textDecoration: 'none', cursor: 'pointer',
    fontFamily: 'inherit', letterSpacing: '0.01em', whiteSpace: 'nowrap',
    transition: 'transform 0.22s cubic-bezier(0.2,0.8,0.2,1), box-shadow 0.3s, border-color 0.3s, background 0.3s',
    transform: hover ? 'translateY(-1.5px)' : 'translateY(0)',
    border: '1px solid',
  }
  const skin: CSSProperties = variant === 'primary'
    ? {
        color: '#0D1415',
        background: hover
          ? 'linear-gradient(115deg, #F4E4C0 0%, #DFBE83 100%)'
          : 'linear-gradient(115deg, #E9DBBB 0%, #D8BD91 100%)',
        borderColor: 'rgba(255,255,255,0.18)',
        boxShadow: hover
          ? `0 10px 40px ${T.phi}55, inset 0 1px 0 rgba(255,255,255,0.5)`
          : `0 6px 24px ${T.phi}33, inset 0 1px 0 rgba(255,255,255,0.4)`,
      }
    : {
        color: hover ? T.text : T.sub,
        background: hover ? 'rgba(218,228,221,0.11)' : 'rgba(218,228,221,0.035)',
        borderColor: hover ? 'rgba(216,218,209,0.47)' : 'rgba(216,218,209,0.24)',
        boxShadow: hover ? `0 8px 30px rgba(0,0,0,0.4), 0 0 30px ${T.indigo}1A` : 'none',
        backdropFilter: 'none',
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
      padding: '7px 13px', borderRadius: 3, fontSize: 12,
      fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', color: accent,
      background: `${accent}10`, border: `1px solid ${accent}30`,
      backdropFilter: 'blur(8px)',
    }}>{children}</span>
  )
}
