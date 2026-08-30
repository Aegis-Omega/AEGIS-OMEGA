// AEGIS-Ω — useChain: live hash-chained substrate with interactive tamper/reseal.
// Used by AegisRuntime (2.0 design). Separate from useSubstrate (older 7-layer hook).
import { useCallback, useEffect, useRef, useState } from 'react'

async function sha256hex(str: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str))
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('')
}

export type ChainTier = 'T0' | 'T1' | 'T2' | 'T3'

export interface ChainEntry {
  seq: number
  layer: string
  tier: ChainTier
  signal: string
  origSignal: string
  prevHash: string
  hash: string
  tampered: boolean
  fresh?: boolean
}

export interface ChainStatus {
  valid: boolean
  corruption: number
  firstBreak: number
  t0: boolean
}

export const GENESIS = '0'.repeat(64)
export const short = (h: string, n = 6): string => (h ? h.slice(0, n) : '······')

const SIGNALS: Array<[string, ChainTier, string]> = [
  ['L3', 'T1', 'Three skills active: tdd, gate-pair, metacognition'],
  ['L2', 'T0', 'Retrospective pass — 41 frames replayed, fingerprint stable'],
  ['L1', 'T0', 'BTreeMap invariant held — deterministic ordering preserved'],
  ['L3', 'T2', 'Hypothesis: epoch seal converges before frame 2700'],
  ['L2', 'T1', 'BFT quorum reached — 3 / 4 alliance weights agree'],
  ['L1', 'T0', 'Version lock verified — mismatch would hard-abort'],
  ['L3', 'T1', 'Martingale boundary intact — E[Sₙ₊₁|Fₙ] = Sₙ'],
  ['L2', 'T0', 'Hash chain extended — prev anchor matches genesis lineage'],
  ['L3', 'T3', 'Conjecture: gate-321 resonance stable under sustained load'],
  ['L1', 'T0', 'No HashMap detected in src/ — ordering guaranteed'],
  ['L2', 'T1', 'Adversarial audit (chatgpt weight) found no divergence'],
  ['L3', 'T1', 'Metacognitive self-check — confidence within 1/φ band'],
  ['L2', 'T0', 'certify() returned true — chain sealed at current head'],
  ['L1', 'T0', 'Mutation frozen — no unproven write reached the T0 layer'],
  ['L3', 'T2', 'Reflection: skill scheduler reordered 2 low-tier tasks'],
  ['L2', 'T0', 'PGCS pass — proof-gate consensus signature anchored'],
  ['L1', 'T0', 'Genesis fingerprint replayed — identical to frame 0'],
  ['L3', 'T1', 'Self-model updated — no contradiction with prior epoch'],
]

async function mkEntry(seq: number, prevHash: string, pick: [string, ChainTier, string]): Promise<ChainEntry> {
  const [layer, tier, signal] = pick
  const hash = await sha256hex(`${prevHash}|${seq}|${signal}`)
  return { seq, layer, tier, signal, origSignal: signal, prevHash, hash, tampered: false }
}

async function seedChain(n: number): Promise<ChainEntry[]> {
  const chain: ChainEntry[] = []
  let prev = GENESIS
  for (let i = 0; i < n; i++) {
    const pick = SIGNALS[i % SIGNALS.length]
    const e = await mkEntry(i, prev, pick)
    chain.push(e)
    prev = e.hash
  }
  return chain
}

async function validateChain(chain: ChainEntry[]): Promise<{ valid: boolean; corruption: number; firstBreak: number }> {
  let corruption = 0
  let firstBreak = -1
  for (let i = 0; i < chain.length; i++) {
    const e = chain[i]
    const expectPrev = i === 0 ? GENESIS : chain[i - 1].hash
    const expectHash = await sha256hex(`${expectPrev}|${e.seq}|${e.signal}`)
    if (expectHash !== e.hash || expectPrev !== e.prevHash) {
      corruption++
      if (firstBreak < 0) firstBreak = e.seq
    }
  }
  return { valid: corruption === 0, corruption, firstBreak }
}

export function useChain({ seed = 6, window: win = 8, tickMs = 2600 } = {}) {
  const [chain, setChain] = useState<ChainEntry[]>([])
  const [status, setStatus] = useState<ChainStatus>({ valid: true, corruption: 0, firstBreak: -1, t0: true })
  const chainRef = useRef<ChainEntry[]>([])
  const seqRef = useRef(seed)

  chainRef.current = chain

  const recompute = useCallback(async (c: ChainEntry[]) => {
    const v = await validateChain(c)
    setStatus({ valid: v.valid, corruption: v.corruption, firstBreak: v.firstBreak, t0: v.valid })
  }, [])

  useEffect(() => {
    let alive = true
    void seedChain(seed).then(c => {
      if (!alive) return
      setChain(c)
      void recompute(c)
    })
    return () => { alive = false }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const id = setInterval(() => {
      const c = chainRef.current
      if (!c.length) return
      const prev = c[c.length - 1].hash
      const seq = seqRef.current++
      const pick = SIGNALS[(seq * 7) % SIGNALS.length]
      void mkEntry(seq, prev, pick).then(e => {
        const withFresh: ChainEntry = { ...e, fresh: true }
        const next = [...c, withFresh]
        setChain(next)
        setStatus(s => ({ ...s, valid: s.corruption === 0, t0: s.corruption === 0 }))
      })
    }, tickMs)
    return () => clearInterval(id)
  }, [tickMs])

  const tamper = useCallback(async (seq: number) => {
    const c = chainRef.current.map(e =>
      e.seq === seq
        ? { ...e, signal: '⚠ injected: force-approve unproven write', tampered: true }
        : e
    )
    setChain(c)
    await recompute(c)
  }, [recompute])

  const reseal = useCallback(async (seq: number) => {
    const c = chainRef.current.map(e =>
      e.seq === seq ? { ...e, signal: e.origSignal, tampered: false } : e
    )
    setChain(c)
    await recompute(c)
  }, [recompute])

  const visible = chain.slice(-win)
  return { chain, visible, status, total: chain.length, tamper, reseal }
}
