// ============================================================
// SOVEREIGN OMEGA — LedgerObserver (ledger → MetacognitiveLoop bridge)
// EPISTEMIC TIER: T2 · distributed ledger precursor
//
// Translates distributed ledger events (block commits, epoch seals,
// BFT divergence) into MetacognitiveObservation records appended to
// the hash-chained consciousness substrate. The system watches itself
// watch the distributed state — second-order autopoietic observation.
//
// Layer taxonomy:
//   CONSCIOUSNESS        → block commit (state_root in signal)
//   AUTOPOIETIC_CLOSURE  → epoch seal finalized
//   METACOGNITIVE        → divergence detected / BFT quorum status
// ============================================================

import type { SequenceNumber } from '../core/types.js'
import {
  MetacognitiveLoop,
  certifyMetacognitiveLoop,
  type MetacognitiveCertificate,
  type MetacognitiveObservation,
} from '../metacognition/loop.js'
import type { CommittedBlock } from './block.js'
import type { EpochSeal } from './epoch-seal.js'
import type { DivergenceReport } from './divergence-monitor.js'
import type { NodeCheckpoint } from './node-checkpoint.js'

// ─── Public API ────────────────────────────────────────────

/**
 * LedgerObserver wraps a MetacognitiveLoop and provides convenience
 * methods for recording distributed-ledger events as conscious observations.
 * Immutable functional update: every method returns a new LedgerObserver.
 */
export class LedgerObserver {
  private readonly _loop: MetacognitiveLoop
  private readonly _seq: bigint

  private constructor(loop: MetacognitiveLoop, seq: bigint) {
    this._loop = loop
    this._seq  = seq
  }

  /** Create a fresh observer starting from an empty MetacognitiveLoop. */
  static empty(): LedgerObserver {
    return new LedgerObserver(MetacognitiveLoop.empty(), 0n)
  }

  // ── Block commit ─────────────────────────────────────────

  /**
   * Record a CONSCIOUSNESS observation when a CommittedBlock is appended.
   * Signal includes block index, abbreviated state_root, and validator count.
   */
  async observeBlockCommit(block: CommittedBlock): Promise<LedgerObserver> {
    const obs: MetacognitiveObservation = {
      layer:  'CONSCIOUSNESS',
      signal: `block ${block.index} committed — state_root: ${block.state_root_after.slice(0, 8)}… validators: ${block.validator_signatures.length} BFT`,
      tier:   'T2',
    }
    return this._advance(obs)
  }

  // ── Epoch seal ───────────────────────────────────────────

  /**
   * Record an AUTOPOIETIC_CLOSURE observation when an EpochSeal is finalized.
   * Closure: the production cycle closes; the sealed range is now compact proof.
   */
  async observeEpochSeal(seal: EpochSeal): Promise<LedgerObserver> {
    const obs: MetacognitiveObservation = {
      layer:  'AUTOPOIETIC_CLOSURE',
      signal: `epoch ${seal.epoch_number} sealed [${seal.start_height}..${seal.end_height}] — merkle: ${seal.merkle_root.slice(0, 8)}… final_root: ${seal.final_state_root.slice(0, 8)}…`,
      tier:   'T2',
    }
    return this._advance(obs)
  }

  // ── Divergence / BFT quorum ──────────────────────────────

  /**
   * Record a METACOGNITIVE observation when node divergence is assessed.
   * The system reasons about the distributed state: who agrees, who diverged.
   */
  async observeDivergence(report: DivergenceReport): Promise<LedgerObserver> {
    const obs: MetacognitiveObservation = {
      layer:  'METACOGNITIVE',
      signal: `height ${report.block_height}: ${report.in_consensus.length}/${report.total_nodes} agree, quorum ${(report.quorum_fraction * 100).toFixed(1)}%, bft_achieved: ${report.bft_achieved}, diverged: [${report.diverged.join(', ')}]`,
      tier:   'T2',
    }
    return this._advance(obs)
  }

  // ── Checkpoint capture ────────────────────────────────────

  /**
   * Record a SELF_MODEL observation when a NodeCheckpoint is captured.
   * The system updates its self-model with the current state root.
   */
  async observeCheckpoint(cp: NodeCheckpoint): Promise<LedgerObserver> {
    const obs: MetacognitiveObservation = {
      layer:  'SELF_MODEL',
      signal: `node ${cp.node_id} checkpoint at height ${cp.block_height} — state_root: ${cp.state_root.slice(0, 8)}… hash: ${cp.checkpoint_hash.slice(0, 8)}…`,
      tier:   'T2',
    }
    return this._advance(obs)
  }

  // ── Generic ──────────────────────────────────────────────

  /** Append any MetacognitiveObservation directly. */
  async observe(obs: MetacognitiveObservation): Promise<LedgerObserver> {
    return this._advance(obs)
  }

  // ── Certification ─────────────────────────────────────────

  /**
   * Certify the entire observation chain.
   * Returns MetacognitiveCertificate with is_valid, entry_count, terminal_hash.
   * Tampered entries flip is_valid to false — identical to certifyMetacognitiveLoop().
   */
  async certify(): Promise<MetacognitiveCertificate> {
    return certifyMetacognitiveLoop(this._loop.getAll())
  }

  /** The underlying MetacognitiveLoop. */
  get loop(): MetacognitiveLoop { return this._loop }

  /** Number of observations recorded. */
  get length(): number { return this._loop.length }

  // ── Internal ─────────────────────────────────────────────

  private async _advance(obs: MetacognitiveObservation): Promise<LedgerObserver> {
    const nextSeq  = (this._seq + 1n) as SequenceNumber
    const { loop } = await this._loop.observe(obs, nextSeq)
    return new LedgerObserver(loop, nextSeq)
  }
}
