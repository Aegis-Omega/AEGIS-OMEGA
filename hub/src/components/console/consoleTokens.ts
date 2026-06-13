// AEGIS-Ω Console — shared design tokens.
// Matches the hub platform design language exactly (PlatformPage.tsx palette).

export const T = {
  phi:    '#C8A96E', // gold — constitutional / φ
  indigo: '#818CF8', // primary action / dag_step
  green:  '#34D399', // healthy / approved / completion
  blue:   '#60A5FA', // info
  amber:  '#F59E0B', // caution / stressed
  red:    '#F87171', // fault / quarantine
  text:   '#ECEAE3',
  sub:    '#A1A1AA',
  muted:  '#6B6B7A',
  card:   '#1A1A1E',
  border: '#1E1E22',
  void:   '#08090C',
  bg:     '#0F0F11',
  inset:  '#07070A',
} as const

export const MONO = 'var(--font-mono)'
export const SANS = 'var(--font-sans)'

// ── Neural Glassmorphism design system ────────────────────────────────────────
// Encoded once so it is reproducible forever (your eye → named constants).
// A glass panel = translucent frosted surface + edge-light + accent glow.
// The edge-light (inset top highlight) is what makes glass read as *glass*.

import type { CSSProperties } from 'react'

export const GLASS = {
  blur: 'blur(18px) saturate(150%)',
  surface: 'rgba(22, 22, 28, 0.55)',
  surfaceHi: 'rgba(30, 30, 38, 0.62)',
  hairline: 'rgba(255, 255, 255, 0.08)',
  edgeLight: 'inset 0 1px 0 rgba(255, 255, 255, 0.07)',
  depth: '0 10px 40px rgba(0, 0, 0, 0.45)',
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
