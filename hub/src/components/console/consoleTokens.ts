// AEGIS-Ω Console — shared design tokens.
// Shared neutral material system across NOUS, Pricing, Compliance and Docs.
// Semantic tier colors retain their original meanings; these are not live status flags.

export const T = {
  phi:    '#C8A96E', // gold — constitutional / φ
  indigo: '#818CF8', // primary action / dag_step
  green:  '#34D399', // healthy / approved / completion
  blue:   '#60A5FA', // info
  amber:  '#F59E0B', // caution / stressed
  red:    '#F87171', // fault / quarantine
  text:   '#EEEAE1',
  sub:    '#BEC8C2',
  muted:  '#99ABA8',
  card:   '#151E21',
  border: 'rgba(199,210,209,0.20)',
  void:   '#080C0F',
  bg:     '#0D1216',
  inset:  '#090E10',
} as const

export const MONO = 'var(--font-mono)'
export const SANS = 'var(--font-sans)'

// ── Structural material surface ────────────────────────────────────────────
// Background is a solid reading plane; optical effects belong to focal art.

import type { CSSProperties } from 'react'

export const GLASS = {
  blur: 'blur(18px) saturate(150%)',
  surface: 'rgba(19, 28, 31, 0.92)',
  surfaceHi: 'rgba(27, 37, 40, 0.94)',
  hairline: 'rgba(219, 227, 214, 0.20)',
  edgeLight: 'inset 0 1px 0 rgba(239, 232, 209, 0.08)',
  depth: '0 14px 36px rgba(0, 0, 0, 0.34)',
} as const

// Glass panel factory. Pass an accent for a soft colored glow at the edge.
export function glass(accent: string = T.indigo, radius = 18): CSSProperties {
  return {
    background: GLASS.surface,
    backdropFilter: GLASS.blur,
    WebkitBackdropFilter: GLASS.blur,
    border: `1px solid ${GLASS.hairline}`,
    borderRadius: radius,
    boxShadow: `${GLASS.depth}, ${GLASS.edgeLight}, 0 0 60px ${accent}0A`,
  }
}

// Homeostasis zone → color + label. The hormetic curve, made legible.
export const ZONE_META: Record<string, { color: string; label: string; band: string }> = {
  slack:    { color: T.blue,  label: 'SLACK',    band: 'under-driven · ease the bar up' },
  optimal:  { color: T.green, label: 'OPTIMAL',  band: 'productive zone · hold steady' },
  stressed: { color: T.amber, label: 'STRESSED', band: 'high output · tighten the bar' },
  critical: { color: T.red,   label: 'CRITICAL', band: 'stagnation risk · intervene' },
}

export const REC_META: Record<string, { color: string; glyph: string }> = {
  EASE:     { color: T.blue,  glyph: '▽' },
  MAINTAIN: { color: T.green, glyph: '○' },
  TIGHTEN:  { color: T.amber, glyph: '△' },
}

export const TIER_META: Record<string, { color: string; ring: number }> = {
  sovereign: { color: T.phi,    ring: 0 }, // innermost
  operator:  { color: T.indigo, ring: 1 },
  explorer:  { color: T.blue,   ring: 2 }, // outermost
}
