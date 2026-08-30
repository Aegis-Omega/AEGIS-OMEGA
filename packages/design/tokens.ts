/**
 * AEGIS-Ω Constitutional Design System — Tokens
 * EPISTEMIC TIER: T2 (engineering hypothesis — visual language reflects constitutional structure)
 *
 * Single source of truth for all color, typography, spacing, and animation tokens.
 * Constitutional invariant: T0 (mechanically proven) is always green.
 *                           AbovePhi (drift) is always red.
 *                           The φ-gold is the governing constant made visible.
 *
 * Copyright (C) 2025 Tarik Skalić — AGPL-3.0-or-later
 */

// ─── Epistemic tier colors ────────────────────────────────────────────────

export const TIER = {
  T0:      '#34D399',  // verified green — mechanically proven, T0_ABORT on violation
  T1:      '#60A5FA',  // trust blue — empirically validated
  T2:      '#A78BFA',  // hypothesis violet — engineering conjecture
  T3:      '#F59E0B',  // conjecture amber — research hypothesis
  T4:      '#F87171',  // blocked red — no T0–T2 authority may derive from T4
  T5:      '#6B6B7A',  // quarantined — creative / worldbuilding, never in src/
} as const

// ─── Constitutional constants made visible ────────────────────────────────

export const PHI = {
  GOLD:       '#C8A96E',  // 1/φ golden ratio governing constant
  GLOW:       '#D4AF7A',  // lighter phi for hover states
  DEEP:       '#8B7050',  // darker phi for backgrounds
  ALPHA_10:   'rgba(200,169,110,0.10)',
  ALPHA_20:   'rgba(200,169,110,0.20)',
} as const

// ─── Background surfaces — dark mode (the system operates in darkness) ───

export const BG = {
  VOID:    '#0A0A0C',  // absolute void — deepest layer (modals, overlays)
  DEEP:    '#0C0C0E',  // deep space — app background
  BASE:    '#0F0F11',  // base layer
  SURFACE: '#141416',  // elevated surface — cards, panels
  CARD:    '#1A1A1E',  // card layer
  HOVER:   '#1E1E26',  // hover / selected state
  ACTIVE:  '#22222C',  // active / pressed state
} as const

// ─── Border tokens ────────────────────────────────────────────────────────

export const BORDER = {
  SUBTLE:  '#17171A',  // barely visible — section dividers
  DEFAULT: '#1E1E22',  // default border — cards, panels
  MEDIUM:  '#27272D',  // medium — focused inputs, table rows
  STRONG:  '#3F3F46',  // strong — active elements
  PHI:     '#3D3020',  // phi-tinted border — constitutional sections
} as const

// ─── Text ─────────────────────────────────────────────────────────────────

export const TEXT = {
  PRIMARY:   '#ECEAE3',  // main content — high contrast
  SECONDARY: '#A1A1AA',  // secondary content
  MUTED:     '#6B6B7A',  // muted — labels, timestamps
  DISABLED:  '#3F3F46',  // disabled state
  LINK:      '#60A5FA',  // interactive link — T1 blue
  CODE:      '#C8A96E',  // inline code — phi gold
  HASH:      '#A78BFA',  // hash values — T2 violet
} as const

// ─── Status colors ────────────────────────────────────────────────────────

export const STATUS = {
  OK:      '#34D399',  // T0 certified — passes constitutional gate
  WARN:    '#C8A96E',  // phi boundary — approaching limit
  ERROR:   '#F87171',  // violation — drift / breach detected
  INFO:    '#60A5FA',  // informational
  NEUTRAL: '#6B6B7A',  // inactive / unknown
} as const

// ─── Network verdict colors ───────────────────────────────────────────────

export const VERDICT = {
  UNIFIED:   '#34D399',  // global section exists — all peers in chord
  CLUSTERED: '#C8A96E',  // multiple compatible classes — bounded drift
  SPLIT:     '#F87171',  // non-global coherence — constitutional breach
} as const

// ─── Typography ───────────────────────────────────────────────────────────

export const FONT = {
  SANS:  "'Inter', 'system-ui', sans-serif",
  MONO:  "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
  SERIF: "'Georgia', 'Times New Roman', serif",  // reserved for spec docs
} as const

export const FONT_SIZE = {
  XS:   '0.625rem',   // 10px — hash truncations, micro labels
  SM:   '0.75rem',    // 12px — captions, metadata
  BASE: '0.8125rem',  // 13px — UI default (dense governance UI)
  MD:   '0.875rem',   // 14px — body text
  LG:   '1rem',       // 16px — section headers
  XL:   '1.125rem',   // 18px — panel titles
  '2XL': '1.25rem',   // 20px — page titles
  '3XL': '1.5rem',    // 24px — hero text
} as const

// ─── Spacing (8px grid) ───────────────────────────────────────────────────

export const SPACE = {
  '0.5': '0.125rem',   // 2px — hairline
  '1':   '0.25rem',    // 4px
  '1.5': '0.375rem',   // 6px
  '2':   '0.5rem',     // 8px
  '3':   '0.75rem',    // 12px
  '4':   '1rem',       // 16px
  '5':   '1.25rem',    // 20px
  '6':   '1.5rem',     // 24px
  '8':   '2rem',       // 32px
  '10':  '2.5rem',     // 40px
  '12':  '3rem',       // 48px
  '16':  '4rem',       // 64px
} as const

// ─── Border radius ────────────────────────────────────────────────────────

export const RADIUS = {
  NONE: '0',
  SM:   '0.125rem',   // 2px — chips, badges
  MD:   '0.25rem',    // 4px — buttons, inputs
  LG:   '0.375rem',   // 6px — cards, panels
  XL:   '0.5rem',     // 8px — modals
  FULL: '9999px',     // pill — tags, status indicators
} as const

// ─── Shadows ──────────────────────────────────────────────────────────────

export const SHADOW = {
  SM:    '0 1px 2px rgba(0,0,0,0.6)',
  MD:    '0 4px 8px rgba(0,0,0,0.6)',
  LG:    '0 8px 24px rgba(0,0,0,0.7)',
  GLOW:  '0 0 12px rgba(200,169,110,0.15)',   // phi glow
  T0:    '0 0 8px rgba(52,211,153,0.20)',     // T0 verified glow
  ERROR: '0 0 8px rgba(248,113,113,0.20)',    // violation glow
} as const

// ─── Animation ────────────────────────────────────────────────────────────

export const ANIM = {
  FAST:    '80ms ease',
  DEFAULT: '150ms ease',
  SLOW:    '300ms ease',
  PULSE:   'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
} as const

// ─── Tailwind CSS variable map ────────────────────────────────────────────
// Use these CSS variable names in className strings: var(--aegis-T0), etc.

export const CSS_VARS = {
  '--aegis-T0':           TIER.T0,
  '--aegis-T1':           TIER.T1,
  '--aegis-T2':           TIER.T2,
  '--aegis-T3':           TIER.T3,
  '--aegis-phi':          PHI.GOLD,
  '--aegis-bg':           BG.DEEP,
  '--aegis-surface':      BG.SURFACE,
  '--aegis-card':         BG.CARD,
  '--aegis-border':       BORDER.DEFAULT,
  '--aegis-text':         TEXT.PRIMARY,
  '--aegis-muted':        TEXT.MUTED,
  '--aegis-ok':           STATUS.OK,
  '--aegis-warn':         STATUS.WARN,
  '--aegis-error':        STATUS.ERROR,
  '--aegis-verdict-u':    VERDICT.UNIFIED,
  '--aegis-verdict-c':    VERDICT.CLUSTERED,
  '--aegis-verdict-s':    VERDICT.SPLIT,
} as const

export type DesignToken = typeof CSS_VARS
