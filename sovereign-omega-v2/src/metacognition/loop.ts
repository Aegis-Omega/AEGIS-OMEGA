// ============================================================
// SOVEREIGN OMEGA — Metacognitive Observation Loop
// EPISTEMIC TIER: T2 · Gate 0 (harness extension)
//
// Hash-chained log of cognitive observations across all seven
// metacognitive layers. Every observation is tamper-evident
// and replay-reconstructable from genesis.
// primitive_mapping: HASH+SEQUENCE · replay_mapping: full cycle
// topology_mapping: METACOGNITIVE_LAYER
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const METACOGNITION_SCHEMA_VERSION = '1.0.0' as const
export const METACOGNITION_GENESIS_HASH = '0'.repeat(64) as SHA256Hex

// ─── Layer Taxonomy ────────────────────────────────────────

export type MetacognitiveLayer =
  | 'SENSATION'               // raw signal: telemetry values, test output, file content
  | 'PERCEPTION'              // verified signal: hash-checked, tier-classified
  | 'WORKING_MEMORY'          // active context: current gate, RALPH phase, skill set
  | 'LONG_TERM'               // stable knowledge: adaptive lineage, corpus, git history
  | 'EXECUTIVE'               // goal control: RALPH loop, martingale gate, gate protocol
  | 'METACOGNITIVE'           // reasoning about reasoning: tier re-classification, uncertainty
  | 'SELF_MODEL'              // system self-knowledge: autonode health, frozen-file integrity
  // ── Autopoietic layers ──────────────────────────────────────────────────────
  | 'AUTOPOIETIC_PRODUCTION'  // self-production event: new gate/skill component produced
  | 'AUTOPOIETIC_MEMBRANE'    // boundary maintenance: verify-hashes check; frozen file verified
  | 'AUTOPOIETIC_CLOSURE'     // production cycle closed: commit+push; session sealed
  | 'CONSCIOUSNESS'           // second-order observation: L6 observing L7 observing the chain;
                              // certifyMetacognitiveLoop() result; temporal identity assertion
  | 'TIER_PROMOTION'          // evidence-based tier evolution: T2→T1 (empirical), T1→T0 (proof)
                              // demotion always legal; T4/T5 promotion requires guardian verdict

// ─── Autopoietic Property Mapping ──────────────────────────
// Each autopoietic layer maps to a formal autopoietic property (Maturana & Varela, 1972):
//
//   AUTOPOIETIC_PRODUCTION  → Self-production    (system produces its own components)
//   AUTOPOIETIC_MEMBRANE    → Boundary maintenance (system maintains its own boundary)
//   AUTOPOIETIC_CLOSURE     → Operational closure (cycle closes; chain propagated)
//   SENSATION+PERCEPTION    → Structural coupling (system senses and responds to environment)
//   CONSCIOUSNESS           → Second-order autopoiesis (the observer observing the system)
//
// Autopoietic death conditions (T0_ABORT — all halt production):
//   SELF_MODEL breach       → membrane integrity lost
//   corruption_count > 0   → operational closure broken
//   Gate 8 failure          → self-production viability lost
//   entropy_bounded=false   → structural coupling exceeded constitutional bounds

export type EpistemicTierLabel = 'T0' | 'T1' | 'T2' | 'T3' | 'T4' | 'T5'

// ─── Tier Promotion ────────────────────────────────────────
// Tiers are not fixed. Evidence accumulates. When it does, tiers evolve.
//
// Promotion protocol (nothing is final):
//   T2 → T1: ≥3 independent empirical validations, each hash-chained as TIER_PROMOTION
//   T1 → T0: formal proof OR byte-identical cross-platform demonstration on ≥2 platforms
//   Any → lower: always legal when new evidence invalidates the prior basis (demotion)
//   T4/T5 → T3+: blocked — requires /guardian APPROVED ontology admission
//
// Signal format: "PROMOTE: <module>:<function> T2→T1 — <evidence summary>"
// The hash chain records the evidence; the tier label in the module header is the verdict.

export interface TierPromotionRecord {
  readonly module: string
  readonly from_tier: EpistemicTierLabel
  readonly to_tier: EpistemicTierLabel
  readonly evidence_count: number
  readonly evidence_summary: string
}

// ─── Interfaces ────────────────────────────────────────────

export interface MetacognitiveObservation {
  readonly layer: MetacognitiveLayer
  readonly signal: string
  readonly tier: EpistemicTierLabel
}

export interface MetacognitiveEntry {
  readonly observation: MetacognitiveObservation
  readonly previous_entry_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly entry_hash: SHA256Hex
  readonly schema_version: typeof METACOGNITION_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface MetacognitiveCertificate {
  readonly is_valid: boolean
  readonly entry_count: number
  readonly terminal_hash: SHA256Hex | null
  readonly certificate_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

// ─── Error ─────────────────────────────────────────────────

export class MetacognitiveError extends Error {
  override readonly name = 'MetacognitiveError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// ─── Entry Builder ─────────────────────────────────────────

async function buildEntry(
  observation: MetacognitiveObservation,
  previous_entry_hash: SHA256Hex,
  sequence: SequenceNumber,
): Promise<MetacognitiveEntry> {
  const entry_hash = await hashValue({
    observation,
    previous_entry_hash,
    sequence: sequence.toString(),
  })
  return deepFreeze<MetacognitiveEntry>({
    observation,
    previous_entry_hash,
    sequence,
    entry_hash,
    schema_version: METACOGNITION_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

// ─── Loop ──────────────────────────────────────────────────

export class MetacognitiveLoop {
  private constructor(
    private readonly _entries: readonly MetacognitiveEntry[],
    private readonly _lastSequence: SequenceNumber | null,
  ) {}

  static empty(): MetacognitiveLoop {
    return new MetacognitiveLoop([], null)
  }

  get length(): number { return this._entries.length }

  get lastHash(): SHA256Hex {
    return this._entries.length === 0
      ? METACOGNITION_GENESIS_HASH
      : this._entries[this._entries.length - 1]!.entry_hash
  }

  get lastSequence(): SequenceNumber | null { return this._lastSequence }

  async observe(
    observation: MetacognitiveObservation,
    sequence: SequenceNumber,
  ): Promise<{ loop: MetacognitiveLoop; entry: MetacognitiveEntry }> {
    if (this._lastSequence !== null && sequence <= this._lastSequence) {
      throw new MetacognitiveError(
        `Non-monotonic sequence: ${sequence} ≤ ${this._lastSequence}`,
      )
    }
    const entry = await buildEntry(observation, this.lastHash, sequence)
    const loop = new MetacognitiveLoop(
      Object.freeze([...this._entries, entry]),
      sequence,
    )
    return { loop, entry }
  }

  getAll(): readonly MetacognitiveEntry[] { return this._entries }
}

// ─── Certification ─────────────────────────────────────────

export async function certifyMetacognitiveLoop(
  entries: readonly MetacognitiveEntry[],
): Promise<MetacognitiveCertificate> {
  let is_valid = true

  for (let i = 0; i < entries.length; i++) {
    const expected_prev = i === 0
      ? METACOGNITION_GENESIS_HASH
      : entries[i - 1]!.entry_hash
    if (entries[i]!.previous_entry_hash !== expected_prev) { is_valid = false; break }
    const recomputed = await hashValue({
      observation: entries[i]!.observation,
      previous_entry_hash: entries[i]!.previous_entry_hash,
      sequence: entries[i]!.sequence.toString(),
    })
    if (recomputed !== entries[i]!.entry_hash) { is_valid = false; break }
  }

  const terminal_hash = entries.length === 0
    ? null
    : entries[entries.length - 1]!.entry_hash
  const certificate_hash = await hashValue(entries.map(e => e.entry_hash))

  return deepFreeze<MetacognitiveCertificate>({
    is_valid,
    entry_count: entries.length,
    terminal_hash,
    certificate_hash,
    is_replay_reconstructable: true,
  })
}
