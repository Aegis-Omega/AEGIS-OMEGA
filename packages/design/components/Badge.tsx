import React from 'react'
import { TIER, STATUS, VERDICT, PHI, BORDER, BG } from '../tokens.js'

type Tier = 'T0' | 'T1' | 'T2' | 'T3' | 'T4' | 'T5'
type Variant = 'tier' | 'status' | 'verdict' | 'phi' | 'neutral'
type StatusKind = 'ok' | 'warn' | 'error' | 'info' | 'neutral'
type VerdictKind = 'UNIFIED' | 'CLUSTERED' | 'SPLIT'

interface BadgeProps {
  children: React.ReactNode
  tier?: Tier
  status?: StatusKind
  verdict?: VerdictKind
  variant?: Variant
  className?: string
}

function colorFor(props: BadgeProps): { color: string; bg: string; border: string } {
  if (props.tier) {
    const c = TIER[props.tier]
    return { color: c, bg: `${c}18`, border: `${c}30` }
  }
  if (props.verdict) {
    const c = VERDICT[props.verdict]
    return { color: c, bg: `${c}18`, border: `${c}30` }
  }
  if (props.status === 'ok')      return { color: STATUS.OK,      bg: `${STATUS.OK}18`,      border: `${STATUS.OK}30`      }
  if (props.status === 'warn')    return { color: STATUS.WARN,    bg: `${STATUS.WARN}18`,    border: `${STATUS.WARN}30`    }
  if (props.status === 'error')   return { color: STATUS.ERROR,   bg: `${STATUS.ERROR}18`,   border: `${STATUS.ERROR}30`   }
  if (props.status === 'info')    return { color: STATUS.INFO,    bg: `${STATUS.INFO}18`,    border: `${STATUS.INFO}30`    }
  if (props.variant === 'phi')    return { color: PHI.GOLD,       bg: PHI.ALPHA_10,           border: `${PHI.DEEP}60`       }
  return { color: '#6B6B7A', bg: BG.CARD, border: BORDER.DEFAULT }
}

export function Badge({ children, className = '', ...props }: BadgeProps) {
  const { color, bg, border } = colorFor(props)
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono font-medium leading-none ${className}`}
      style={{ color, background: bg, border: `1px solid ${border}` }}
    >
      {children}
    </span>
  )
}

export function TierBadge({ tier }: { tier: Tier }) {
  return <Badge tier={tier}>{tier}</Badge>
}

export function VerdictBadge({ verdict }: { verdict: VerdictKind }) {
  return <Badge verdict={verdict}>{verdict}</Badge>
}
