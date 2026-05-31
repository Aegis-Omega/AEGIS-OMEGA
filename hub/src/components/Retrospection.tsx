// AEGIS Omega — Retrospection: the system reviewing its own past actions.
//
// L6 metacognition runs a post-action protocol after every cycle and scans for
// error patterns. This panel renders that retrospective loop: the questions the
// automaton asks itself about what it just did, and the catalogue of error
// patterns it has learned to prevent. As the substrate ticks, the protocol
// re-runs — the system is always looking back before it moves forward.

import { useEffect, useState } from 'react'
import type { MetacognitiveCertificate } from '../lib/substrate.js'

const POST_ACTION = [
  'Was the action at the correct epistemic tier?',
  'Was ASSESS done before LOCK?',
  'Was npm run build run before committing TS changes?',
  'Did frozen files change? → T0_ABORT if so.',
  'Did a new error pattern emerge? → add to retrospective.',
  'Gate passed → advance. Gate failed → fix code, never weaken the test.',
]

const ERROR_PATTERNS = [
  { error: 'Dead code noted, annotation deferred', layer: 'L5 orphaned', fix: 'Classify → act in the same RALPH cycle' },
  { error: 'Wrong type used in test', layer: 'L2 failure', fix: 'Read the type definition before writing the test' },
  { error: 'Vendor chosen before checking support', layer: 'L6 missed', fix: 'Check API constraints before writing code' },
  { error: 'CI branch set to nonexistent target', layer: 'L2 failure', fix: 'git branch --list before modifying workflow' },
  { error: 'Build needed N fix commits', layer: 'L5 failure', fix: 'npm run build before every git commit' },
]

export function Retrospection({ certificate }: { certificate: MetacognitiveCertificate }) {
  // Cycle a "currently reviewing" pointer through the post-action questions.
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setIdx(i => (i + 1) % POST_ACTION.length), 1600)
    return () => clearInterval(id)
  }, [])

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
      {/* Post-action protocol — the system interrogating its own last move */}
      <div style={{
        border: '1px solid rgba(96,165,250,0.18)', borderRadius: 16,
        background: 'rgba(96,165,250,0.03)', padding: '20px 22px',
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: '#60A5FA', marginBottom: 4 }}>
          POST-ACTION PROTOCOL · L6
        </div>
        <div style={{ fontSize: 12, color: '#475569', marginBottom: 16 }}>
          Re-run every cycle. Reviewed {certificate.entry_count} observations so far.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          {POST_ACTION.map((q, i) => {
            const reviewing = i === idx
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 10,
                padding: '8px 12px', borderRadius: 9,
                background: reviewing ? 'rgba(96,165,250,0.1)' : 'transparent',
                border: `1px solid ${reviewing ? 'rgba(96,165,250,0.3)' : 'transparent'}`,
                transition: 'all 0.4s ease',
              }}>
                <span style={{
                  fontSize: 11, color: reviewing ? '#60A5FA' : '#34D399', marginTop: 1, fontWeight: 700,
                }}>{reviewing ? '▸' : '✓'}</span>
                <span style={{ fontSize: 13, color: reviewing ? '#CBD5E1' : '#64748B', lineHeight: 1.5 }}>{q}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Error-pattern memory — what it has learned not to do again */}
      <div style={{
        border: '1px solid rgba(236,72,153,0.16)', borderRadius: 16,
        background: 'rgba(236,72,153,0.03)', padding: '20px 22px',
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: '#EC4899', marginBottom: 4 }}>
          ERROR-PATTERN MEMORY · LEARNED
        </div>
        <div style={{ fontSize: 12, color: '#475569', marginBottom: 16 }}>
          Each past mistake mapped to the layer that failed and the rule that prevents recurrence.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {ERROR_PATTERNS.map((p, i) => (
            <div key={i} style={{ borderLeft: '2px solid rgba(236,72,153,0.3)', paddingLeft: 12 }}>
              <div style={{ fontSize: 12.5, color: '#CBD5E1', fontWeight: 600 }}>{p.error}</div>
              <div style={{ fontSize: 11, color: '#64748B', marginTop: 2 }}>
                <span style={{ color: '#EC4899' }}>{p.layer}</span> → {p.fix}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
