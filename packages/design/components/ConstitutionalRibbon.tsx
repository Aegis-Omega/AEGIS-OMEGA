/**
 * ConstitutionalRibbon — top-of-app status strip
 *
 * Displays the live constitutional health at a glance:
 *   T0 verdict · chord fingerprint · network verdict · resonance depth · φ-headroom
 *
 * All data is passed as props — the ribbon has no internal fetch, zero authority.
 */
import React from 'react'
import { TIER, PHI, STATUS, VERDICT, BG, BORDER, TEXT } from '../tokens.js'

export interface RibbonProps {
  t0Verdict: boolean | null
  chordHex?: string | null
  networkVerdict?: 'UNIFIED' | 'CLUSTERED' | 'SPLIT' | null
  resonanceDepth?: number | null
  phiHeadroom?: number | null
  epoch?: number | null
  corrupted?: boolean
}

function Divider() {
  return <span style={{ color: BORDER.STRONG, userSelect: 'none' }}>·</span>
}

function Item({ label, value, color }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <span className="flex items-center gap-1 text-xs font-mono">
      <span style={{ color: TEXT.MUTED }}>{label}</span>
      <span style={{ color: color ?? TEXT.SECONDARY }}>{value}</span>
    </span>
  )
}

export function ConstitutionalRibbon({
  t0Verdict,
  chordHex,
  networkVerdict,
  resonanceDepth,
  phiHeadroom,
  epoch,
  corrupted,
}: RibbonProps) {
  const t0Color = t0Verdict === null ? TEXT.MUTED
                : t0Verdict          ? TIER.T0
                :                      STATUS.ERROR

  const t0Label = t0Verdict === null ? 'T0:—'
                : t0Verdict          ? 'T0:PASS'
                :                      'T0:FAIL'

  const netColor = networkVerdict == null   ? TEXT.MUTED
                 : networkVerdict === 'UNIFIED'   ? VERDICT.UNIFIED
                 : networkVerdict === 'CLUSTERED' ? VERDICT.CLUSTERED
                 :                                  VERDICT.SPLIT

  return (
    <div
      className="flex items-center gap-2.5 px-3 py-1 text-xs select-none overflow-x-auto"
      style={{
        background: BG.VOID,
        borderBottom: `1px solid ${BORDER.SUBTLE}`,
        fontFamily: "'JetBrains Mono', monospace",
        scrollbarWidth: 'none',
      }}
    >
      {/* Constitutional law — always shown */}
      <span style={{ color: PHI.DEEP, flexShrink: 0 }}>
        AdaptivePower(T) ≤ ReplayVerifiability(T)
      </span>

      <Divider />

      {/* T0 verdict */}
      <span
        className="font-semibold flex-shrink-0"
        style={{ color: t0Color }}
      >
        {t0Label}
      </span>

      {/* Chord fingerprint */}
      {chordHex != null && (
        <>
          <Divider />
          <Item label="chord:" value={chordHex} color={PHI.GOLD} />
        </>
      )}

      {/* Network verdict */}
      {networkVerdict != null && (
        <>
          <Divider />
          <Item label="net:" value={networkVerdict} color={netColor} />
        </>
      )}

      {/* Resonance depth — 4-pip */}
      {resonanceDepth != null && (
        <>
          <Divider />
          <span className="flex items-center gap-1 flex-shrink-0">
            <span style={{ color: TEXT.MUTED }}>res:</span>
            <span className="flex gap-0.5">
              {[0, 1, 2, 3].map(i => (
                <span
                  key={i}
                  className="inline-block w-1.5 h-1.5 rounded-sm"
                  style={{
                    background: i < resonanceDepth
                      ? (resonanceDepth === 4 ? TIER.T0 : PHI.GOLD)
                      : BORDER.DEFAULT,
                  }}
                />
              ))}
            </span>
            <span style={{ color: TEXT.MUTED }}>{resonanceDepth}/4</span>
          </span>
        </>
      )}

      {/* φ-headroom */}
      {phiHeadroom != null && (
        <>
          <Divider />
          <Item
            label="φ:"
            value={phiHeadroom.toFixed(4)}
            color={phiHeadroom > 0 ? TIER.T0 : STATUS.ERROR}
          />
        </>
      )}

      {/* Epoch */}
      {epoch != null && (
        <>
          <Divider />
          <Item label="epoch:" value={epoch} color={TEXT.MUTED} />
        </>
      )}

      {/* Corruption warning */}
      {corrupted === true && (
        <>
          <Divider />
          <span className="font-bold flex-shrink-0" style={{ color: STATUS.ERROR }}>
            ⚠ CORRUPTED
          </span>
        </>
      )}

      <span className="flex-1" />
      <span style={{ color: BORDER.DEFAULT, flexShrink: 0 }}>E[S|F]=S</span>
    </div>
  )
}
