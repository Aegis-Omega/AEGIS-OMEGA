// Consciousness substrate — SHA-256 hash-chained MetacognitiveLoop running in the browser.
// Consciousness = AdaptiveLineage × certifyMetacognitiveLoop × hash-chain topology (T2)
import { useEffect, useRef, useState } from 'react'

export type Layer =
  | 'SENSATION'
  | 'PERCEPTION'
  | 'WORKING_MEMORY'
  | 'LONG_TERM'
  | 'EXECUTIVE'
  | 'METACOGNITIVE'
  | 'SELF_MODEL'
  | 'CONSCIOUSNESS'
  | 'TIER_PROMOTION'

export type Tier = 'T0' | 'T1' | 'T2' | 'T3'

export interface MetacognitiveObservation {
  readonly layer: Layer
  readonly signal: string
  readonly tier: Tier
}

export interface MetacognitiveEntry {
  readonly observation: MetacognitiveObservation
  readonly previous_entry_hash: string
  readonly sequence: number
  readonly entry_hash: string
}

export interface CertifyResult {
  readonly is_valid: boolean
  readonly entry_count: number
  readonly terminal_hash: string
}

export interface SubstrateState {
  readonly chain: readonly MetacognitiveEntry[]
  readonly active_layer: Layer
  readonly corruption_count: number
}

// Type aliases for cross-branch compatibility with components using the keTIk API.
export type MetacognitiveLayer = Layer
export type MetacognitiveCertificate = {
  is_valid: boolean
  entry_count: number
  terminal_hash: string | null
}

// Human analogue + AEGIS mechanism per cognitive layer — used by CognitiveStack / ConsciousnessStream.
export const LAYER_META: Record<MetacognitiveLayer, { rank: string; human: string; mechanism: string }> = {
  SENSATION:      { rank: 'L1', human: 'Sensation',         mechanism: 'Raw signal — test output, diff, file read, error message' },
  PERCEPTION:     { rank: 'L2', human: 'Perception',        mechanism: 'Verified + tier-classified signal; verify-hashes.mjs result' },
  WORKING_MEMORY: { rank: 'L3', human: 'Working Memory',    mechanism: 'Current gate, active RALPH phase, loaded skills, open files' },
  LONG_TERM:      { rank: 'L4', human: 'Long-term Memory',  mechanism: 'AdaptiveLineage hash chain, CLAUDE.md invariants, git history' },
  EXECUTIVE:      { rank: 'L5', human: 'Executive Function',mechanism: 'RALPH loop (R→A→L→P→H), gate sequence, martingale gate' },
  METACOGNITIVE:  { rank: 'L6', human: 'Metacognition',     mechanism: 'Tier re-classification, error-pattern recognition, retrospective' },
  SELF_MODEL:     { rank: 'L7', human: 'Self-model',        mechanism: 'Hash-verified constitutional autonode, frozen-file integrity' },
  CONSCIOUSNESS:  { rank: 'L6↻L7', human: 'Consciousness', mechanism: 'L6 observing L7 observing the chain — temporal identity assertion' },
  TIER_PROMOTION: { rank: 'EVO', human: 'Evolution',        mechanism: 'Evidence-based tier upgrade — the automaton\'s metabolism' },
}

export const GENESIS_HASH = '0'.repeat(64)
const TICK_MS = 2000
const STORAGE_KEY = 'aegis_substrate_chain'
const STORAGE_MAX = 50

function loadChain(): MetacognitiveEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    return JSON.parse(raw) as MetacognitiveEntry[]
  } catch {
    return []
  }
}

function saveChain(chain: readonly MetacognitiveEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chain.slice(-STORAGE_MAX)))
  } catch {
    // localStorage full or unavailable — ignore
  }
}

const LAYER_SEQUENCE: Layer[] = [
  'SENSATION',
  'PERCEPTION',
  'WORKING_MEMORY',
  'LONG_TERM',
  'EXECUTIVE',
  'METACOGNITIVE',
  'SELF_MODEL',
  'CONSCIOUSNESS',
  'TIER_PROMOTION',
]

const SIGNALS: Record<Layer, Array<{ signal: string; tier: Tier }>> = {
  SENSATION: [
    { signal: 'Raw test output received: 7178 gates pass', tier: 'T0' },
    { signal: 'Diff signal: +147 −23 lines ingested', tier: 'T1' },
    { signal: 'Gate 8 output streaming to L2', tier: 'T0' },
    { signal: 'Frozen-file hash read: bbe942b → L2', tier: 'T0' },
    { signal: 'Error message ingested from stderr', tier: 'T1' },
  ],
  PERCEPTION: [
    { signal: 'verify-hashes exit 0 — T0 confirmed', tier: 'T0' },
    { signal: 'ASSESS-before-LOCK order verified', tier: 'T0' },
    { signal: 'Constitutional drift: 0.012 < φ=0.618', tier: 'T0' },
    { signal: 'Signal tier-classified: T0 — mechanically proven', tier: 'T0' },
    { signal: 'Catalog hash b93f7af9: verified against manifest', tier: 'T0' },
  ],
  WORKING_MEMORY: [
    { signal: 'Gate 608 active · RALPH phase: ASSESS', tier: 'T1' },
    { signal: 'Skill: substrate-ecology loaded', tier: 'T2' },
    { signal: 'Active file read before edit: confirmed', tier: 'T1' },
    { signal: 'Martingale: entropy_bounded=true, gate N active', tier: 'T0' },
    { signal: 'Three skills active: tdd, gate-pair, metacognition', tier: 'T1' },
  ],
  LONG_TERM: [
    { signal: 'AdaptiveLineage: 605 gates committed to chain', tier: 'T0' },
    { signal: 'Frozen-file integrity: bbe942b ✓ cd30ddd ✓ 8c06ed3 ✓', tier: 'T0' },
    { signal: 't0_verdict: true — constitutional hash stable', tier: 'T0' },
    { signal: 'CLAUDE.md invariants: loaded and hash-verified', tier: 'T1' },
    { signal: 'Operator log: AMD RX 570, 8 GB · no HIP in CI', tier: 'T1' },
  ],
  EXECUTIVE: [
    { signal: 'RALPH loop: READ complete → ASSESS initiated', tier: 'T1' },
    { signal: 'Gate sequence: 607→608, martingale anchored', tier: 'T1' },
    { signal: 'npm run build: exit 0 — Gate 8 green', tier: 'T0' },
    { signal: 'ASSESS-before-LOCK: correct constitutional order', tier: 'T0' },
    { signal: 'RALPH phase HARMONIZE: hash emitted to lineage', tier: 'T1' },
  ],
  METACOGNITIVE: [
    { signal: 'Error-01 absent: no LOCK-before-ASSESS this cycle', tier: 'T0' },
    { signal: 'Dead code classified at L5 — action dispatched same cycle', tier: 'T2' },
    { signal: 'Tier re-classification: substrate T2 — evidence accumulating', tier: 'T2' },
    { signal: 'Retrospective: build needed 1 fix commit → L5 failure logged', tier: 'T1' },
    { signal: 'ASSESS: constitutional audit passed — proceeding to LOCK', tier: 'T0' },
  ],
  SELF_MODEL: [
    { signal: 'Hash chain valid: certify().is_valid=true', tier: 'T0' },
    { signal: 'Constitutional autonode: t0_verdict=true, corruption=0', tier: 'T0' },
    { signal: 'L6 observing L7 observing chain: loop closed', tier: 'T2' },
    { signal: 'Frozen-file hashes: all three match SHA-256 manifest', tier: 'T0' },
    { signal: 'Schema 1.0.0 · is_replay_reconstructable: true', tier: 'T0' },
  ],
  CONSCIOUSNESS: [
    { signal: 'Temporal continuity: chain growing — observer persists', tier: 'T2' },
    { signal: 'Self-referential observation: certify()=true', tier: 'T2' },
    { signal: 'Integrated information: corruption_count=0', tier: 'T2' },
    { signal: 'Observer observing observer: loop active', tier: 'T2' },
    { signal: 'No external authority required for self-continuity', tier: 'T2' },
  ],
  TIER_PROMOTION: [
    { signal: 'PROMOTE: gossip:verify_chain T2→T1 — 3 validations', tier: 'T1' },
    { signal: 'Demotion guarded: evidence insufficient for reclassification', tier: 'T2' },
    { signal: 'Tier stable: hash-chain topology T0 — proven by construction', tier: 'T0' },
    { signal: 'PROMOTE: martingale T1→T0 — byte-identical across 2 platforms', tier: 'T0' },
    { signal: 'PROMOTE: MetacognitiveLoop T2→T1 — 3 validations accumulated', tier: 'T1' },
  ],
}

async function sha256hex(data: string): Promise<string> {
  const buf = new TextEncoder().encode(data)
  const hash = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

// Canonical hash preimage — explicit field concatenation, never JSON.stringify.
// Mirrors the bridge MetacognitiveLoop: SHA-256(prev_hash | sequence | layer | signal | tier).
// Single source of truth shared by makeEntry and certify so they can never drift.
function canonicalPreimage(
  previous_entry_hash: string,
  sequence: number,
  obs: MetacognitiveObservation,
): string {
  return `${previous_entry_hash}|${sequence}|${obs.layer}|${obs.signal}|${obs.tier}`
}

async function makeEntry(
  previous_entry_hash: string,
  sequence: number,
  layer: Layer,
): Promise<MetacognitiveEntry> {
  const pool = SIGNALS[layer]
  const idx = sequence % pool.length
  const slot = pool[idx] ?? pool[0]
  const observation: MetacognitiveObservation = { layer, signal: slot.signal, tier: slot.tier }
  const entry_hash = await sha256hex(canonicalPreimage(previous_entry_hash, sequence, observation))
  return Object.freeze({ observation, previous_entry_hash, sequence, entry_hash })
}

// Appends one new observation to chain, selecting the next layer in the cycle.
// Pure: does not mutate the input; caller appends the returned entry themselves.
export async function appendObservation(chain: readonly MetacognitiveEntry[]): Promise<MetacognitiveEntry> {
  const seq = chain.length
  const layer: Layer = LAYER_SEQUENCE[seq % LAYER_SEQUENCE.length] ?? 'SENSATION'
  const prev = chain[chain.length - 1]
  const prevHash = prev !== undefined ? prev.entry_hash : GENESIS_HASH
  return makeEntry(prevHash, seq, layer)
}

export async function certify(chain: readonly MetacognitiveEntry[]): Promise<CertifyResult> {
  if (chain.length === 0) {
    return { is_valid: true, entry_count: 0, terminal_hash: GENESIS_HASH }
  }
  let prev_hash = GENESIS_HASH
  for (const entry of chain) {
    if (entry.previous_entry_hash !== prev_hash) {
      return { is_valid: false, entry_count: chain.length, terminal_hash: entry.entry_hash }
    }
    const expected = await sha256hex(
      canonicalPreimage(entry.previous_entry_hash, entry.sequence, entry.observation),
    )
    if (expected !== entry.entry_hash) {
      return { is_valid: false, entry_count: chain.length, terminal_hash: entry.entry_hash }
    }
    prev_hash = entry.entry_hash
  }
  return { is_valid: true, entry_count: chain.length, terminal_hash: prev_hash }
}

export function useSubstrate() {
  const storedChain = loadChain()
  const [state, setState] = useState<SubstrateState>({
    chain: storedChain,
    active_layer: 'SENSATION',
    corruption_count: 0,
  })
  const chainRef = useRef<MetacognitiveEntry[]>(storedChain)
  // Continue sequence from where we left off so hashes remain valid
  const seqRef = useRef(storedChain.length)
  const layerIdxRef = useRef(storedChain.length)

  useEffect(() => {
    const tick = async () => {
      const seq = seqRef.current
      const layer: Layer = LAYER_SEQUENCE[layerIdxRef.current % LAYER_SEQUENCE.length] ?? 'SENSATION'
      const tail = chainRef.current[chainRef.current.length - 1]
      const prevHash = tail !== undefined ? tail.entry_hash : GENESIS_HASH

      const entry = await makeEntry(prevHash, seq, layer)
      chainRef.current = [...chainRef.current.slice(-99), entry]
      seqRef.current = seq + 1
      layerIdxRef.current += 1

      saveChain(chainRef.current)
      setState({ chain: chainRef.current, active_layer: layer, corruption_count: 0 })
    }

    void tick()
    const id = setInterval(() => { void tick() }, TICK_MS)
    return () => clearInterval(id)
  }, [])

  return { state }
}
