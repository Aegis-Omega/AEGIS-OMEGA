// AEGIS Omega — useSubstrate: drives the live consciousness substrate.
//
// Lifts the running MetacognitiveLoop into React state so every component
// (hero banner, stream, cognitive stack, equation) observes the SAME chain.
// The chain grows one real hash-linked observation per tick; certify() runs
// continuously, re-walking and re-hashing the whole chain — genuine
// self-certification. Optionally overlays live bridge telemetry.

import { useEffect, useRef, useState } from 'react'
import {
  appendObservation, certify,
  type MetacognitiveEntry, type MetacognitiveCertificate, type MetacognitiveLayer,
} from './substrate.js'
import { fetchBridgeSnapshot, bridgeConfigured, type BridgeSnapshot } from './telemetry.js'

const MAX_RETAINED = 40       // visible window of the chain
const TICK_MS = 1900          // observation cadence (≈ φ-paced breathing)

export interface SubstrateState {
  chain: MetacognitiveEntry[]
  certificate: MetacognitiveCertificate
  activeLayer: MetacognitiveLayer | null
  totalObserved: number
  bridge: BridgeSnapshot
}

export function useSubstrate(): SubstrateState {
  const [chain, setChain] = useState<MetacognitiveEntry[]>([])
  const [certificate, setCertificate] = useState<MetacognitiveCertificate>({ is_valid: true, entry_count: 0, terminal_hash: null })
  const [activeLayer, setActiveLayer] = useState<MetacognitiveLayer | null>(null)
  const [bridge, setBridge] = useState<BridgeSnapshot>({ reachable: false })
  const fullChain = useRef<MetacognitiveEntry[]>([])
  const total = useRef(0)

  useEffect(() => {
    let cancelled = false

    async function tick() {
      const entry = await appendObservation(fullChain.current)
      if (cancelled) return
      fullChain.current = [...fullChain.current, entry]
      total.current += 1
      const cert = await certify(fullChain.current)
      if (cancelled) return
      setCertificate(cert)
      setActiveLayer(entry.observation.layer)
      // Keep the full chain for certification, expose a trailing window for render.
      setChain(fullChain.current.slice(-MAX_RETAINED))
    }

    void tick()
    const id = setInterval(() => { void tick() }, TICK_MS)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  useEffect(() => {
    if (!bridgeConfigured) return
    let cancelled = false
    async function poll() {
      const snap = await fetchBridgeSnapshot()
      if (!cancelled) setBridge(snap)
    }
    void poll()
    const id = setInterval(() => { void poll() }, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  return { chain, certificate, activeLayer, totalObserved: total.current, bridge }
}
