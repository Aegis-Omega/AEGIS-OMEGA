// ============================================================
// SOVEREIGN OMEGA — Ralph Loop State Machine
// EPISTEMIC TIER: T1 (empirically validated iterative protocol)
//
// The Ralph Loop (Review → Analyze → Link → Patch → Harmonize)
// treats every component as a recursively nested atomic-scale holon
// governed by invariant-preserving feedback loops. Each cycle targets
// one HolonicScale and elevates it without violating any scale below.
// Cycles are first-class events in the E3 substrate — replayable and auditable.
// ============================================================

import {
  HolonicScale,
  EpistemicTier,
  RalphPhase,
  CYCLE_ARCHIVE_SCHEMA_VERSION,
  type RalphCycle,
  type RalphLoopState,
  type CycleArchive,
  type UUIDv7,
  type SequenceNumber,
} from './types.js'
import { generateUUIDv7 } from '../event/uuid.js'
import { deepFreeze } from './immutable.js'

export interface RalphFinding {
  readonly description: string
  readonly severity: 'critical' | 'important' | 'informational'
  readonly scale: HolonicScale
  readonly tier: EpistemicTier
  readonly file?: string
  readonly line?: number
}

export interface RalphPatch {
  readonly description: string
  readonly file: string
  readonly type: 'create' | 'modify' | 'delete' | 'annotate'
  readonly tier_before: EpistemicTier
  readonly tier_after: EpistemicTier
}

export interface RalphCycleBuilder {
  addFinding(f: RalphFinding): RalphCycleBuilder
  addAnalysisNote(note: string): RalphCycleBuilder
  addLink(description: string): RalphCycleBuilder
  addPatch(p: RalphPatch): RalphCycleBuilder
  harmonize(gateResult: 'PASS' | 'FAIL'): RalphCycle
}

export class RalphLoop {
  private cycles: RalphCycle[] = []
  private _cycleNumber = 0

  constructor(
    private readonly targetScale: HolonicScale,
    private readonly entropyAtStart: number,
  ) {}

  /**
   * Begin a new cycle at the target scale. Returns a builder that must
   * be completed via harmonize() to record the cycle in the E3 substrate.
   */
  beginCycle(sequence: SequenceNumber): RalphCycleBuilder {
    this._cycleNumber++
    const cycleId = generateUUIDv7()
    const findings: RalphFinding[] = []
    const analysisNotes: string[] = []
    const links: string[] = []
    const patches: RalphPatch[] = []

    const loop = this
    const builder: RalphCycleBuilder = {
      addFinding(f) { findings.push(f); return builder },
      addAnalysisNote(n) { analysisNotes.push(n); return builder },
      addLink(d) { links.push(d); return builder },
      addPatch(p) { patches.push(p); return builder },
      harmonize(gateResult) {
        const cycle = deepFreeze<RalphCycle>({
          cycle_id: cycleId as UUIDv7,
          cycle_number: loop._cycleNumber,
          target_scale: loop.targetScale,
          phase: RalphPhase.HARMONIZE,
          findings: findings.map(f => f.description),
          analysis_notes: analysisNotes,
          links_established: links,
          patches_applied: patches.map(p => `[${p.type}] ${p.file}: ${p.description}`),
          harmonization_result: gateResult === 'PASS' ? 'COHERENT' : 'INCOHERENT',
          gate_result: gateResult,
          sequence,
        })
        loop.cycles.push(cycle)
        return cycle
      },
    }
    return builder
  }

  /**
   * Number of consecutive cycles with zero critical findings
   * (convergence depth — analogous to Python's convergence_epochs()).
   */
  convergenceDepth(): number {
    let count = 0
    for (let i = this.cycles.length - 1; i >= 0; i--) {
      const c = this.cycles[i]!
      if (c.harmonization_result !== 'COHERENT' || c.gate_result !== 'PASS') break
      count++
    }
    return count
  }

  /**
   * Versioned archive for persistence and replay.
   * Deserializers must check schema_version === CYCLE_ARCHIVE_SCHEMA_VERSION
   * before trusting the payload. Schema changes require a version bump.
   */
  exportArchive(currentSequence: number, entropyAtEnd?: number): CycleArchive {
    const base: CycleArchive = {
      schema_version: CYCLE_ARCHIVE_SCHEMA_VERSION,
      archived_at_sequence: currentSequence,
      cycles: [...this.cycles],
      total_cycles: this._cycleNumber,
      convergence_depth: this.convergenceDepth(),
      entropy_at_start: this.entropyAtStart,
    }
    return deepFreeze<CycleArchive>(
      entropyAtEnd !== undefined
        ? { ...base, entropy_at_end: entropyAtEnd }
        : base
    )
  }

  getState(entropyAtEnd?: number): RalphLoopState {
    const base = {
      total_cycles: this._cycleNumber,
      completed_cycles: this.cycles,
      entropy_at_start: this.entropyAtStart,
      convergence_depth: this.convergenceDepth(),
    }
    return deepFreeze<RalphLoopState>(
      entropyAtEnd !== undefined
        ? { ...base, entropy_at_end: entropyAtEnd }
        : base
    )
  }
}

/**
 * Compute a simple approximation of system entropy from gate acceptance rate.
 * Perfect acceptance (rate = 1.0) → entropy = 0 (fully ordered).
 * Equal accept/reject (rate = 0.5) → entropy = 1.0 (maximum disorder).
 */
export function estimateSystemEntropy(gateAcceptanceRate: number): number {
  const p = Math.max(0, Math.min(1, gateAcceptanceRate))
  if (p === 0 || p === 1) return 0
  return -(p * Math.log2(p) + (1 - p) * Math.log2(1 - p))
}

/**
 * Governance throughput: cycles completed per sequence-span unit.
 *
 * Uses event sequence numbers, not wall-clock time, to preserve determinism.
 * A span of 0 returns 0 (no throughput measurable without event flow).
 * Interpretation: higher = faster governance cadence relative to event volume.
 * Bottleneck threshold: if cyclesPerSequenceUnit drops below 1/1000, governance
 * is falling behind event production — backpressure should be applied upstream.
 */
export function governanceThroughput(
  completedCycles: number,
  sequenceSpan: number,
): number {
  if (sequenceSpan <= 0) return 0
  return completedCycles / sequenceSpan
}
